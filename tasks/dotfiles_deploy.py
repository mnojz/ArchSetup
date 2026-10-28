"""
Task: Dotfiles Deployment
Links bundled user dotfiles to $HOME via GNU Stow.
Remote/repo configs take precedence over existing local configurations.
"""

import shutil
from datetime import datetime
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_error, log_running, prompt_yes_no
from core.logger import logger
from core.pacman import pm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTFILES_DIR = PROJECT_ROOT / "dotfiles"
TARGET_DIR = Path.home()

def _ensure_stow() -> bool:
    """Verifies GNU stow is installed, attempting package installation if missing."""
    if shutil.which("stow"):
        return True

    log_running("Installing GNU stow...")
    if pm.install_package("stow"):
        return True

    code, _ = logger.run_cmd(["sudo", "pacman", "-S", "--needed", "--noconfirm", "stow"], check=False)
    return code == 0 and shutil.which("stow") is not None

def _clean_legacy_symlinks():
    """Removes broken or outdated symlinks in ~/.config pointing to old dotfile locations."""
    config_dir = TARGET_DIR / ".config"
    if not config_dir.is_dir():
        return

    for link in config_dir.glob("**/*"):
        if link.is_symlink():
            try:
                target_str = str(link.readlink())
                # If pointing to an old dotfiles folder outside ArchSetup or broken
                if "dotfiles" in target_str and not link.resolve().exists():
                    link.unlink(missing_ok=True)
            except Exception:
                pass

def run(auto_confirm: bool = False) -> bool:
    """Deploys all bundled dotfile packages to $HOME using GNU Stow."""
    if not prompt_yes_no("Deploy bundled dotfiles (Hyprland, Waybar, Kitty, Fish, etc.)?", default=True, auto_confirm=auto_confirm):
        log_info("Skipping dotfiles deployment")
        return True

    if not DOTFILES_DIR.is_dir():
        log_error(f"Dotfiles directory not found at {DOTFILES_DIR}")
        return False

    if not _ensure_stow():
        log_error("GNU stow could not be installed. Aborting dotfiles deployment.")
        return False

    _clean_legacy_symlinks()

    backup_base = TARGET_DIR / f".config/dotfiles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backed_up_count = 0

    log_running("Resolving file conflicts and preparing targets...")
    packages = [p for p in DOTFILES_DIR.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "assets"]

    for pkg_dir in packages:
        # Pre-resolve any conflicts for each file in the package
        for src_item in pkg_dir.glob("**/*"):
            rel_path = src_item.relative_to(pkg_dir)
            target_path = TARGET_DIR / rel_path

            if src_item.is_file() or src_item.is_symlink():
                if target_path.is_symlink():
                    try:
                        # If already pointing to the exact source item, no conflict
                        if target_path.resolve() == src_item.resolve():
                            continue
                    except Exception:
                        pass
                    # Stale or foreign symlink: remove
                    target_path.unlink(missing_ok=True)
                elif target_path.is_file():
                    # Preserve existing non-symlinked local file in backup dir
                    backup_target = backup_base / rel_path
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, backup_target)
                    backed_up_count += 1
                    target_path.unlink()
            elif src_item.is_dir():
                if target_path.is_symlink():
                    target_path.unlink(missing_ok=True)

        log_running(f"Stowing [cyan]{pkg_dir.name}[/]...")
        code, _ = logger.run_cmd(["stow", "-d", str(DOTFILES_DIR), "-t", str(TARGET_DIR), pkg_dir.name], check=False)
        if code != 0:
            log_warning(f"GNU stow reported warnings while linking {pkg_dir.name}")

    if backed_up_count > 0:
        log_info(f"Preserved {backed_up_count} pre-existing local file(s) in [white]{backup_base.name}[/]")

    log_success("All bundled dotfiles deployed and symlinked successfully")
    return True
