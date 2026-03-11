import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

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
    'options': '-vn -filter:a volume=0.5',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.playing = False
        self.disconnect_task = None
        self.voice_client = None

    def add(self, source):
        self.queue.append(source)
        self._cancel_disconnect()

    def next(self):
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        return None

    def start_disconnect_timer(self, vc, loop):
        """Start a timer to disconnect after 5 minutes of inactivity"""
        self.voice_client = vc
        self._cancel_disconnect()
        self.disconnect_task = loop.create_task(self._disconnect_after_delay(vc))

    def _cancel_disconnect(self):
        """Cancel the disconnect timer if it exists"""
        if self.disconnect_task and not self.disconnect_task.done():
            self.disconnect_task.cancel()
            self.disconnect_task = None

    async def _disconnect_after_delay(self, vc, delay=300):
        """Disconnect from voice channel after delay seconds (default 5 minutes)"""
        await asyncio.sleep(delay)
        if vc and vc.is_connected():
            await vc.disconnect()
            print(f"Auto-disconnected from {vc.guild.name} after inactivity")


queues = {}


def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a YouTube URL or search")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user.voice:
            await interaction.followup.send("You must be in a voice channel!")
            return

        channel = interaction.user.voice.channel

        if not interaction.guild.voice_client:
            vc = await channel.connect()
        else:
            vc = interaction.guild.voice_client

        queue = get_queue(interaction.guild_id)

        async with interaction.channel.typing():
            try:
                player = await YTDLSource.from_url(query, loop=self.bot.loop)
                queue.add(player)
                await interaction.followup.send(f"Added to queue: {player.title}")
            except Exception as e:
                await interaction.followup.send(f"Error: {str(e)}")
                return

        if not queue.playing:
            await self.play_next(interaction.guild_id, vc)

    async def play_next(self, guild_id, vc):
        queue = get_queue(guild_id)
        source = queue.next()

        if not source:
            queue.playing = False
            queue.start_disconnect_timer(vc, self.bot.loop)
            return

        queue.playing = True

        def after_playing(error):
            if error:
                print(f"Error: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild_id, vc), self.bot.loop)

        vc.play(source, after=after_playing)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
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
            embed.add_field(name=f"{i}. {item.title}", value="\u200b", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clear", description="Clear the queue")
    async def clear(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild_id)
        queue.queue.clear()
        
        # If nothing is playing, start disconnect timer
        vc = interaction.guild.voice_client
        if vc and not queue.playing:
            queue.start_disconnect_timer(vc, self.bot.loop)
        
        await interaction.response.send_message("Queue cleared!")

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            queue = get_queue(interaction.guild_id)
            queue._cancel_disconnect()  # Cancel any pending disconnect
            await vc.disconnect()
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
