"""
rEFInd Bootloader Adapter for Secure Boot
Handles detection, signing, and verification for rEFInd.
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


class RefindAdapter(BootloaderAdapter):
    @property
    def name(self) -> str:
        return "refind"

    @property
    def display_name(self) -> str:
        return "rEFInd Boot Manager"

    def detect(self, inventory: Dict[str, Any]) -> bool:
        bl_info = inventory.get("bootloader", {})
        if bl_info.get("name") == "refind":
            return True

        if Path("/boot/refind_linux.conf").is_file():
            return True

        esp = get_primary_esp_path()
        if esp and (esp / "EFI/refind/refind_x64.efi").is_file():
            return True

        return False

    def get_signable_files(self) -> List[Path]:
        files: List[Path] = []
        esps = find_esp_mounts()
        for esp in esps:
            m = Path(esp["mountpoint"])
            refind_efi = m / "EFI/refind/refind_x64.efi"
            if refind_efi.is_file():
                files.append(refind_efi)

            # Also sign filesystem drivers if present
            drivers_dir = m / "EFI/refind/drivers_x64"
            if drivers_dir.is_dir():
                for drv in drivers_dir.glob("*.efi"):
                    files.append(drv)
        return files

    def inspect(self) -> Dict[str, Any]:
        signable = self.get_signable_files()
        refind_conf = Path("/boot/refind_linux.conf")
        return {
            "name": self.name,
            "display_name": self.display_name,
            "signable_files": [str(f) for f in signable],
            "refind_conf_exists": refind_conf.is_file(),
            "chain_notes": (
                "rEFInd requires both the main binary (refind_x64.efi) and any loaded drivers "
                "to be signed with enrolled keys. rEFInd can use Shim/MOK or direct signature checking."
            ),
        }

    def prepare(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No rEFInd EFI executables found on ESP."
        return True, "rEFInd executables identified and ready for signing."

    def sign(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No rEFInd EFI executables found."

        if not shutil.which("sbctl"):
            return False, "sbctl is not installed."

        from core.logger import logger
        signed_count = 0
        for f in files:
            code, _ = logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(f)], check=False)
            if code == 0:
                signed_count += 1

        if signed_count > 0:
            return True, f"Signed and registered {signed_count} rEFInd executable(s)."
        return False, "Failed to sign rEFInd executables."

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
        return True, "rEFInd registered with sbctl for automatic re-signing."

    def remove_integration(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        from core.logger import logger
        for f in files:
            logger.run_cmd(["sudo", "sbctl", "remove-file", str(f)], check=False)
        return True, "rEFInd signing registration removed."

