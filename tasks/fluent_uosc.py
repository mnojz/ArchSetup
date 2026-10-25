"""
Task: Fluent UOSC Installation
Installs and maintains mnojz's custom Fluent UOSC theme and interface for mpv.
Repository: https://github.com/mnojz/fluent_UOSC.git
"""

import shutil
from datetime import datetime
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_error, log_running, prompt_yes_no
from core.logger import logger
from core.pacman import pm

FLUENT_UOSC_REPO = "https://github.com/mnojz/fluent_UOSC.git"
MPV_CONFIG_DIR = Path.home() / ".config/mpv"

def cleanup_legacy_uosc():
    """Removes conflicting official or AUR mpv-uosc package if installed."""
    if pm.is_installed("mpv-uosc"):
        log_running("Removing conflicting legacy mpv-uosc package...")
        code, _ = logger.run_cmd(["sudo", "pacman", "-R", "--noconfirm", "mpv-uosc"], check=False)
        if code == 0:
            log_success("Legacy mpv-uosc package removed")
            pm._refresh_installed_cache()
        else:
            log_warning("Could not remove legacy mpv-uosc package automatically")

def run(auto_confirm: bool = False) -> bool:
    """Clones or updates fluent_UOSC in ~/.config/mpv."""
    cleanup_legacy_uosc()

    # Case 1: Existing git repository in ~/.config/mpv
    if (MPV_CONFIG_DIR / ".git").is_dir():
        log_info(f"Existing git repository detected at {MPV_CONFIG_DIR}")
        log_running("Pulling latest fluent_UOSC changes from GitHub...")
        code, _ = logger.run_cmd(["git", "-C", str(MPV_CONFIG_DIR), "pull", "--rebase"], check=False)
        if code != 0:
            log_running("Resetting conflicting local MPV files to match remote repository...")
            logger.run_cmd(["git", "-C", str(MPV_CONFIG_DIR), "fetch", "origin"], check=False)
            code, _ = logger.run_cmd(["git", "-C", str(MPV_CONFIG_DIR), "reset", "--hard", "origin/main"], check=False)

        if code == 0:
            log_success("fluent_UOSC updated successfully")
            return True
        else:
            log_warning("Could not sync remote fluent_UOSC. Retaining current configuration.")
            return True

    # Case 2: Existing non-git directory with files -> backup first
    backup_dir = None
    if MPV_CONFIG_DIR.exists() and any(MPV_CONFIG_DIR.iterdir()):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path.home() / f".config/mpv.backup_{timestamp}"
        log_info(f"Backing up existing mpv configuration to {backup_dir.name}")
        try:
            shutil.move(str(MPV_CONFIG_DIR), str(backup_dir))
        except Exception as e:
            log_warning(f"Could not move existing ~/.config/mpv: {e}")

    # Case 3: Clone fluent_UOSC from GitHub
    log_running(f"Cloning fluent_UOSC from {FLUENT_UOSC_REPO}...")
    code, _ = logger.run_cmd(["git", "clone", "--depth=1", FLUENT_UOSC_REPO, str(MPV_CONFIG_DIR)], check=False)
    if code == 0:
        log_success("fluent_UOSC installed successfully into ~/.config/mpv")
        return True

    log_error("Failed to clone fluent_UOSC repository.")
    if backup_dir and backup_dir.exists():
        log_info(f"Restoring previous configuration from {backup_dir.name}")
        shutil.move(str(backup_dir), str(MPV_CONFIG_DIR))
    return False

