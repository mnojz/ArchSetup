"""Deploy repository dotfiles with GNU Stow, replacing local conflicts."""

import shutil
import subprocess
from pathlib import Path

from rich.markup import escape

from core.tui import (
    log_info, log_success, log_error, log_running, prompt_yes_no,
    show_dotfiles_summary,
)
from core.logger import logger
from core.pacman import pm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTFILES_DIR = PROJECT_ROOT / "dotfiles"
TARGET_DIR = Path.home()


def _ensure_stow() -> bool:
    """Install through the shared package manager so failed upgrades stop here."""
    if shutil.which("stow"):
        return True
    log_running("Installing GNU Stow...")
    return pm.install_package("stow") and shutil.which("stow") is not None


def _clean_legacy_symlinks() -> int:
    """Remove broken links to previous dotfiles deployments."""
    config_dir = TARGET_DIR / ".config"
    if not config_dir.is_dir():
        return 0

    removed = 0
    for link in sorted(config_dir.glob("**/*")):
        if link.is_symlink() and "dotfiles" in str(link.readlink()) and not link.exists():
            link.unlink()
            logger.log("DOTFILES", f"Removed broken legacy link: {link}")
            removed += 1
    return removed


def _prepare_conflicts(source: Path, target: Path, replaced: list[Path]) -> None:
    """Clear conflicting files/links in parent-first order; keep correct links."""
    if target.is_symlink():
        if target.resolve() == source.resolve():
            return
        target.unlink()
        logger.log("DOTFILES", f"Removed conflicting link: {target}")
        replaced.append(target)

    if source.is_dir() and not source.is_symlink():
        if target.is_file():
            target.unlink()
            logger.log("DOTFILES", f"Removed file blocking directory: {target}")
            replaced.append(target)
        for child in sorted(source.iterdir()):
            _prepare_conflicts(child, target / child.name, replaced)
    elif target.is_file():
        target.unlink()
        logger.log("DOTFILES", f"Replaced local config: {target}")
        replaced.append(target)
    elif target.exists():
        raise OSError(f"A directory or special file blocks config file: {target}")


def run(auto_confirm: bool = False) -> bool:
    """Deploy all packages; repository configs take precedence without backups."""
    try:
        if not DOTFILES_DIR.is_dir():
            log_error(f"Dotfiles directory not found: {escape(str(DOTFILES_DIR))}")
            return False
        packages = sorted(
            p for p in DOTFILES_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name != "assets"
        )
        if not packages:
            log_error("No bundled dotfile packages found")
            return False
        if not prompt_yes_no(
            f"Deploy {len(packages)} bundled dotfile packages, replacing existing configs?",
            default=True, auto_confirm=auto_confirm,
        ):
            log_info("Skipping dotfiles deployment")
            return True
        if not _ensure_stow():
            log_error("GNU Stow is unavailable; dotfiles deployment stopped")
            return False
        removed_legacy = _clean_legacy_symlinks()
    except (OSError, subprocess.SubprocessError) as exc:
        log_error(f"Could not prepare dotfiles deployment: {escape(str(exc))}")
        return False

    log_info("Repository configs take priority; existing conflicting files and links are replaced")
    results = []
    replaced = []
    for index, pkg_dir in enumerate(packages, 1):
        log_running(f"({index}/{len(packages)}) Linking [cyan]{escape(pkg_dir.name)}[/]...")
        try:
            for source in sorted(pkg_dir.iterdir()):
                _prepare_conflicts(source, TARGET_DIR / source.name, replaced)
            # Real directories keep packages sharing .config independent of one
            # another, including when deploying into a completely empty home.
            code, _ = logger.run_cmd(
                ["stow", "--no-folding", "-d", str(DOTFILES_DIR), "-t", str(TARGET_DIR), pkg_dir.name],
                check=False,
            )
            if code != 0:
                raise subprocess.CalledProcessError(code, ["stow", pkg_dir.name])
        except (OSError, subprocess.SubprocessError) as exc:
            logger.log("DOTFILES_FAIL", f"{pkg_dir.name}: {exc}")
            log_error(f"Failed to deploy {escape(pkg_dir.name)}: {escape(str(exc))}")
            results.append((pkg_dir.name, "Failed"))
            results.extend((remaining.name, "Skipped") for remaining in packages[index:])
            show_dotfiles_summary(results, len(replaced), removed_legacy, logger.log_path_str)
            return False
        results.append((pkg_dir.name, "Linked"))

    show_dotfiles_summary(results, len(replaced), removed_legacy, logger.log_path_str)
    log_success(f"All {len(packages)} dotfile packages deployed successfully")
    return True
