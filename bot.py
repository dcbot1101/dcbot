import discord
from discord import app_commands
from discord.ext import commands
import config
from music import MusicCog
import asyncio
from aiohttp import web

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
    print(f"Bot logged in as {bot.user}")
    await bot.add_cog(MusicCog(bot))
    await bot.tree.sync()
    print("Commands synced!")


async def main():
    await asyncio.gather(run_web(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
