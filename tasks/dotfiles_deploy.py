"""
Task: Dotfiles Deployment
Clones or updates user dotfiles repository and executes dotfile installer.
"""

import os
import subprocess
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_error, log_running, prompt_yes_no
from core.logger import logger

DOTFILES_REPO = "https://github.com/mnojz/dotfiles.git"
DOTFILES_DIR = Path.home() / "dotfiles"

def run(auto_confirm: bool = False) -> bool:
    if not prompt_yes_no(f"Install and apply dotfiles from GitHub ({DOTFILES_REPO})?", default=True, auto_confirm=auto_confirm):
        log_info("Skipping dotfiles installation")
        return True

    if (DOTFILES_DIR / ".git").is_dir():
        log_info(f"Existing dotfiles repository detected at {DOTFILES_DIR}")
        log_running("Pulling latest git changes...")
        logger.run_cmd(["git", "-C", str(DOTFILES_DIR), "pull", "--rebase"], check=False)
    elif DOTFILES_DIR.is_dir():
        log_warning(f"Directory {DOTFILES_DIR} exists but is not a git repository. Skipping clone.")
    else:
        log_running("Cloning dotfiles repository...")
        code, _ = logger.run_cmd(["git", "clone", "--depth=1", DOTFILES_REPO, str(DOTFILES_DIR)], check=False)
        if code != 0:
            log_error("Failed to clone dotfiles repository.")
            return False

    install_script = DOTFILES_DIR / "install.sh"
    if install_script.is_file():
        log_running("Executing dotfiles install.sh...")
        os.chmod(install_script, 0o755)
        code, _ = logger.run_cmd(["bash", str(install_script)], check=False)
        if code == 0:
            log_success("Dotfiles installed and applied successfully")
            return True
        else:
            log_warning("Dotfiles install script reported errors. Check log file.")
            return False
    else:
        log_warning(f"No install.sh found in {DOTFILES_DIR}")
        return True

