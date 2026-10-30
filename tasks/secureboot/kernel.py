"""
Kernel & UKI Detection & Signing Integration
Distinguishes traditional kernels vs Unified Kernel Images (UKIs), validates PE structures,
and registers signable kernel binaries with sbctl.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.config import ARCH_KERNEL_NAMES
from tasks.secureboot.inventory import (
    detect_installed_kernels,
    detect_unified_kernel_images,
    find_esp_mounts,
    get_primary_esp_path,
)


def inspect_kernel_configuration() -> Dict[str, Any]:
    """
    Analyzes kernel and boot setup to determine whether the machine boots via
    traditional separate kernel+initramfs or Unified Kernel Images (UKIs).
    """
    kernels = detect_installed_kernels()
    ukis = detect_unified_kernel_images()
    primary_esp = get_primary_esp_path()

    # Check bootloader entries to see what's actually configured to boot
    boots_via_uki = False
    active_kernel_files: List[str] = []

    # Check systemd-boot entries
    if primary_esp:
        entries_dir = primary_esp / "loader/entries"
        if entries_dir.is_dir():
            for conf in entries_dir.glob("*.conf"):
                try:
                    content = conf.read_text(encoding="utf-8", errors="ignore")
                    for line in content.splitlines():
                        line_s = line.strip()
                        if line_s.startswith("efi ") and ".efi" in line_s:
                            boots_via_uki = True
                            active_kernel_files.append(line_s.split(None, 1)[1])
                        elif line_s.startswith("linux "):
                            kfile = line_s.split(None, 1)[1]
                            active_kernel_files.append(kfile)
                except OSError:
                    pass

    if len(ukis) > 0 and (boots_via_uki or not kernels):
        boots_via_uki = True

    return {
        "uses_uki": boots_via_uki,
        "traditional_kernels": kernels,
        "ukis": ukis,
        "active_referenced_files": active_kernel_files,
        "tamper_warning": (
            "NOTICE: With traditional kernels (vmlinuz + initramfs + cmdline), Secure Boot "
            "only authenticates the vmlinuz executable itself. The initramfs archive and kernel "
            "command line parameters are NOT authenticated. For complete tamper protection, "
            "consider migrating to Unified Kernel Images (UKIs)."
        ) if not boots_via_uki else None,
    }


def get_signable_kernel_files() -> List[Path]:
    """
    Returns all kernel-related EFI/PE binaries that must be signed.
    Includes both UKIs and traditional vmlinuz kernels on /boot or ESP.
    """
    files: List[Path] = []
    seen: set = set()

    # 1. Unified Kernel Images
    ukis = detect_unified_kernel_images()
    for u in ukis:
        p = Path(u["path"])
        if p.is_file() and str(p) not in seen:
            files.append(p)
            seen.add(str(p))

    # 2. Traditional kernels on /boot
    for k in ARCH_KERNEL_NAMES:
        vm = Path(f"/boot/vmlinuz-{k}")
        if vm.is_file() and str(vm) not in seen:
            files.append(vm)
            seen.add(str(vm))

    # 3. Check ESP mounts for vmlinuz files
    for esp in find_esp_mounts():
        m = Path(esp["mountpoint"])
        for vm in m.glob("vmlinuz*"):
            if vm.is_file() and str(vm) not in seen:
                files.append(vm)
                seen.add(str(vm))

    return files


def sign_all_kernels() -> Tuple[bool, List[str], List[str]]:
    """
    Signs all detected kernel and UKI binaries using `sbctl sign -s`.
    Returns (success, signed_files, failed_files).
    """
    files = get_signable_kernel_files()
    if not files:
        return False, [], ["No kernel or UKI images found to sign."]

    if not shutil.which("sbctl"):
        return False, [], ["sbctl is not installed."]

    from core.logger import logger

    signed: List[str] = []
    failed: List[str] = []

    for f in files:
        code, _ = logger.run_cmd(["sudo", "sbctl", "sign", "-s", str(f)], check=False)
        if code == 0:
            signed.append(str(f))
        else:
            failed.append(str(f))

    success = len(signed) > 0 and len(failed) == 0
    return success, signed, failed


def verify_kernel_signatures() -> Dict[str, bool]:
    """Verifies signatures of all detected kernels and UKIs."""
    files = get_signable_kernel_files()
    results: Dict[str, bool] = {}

    if not shutil.which("sbctl"):
        return {str(f): False for f in files}

    for f in files:
        try:
            code = subprocess.run(
                ["sbctl", "verify", str(f)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            results[str(f)] = (code == 0)
        except Exception:
            results[str(f)] = False

    return results

