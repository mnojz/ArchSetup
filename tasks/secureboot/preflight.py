"""
Comprehensive Read-Only Preflight Verification
Validates environment, UEFI support, efivarfs accessibility, tools, and permissions.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from tasks.secureboot.config import (
    OPTIONAL_TOOLS,
    REQUIRED_TOOLS,
    STATUS_FAILED,
    STATUS_HEALTHY,
    STATUS_WARNING,
)
from tasks.secureboot.firmware import (
    inspect_firmware,
    is_efivars_mounted,
    is_secure_boot_enabled,
    is_setup_mode,
    is_uefi_boot,
)


def is_arch_linux() -> bool:
    """Checks whether the running system is Arch Linux or an Arch derivative."""
    if Path("/etc/arch-release").is_file():
        return True
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        try:
            content = os_release.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if line.startswith("ID=") and "arch" in line.lower():
                    return True
                if line.startswith("ID_LIKE=") and "arch" in line.lower():
                    return True
        except OSError:
            pass
    return False


def get_sbctl_version() -> Optional[str]:
    """Returns installed sbctl version string or None."""
    if not shutil.which("sbctl"):
        return None
    try:
        out = subprocess.check_output(
            ["sbctl", "version"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        ).strip()
        # Output is usually: "sbctl version 0.16" or similar
        return out
    except Exception:
        return "Installed (version query failed)"


def check_tool_availability() -> Dict[str, bool]:
    """Inspects PATH for required and optional utilities."""
    tools: Dict[str, bool] = {}
    for tool in REQUIRED_TOOLS:
        tools[tool] = shutil.which(tool) is not None
    for tool in OPTIONAL_TOOLS:
        tools[tool] = shutil.which(tool) is not None
    return tools


def check_disk_space(mount_point: Path) -> int:
    """Returns free space in bytes on filesystem containing mount_point."""
    try:
        stat = os.statvfs(str(mount_point))
        return stat.f_bavail * stat.f_frsize
    except OSError:
        return 0


class PreflightReport:
    """Structured result of preflight checks."""

    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.blockers: List[str] = []
        self.warnings: List[str] = []
        self.is_ready_for_setup: bool = False
        self.firmware_info: Dict[str, Any] = {}
        self.sbctl_version: Optional[str] = None
        self.tools: Dict[str, bool] = {}

    def add_check(
        self,
        name: str,
        status: str,
        details: str,
        is_blocker: bool = False,
        is_warning: bool = False,
    ) -> None:
        self.checks.append({
            "name": name,
            "status": status,
            "details": details,
        })
        if is_blocker:
            self.blockers.append(f"{name}: {details}")
        elif is_warning:
            self.warnings.append(f"{name}: {details}")


def run_preflight(require_setup_mode: bool = False) -> PreflightReport:
    """
    Executes all read-only preflight inspections.
    Does not modify any files or firmware variables.
    """
    report = PreflightReport()

    # 1. UEFI Boot Mode
    uefi = is_uefi_boot()
    if uefi:
        report.add_check("UEFI Boot Mode", STATUS_HEALTHY, "System booted in UEFI mode")
    else:
        report.add_check(
            "UEFI Boot Mode",
            STATUS_FAILED,
            "System booted in Legacy BIOS / CSM mode. Secure Boot requires native UEFI.",
            is_blocker=True,
        )

    # 2. efivarfs accessibility
    efivars_ok = is_efivars_mounted()
    if efivars_ok:
        report.add_check("EFI Variables Interface", STATUS_HEALTHY, "efivarfs is mounted and accessible")
    else:
        report.add_check(
            "EFI Variables Interface",
            STATUS_FAILED,
            "efivars is inaccessible. Firmware variables cannot be inspected or written.",
            is_blocker=True,
        )

    # 3. Arch Linux verification
    arch = is_arch_linux()
    if arch:
        report.add_check("Linux Distribution", STATUS_HEALTHY, "Arch Linux detected")
    else:
        report.add_check(
            "Linux Distribution",
            STATUS_WARNING,
            "Non-Arch Linux system detected. Some packaging hooks may differ.",
            is_warning=True,
        )

    # 4. sbctl installation & version
    sbctl_ver = get_sbctl_version()
    report.sbctl_version = sbctl_ver
    if sbctl_ver:
        report.add_check("sbctl Key Manager", STATUS_HEALTHY, f"Available ({sbctl_ver})")
    else:
        report.add_check(
            "sbctl Key Manager",
            STATUS_WARNING,
            "sbctl is not installed. Will be installed automatically via pacman.",
            is_warning=True,
        )

    # 5. Required and optional utilities
    tools = check_tool_availability()
    report.tools = tools
    missing_required = [t for t in REQUIRED_TOOLS if not tools.get(t, False)]
    if not missing_required:
        report.add_check("Core Tools", STATUS_HEALTHY, "All required tools available")
    else:
        report.add_check(
            "Core Tools",
            STATUS_WARNING,
            f"Missing tools: {', '.join(missing_required)}",
            is_warning=True,
        )

    # 6. Firmware state: Secure Boot & Setup Mode
    fw = inspect_firmware()
    report.firmware_info = fw

    sb_active = fw.get("secure_boot_enabled", False)
    setup_mode = fw.get("setup_mode", False)

    if sb_active:
        report.add_check(
            "Secure Boot Status",
            STATUS_HEALTHY,
            "Secure Boot is ENABLED and actively enforcing signatures",
        )
    else:
        report.add_check(
            "Secure Boot Status",
            STATUS_WARNING,
            "Secure Boot is currently DISABLED in firmware",
        )

    if setup_mode:
        report.add_check(
            "Firmware Setup Mode",
            STATUS_HEALTHY,
            "Setup Mode is ACTIVE (firmware is ready to enroll custom keys)",
        )
    else:
        if require_setup_mode:
            report.add_check(
                "Firmware Setup Mode",
                STATUS_FAILED,
                "Firmware is in User Mode. To enroll keys, clear existing keys in BIOS setup.",
                is_blocker=True,
            )
        else:
            report.add_check(
                "Firmware Setup Mode",
                STATUS_WARNING,
                "Firmware is in User Mode (keys cannot be enrolled until cleared in BIOS)",
                is_warning=True,
            )

    # 7. Sudo / privilege check
    from core import auth
    sudo_active = auth.is_sudo_active() or os.geteuid() == 0
    if sudo_active:
        report.add_check("Administrative Privileges", STATUS_HEALTHY, "Root/sudo privileges available")
    else:
        report.add_check(
            "Administrative Privileges",
            STATUS_WARNING,
            "Sudo session inactive (will prompt when modification is requested)",
        )

    # Ready evaluation
    report.is_ready_for_setup = len(report.blockers) == 0

    return report

