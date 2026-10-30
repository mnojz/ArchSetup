"""
Secure Boot Module Configuration & Constants
Defines paths, database names, exit codes, status levels, and operation types.
"""

import os
from pathlib import Path

MODULE_VERSION = "1.0.0"
MODULE_NAME = "secureboot"

# ---------------------------------------------------------------------------
# Persistent state directories
# ---------------------------------------------------------------------------
def _init_state_dir() -> Path:
    preferred = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "archsetup"
        / "secureboot"
    )
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except (OSError, PermissionError):
        fallback = Path("/tmp/archsetup/secureboot")
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return fallback

STATE_DIR = _init_state_dir()
JOURNAL_DIR = STATE_DIR / "journal"
BACKUP_DIR = STATE_DIR / "backups"
REPORT_DIR = STATE_DIR / "reports"

# ---------------------------------------------------------------------------
# UEFI firmware sysfs / efivarfs paths
# ---------------------------------------------------------------------------
EFI_SYS_DIR = Path("/sys/firmware/efi")
EFIVARS_DIR = EFI_SYS_DIR / "efivars"

# EFI global variable GUID (UEFI spec §3.3)
EFI_GLOBAL_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"

# Well-known EFI variable names (appended with -{GUID} in efivarfs)
EFIVAR_SECURE_BOOT = f"SecureBoot-{EFI_GLOBAL_GUID}"
EFIVAR_SETUP_MODE = f"SetupMode-{EFI_GLOBAL_GUID}"
EFIVAR_PK = f"PK-{EFI_GLOBAL_GUID}"

# ---------------------------------------------------------------------------
# sbctl paths (discovers /var/lib/sbctl or legacy /usr/share/secureboot)
# ---------------------------------------------------------------------------
def _resolve_sbctl_dir() -> Path:
    for cand in (Path("/var/lib/sbctl"), Path("/usr/share/secureboot")):
        if cand.is_dir():
            return cand
    return Path("/var/lib/sbctl")

SBCTL_DB_DIR = _resolve_sbctl_dir()
SBCTL_KEYS_DIR = SBCTL_DB_DIR / "keys"
SBCTL_GUID_FILE = SBCTL_DB_DIR / "GUID"
SBCTL_BUNDLES_DB = SBCTL_DB_DIR / "bundles.db"
SBCTL_FILES_DB = SBCTL_DB_DIR / "files.json"

# ---------------------------------------------------------------------------
# Secure Boot key databases (UEFI spec §32)
# ---------------------------------------------------------------------------
SB_DATABASES = ("PK", "KEK", "db", "dbx")

# Key database descriptions for user display
SB_DB_DESCRIPTIONS = {
    "PK": "Platform Key – root of the Secure Boot trust chain",
    "KEK": "Key Exchange Key – authorizes db/dbx updates",
    "db": "Signature Database – trusted signing certificates",
    "dbx": "Forbidden Signatures Database – revoked hashes/certs",
}

# ---------------------------------------------------------------------------
# Microsoft Secure Boot certificate identifiers
# ---------------------------------------------------------------------------
MS_CERT_NAMES = {
    "ms_win_prod_2011": "Microsoft Windows Production PCA 2011",
    "ms_uefi_ca_2011": "Microsoft Corporation UEFI CA 2011",
    "ms_win_prod_2023": "Windows UEFI CA 2023",
    "ms_uefi_ca_2023": "Microsoft UEFI CA 2023",
}

# ---------------------------------------------------------------------------
# Windows detection paths (relative to ESP mount)
# ---------------------------------------------------------------------------
WINDOWS_BOOTMGR_REL = "EFI/Microsoft/Boot/bootmgfw.efi"
WINDOWS_BOOT_DIR_REL = "EFI/Microsoft/Boot"

# ---------------------------------------------------------------------------
# Supported bootloaders (ordered by adapter priority)
# ---------------------------------------------------------------------------
SUPPORTED_BOOTLOADERS = ("systemd-boot", "grub", "refind", "limine")

# ---------------------------------------------------------------------------
# Required and optional external tools
# ---------------------------------------------------------------------------
REQUIRED_TOOLS = ("sbctl",)
OPTIONAL_TOOLS = ("bootctl", "efibootmgr", "findmnt", "lsblk", "mokutil", "objdump")

# ---------------------------------------------------------------------------
# Exit / error codes
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_NOT_UEFI = 10
EXIT_NO_EFIVARS = 11
EXIT_NO_SBCTL = 12
EXIT_NO_ROOT = 13
EXIT_NOT_ARCH = 14
EXIT_PREFLIGHT_FAIL = 15
EXIT_NO_ESP = 16

# ---------------------------------------------------------------------------
# Health-check status levels
# ---------------------------------------------------------------------------
STATUS_HEALTHY = "HEALTHY"
STATUS_CONFIGURED = "CONFIGURED"
STATUS_WARNING = "WARNING"
STATUS_FAILED = "FAILED"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_MANUAL = "MANUAL_INTERVENTION"
STATUS_NOT_APPLICABLE = "N/A"

# ---------------------------------------------------------------------------
# Operation types (for the operation journal)
# ---------------------------------------------------------------------------
OP_KEY_GENERATE = "key_generate"
OP_KEY_ENROLL = "key_enroll"
OP_SIGN_FILE = "sign_file"
OP_SIGN_REMOVE = "sign_remove"
OP_HOOK_INSTALL = "hook_install"
OP_HOOK_REMOVE = "hook_remove"
OP_BACKUP_CREATE = "backup_create"
OP_BACKUP_RESTORE = "backup_restore"
OP_MS_CERT_ENROLL = "ms_cert_enroll"
OP_ENROLLMENT = "firmware_enrollment"

# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------
MODE_DRY_RUN = "dry_run"
MODE_INTERACTIVE = "interactive"
MODE_AUTO = "auto"

# ---------------------------------------------------------------------------
# Pacman hook paths
# ---------------------------------------------------------------------------
PACMAN_HOOK_DIR = Path("/etc/pacman.d/hooks")
SBCTL_PACMAN_HOOK = PACMAN_HOOK_DIR / "99-sbctl-resign.hook"

# ---------------------------------------------------------------------------
# Kernel patterns (Arch Linux)
# ---------------------------------------------------------------------------
ARCH_KERNEL_NAMES = ("linux", "linux-lts", "linux-zen", "linux-hardened")
UKI_SEARCH_DIRS = ("EFI/Linux",)

