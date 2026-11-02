"""
Task: Desktop Integration & MIME Repair
Configures Dolphin menu structures and repairs XDG MIME cache.
"""

import subprocess
import shutil
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_running, prompt_yes_no
from core.logger import logger

def run(auto_confirm: bool = False) -> bool:
    try:
        return _configure(auto_confirm)
    except (OSError, subprocess.SubprocessError) as exc:
        log_warning(f"Desktop integration failed: {exc}")
        return False


def _configure(auto_confirm: bool = False) -> bool:
    if not prompt_yes_no("Repair Dolphin file associations and menus?", default=True, auto_confirm=auto_confirm):
        log_info("Skipping Dolphin MIME configuration")
        return True

    arch_menu = Path("/etc/xdg/menus/arch-applications.menu")
    target_menu = Path("/etc/xdg/menus/applications.menu")

    if arch_menu.exists():
        log_running("Linking arch-applications.menu → applications.menu...")
        logger.run_cmd(["sudo", "ln", "-sf", str(arch_menu), str(target_menu)])
    else:
        log_warning("arch-applications.menu not found; skipping menu link")

    # Clear old Sycoca cache
    for cache_f in Path.home().glob(".cache/ksycoca6_*"):
        try:
            cache_f.unlink()
        except Exception:
            pass

    if shutil.which("kbuildsycoca6"):
        log_running("Rebuilding KSycoca6 cache...")
        logger.run_cmd(["kbuildsycoca6", "--noincremental"])

    if shutil.which("update-mime-database"):
        log_running("Updating system MIME database...")
        logger.run_cmd(["sudo", "update-mime-database", "/usr/share/mime"])

    log_success("Dolphin associations and MIME database updated")
    return True

