import discord
from discord import app_commands
from discord.ext import commands
import config
from music import MusicCog
import asyncio
from aiohttp import web
import logging
import sys
import traceback
from datetime import datetime

# Set up logging
log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

# File handler for debug logs
file_handler = logging.FileHandler('bot_debug.log', mode='a', encoding='utf-8')
file_handler.setFormatter(log_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Set log levels based on debug mode
if config.DEBUG:
    root_logger.setLevel(logging.DEBUG)
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.DEBUG)
    print(f"[DEBUG] Debug mode enabled - detailed logging active")
else:
    root_logger.setLevel(logging.INFO)
    # Reduce discord.py noise in normal mode
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)

logger = logging.getLogger('bot')

# Log startup info
logger.info("=" * 50)
logger.info("Bot starting up...")
logger.info(f"Debug mode: {config.DEBUG}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Discord.py version: {discord.__version__}")
logger.info("=" * 50)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def health_check(request):
    return web.Response(text="OK")


async def run_bot():
    await bot.start(config.DISCORD_TOKEN)


async def run_web():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()


@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    for guild in bot.guilds:
        logger.debug(f"  - {guild.name} (ID: {guild.id})")
    
    try:
        await bot.add_cog(MusicCog(bot))
        logger.info("MusicCog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load MusicCog: {e}")
        logger.debug(traceback.format_exc())
        raise
    
    # Sync commands to specific guilds for instant availability
    if config.GUILD_IDS:
        logger.info(f"Syncing commands to {len(config.GUILD_IDS)} guild(s)...")
        for guild_id in config.GUILD_IDS:
            try:
                guild = discord.Object(id=guild_id)
                await bot.tree.sync(guild=guild)
                logger.info(f"Commands synced to guild {guild_id}!")
            except Exception as e:
                logger.error(f"Failed to sync commands to guild {guild_id}: {e}")
                logger.debug(traceback.format_exc())
    else:
        # Fallback to global sync if no guilds specified
        logger.info("Syncing commands globally...")
        try:
            await bot.tree.sync()
            logger.info("Commands synced globally!")
        except Exception as e:
            logger.error(f"Failed to sync commands globally: {e}")
            logger.debug(traceback.format_exc())


@bot.event
async def on_error(event, *args, **kwargs):
    """Global error handler for discord.py events"""
    logger.error(f"Error in event {event}: ", exc_info=True)
    logger.debug(f"Event args: {args}, kwargs: {kwargs}")


@bot.event
async def on_command_error(ctx, error):
    """Global command error handler"""
    logger.error(f"Command error in {ctx.command}: {error}")
    logger.debug(traceback.format_exc())


@bot.event
async def on_connect():
    logger.info("Connected to Discord gateway")


@bot.event
async def on_disconnect():
    logger.warning("Disconnected from Discord gateway")


@bot.event
async def on_resumed():
    logger.info("Session resumed")


async def main():
    try:
        await asyncio.gather(run_web(), run_bot())
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}")
        logger.critical(traceback.format_exc())
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
