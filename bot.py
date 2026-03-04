import discord
from discord import app_commands
from discord.ext import commands
import config
from music import MusicCog

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await bot.add_cog(MusicCog(bot))
    await bot.tree.sync()
    print("Commands synced!")


bot.run(config.DISCORD_TOKEN)
