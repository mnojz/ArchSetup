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

