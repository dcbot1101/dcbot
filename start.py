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

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
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

def main():
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    print("=" * 50)
    print("   Discord Bot Launcher")
    print("=" * 50)
    print()
    
    # Check Python (should always pass since we're running Python)
    print_status(f"Python: {get_python_version()}", "ok")
    
    # Check FFmpeg
    print_status("Checking FFmpeg...")
    if not check_command(["ffmpeg", "-version"]):
        print_status("FFmpeg not found!", "error")
        print()
        print("FFmpeg is REQUIRED for the music bot.")
        print()
        
        # Check if winget is available for auto-install
        if check_command(["winget", "--version"]):
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
                        capture_output=False,
                        text=True
                    )
                    
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
                        
                except Exception as e:
                    print()
                    print_status(f"Error during installation: {e}", "error")
        
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
    
    if not env_file.exists():
        print_status("No .env file found!", "warning")
        print()
        print("You need to create a .env file with your Discord bot token.")
        print()
        
        create = input("Create it now? (y/n): ").lower().strip()
        if create != 'y':
            print()
            print_status("Cannot start without Discord token.", "error")
            input("Press Enter to exit...")
            sys.exit(1)
        
        print()
        token = input("Enter your Discord bot token: ").strip()
        if not token:
            print_status("No token provided.", "error")
            input("Press Enter to exit...")
            sys.exit(1)
        
        env_file.write_text(f"DISCORD_TOKEN={token}\n")
        print_status(".env file created", "ok")
    else:
        print_status("Configuration found", "ok")
    print()
    
    # Check virtual environment
    print_status("Setting up environment...")
    venv_dir = script_dir / "venv"
    venv_python = venv_dir / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        print_status("Creating virtual environment...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            print_status("Virtual environment created", "ok")
        except subprocess.CalledProcessError:
            print_status("Failed to create virtual environment", "error")
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        print_status("Virtual environment ready", "ok")
    print()
    
    # Activate and install requirements
    print_status("Installing dependencies...")
    try:
        # Upgrade pip
        subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], 
                      capture_output=True)
        
        # Install requirements
        result = subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print_status("Failed to install packages", "error")
            print(result.stderr)
            input("Press Enter to exit...")
            sys.exit(1)
        
        print_status("Packages ready", "ok")
    except Exception as e:
        print_status(f"Error installing packages: {e}", "error")
        input("Press Enter to exit...")
        sys.exit(1)
    print()
    
    # Git pull (optional)
    print_status("Checking for updates...")
    if (script_dir / ".git").exists():
        try:
            result = subprocess.run(["git", "pull"], capture_output=True, text=True)
            if result.returncode == 0:
                print_status("Up to date", "ok")
            else:
                print_status("Could not check for updates (this is OK)", "warning")
        except:
            print_status("Git not available", "warning")
    else:
        print_status("Not a git repository (this is OK)", "info")
    print()
    
    # Run the bot
    print("=" * 50)
    print_status("Starting bot... (Press Ctrl+C to stop)")
    print("=" * 50)
    print()
    
    try:
        # Run bot with the venv Python
        result = subprocess.run([str(venv_python), "bot.py"])
        
        print()
        print("=" * 50)
        if result.returncode == 0:
            print_status("Bot stopped normally")
        else:
            print_status(f"Bot exited with code: {result.returncode}", "error")
        print("=" * 50)
        
    except KeyboardInterrupt:
        print()
        print_status("Bot stopped by user")
    except Exception as e:
        print()
        print_status(f"Error running bot: {e}", "error")
    
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.RESET}")
        input("Press Enter to exit...")
        sys.exit(1)
