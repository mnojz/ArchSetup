"""
Task: AUR Helper Bootstrap (yay-bin)
"""

import shutil
import tempfile
from pathlib import Path
from core.tui import log_info, log_success, log_error, log_running
from core.logger import logger
from core.pacman import pm

def run(auto_confirm: bool = False) -> bool:
    aur_tool = pm.get_aur_helper()
    if aur_tool:
        log_success(f"{aur_tool} AUR helper is already installed and ready")
        return True

    log_running("Installing build prerequisites (git, base-devel)...")
    code, _ = logger.run_cmd(
        ["sudo", "pacman", "-S", "--needed", "--noconfirm", "git", "base-devel"],
        check=False
    )
    if code != 0:
        log_error("Failed to install base-devel prerequisites.")
        return False

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        log_running("Cloning yay-bin from AUR...")
        code, _ = logger.run_cmd(
            ["git", "clone", "--depth=1", "https://aur.archlinux.org/yay-bin.git", str(tmp_path)],
            check=False
        )
        if code != 0:
            log_error("Failed to clone yay-bin repository.")
            return False

        log_running("Compiling and installing yay-bin...")
        code, _ = logger.run_cmd(
            ["makepkg", "-si", "--noconfirm"],
            cwd=tmp_path,
            check=False
        )
        
        if code == 0 and shutil.which("yay"):
            log_success("yay AUR helper installed successfully")
            return True
        else:
            log_error("Failed to build/install yay-bin. Check install.log for details.")
            return False

