#!/usr/bin/env python3
"""
Discord Bot Launcher
Double-click to run - handles everything automatically
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import argparse
import traceback
from datetime import datetime

# Parse arguments early for debug mode
parser = argparse.ArgumentParser(description='Discord Bot Launcher')
parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
args, remaining_args = parser.parse_known_args()

# Debug mode flag
DEBUG_MODE = args.debug

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'

def print_status(message, status="info"):
    """Print colored status messages"""
    if status == "ok":
        print(f"{Colors.GREEN}[OK]{Colors.RESET} {message}")
    elif status == "warning":
        print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {message}")
    elif status == "error":
        print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}")
    elif status == "info":
        print(f"{Colors.CYAN}[INFO]{Colors.RESET} {message}")
    else:
        print(message)

def check_command(cmd):
    """Check if a command exists"""
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_python_version():
    """Get Python version string"""
    return f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

def log_debug(message, log_file=None):
    """Write debug message to log file and console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    
    if DEBUG_MODE:
        print(f"{Colors.MAGENTA}[DEBUG]{Colors.RESET} {message}")
    
    if log_file:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')


def get_system_info():
    """Gather system information for debugging"""
    info = {
        'platform': platform.platform(),
        'python_version': sys.version,
        'python_executable': sys.executable,
        'cwd': os.getcwd(),
    }
    
    # Check key dependencies
    try:
        import discord
        info['discord_version'] = discord.__version__
    except ImportError:
        info['discord_version'] = 'NOT INSTALLED'
    
    try:
        import aiohttp
        info['aiohttp_version'] = aiohttp.__version__
    except ImportError:
        info['aiohttp_version'] = 'NOT INSTALLED'
    
    try:
        import yt_dlp
        info['yt_dlp_version'] = yt_dlp.version.__version__
    except ImportError:
        info['yt_dlp_version'] = 'NOT INSTALLED'
    
    return info


