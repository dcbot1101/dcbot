import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Parse SERVERS env var (comma-separated list of guild IDs). Parse defensively:
# a single non-numeric token must not crash the whole process at import time
# (config is imported before logging/error handling is set up).
servers_str = os.getenv("SERVERS", "")
GUILD_IDS = []
for _gid in servers_str.split(","):
    _gid = _gid.strip()
    if not _gid:
        continue
    try:
        GUILD_IDS.append(int(_gid))
    except ValueError:
        print(f"[config] Ignoring invalid guild ID in SERVERS: {_gid!r}")

# Debug mode - set DEBUG=true in .env or use --debug flag
DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
