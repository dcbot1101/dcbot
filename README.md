# Discord Music Bot - Windows Setup

## Quick Start

### 1. Prerequisites

Before running, you need:
- **Python 3.8+** - https://www.python.org/downloads/
- **FFmpeg** - Required for audio playback
- **Discord Bot Token** - Get from https://discord.com/developers/applications

### 2. Install FFmpeg (REQUIRED)

Open PowerShell or Command Prompt and run ONE of these:

**Using winget (Windows 10/11 - easiest):**
```powershell
winget install --id Gyan.FFmpeg
```

**Using Chocolatey:**
```powershell
choco install ffmpeg
```

**Using Scoop:**
```powershell
scoop install ffmpeg
```

**Verify it's installed:**
```powershell
ffmpeg -version
```

### 3. Run the Bot

**Double-click to run:**
```
start.bat
```

Or run directly:
```
python start.py
```

## What the Launcher Does

The launcher (`start.py` / `start.bat`) automatically:

1. ✅ **Checks FFmpeg** - Stops with instructions if not installed
2. ✅ **Checks .env file** - Prompts to create if missing (asks for your Discord token)
3. ✅ **Creates virtual environment** - Sets up Python venv if needed
4. ✅ **Installs packages** - Installs/updates requirements.txt
5. ✅ **Checks for updates** - Runs `git pull` if this is a git repo
6. ✅ **Runs the bot** - Starts the Discord bot
7. ✅ **Handles errors** - Shows clear error messages and pauses

**The window stays open** until you press Enter at the end!

## First Run

On first run, the launcher will:
1. Ask if you want to create `.env` file
2. Ask for your Discord bot token
3. Create the virtual environment (takes 1-2 minutes)
4. Download and install Python packages (takes 2-3 minutes)

Subsequent runs are much faster!

## Files

```
dcbot/
├── start.py          ← Main launcher (Python)
├── start.bat         ← Double-click wrapper (runs start.py)
├── bot.py            ← Main bot code
├── music.py          ← Music commands
├── config.py         ← Configuration
├── requirements.txt  ← Python dependencies
└── .env              ← Your Discord token (created on first run)
```

## Troubleshooting

### "FFmpeg is not installed"
Install FFmpeg using one of the commands in Step 2 above, then run again.

### "Window closes immediately"
The launcher should never auto-close. If it does:
- Run from Command Prompt to see the error:
  ```cmd
  cd C:\path\to\dcbot
  python start.py
  ```

### "No module named 'xxx'"
Delete the `venv` folder and run again - it will recreate everything.

### "Invalid token"
Delete the `.env` file and run again - it will prompt for a new token.

## Manual Setup

If you prefer to set up manually:

```batch
# Install FFmpeg first

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate.bat

# Install packages
pip install -r requirements.txt

# Create .env file with your token
echo DISCORD_TOKEN=your_token_here > .env

# Run the bot
python bot.py
```
