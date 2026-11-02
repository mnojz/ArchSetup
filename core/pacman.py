"""
ArchSetup Package Manager Interface
High-speed in-memory package state tracking and smart Pacman / AUR routing.
"""

import shutil
import subprocess
from typing import Set, List, Optional
from core.logger import logger

class PackageManager:
    def __init__(self):
        self._installed_cache: Set[str] = set()
        self.success_packages: List[str] = []
        self.skipped_packages: List[str] = []
        self.failed_packages: List[str] = []
        self._upgrade_ready = False
        self._refresh_installed_cache()

    def _refresh_installed_cache(self):
        """Loads all currently installed packages into an in-memory set in ~0.05s."""
        try:
            res = subprocess.run(
                ["pacman", "-Qq"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                self._installed_cache = set(res.stdout.strip().splitlines())
        except Exception:
            self._installed_cache = set()

    def reset_operation(self):
        """Start a new menu operation with fresh results and package state."""
        self.success_packages.clear()
        self.skipped_packages.clear()
        self.failed_packages.clear()
        self._upgrade_ready = False
        self._refresh_installed_cache()

    def invalidate_transaction(self):
        """Require another full upgrade after repository settings change."""
        self._upgrade_ready = False

    def prepare_transaction(self) -> bool:
        """Complete a full upgrade before any selective package installation."""
        if self._upgrade_ready:
            return True
        from core.tui import log_running
        log_running("Completing a full system upgrade before installing packages...")
        code, _ = logger.run_cmd(
            ["sudo", "pacman", "-Syu", "--noconfirm"], check=False
        )
        self._refresh_installed_cache()
        self._upgrade_ready = code == 0
        return self._upgrade_ready

    def is_installed(self, pkg: str) -> bool:
        return pkg in self._installed_cache

    def in_official_repo(self, pkg: str) -> bool:
        """Checks if package exists in official synced repositories."""
        res = subprocess.run(
            ["pacman", "-Si", pkg],
            capture_output=True,
            check=False
        )
        return res.returncode == 0

    def get_aur_helper(self) -> Optional[str]:
        if shutil.which("yay"):
            return "yay"
        elif shutil.which("paru"):
            return "paru"
        return None

    def install_package(self, pkg: str) -> bool:
        if self.is_installed(pkg):
            self.skipped_packages.append(pkg)
            return True

        if not self.prepare_transaction():
            logger.log("PKG_FAIL", f"System upgrade failed; refusing to install {pkg}")
            self.failed_packages.append(pkg)
            return False

        # Try official pacman first
        if self.in_official_repo(pkg):
            logger.log("PKG", f"Installing {pkg} via pacman")
            code, _ = logger.run_cmd(
                ["sudo", "pacman", "-S", "--needed", "--noconfirm", pkg],
                check=False
            )
            if code == 0:
                self._installed_cache.add(pkg)
                self.success_packages.append(pkg)
                return True

            # An official package install failure is not evidence of an AUR package.
            self.failed_packages.append(pkg)
            return False

        # Fall back to AUR helper
        aur_tool = self.get_aur_helper()
        if aur_tool:
            logger.log("PKG", f"Installing {pkg} via {aur_tool}")
            if aur_tool == "yay":
                cmd = ["yay", "-S", "--needed", "--noconfirm", "--answerclean", "None", "--answerdiff", "None", pkg]
            else:
                cmd = [aur_tool, "-S", "--needed", "--noconfirm", pkg]
            code, _ = logger.run_cmd(cmd, check=False)
            if code == 0:
                self._installed_cache.add(pkg)
                self.success_packages.append(pkg)
                return True

        logger.log("PKG_FAIL", f"Failed to install {pkg}")
        self.failed_packages.append(pkg)
        return False

# Global singleton
pm = PackageManager()

