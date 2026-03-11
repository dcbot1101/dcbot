import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Parse SERVERS env var (comma-separated list of guild IDs)
servers_str = os.getenv("SERVERS", "")
GUILD_IDS = [int(guild_id.strip()) for guild_id in servers_str.split(",") if guild_id.strip()]