def main():
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Setup debug logging
    debug_log = script_dir / 'launcher_debug.log' if DEBUG_MODE else None
    
    if DEBUG_MODE:
        print("=" * 50)
        print(f"{Colors.MAGENTA}   DEBUG MODE ENABLED{Colors.RESET}")
        print("=" * 50)
        if debug_log:
            with open(debug_log, 'w', encoding='utf-8') as f:
                f.write(f"Launcher Debug Log - {datetime.now()}\n")
                f.write("=" * 50 + "\n\n")
        log_debug("Debug mode activated", debug_log)
    
    print("=" * 50)
    print("   Discord Bot Launcher")
    print("=" * 50)
    print()
    
    if DEBUG_MODE:
        log_debug("Starting system information collection...", debug_log)
        info = get_system_info()
        log_debug(f"Platform: {info['platform']}", debug_log)
        log_debug(f"Python: {info['python_version'][:50]}...", debug_log)
        log_debug(f"Working directory: {info['cwd']}", debug_log)
        log_debug(f"discord.py: {info.get('discord_version', 'unknown')}", debug_log)
        log_debug(f"aiohttp: {info.get('aiohttp_version', 'unknown')}", debug_log)
        log_debug(f"yt-dlp: {info.get('yt_dlp_version', 'unknown')}", debug_log)
        print()
    
    # Check Python (should always pass since we're running Python)
    print_status(f"Python: {get_python_version()}", "ok")
    if DEBUG_MODE:
        log_debug(f"Python executable: {sys.executable}", debug_log)
    
    # Check FFmpeg
    print_status("Checking FFmpeg...")
    if DEBUG_MODE:
        log_debug("Checking for FFmpeg installation...", debug_log)
    
    ffmpeg_ok = False
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        ffmpeg_ok = result.returncode == 0
        if DEBUG_MODE:
            log_debug(f"FFmpeg check result: returncode={result.returncode}", debug_log)
            if ffmpeg_ok:
                version_line = result.stdout.split('\n')[0] if result.stdout else 'unknown'
                log_debug(f"FFmpeg version: {version_line}", debug_log)
    except Exception as e:
        if DEBUG_MODE:
            log_debug(f"FFmpeg check failed with exception: {e}", debug_log)
            log_debug(traceback.format_exc(), debug_log)
    
    if not ffmpeg_ok:
        print_status("FFmpeg not found!", "error")
        if DEBUG_MODE:
            log_debug("FFmpeg NOT FOUND - this will prevent music playback", debug_log)
        print()
        print("FFmpeg is REQUIRED for the music bot.")
        print()
        
        # Check if winget is available for auto-install
        winget_available = check_command(["winget", "--version"])
        if DEBUG_MODE:
            log_debug(f"winget available: {winget_available}", debug_log)
        
        if winget_available:
            print("Would you like to install FFmpeg automatically using winget?")
            install_choice = input("Install now? (y/n): ").lower().strip()
            
            if install_choice == 'y':
                print()
                print_status("Installing FFmpeg via winget...")
                print("This may take a few minutes...")
                print()
                
                try:
                    # Install FFmpeg using winget
                    result = subprocess.run(
                        ["winget", "install", "--id", "Gyan.FFmpeg", "-e", 
                         "--accept-package-agreements", "--accept-source-agreements"],
                        capture_output=DEBUG_MODE,
                        text=True
                    )
                    
                    if DEBUG_MODE:
                        log_debug(f"winget install return code: {result.returncode}", debug_log)
                        if result.stdout:
                            log_debug(f"winget stdout: {result.stdout[:500]}", debug_log)
                        if result.stderr:
                            log_debug(f"winget stderr: {result.stderr[:500]}", debug_log)
                    
                    if result.returncode == 0:
                        print()
                        print_status("FFmpeg installed successfully!", "ok")
                        print_status("Please restart the script to continue.")
                        print()
                        input("Press Enter to exit...")
                        sys.exit(0)
                    else:
                        print()
                        print_status("Installation failed or was cancelled.", "error")
                        if DEBUG_MODE:
                            log_debug(f"FFmpeg installation failed with code {result.returncode}", debug_log)
                        
                except Exception as e:
                    print()
                    print_status(f"Error during installation: {e}", "error")
                    if DEBUG_MODE:
                        log_debug(f"FFmpeg installation exception: {e}", debug_log)
                        log_debug(traceback.format_exc(), debug_log)
        
        # If we get here, either winget isn't available, user said no, or install failed
        print()
        print("You can install FFmpeg manually using ONE of these commands:")
        print()
        print("  winget install --id Gyan.FFmpeg")
        print("  choco install ffmpeg")
        print("  scoop install ffmpeg")
        print()
        print("Or download from: https://www.gyan.dev/ffmpeg/builds/")
        print()
        input("Press Enter to exit...")
        sys.exit(1)
    
    print_status("FFmpeg found", "ok")
    print()
    
    # Check .env file
    print_status("Checking configuration...")
    env_file = script_dir / ".env"
    
    if DEBUG_MODE:
        log_debug(f"Looking for .env file at: {env_file}", debug_log)
        log_debug(f".env exists: {env_file.exists()}", debug_log)
    
    if not env_file.exists():
        print_status("No .env file found!", "warning")
        print()
        print("You need to create a .env file with your Discord bot token.")
        print()
        
        create = input("Create it now? (y/n): ").lower().strip()
        if create != 'y':
            print()
            print_status("Cannot start without Discord token.", "error")
            if DEBUG_MODE:
                log_debug("User declined to create .env file", debug_log)
            input("Press Enter to exit...")
            sys.exit(1)
        
        print()
        token = input("Enter your Discord bot token: ").strip()
        if not token:
            print_status("No token provided.", "error")
            if DEBUG_MODE:
                log_debug("No token provided by user", debug_log)
            input("Press Enter to exit...")
            sys.exit(1)
        
        env_file.write_text(f"DISCORD_TOKEN={token}\n")
        print_status(".env file created", "ok")
        if DEBUG_MODE:
            log_debug(".env file created successfully", debug_log)
    else:
        print_status("Configuration found", "ok")
        if DEBUG_MODE:
            # Check if token exists in .env (without exposing the actual token)
            try:
                env_content = env_file.read_text()
                has_token = 'DISCORD_TOKEN=' in env_content and len(env_content.split('DISCORD_TOKEN=')[1].strip()) > 10
                log_debug(f".env file has DISCORD_TOKEN set: {has_token}", debug_log)
            except Exception as e:
                log_debug(f"Error reading .env: {e}", debug_log)
    print()
    
    # Check virtual environment
    print_status("Setting up environment...")
    venv_dir = script_dir / "venv"
    venv_python = venv_dir / "Scripts" / "python.exe"
    
    if DEBUG_MODE:
        log_debug(f"Virtual environment path: {venv_dir}", debug_log)
        log_debug(f"Venv Python executable: {venv_python}", debug_log)
        log_debug(f"Venv exists: {venv_python.exists()}", debug_log)
    
    if not venv_python.exists():
        print_status("Creating virtual environment...")
        if DEBUG_MODE:
            log_debug("Creating new virtual environment...", debug_log)
        try:
            result = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], 
                                   capture_output=DEBUG_MODE, text=True, check=True)
            if DEBUG_MODE:
                log_debug("Virtual environment created successfully", debug_log)
            print_status("Virtual environment created", "ok")
        except subprocess.CalledProcessError as e:
            print_status("Failed to create virtual environment", "error")
            if DEBUG_MODE:
                log_debug(f"Venv creation failed: {e}", debug_log)
                if e.stdout:
                    log_debug(f"stdout: {e.stdout}", debug_log)
                if e.stderr:
                    log_debug(f"stderr: {e.stderr}", debug_log)
            input("Press Enter to exit...")
            sys.exit(1)
        except Exception as e:
            print_status(f"Error creating venv: {e}", "error")
            if DEBUG_MODE:
                log_debug(f"Venv creation exception: {e}", debug_log)
                log_debug(traceback.format_exc(), debug_log)
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        print_status("Virtual environment ready", "ok")
    print()
    
    # Activate and install requirements
    print_status("Installing dependencies...")
    if DEBUG_MODE:
        log_debug("Starting dependency installation...", debug_log)
    
    try:
        # Upgrade pip
        if DEBUG_MODE:
            log_debug("Upgrading pip...", debug_log)
        pip_upgrade = subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], 
                      capture_output=DEBUG_MODE, text=True)
        if DEBUG_MODE:
            log_debug(f"Pip upgrade result: {pip_upgrade.returncode}", debug_log)
        
        # Install requirements
        if DEBUG_MODE:
            log_debug("Installing requirements from requirements.txt...", debug_log)
        result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=True,
            text=True
        )
        
        if DEBUG_MODE:
            log_debug(f"Pip install result: {result.returncode}", debug_log)
            if result.stdout:
                log_debug(f"Pip stdout:\n{result.stdout}", debug_log)
            if result.stderr:
                log_debug(f"Pip stderr:\n{result.stderr}", debug_log)
        
        if result.returncode != 0:
            print_status("Failed to install packages", "error")
            print(result.stderr)
            if DEBUG_MODE:
                log_debug("Package installation FAILED", debug_log)
            input("Press Enter to exit...")
            sys.exit(1)
        
        print_status("Packages ready", "ok")
        if DEBUG_MODE:
            log_debug("All packages installed successfully", debug_log)
    except Exception as e:
        print_status(f"Error installing packages: {e}", "error")
        if DEBUG_MODE:
            log_debug(f"Package installation exception: {e}", debug_log)
            log_debug(traceback.format_exc(), debug_log)
        input("Press Enter to exit...")
        sys.exit(1)
    print()
    
    # Git pull (optional)
    print_status("Checking for updates...")
    git_exists = (script_dir / ".git").exists()
    if DEBUG_MODE:
        log_debug(f".git directory exists: {git_exists}", debug_log)
    
    if git_exists:
        try:
            result = subprocess.run(["git", "pull"], capture_output=True, text=True)
            if DEBUG_MODE:
                log_debug(f"Git pull result: {result.returncode}", debug_log)
                log_debug(f"Git output: {result.stdout}", debug_log)
            if result.returncode == 0:
                print_status("Up to date", "ok")
            else:
                print_status("Could not check for updates (this is OK)", "warning")
                if DEBUG_MODE:
                    log_debug(f"Git pull stderr: {result.stderr}", debug_log)
        except Exception as e:
            print_status("Git not available", "warning")
            if DEBUG_MODE:
                log_debug(f"Git error: {e}", debug_log)
    else:
        print_status("Not a git repository (this is OK)", "info")
    print()
    
    # Run the bot
    print("=" * 50)
    print_status("Starting bot... (Press Ctrl+C to stop)")
    if DEBUG_MODE:
        print(f"{Colors.MAGENTA}[DEBUG]{Colors.RESET} Debug logging to bot_debug.log")
    print("=" * 50)
    print()
    
    # Set environment variable for debug mode
    env = os.environ.copy()
    if DEBUG_MODE:
        env['DEBUG'] = 'true'
        log_debug("Starting bot subprocess with DEBUG=true", debug_log)
    
    try:
        # Run bot with the venv Python
        # In debug mode, capture output to show in real-time
        if DEBUG_MODE:
            log_debug(f"Running: {venv_python} bot.py", debug_log)
            # Use Popen to stream output in real-time
            process = subprocess.Popen(
                [str(venv_python), "bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            
            # Stream output
            for line in process.stdout:
                print(line, end='')
                if debug_log:
                    with open(debug_log, 'a', encoding='utf-8') as f:
                        f.write(line)
            
            process.wait()
            result_returncode = process.returncode
        else:
            result = subprocess.run([str(venv_python), "bot.py"], env=env)
            result_returncode = result.returncode
        
        print()
        print("=" * 50)
        if result_returncode == 0:
            print_status("Bot stopped normally")
            if DEBUG_MODE:
                log_debug("Bot exited with code 0", debug_log)
        else:
            print_status(f"Bot exited with code: {result_returncode}", "error")
            if DEBUG_MODE:
                log_debug(f"Bot exited with ERROR code: {result_returncode}", debug_log)
                print()
                print(f"{Colors.YELLOW}Check bot_debug.log for detailed error information{Colors.RESET}")
                print(f"{Colors.YELLOW}Check launcher_debug.log for launcher diagnostics{Colors.RESET}")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print()
        print_status("Bot stopped by user")
        if DEBUG_MODE:
            log_debug("Bot stopped by user (KeyboardInterrupt)", debug_log)
    except Exception as e:
        print()
        print_status(f"Error running bot: {e}", "error")
        if DEBUG_MODE:
            log_debug(f"Bot run exception: {e}", debug_log)
            log_debug(traceback.format_exc(), debug_log)
    
    print()
    if DEBUG_MODE:
        print(f"{Colors.CYAN}Debug logs saved to:{Colors.RESET}")
        print(f"  - bot_debug.log (bot runtime logs)")
        print(f"  - launcher_debug.log (launcher diagnostics)")
        print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        if DEBUG_MODE:
            print(f"\n{Colors.MAGENTA}[DEBUG]{Colors.RESET} Full traceback:")
            traceback.print_exc()
            # Also try to log to file
            try:
                with open('launcher_debug.log', 'a', encoding='utf-8') as f:
                    f.write(f"\n[{datetime.now()}] FATAL ERROR: {e}\n")
                    f.write(traceback.format_exc())
            except:
                pass
        input("Press Enter to exit...")
        sys.exit(1)
