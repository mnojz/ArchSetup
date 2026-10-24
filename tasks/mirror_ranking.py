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
        logger.run_cmd(["sudo", "cp", str(mirrorlist), str(backup_file)], check=False)

    log_running("Benchmarking fastest Arch mirrors (this may take 15-30s)...")
    with tempfile.NamedTemporaryFile(delete=False) as tmp_out:
        tmp_path = tmp_out.name

    code, _ = logger.run_cmd(["rate-mirrors", f"--save={tmp_path}", "arch"], check=False)
    if code == 0 and Path(tmp_path).stat().st_size > 0:
        logger.run_cmd(["sudo", "cp", tmp_path, str(mirrorlist)], check=False)
        logger.run_cmd(["sudo", "pacman", "-Syy"], check=False)
        log_success("Mirrorlist optimized and package databases synchronized")
        Path(tmp_path).unlink(missing_ok=True)
        return True
    else:
        log_warning("rate-mirrors failed or returned empty list; restoring original mirrorlist")
        if backup_file.exists():
            logger.run_cmd(["sudo", "cp", str(backup_file), str(mirrorlist)], check=False)
        Path(tmp_path).unlink(missing_ok=True)
        return False

