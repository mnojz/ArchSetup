"""
Task: Mirrorlist Optimization (rate-mirrors)
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_running, prompt_yes_no
from core.logger import logger
from core.pacman import pm

def run(auto_confirm: bool = False) -> bool:
    if not prompt_yes_no("Optimize pacman mirrorlist using rate-mirrors?", default=True, auto_confirm=auto_confirm):
        log_info("Skipping mirror optimization")
        return True

    if not shutil.which("rate-mirrors"):
        log_running("Installing rate-mirrors...")
        pm.install_package("rate-mirrors")

    if not shutil.which("rate-mirrors"):
        log_warning("rate-mirrors could not be installed; skipping mirror ranking")
        return False

    mirrorlist = Path("/etc/pacman.d/mirrorlist")
    backup_file = Path(f"/etc/pacman.d/mirrorlist.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if mirrorlist.exists():
        code, _ = logger.run_cmd(["sudo", "cp", str(mirrorlist), str(backup_file)], check=False)
        if code != 0:
            log_warning("Mirrorlist backup failed; leaving the mirrorlist unchanged")
            return False

    log_running("Benchmarking fastest Arch mirrors (this may take 15-30s)...")
    with tempfile.TemporaryDirectory(prefix="archsetup-mirrors-") as tmp_dir:
        tmp_path = Path(tmp_dir) / "mirrorlist"
        code, _ = logger.run_cmd(["rate-mirrors", f"--save={tmp_path}", "arch"], check=False)
        if code != 0 or not tmp_path.is_file() or tmp_path.stat().st_size == 0:
            log_warning("rate-mirrors failed or returned an empty list; mirrorlist unchanged")
            return False
        code, _ = logger.run_cmd(["sudo", "cp", str(tmp_path), str(mirrorlist)], check=False)
        if code != 0:
            log_warning("Failed to install mirrorlist")
            if backup_file.exists():
                restore_code, _ = logger.run_cmd(["sudo", "cp", str(backup_file), str(mirrorlist)], check=False)
                if restore_code != 0:
                    log_warning(f"Mirrorlist recovery failed; restore {backup_file} manually")
            return False
    # Do not refresh databases independently of a full system upgrade.
    pm.invalidate_transaction()
    log_success("Mirrorlist optimized; package databases will refresh with the next full upgrade")
    return True
