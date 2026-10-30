"""
Guided Recovery Center
Diagnoses Secure Boot failure scenarios and provides actionable, step-by-step recovery guidance.
SAFETY: Never automatically clears firmware keys or alters BIOS variables destructively.
"""

from typing import Any, Dict, List, Tuple

from tasks.secureboot.adapters import get_active_adapter
from tasks.secureboot.firmware import (
    is_efivars_mounted,
    is_secure_boot_enabled,
    is_setup_mode,
    is_uefi_boot,
)
from tasks.secureboot.inventory import detect_windows, find_esp_mounts
from tasks.secureboot.keys import do_keys_exist, inspect_key_inventory
from tasks.secureboot.signing import verify_all_system_files
from tasks.secureboot.updates import inspect_update_hooks


def diagnose_system() -> List[Dict[str, Any]]:
    """
    Analyzes current failure modes and returns a prioritized list of issues
    with root cause explanations and recovery actions.
    """
    issues: List[Dict[str, Any]] = []

    # Issue: Legacy Boot
    if not is_uefi_boot():
        issues.append({
            "title": "Legacy BIOS / CSM Mode Detected",
            "severity": "CRITICAL",
            "description": "Your system was booted using Legacy BIOS (CSM) rather than native UEFI.",
            "recovery_steps": [
                "Reboot your computer and enter BIOS/UEFI firmware settings.",
                "Disable 'CSM' (Compatibility Support Module) or 'Legacy Boot'.",
                "Set boot mode to 'UEFI Only'.",
                "Ensure your disk partition table is GPT (GUID Partition Table).",
                "Reboot into Arch Linux in UEFI mode.",
            ],
            "automatic_fix": False,
        })

    # Issue: Inaccessible efivars
    elif not is_efivars_mounted():
        issues.append({
            "title": "EFI Variables (efivarfs) Inaccessible",
            "severity": "CRITICAL",
            "description": "The Linux efivarfs filesystem is not mounted. Firmware variables cannot be read or written.",
            "recovery_steps": [
                "Run: sudo mount -t efivarfs efivarfs /sys/firmware/efi/efivars",
                "Verify with: ls /sys/firmware/efi/efivars",
            ],
            "automatic_fix": True,
            "fix_action": "mount_efivars",
        })

    # Issue: No ESP mounted
    esps = find_esp_mounts()
    if not esps:
        issues.append({
            "title": "No EFI System Partition (ESP) Mounted",
            "severity": "CRITICAL",
            "description": "Neither /boot nor /efi is mounted as a FAT32 EFI System Partition.",
            "recovery_steps": [
                "Identify your ESP partition (type EFI System Partition, FAT32) using: lsblk -f",
                "Mount it to /boot or /efi: sudo mount /dev/sdX1 /boot",
                "Add the mount entry to /etc/fstab for persistence.",
            ],
            "automatic_fix": False,
        })

    # Issue: Keys missing
    if not do_keys_exist():
        issues.append({
            "title": "Secure Boot Signing Keys Missing",
            "severity": "HIGH",
            "description": "No custom Secure Boot key-pairs (PK, KEK, db) have been generated on this machine.",
            "recovery_steps": [
                "Run 'Initial Secure Boot Setup' or 'Key Management -> Generate Keys' in ArchSetup.",
                "Or manually run: sudo sbctl create-keys",
            ],
            "automatic_fix": True,
            "fix_action": "generate_keys",
        })

    # Issue: Unsigned or invalid boot files
    ver = verify_all_system_files()
    if not ver.get("all_verified", False):
        failed_files = [f for f, ok in ver.get("results", {}).items() if not ok]
        issues.append({
            "title": "Unsigned or Invalid EFI Executables",
            "severity": "HIGH",
            "description": f"The following boot binaries lack valid signatures: {', '.join(failed_files)}",
            "recovery_steps": [
                "Sign all boot binaries with ArchSetup's 'Kernel & EFI Signing -> Sign All'.",
                "Or manually run: sudo sbctl sign -s <path_to_file>",
                "Then verify with: sudo sbctl verify",
            ],
            "automatic_fix": True,
            "fix_action": "sign_all",
        })

    # Issue: Not in Setup Mode when keys need enrollment
    if do_keys_exist() and not is_secure_boot_enabled() and not is_setup_mode():
        issues.append({
            "title": "Firmware in User Mode (Setup Mode Required for Enrollment)",
            "severity": "MEDIUM",
            "description": "The firmware has existing vendor keys locked in NVRAM. Custom keys cannot be enrolled.",
            "recovery_steps": [
                "Reboot into your BIOS/UEFI setup utility (F2, F12, Del, or Esc).",
                "Navigate to Security -> Secure Boot.",
                "Select 'Clear Secure Boot Keys', 'Erase PK', or 'Enter Setup Mode'.",
                "Save changes, exit BIOS, and boot back into Arch Linux.",
                "Re-run ArchSetup -> Secure Boot Management -> Initial Setup.",
            ],
            "automatic_fix": False,
        })

    # Issue: Missing update hook
    hk = inspect_update_hooks()
    if not hk.get("is_configured", False):
        issues.append({
            "title": "Automatic Re-Signing Pacman Hook Missing",
            "severity": "MEDIUM",
            "description": "Subsequent kernel or systemd updates may break Secure Boot because binaries will not be automatically re-signed.",
            "recovery_steps": [
                "In ArchSetup, select 'Update Automation -> Install Pacman Hook'.",
                "Or manually install /etc/pacman.d/hooks/99-sbctl-resign.hook",
            ],
            "automatic_fix": True,
            "fix_action": "install_hook",
        })

    # Issue: Windows detected without MS certs warning
    win = detect_windows()
    if win.get("detected", False) and not is_secure_boot_enabled():
        issues.append({
            "title": "Windows Dual-Boot Detected: BitLocker & MS Certificate Advisory",
            "severity": "WARNING",
            "description": (
                "A Windows installation exists on this machine. When enrolling keys, "
                "Microsoft certificates must be included, and BitLocker may require recovery key."
            ),
            "recovery_steps": [
                "Boot into Windows and back up your BitLocker recovery key from aka.ms/myrecoverykey",
                "Alternatively, suspend BitLocker protection in Windows Control Panel before enrolling keys.",
                "When enrolling keys in ArchSetup, choose 'Include Microsoft Certificates' (default: Yes).",
            ],
            "automatic_fix": False,
        })

    # Issue: Immutable efivarfs attributes
    from tasks.secureboot.enrollment import get_immutable_efivars
    locked_vars = get_immutable_efivars()
    if locked_vars and is_setup_mode():
        issues.append({
            "title": f"Firmware Variables Locked ({len(locked_vars)} efivars immutable)",
            "severity": "MEDIUM",
            "description": (
                "The Linux kernel has marked efivarfs security variables (PK, KEK, db) as immutable (+i). "
                "This blocks key enrollment until the immutable flags are cleared."
            ),
            "recovery_steps": [
                "Run automatic fix in ArchSetup, or execute:",
                "sudo chattr -i /sys/firmware/efi/efivars/{PK,KEK,db,dbx}*",
            ],
            "automatic_fix": True,
            "fix_action": "unlock_efivars",
        })

    return issues


