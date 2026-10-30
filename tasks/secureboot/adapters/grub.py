"""
GRUB Bootloader Adapter for Secure Boot
Handles detection, signing, verification, and Secure Boot chain warnings for GRUB.
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


class GrubAdapter(BootloaderAdapter):
    @property
    def name(self) -> str:
        return "grub"

    @property
    def display_name(self) -> str:
        return "GRUB (Grand Unified Bootloader)"

    def detect(self, inventory: Dict[str, Any]) -> bool:
        bl_info = inventory.get("bootloader", {})
        if bl_info.get("name") == "grub":
            return True

        if Path("/boot/grub/grub.cfg").is_file():
            return True

        esp = get_primary_esp_path()
        if esp:
            for p in (esp / "EFI/arch/grubx64.efi", esp / "EFI/grub/grubx64.efi"):
                if p.is_file():
                    return True

        return False

    def get_signable_files(self) -> List[Path]:
        files: List[Path] = []
        esps = find_esp_mounts()
        for esp in esps:
            m = Path(esp["mountpoint"])
            for rel in ("EFI/arch/grubx64.efi", "EFI/grub/grubx64.efi", "EFI/BOOT/grubx64.efi"):
                target = m / rel
                if target.is_file():
                    files.append(target)
        return files

    def inspect(self) -> Dict[str, Any]:
        signable = self.get_signable_files()
        grub_cfg = Path("/boot/grub/grub.cfg")
        enforce_signatures = False
        if grub_cfg.is_file():
            try:
                content = grub_cfg.read_text(encoding="utf-8", errors="ignore")
                enforce_signatures = "check_signatures=enforce" in content
            except OSError:
                pass

        return {
            "name": self.name,
            "display_name": self.display_name,
            "signable_files": [str(f) for f in signable],
            "grub_cfg_exists": grub_cfg.is_file(),
            "enforces_signatures": enforce_signatures,
            "chain_notes": (
                "CRITICAL: Signing grubx64.efi verifies the GRUB binary itself, but GRUB "
                "does NOT automatically verify loaded kernels unless standalone PGP verification "
                "or Shim integration is configured. Unified Kernel Images (UKIs) or systemd-boot "
                "are recommended for complete hardware-to-kernel trust chains."
            ),
        }

    def prepare(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No GRUB EFI executables found to prepare."
        return True, "GRUB EFI binary identified. Note: GRUB kernel verification requires standalone configuration."

    def sign(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        if not files:
            return False, "No GRUB EFI executables found on ESP."

        if not shutil.which("sbctl"):
            return False, "sbctl is not installed."

        from core.logger import logger
        signed_count = 0
        for f in files:
            code, _ = logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(f)], check=False)
            if code == 0:
                signed_count += 1

        if signed_count > 0:
            return True, f"Signed and registered {signed_count} GRUB executable(s)."
        return False, "Failed to sign GRUB executables."

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
        return True, "GRUB registered with sbctl database for automatic re-signing."

    def remove_integration(self) -> Tuple[bool, str]:
        files = self.get_signable_files()
        from core.logger import logger
        for f in files:
            logger.run_cmd(["sudo", "sbctl", "remove-file", str(f)], check=False)
        return True, "GRUB signing registration removed."

