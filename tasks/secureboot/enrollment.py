"""
Firmware Key Enrollment Interface
Orchestrates firmware key enrollment through sbctl with rigorous pre-conditions,
explicit user confirmations, Windows / BitLocker safety checks, and Microsoft certificate inclusion.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.backup import has_existing_backup
from tasks.secureboot.firmware import (
    inspect_firmware,
    is_efivars_mounted,
    is_setup_mode,
    is_uefi_boot,
)
from tasks.secureboot.inventory import detect_windows
from tasks.secureboot.keys import do_keys_exist, inspect_key_inventory
from tasks.secureboot.signing import verify_all_system_files


class EnrollmentPreconditionCheck:
    """Pre-flight validation specifically for firmware key enrollment."""

    def __init__(self) -> None:
        self.passed: bool = False
        self.blockers: List[str] = []
        self.warnings: List[str] = []
        self.details: Dict[str, Any] = {}

    def run(self) -> bool:
        self.blockers.clear()
        self.warnings.clear()

        # 1. UEFI mode
        if not is_uefi_boot():
            self.blockers.append("System did not boot in UEFI mode.")

        # 2. efivarfs accessible
        if not is_efivars_mounted():
            self.blockers.append("efivarfs is not mounted or accessible.")

        # 3. Setup Mode check
        if not is_setup_mode():
            self.blockers.append(
                "Firmware is NOT in Setup Mode. Firmware keys cannot be enrolled "
                "until existing platform keys are cleared or set to Setup Mode in your BIOS/UEFI settings."
            )

        # 4. Key existence check
        if not do_keys_exist():
            self.blockers.append("No custom Secure Boot keys found on disk. Generate keys first.")
        else:
            inv = inspect_key_inventory()
            for db in ("PK", "KEK", "db"):
                if not inv.get(db, {}).get("ready", False):
                    self.blockers.append(f"Incomplete key pair for {db} database.")

        # 5. Boot files signed and verified
        verify_status = verify_all_system_files()
        if not verify_status.get("all_verified", False):
            failed = [f for f, ok in verify_status.get("results", {}).items() if not ok]
            self.blockers.append(
                f"Unsigned or unverified boot executables detected: {', '.join(failed)}. "
                "All bootloader and kernel binaries MUST be signed and verified before enrollment."
            )

        # 6. Windows / BitLocker warning
        win_info = detect_windows()
        if win_info.get("detected", False):
            self.warnings.append(
                "Windows installation detected: Microsoft certificates MUST be enrolled (--microsoft) "
                "to preserve Windows dual-boot capability."
            )
            self.warnings.append(
                "BITLOCKER WARNING: Enrolling custom Secure Boot keys will change TPM PCR 7 measurements. "
                "Ensure you have your 48-digit BitLocker recovery key safely backed up, or suspend "
                "BitLocker protection from Windows before enrolling."
            )

        # 7. Backup check
        if not has_existing_backup():
            self.warnings.append("No existing backup of keys and EFI configuration found. Highly recommended before enrolling.")

        self.passed = len(self.blockers) == 0
        return self.passed


def execute_enrollment(
    include_microsoft: bool = True,
    firmware_builtin: bool = False,
) -> Tuple[bool, str]:
    """
    Executes key enrollment into firmware using `sbctl enroll-keys`.
    SAFETY: Fails if preconditions are not met.
    """
    pre = EnrollmentPreconditionCheck()
    if not pre.run():
        return False, "Enrollment blocked: " + "; ".join(pre.blockers)

    if not shutil.which("sbctl"):
        return False, "sbctl is not installed."

    from core.logger import logger

    cmd = ["sudo", "sbctl", "enroll-keys"]
    if include_microsoft:
        cmd.append("--microsoft")
    if firmware_builtin:
        cmd.append("--firmware-builtin")

    code, _ = logger.run_cmd(cmd, check=False)
    if code == 0:
        return True, (
            "Keys enrolled successfully into firmware!\n\n"
            "CRITICAL NEXT STEP:\n"
            "Key enrollment puts your keys into firmware NVRAM, but Secure Boot must now be "
            "ENABLED in your BIOS/UEFI setup.\n"
            "1. Reboot your computer.\n"
            "2. Enter UEFI/BIOS settings.\n"
            "3. Navigate to Security / Secure Boot and set Secure Boot to [Enabled].\n"
            "4. Save settings and boot into Arch Linux.\n"
            "5. Run ArchSetup's Secure Boot Health Check to confirm active enforcement."
        )

    return False, f"sbctl enroll-keys exited with code {code}. Check install log for details."

