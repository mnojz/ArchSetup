"""
UEFI Firmware Inspection & efivarfs Interface
Reads UEFI firmware state, SecureBoot, SetupMode, and key databases directly from sysfs / efivarfs
with graceful fallbacks.
"""

import os
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.config import (
    EFI_GLOBAL_GUID,
    EFI_SYS_DIR,
    EFIVAR_PK,
    EFIVAR_SECURE_BOOT,
    EFIVAR_SETUP_MODE,
    EFIVARS_DIR,
)


def is_uefi_boot() -> bool:
    """Checks whether the system booted in UEFI mode."""
    return EFI_SYS_DIR.is_dir()


def is_efivars_mounted() -> bool:
    """Checks whether efivarfs is mounted and accessible."""
    if not EFIVARS_DIR.is_dir():
        return False
    try:
        # Check if directory can be listed
        next(EFIVARS_DIR.iterdir(), None)
        return True
    except (PermissionError, OSError):
        return False


def read_efivar_raw(var_name_with_guid: str) -> Optional[Tuple[int, bytes]]:
    """
    Reads a raw EFI variable from efivarfs.
    In Linux efivarfs, the first 4 bytes are UINT32 attributes, followed by variable data.
    Returns (attributes, data_bytes) or None if inaccessible.
    """
    var_path = EFIVARS_DIR / var_name_with_guid
    if not var_path.is_file():
        return None
    try:
        with open(var_path, "rb") as f:
            raw = f.read()
        if len(raw) < 4:
            return None
        attrs = struct.unpack("<I", raw[:4])[0]
        data = raw[4:]
        return attrs, data
    except (PermissionError, OSError):
        return None


def get_firmware_vendor() -> str:
    """Reads UEFI firmware vendor from sysfs if available."""
    vendor_file = EFI_SYS_DIR / "fw_vendor"
    if vendor_file.is_file():
        try:
            return vendor_file.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            pass
    # Fallback to DMI sysfs
    dmi_vendor = Path("/sys/class/dmi/id/bios_vendor")
    if dmi_vendor.is_file():
        try:
            return dmi_vendor.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            pass
    return "Unknown"


def get_firmware_version() -> str:
    """Reads UEFI BIOS version from DMI sysfs if available."""
    dmi_version = Path("/sys/class/dmi/id/bios_version")
    if dmi_version.is_file():
        try:
            return dmi_version.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            pass
    return "Unknown"


def is_secure_boot_enabled() -> bool:
    """
    Checks whether Secure Boot is currently active and enforcing signatures.
    Directly reads efivarfs SecureBoot variable (byte 4 == 1).
    Falls back to sbctl or bootctl if efivars unreadable.
    """
    res = read_efivar_raw(EFIVAR_SECURE_BOOT)
    if res is not None:
        _, data = res
        if len(data) >= 1:
            return data[0] == 1

    # Fallback: sbctl status --json
    if shutil.which("sbctl"):
        try:
            out = subprocess.check_output(
                ["sbctl", "status", "--json"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            import json
            parsed = json.loads(out)
            return bool(parsed.get("secure_boot", False))
        except Exception:
            pass

    # Fallback: bootctl status
    if shutil.which("bootctl"):
        try:
            out = subprocess.check_output(
                ["bootctl", "status"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            for line in out.splitlines():
                if "Secure Boot:" in line:
                    return "enabled" in line.lower()
        except Exception:
            pass

    return False


def is_setup_mode() -> bool:
    """
    Checks whether the firmware is currently in Setup Mode (ready to accept new PK).
    Directly reads efivarfs SetupMode variable (byte 4 == 1).
    Falls back to sbctl status --json.
    """
    res = read_efivar_raw(EFIVAR_SETUP_MODE)
    if res is not None:
        _, data = res
        if len(data) >= 1:
            return data[0] == 1

    # Fallback: sbctl status --json
    if shutil.which("sbctl"):
        try:
            out = subprocess.check_output(
                ["sbctl", "status", "--json"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            import json
            parsed = json.loads(out)
            return bool(parsed.get("setup_mode", False))
        except Exception:
            pass

    return False


def inspect_efivars_keys() -> Dict[str, Dict[str, Any]]:
    """
    Inspects key database variables in efivarfs: PK, KEK, db, dbx.
    Returns status and size for each database.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for db_name in ("PK", "KEK", "db", "dbx"):
        var_name = f"{db_name}-{EFI_GLOBAL_GUID}"
        res = read_efivar_raw(var_name)
        if res is not None:
            attrs, data = res
            results[db_name] = {
                "present": True,
                "size_bytes": len(data),
                "attributes": attrs,
                "enrolled": len(data) > 0,
            }
        else:
            results[db_name] = {
                "present": False,
                "size_bytes": 0,
                "attributes": 0,
                "enrolled": False,
            }
    return results


def inspect_firmware() -> Dict[str, Any]:
    """Comprehensive firmware state summary."""
    uefi = is_uefi_boot()
    efivars = is_efivars_mounted()
    sb_enabled = is_secure_boot_enabled() if efivars else False
    setup_mode = is_setup_mode() if efivars else False
    key_dbs = inspect_efivars_keys() if efivars else {}

    return {
        "is_uefi": uefi,
        "efivars_accessible": efivars,
        "secure_boot_enabled": sb_enabled,
        "setup_mode": setup_mode,
        "vendor": get_firmware_vendor(),
        "bios_version": get_firmware_version(),
        "key_databases": key_dbs,
    }

