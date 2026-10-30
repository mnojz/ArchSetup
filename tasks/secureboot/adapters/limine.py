"""
Limine Bootloader Adapter for Secure Boot
Handles detection, signing, and verification for Limine.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.adapters.common import BootloaderAdapter
from tasks.secureboot.inventory import find_esp_mounts, get_primary_esp_path
from tasks.secureboot.utils import (
    dir_exists_privileged,
    file_exists_privileged,
    run_privileged,
)


class LimineAdapter(BootloaderAdapter):
    @property
    def name(self) -> str:
        return "limine"

    @property
    def display_name(self) -> str:
        return "Limine Bootloader"

    def detect(self, inventory: Dict[str, Any]) -> bool:
        bl_info = inventory.get("bootloader", {})
        if bl_info.get("name") == "limine":
            return True

        if Path("/boot/limine.cfg").is_file():
            return True

        esp = get_primary_esp_path()
        if esp:
            if (esp / "limine.cfg").is_file() or (esp / "EFI/limine/BOOTX64.EFI").is_file():
                return True

        return False

    def get_signable_files(self) -> List[Path]:
        files: List[Path] = []
        esps = find_esp_mounts()
        for esp in esps:
            m = Path(esp["mountpoint"])
            for rel in ("EFI/limine/BOOTX64.EFI", "EFI/BOOT/BOOTX64.EFI"):
                cand = m / rel
                if cand.is_file():
                    files.append(cand)
        return files

    def inspect(self) -> Dict[str, Any]:
        signable = self.get_signable_files()
        cfg_found = Path("/boot/limine.cfg").is_file()
        return {
            "name": self.name,
            "display_name": self.display_name,
            "signable_files": [str(f) for f in signable],
            "limine_cfg_exists": cfg_found,
            "chain_notes": (
                "Limine EFI binary must be signed. Limine protocol directly loads the kernel; "
                "ensure kernel and modules are verified."
            ),
        }

    def prepare(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No Limine EFI executables found on ESP."
        return True, "Limine binary identified and ready for signing."

    def sign(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No Limine EFI executables found."

        if not shutil.which("sbctl"):
            return False, "sbctl is not installed."

        from core.logger import logger
        signed_count = 0
        for f in files:
            code, _ = logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(f)], check=False)
            if code == 0:
                signed_count += 1

        if signed_count > 0:
            return True, f"Signed and registered {signed_count} Limine executable(s)."
        return False, "Failed to sign Limine executables."

    def verify(self) -> Dict[str, Any]:
        files = self.get_signable_files()
        results: Dict[str, bool] = {}

        if not shutil.which("sbctl"):
            return {"all_signed": False, "files": {}}

        for f in files:
            try:
                code, _, _ = run_privileged(["sbctl", "verify", str(f)])
                results[str(f)] = (code == 0)
            except Exception:
                results[str(f)] = False

        all_ok = len(results) > 0 and all(results.values())
        return {
            "all_signed": all_ok,
            "files": results,
        }

    def configure_updates(self) -> Tuple[bool, str]:
        return True, "Limine registered with sbctl database for automatic re-signing."

    def remove_integration(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        from core.logger import logger
        for f in files:
            logger.run_cmd(["sudo", "sbctl", "remove-file", str(f)], check=False)
        return True, "Limine signing registration removed."

