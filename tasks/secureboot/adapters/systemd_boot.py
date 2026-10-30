"""
systemd-boot Adapter for Secure Boot
Handles detection, signing, verification, and update integration for systemd-boot.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.adapters.common import BootloaderAdapter
from tasks.secureboot.inventory import find_esp_mounts, get_primary_esp_path


class SystemdBootAdapter(BootloaderAdapter):
    @property
    def name(self) -> str:
        return "systemd-boot"

    @property
    def display_name(self) -> str:
        return "systemd-boot (Linux Boot Manager)"

    def detect(self, inventory: Dict[str, Any]) -> bool:
        bl_info = inventory.get("bootloader", {})
        if bl_info.get("name") == "systemd-boot":
            return True

        # Check ESP files directly
        esp = get_primary_esp_path()
        if esp:
            if (esp / "EFI/systemd/systemd-bootx64.efi").is_file():
                return True
            if (esp / "loader/loader.conf").is_file():
                return True

        if Path("/boot/loader/loader.conf").is_file():
            return True

        return False

    def get_signable_files(self) -> List[Path]:
        files: List[Path] = []
        esps = find_esp_mounts()
        for esp in esps:
            m = Path(esp["mountpoint"])
            sd_efi = m / "EFI/systemd/systemd-bootx64.efi"
            if sd_efi.is_file():
                files.append(sd_efi)

            # Check generic fallback bootx64.efi
            fallback_efi = m / "EFI/BOOT/BOOTX64.EFI"
            if fallback_efi.is_file():
                # Check if it has similar size to systemd-bootx64.efi or is identical
                if sd_efi.is_file() and abs(fallback_efi.stat().st_size - sd_efi.stat().st_size) < 4096:
                    files.append(fallback_efi)

        return files

    def inspect(self) -> Dict[str, Any]:
        signable = self.get_signable_files()
        primary_esp = get_primary_esp_path()
        loader_conf = primary_esp / "loader/loader.conf" if primary_esp else Path("/boot/loader/loader.conf")

        return {
            "name": self.name,
            "display_name": self.display_name,
            "signable_files": [str(f) for f in signable],
            "loader_conf_exists": loader_conf.is_file(),
            "loader_conf_path": str(loader_conf) if loader_conf.is_file() else None,
            "chain_notes": (
                "systemd-boot executes kernels directly or chainloads UKIs. "
                "Signing systemd-bootx64.efi only authenticates the bootloader; "
                "kernels and UKIs must be signed separately."
            ),
        }

    def prepare(self) -> Tuple[bool, str]:
        """Prepares systemd-boot for Secure Boot."""
        # Ensure systemd-boot directories exist on ESP
        esp = get_primary_esp_path()
        if not esp:
            return False, "EFI System Partition not found."
        return True, "systemd-boot verified and ready for signing."

    def sign(self) -> Tuple[bool, str]:
        """Signs systemd-boot EFI executables and registers them with sbctl."""
        files = self.get_signable_files()
        if not files:
            return False, "No systemd-boot EFI executables found to sign."

        if not shutil.which("sbctl"):
            return False, "sbctl is not installed."

        from core.logger import logger
        signed_count = 0
        for f in files:
            # Register and sign with sbctl (-s saves to database)
            code, _ = logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(f)], check=False)
            if code == 0:
                signed_count += 1

        if signed_count > 0:
            return True, f"Signed and registered {signed_count} systemd-boot executable(s)."
        return False, "Failed to sign systemd-boot executables with sbctl."

    def verify(self) -> Dict[str, Any]:
        """Verifies signatures of systemd-boot files."""
        files = self.get_signable_files()
        results: Dict[str, bool] = {}

        if not shutil.which("sbctl"):
            return {"all_signed": False, "files": {str(f): False for f in files}}

        for f in files:
            try:
                # sbctl verify <file>
                code = subprocess.run(
                    ["sbctl", "verify", str(f)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                ).returncode
                results[str(f)] = (code == 0)
            except Exception:
                results[str(f)] = False

        all_ok = len(results) > 0 and all(results.values())
        return {
            "all_signed": all_ok,
            "files": results,
        }

    def configure_updates(self) -> Tuple[bool, str]:
        """
        Configures update automation for systemd-boot.
        With sbctl registered files (-s), sbctl sign-all hook automatically re-signs them.
        Additionally, signs /usr/lib/systemd/boot/efi/systemd-bootx64.efi if present so
        systemd's internal update mechanism deploys signed binaries.
        """
        sys_sd_efi = Path("/usr/lib/systemd/boot/efi/systemd-bootx64.efi")
        if sys_sd_efi.is_file() and shutil.which("sbctl"):
            from core.logger import logger
            logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(sys_sd_efi)], check=False)
            # Create the .efi.signed file that bootctl update looks for
            signed_dest = sys_sd_efi.with_suffix(".efi.signed")
            logger.run_cmd(["sudo", "cp", str(sys_sd_efi), str(signed_dest)], check=False)

        return True, "systemd-boot update integration configured."

    def remove_integration(self) -> Tuple[bool, str]:
        """Removes registered systemd-boot files from sbctl database."""
        files = self.get_signable_files()
        from core.logger import logger
        for f in files:
            logger.run_cmd(["sudo", "sbctl", "remove-file", str(f)], check=False)
        return True, "systemd-boot signing registration removed."