def apply_recovery_fix(fix_action: str) -> Tuple[bool, str]:
    """Applies an automated recovery fix for a recognized actionable issue."""
    if fix_action == "unlock_efivars":
        from tasks.secureboot.enrollment import unlock_efivar_immutability
        ok, targets = unlock_efivar_immutability()
        if ok:
            return True, f"Successfully cleared immutable flags on {len(targets)} efivars."
        return False, "Failed to clear immutable flags. Ensure sudo privileges are available."

    elif fix_action == "mount_efivars":
        from core.logger import logger
        code, _ = logger.run_cmd(["sudo", "mount", "-t", "efivarfs", "efivarfs", "/sys/firmware/efi/efivars"], check=False)
        return code == 0, "Mounted efivarfs successfully." if code == 0 else "Failed to mount efivarfs."

    elif fix_action == "generate_keys":
        from tasks.secureboot.keys import create_keys
        return create_keys()

    elif fix_action == "sign_all":
        from tasks.secureboot.adapters import get_active_adapter
        from tasks.secureboot.kernel import sign_all_kernels
        ad = get_active_adapter()
        ad_ok, ad_msg = (ad.sign() if ad else (True, "No bootloader adapter required"))
        k_ok, k_signed, k_failed = sign_all_kernels()
        k_msg = f"Signed {len(k_signed)} kernel(s)" if k_ok else f"Failed to sign: {', '.join(k_failed)}"
        return (ad_ok and k_ok), f"Bootloader: {ad_msg}\nKernels: {k_msg}"

    elif fix_action == "install_hook":
        from tasks.secureboot.updates import install_update_hooks
        return install_update_hooks()

    return False, f"Unknown fix action: {fix_action}"

