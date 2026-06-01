import asyncio
import os
import time
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import logging
import traceback

logger = logging.getLogger('music')

# Debug: capture FFmpeg's own stderr to a log so we can see reconnect
# attempts, "Premature end of file", etc. during stutters. Remove once
# the stutter is diagnosed.
_ffmpeg_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg_debug.log')
_ffmpeg_log = open(_ffmpeg_log_path, 'ab')

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
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -af volume=0.5',
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
        t0 = time.monotonic()
        data = await loop.run_in_executor(None, lambda: _extract(self.webpage_url))
        t_extract = time.monotonic() - t0

        # We must RE-ENCODE so the `-af volume=0.5` filter is honored. We avoid
        # FFmpegOpusAudio.from_probe because it selects `-c:a copy` for Opus
        # sources, and ffmpeg refuses a filter with stream copy ("Filtering and
        # streamcopy cannot be used together") -> the track produces no audio.
        # GOTCHA (discord.py player.py:497): codec in {opus,libopus,copy} maps
        # to `-c:a copy`; ONLY codec=None (omitted) yields a real `-c:a libopus`
        # re-encode. So we pass NO codec here.
        t1 = time.monotonic()
        source = discord.FFmpegOpusAudio(
            data['url'],
            **ffmpeg_options,
            stderr=_ffmpeg_log,
        )
        t_setup = time.monotonic() - t1
        logger.info(f"[debug] '{self.title}' extract={t_extract:.2f}s setup={t_setup:.2f}s")
        return source


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
        # A track may have (re)started while we slept, so re-check before cutting
        # the connection. is_playing() is False while paused, so a parked pause
        # is still cleaned up, but an actively-playing track is never cut off.
        if vc and vc.is_connected() and not vc.is_playing():
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
    @app_commands.guild_only()
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
                # Already connected. If the requester is in a different channel,
                # move to them — but only when nothing is playing, so we don't
                # yank the bot out of an active session for other listeners.
                if vc.channel.id != channel.id:
                    if vc.is_playing() or vc.is_paused():
                        await interaction.followup.send(
                            f"I'm already playing in **{vc.channel.name}**. "
                            f"Join that channel or wait until it's free."
                        )
                        return
                    logger.debug(f"Moving from {vc.channel.name} to {channel.name}")
                    await vc.move_to(channel)
                else:
                    logger.debug("Using existing voice client")
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
            # Don't arm a timer on a vc that's already gone (avoids orphaning a
            # task if we're racing a disconnect that's about to pop the queue).
            if vc.is_connected():
                queue.start_disconnect_timer(vc, self.bot.loop)
            return

        queue.playing = True
        # Starting a track: cancel any pending idle/pause disconnect timer so it
        # can't fire mid-song (e.g. after /skip from a paused track).
        queue._cancel_disconnect()

        try:
            source = await item.create_source(loop=self.bot.loop)
        except Exception as e:
            logger.error(f"Failed to resolve '{item.title}' for playback: {e}")
            logger.debug(traceback.format_exc())
            await self.play_next(guild_id, vc)
            return

        logger.info(f"Now playing in guild {guild_id}: {item.title}")
        play_start = time.monotonic()

        def after_playing(error):
            elapsed = time.monotonic() - play_start
            if error:
                logger.error(f"Playback error in guild {guild_id} after {elapsed:.1f}s: {error}")
            else:
                logger.info(f"[debug] '{item.title}' finished after {elapsed:.1f}s")
            # after_playing runs in discord.py's audio thread; hop back to the
            # loop. play_next is the ONLY thing that advances the queue, so make
            # sure an exception in it can't vanish into the discarded future.
            fut = asyncio.run_coroutine_threadsafe(self.play_next(guild_id, vc), self.bot.loop)

            def _log_play_next_exc(f):
                exc = f.exception()
                if exc:
                    logger.error(f"play_next failed in guild {guild_id}: {exc}", exc_info=exc)

            fut.add_done_callback(_log_play_next_exc)

        try:
            vc.play(source, after=after_playing)
            logger.debug(f"Playback started successfully for guild {guild_id}")
        except Exception as e:
            # vc.play() can raise (e.g. "Not connected to voice." if the socket
            # dropped during create_source). It raises BEFORE the audio player
            # is created, so after_playing never fires — we must recover here.
            logger.error(f"Error starting playback in guild {guild_id}: {e}")
            logger.debug(traceback.format_exc())
            source.cleanup()  # kill the ffmpeg process we just spawned; nothing owns it
            queue.playing = False
            if vc.is_connected() and not vc.is_playing():
                # Per-track/transient failure but still connected: skip this one.
                await self.play_next(guild_id, vc)
            else:
                # Socket is down (or something's already playing): keep the queue
                # intact and put this track back at the front instead of draining
                # the whole queue (one extract + ffmpeg spawn per item) into the void.
                # after_playing never fired (vc.play raised before the player was
                # created) and discord.py's reconnect doesn't restart playback, so
                # we re-drive it ourselves once the socket comes back.
                queue.queue.insert(0, item)
                queue.current = None
                self.bot.loop.create_task(self._resume_after_reconnect(guild_id))

    def _live_vc(self, guild_id):
        """Current voice client for the guild, or None if fully disconnected.
        Re-fetched (not a captured handle) so we always see the live state — a
        reconnect keeps the same client; a terminal disconnect makes it None."""
        guild = self.bot.get_guild(guild_id)
        return guild.voice_client if guild else None

    async def _resume_after_reconnect(self, guild_id, delay=3, max_wait=120):
        """Resume a queue stranded when the voice socket dropped while a track was
        starting (vc.play raised before any audio player existed, so after_playing
        never fires and discord.py's in-player reconnect can't help). Polls the
        live voice client until the socket comes back, then re-drives play_next.
        Bails cleanly if playback already resumed, the queue was cleared, or the
        client is gone (discord.py gave up — a later /play will reconnect+resume).
        On give-up it arms the idle timer so we never sit connected-but-silent."""
        waited = 0
        while waited < max_wait:
            await asyncio.sleep(delay)
            waited += delay
            queue = get_queue(guild_id)
            if queue.playing or not queue.queue:
                return  # already resumed, or nothing left to resume
            vc = self._live_vc(guild_id)
            if vc is None:
                return  # voice client fully gone; next /play reconnects + resumes
            if vc.is_connected() and not vc.is_playing():
                logger.info(f"Voice reconnected for guild {guild_id}; resuming queue")
                await self.play_next(guild_id, vc)
                return
        # Gave up waiting for the socket. Don't leak the connection: arm the idle
        # timer (the user still has the preserved queue + a window to /play).
        logger.warning(f"Voice did not recover for guild {guild_id} within {max_wait}s; run /play to resume")
        vc = self._live_vc(guild_id)
        if vc and vc.is_connected():
            get_queue(guild_id).start_disconnect_timer(vc, self.bot.loop)

    @app_commands.command(name="skip", description="Skip the current song")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        logger.debug(f"Skip command invoked by {interaction.user}")
        vc = interaction.guild.voice_client
        # is_playing() is False while paused, so check both — otherwise /skip
        # refuses to skip a paused track. vc.stop() fires the after callback,
        # which advances the queue (no manual resume needed).
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            logger.info(f"Song skipped by {interaction.user}")
            await interaction.response.send_message("Skipped!")
        else:
            await interaction.response.send_message("Nothing playing!")

    @app_commands.command(name="queue", description="Show the queue")
    @app_commands.guild_only()
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
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction):
        queue = get_queue(interaction.guild_id)
        queue.queue.clear()

        vc = interaction.guild.voice_client
        if vc and not queue.playing:
            queue.start_disconnect_timer(vc, self.bot.loop)

        await interaction.response.send_message("Queue cleared!")

    @app_commands.command(name="leave", description="Leave the voice channel")
    @app_commands.guild_only()
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
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            # A paused track holds the voice connection open indefinitely
            # (discord.py keeps sending silence), so arm the inactivity timer
            # while paused — it's cancelled on resume / new tracks.
            queue = get_queue(interaction.guild_id)
            queue.start_disconnect_timer(vc, self.bot.loop)
            await interaction.response.send_message("Paused!")
        else:
            await interaction.response.send_message("Nothing playing!")

    @app_commands.command(name="resume", description="Resume the current song")
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            queue = get_queue(interaction.guild_id)
            queue._cancel_disconnect()  # active again — don't auto-disconnect
            vc.resume()
            await interaction.response.send_message("Resumed!")
        else:
            await interaction.response.send_message("Nothing paused!")
