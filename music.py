import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import logging
import traceback

logger = logging.getLogger('music')

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


def _extract(query):
    data = ytdl.extract_info(query, download=False)
    if 'entries' in data:
        data = data['entries'][0]
    return data


class QueueItem:
    # Holds the canonical webpage URL and title. The CDN stream URL is fetched
    # lazily at playback time so it doesn't expire while sitting in the queue.
    def __init__(self, *, title, webpage_url):
        self.title = title
        self.webpage_url = webpage_url

    async def create_source(self, *, loop):
        data = await loop.run_in_executor(None, lambda: _extract(self.webpage_url))
        ffmpeg = discord.FFmpegPCMAudio(data['url'], **ffmpeg_options)
        return discord.PCMVolumeTransformer(ffmpeg, volume=0.5)


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.playing = False
        self.disconnect_task = None
        self.voice_client = None

    def add(self, item):
        self.queue.append(item)
        self._cancel_disconnect()

    def next(self):
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        self.current = None
        return None

    def start_disconnect_timer(self, vc, loop):
        """Start a timer to disconnect after 5 minutes of inactivity"""
        self.voice_client = vc
        self._cancel_disconnect()
        self.disconnect_task = loop.create_task(self._disconnect_after_delay(vc))

    def _cancel_disconnect(self):
        if self.disconnect_task and not self.disconnect_task.done():
            self.disconnect_task.cancel()
            self.disconnect_task = None

    async def _disconnect_after_delay(self, vc, delay=300):
        await asyncio.sleep(delay)
        if vc and vc.is_connected():
            await vc.disconnect()
            logger.info(f"Auto-disconnected from {vc.guild.name} after inactivity")
            queues.pop(vc.guild.id, None)


queues = {}


def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("MusicCog initialized")

    @app_commands.command(name="play", description="Play a YouTube URL or search")
    async def play(self, interaction: discord.Interaction, query: str):
        logger.debug(f"Play command invoked by {interaction.user} in guild {interaction.guild_id}")
        await interaction.response.defer()

        if not interaction.user.voice:
            logger.debug(f"User {interaction.user} not in voice channel")
            await interaction.followup.send("You must be in a voice channel!")
            return

        channel = interaction.user.voice.channel
        logger.debug(f"Target voice channel: {channel.name} (ID: {channel.id})")

        try:
            if not interaction.guild.voice_client:
                logger.debug(f"Connecting to voice channel {channel.name}")
                vc = await channel.connect()
                logger.info(f"Connected to voice channel {channel.name} in guild {interaction.guild.name}")
            else:
                vc = interaction.guild.voice_client
                logger.debug(f"Using existing voice client")
        except Exception as e:
            logger.error(f"Failed to connect to voice channel: {e}")
            logger.debug(traceback.format_exc())
            await interaction.followup.send(f"Error connecting to voice channel: {str(e)}")
            return

        queue = get_queue(interaction.guild_id)

        async with interaction.channel.typing():
            try:
                logger.debug(f"Processing query: {query}")
                data = await self.bot.loop.run_in_executor(None, lambda: _extract(query))
                item = QueueItem(
                    title=data.get('title') or query,
                    webpage_url=data.get('webpage_url') or query,
                )
                queue.add(item)
                logger.info(f"Added to queue: {item.title}")
                await interaction.followup.send(f"Added to queue: {item.title}")
            except Exception as e:
                logger.error(f"Error processing query '{query}': {e}")
                logger.debug(traceback.format_exc())
                await interaction.followup.send(f"Error: {str(e)}")
                return

        if not queue.playing:
            logger.debug("Starting playback (queue was not playing)")
            await self.play_next(interaction.guild_id, vc)

    async def play_next(self, guild_id, vc):
        logger.debug(f"play_next called for guild {guild_id}")
        queue = get_queue(guild_id)
        item = queue.next()

        if not item:
            logger.debug(f"Queue empty for guild {guild_id}, starting disconnect timer")
            queue.playing = False
            queue.start_disconnect_timer(vc, self.bot.loop)
            return

        queue.playing = True

        try:
            source = await item.create_source(loop=self.bot.loop)
        except Exception as e:
            logger.error(f"Failed to resolve '{item.title}' for playback: {e}")
            logger.debug(traceback.format_exc())
            await self.play_next(guild_id, vc)
            return

        logger.info(f"Now playing in guild {guild_id}: {item.title}")

        def after_playing(error):
            if error:
                logger.error(f"Playback error in guild {guild_id}: {error}")
            else:
                logger.debug(f"Finished playing in guild {guild_id}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild_id, vc), self.bot.loop)

        try:
            vc.play(source, after=after_playing)
            logger.debug(f"Playback started successfully for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error starting playback in guild {guild_id}: {e}")
            logger.debug(traceback.format_exc())

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        logger.debug(f"Skip command invoked by {interaction.user}")
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            logger.info(f"Song skipped by {interaction.user}")
            await interaction.response.send_message("Skipped!")
        else:
            await interaction.response.send_message("Nothing playing!")

    @app_commands.command(name="queue", description="Show the queue")
    async def queue(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild_id)
        if not queue.queue and not queue.current:
            await interaction.response.send_message("Queue is empty!")
            return

        embed = discord.Embed(title="Queue")

        if queue.current:
            embed.add_field(name="Now Playing", value=f"{queue.current.title}", inline=False)

        for i, item in enumerate(queue.queue, 1):
            embed.add_field(name=f"{i}. {item.title}", value="​", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="Clear the queue")
    async def clear(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild_id)
        queue.queue.clear()

        vc = interaction.guild.voice_client
        if vc and not queue.playing:
            queue.start_disconnect_timer(vc, self.bot.loop)

        await interaction.response.send_message("Queue cleared!")

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        logger.debug(f"Leave command invoked by {interaction.user}")
        vc = interaction.guild.voice_client
        if vc:
            queue = get_queue(interaction.guild_id)
            queue._cancel_disconnect()
            await vc.disconnect()
            queues.pop(interaction.guild_id, None)
            logger.info(f"Left voice channel in guild {interaction.guild.name}")
            await interaction.response.send_message("Left!")
        else:
            await interaction.response.send_message("Not in a voice channel!")

    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Paused!")
        else:
            await interaction.response.send_message("Nothing playing!")

    @app_commands.command(name="resume", description="Resume the current song")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed!")
        else:
            await interaction.response.send_message("Nothing paused!")
