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
            # If sbctl status reports installed, we trust sbctl key manager
            for db in ("PK", "KEK", "db"):
                db_data = inv.get(db, {})
                if not db_data.get("has_certificate") and not db_data.get("ready"):
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


def get_immutable_efivars() -> List[Path]:
    """
    Returns a list of security-related efivarfs files (PK, KEK, db, dbx) that have the
    +i (immutable) flag set.
    """
    efivars_dir = Path("/sys/firmware/efi/efivars")
    if not efivars_dir.is_dir():
        return []

    target_prefixes = ("PK-", "KEK-", "db-", "dbx-", "AuditMode-", "DeployedMode-")
    locked: List[Path] = []

    try:
        proc = subprocess.run(
            ["lsattr", str(efivars_dir)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    attrs, path_str = parts[0], parts[1]
                    if "i" in attrs:
                        p = Path(path_str)
                        if any(p.name.startswith(pfx) for pfx in target_prefixes):
                            locked.append(p)
            return locked
    except Exception:
        pass

    # Fallback: check candidate files directly
    for pfx in target_prefixes:
        for p in efivars_dir.glob(f"{pfx}*"):
            locked.append(p)

    return locked


def unlock_efivar_immutability() -> Tuple[bool, List[str]]:
    """
    Clears the immutable (+i) filesystem flag on efivarfs nodes (PK, KEK, db, dbx).
    The Linux kernel's efivarfs driver sets +i by default to protect firmware NVRAM.
    sbctl requires these to be unlocked before enrolling keys into NVRAM.
    Returns (success, list of target files).
    """
    efivars_dir = Path("/sys/firmware/efi/efivars")
    if not efivars_dir.is_dir():
        return True, []

    target_prefixes = ("PK-", "KEK-", "db-", "dbx-", "AuditMode-", "DeployedMode-")
    targets: List[str] = []
    try:
        for p in efivars_dir.iterdir():
            if any(p.name.startswith(pfx) for pfx in target_prefixes):
                targets.append(str(p))
    except Exception:
        import glob
        for pfx in target_prefixes:
            targets.extend(glob.glob(str(efivars_dir / f"{pfx}*")))

    if not targets:
        return True, []

    from core.logger import logger
    cmd = ["sudo", "chattr", "-i"] + targets
    code, _ = logger.run_cmd(cmd, check=False)
    return code == 0, targets


def _get_recent_log_errors(lines_count: int = 5) -> str:
    """Reads trailing output lines from the active log file to provide error context."""
    try:
        from core.logger import logger
        log_file = getattr(logger, "log_file", None)
        if log_file and Path(log_file).is_file():
            content = Path(log_file).read_text(encoding="utf-8", errors="ignore").splitlines()
            relevant = [line for line in content if not line.startswith("[CMD_EXIT]")][-lines_count:]
            return "\n".join(relevant)
    except Exception:
        pass
    return ""


def execute_enrollment(
    include_microsoft: bool = True,
    firmware_builtin: bool = False,
) -> Tuple[bool, str]:
    """
    Executes key enrollment into firmware using `sbctl enroll-keys`.
    SAFETY: Fails if preconditions are not met.
    Automatically unlocks efivarfs immutability and passes --ignore-immutable for seamless execution.
    """
    pre = EnrollmentPreconditionCheck()
    if not pre.run():
        return False, "Enrollment blocked: " + "; ".join(pre.blockers)

    if not shutil.which("sbctl"):
        return False, "sbctl is not installed."

    from core import auth
    from core.logger import logger

    if not auth.is_sudo_active():
        if not auth.request_sudo_auth("Firmware Key Enrollment"):
            return False, "Sudo authorization cancelled or required for firmware key enrollment."

    # 1. Proactively clear immutable attributes on efivars
    unlock_efivar_immutability()

    # 2. Check if sbctl supports --ignore-immutable
    has_ignore_immutable = False
    try:
        help_out = subprocess.run(
            ["sbctl", "enroll-keys", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout
        if "--ignore-immutable" in help_out or "-i," in help_out:
            has_ignore_immutable = True
    except Exception:
        pass

    cmd = ["sudo", "sbctl", "enroll-keys"]
    if has_ignore_immutable:
        cmd.append("--ignore-immutable")
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

    # If it failed, extract recent log details to diagnose
    last_err = _get_recent_log_errors()
    if "immutable" in last_err.lower() and not has_ignore_immutable:
        # Retry with forced chattr -i
        unlock_efivar_immutability()
        retry_cmd = ["sudo", "sbctl", "enroll-keys", "--ignore-immutable"]
        if include_microsoft:
            retry_cmd.append("--microsoft")
        if firmware_builtin:
            retry_cmd.append("--firmware-builtin")
        retry_code, _ = logger.run_cmd(retry_cmd, check=False)
        if retry_code == 0:
            return True, (
                "Keys enrolled successfully into firmware!\n\n"
                "CRITICAL NEXT STEP:\n"
                "1. Reboot and enter UEFI/BIOS settings.\n"
                "2. Set Secure Boot to [Enabled].\n"
                "3. Boot Arch Linux and run Health Check."
            )
        last_err = _get_recent_log_errors()

    err_summary = f"sbctl enroll-keys exited with code {code}."
    if last_err:
        err_summary += f"\n\nDetails from log:\n{last_err}"
    return False, err_summary

