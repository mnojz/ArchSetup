"""
Secure Boot Comprehensive Health & Signature Verification Engine
Audits 11 distinct dimensions of the Secure Boot chain to produce a definitive health report.
Never marks the system healthy merely because sbctl verify succeeds.
"""

from typing import Any, Dict, List

from tasks.secureboot.adapters import get_active_adapter
from tasks.secureboot.config import (
    STATUS_CONFIGURED,
    STATUS_FAILED,
    STATUS_HEALTHY,
    STATUS_MANUAL,
    STATUS_UNSUPPORTED,
    STATUS_WARNING,
)
from tasks.secureboot.firmware import (
    inspect_firmware,
    is_efivars_mounted,
    is_secure_boot_enabled,
    is_setup_mode,
    is_uefi_boot,
)
from tasks.secureboot.inventory import (
    detect_windows,
    find_esp_mounts,
    get_primary_esp_path,
)
from tasks.secureboot.kernel import inspect_kernel_configuration
from tasks.secureboot.keys import do_keys_exist, inspect_key_inventory
from tasks.secureboot.signing import verify_all_system_files
from tasks.secureboot.updates import inspect_update_hooks


class HealthCheckResult:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.overall_status: str = STATUS_HEALTHY
        self.summary_message: str = ""
        self.passed_count: int = 0
        self.warning_count: int = 0
        self.failed_count: int = 0

    def add_item(self, component: str, status: str, details: str, category: str = "Core") -> None:
        self.checks.append({
            "component": component,
            "status": status,
            "details": details,
            "category": category,
        })
        if status in (STATUS_HEALTHY, STATUS_CONFIGURED):
            self.passed_count += 1
        elif status == STATUS_WARNING:
            self.warning_count += 1
        elif status in (STATUS_FAILED, STATUS_MANUAL, STATUS_UNSUPPORTED):
            self.failed_count += 1

    def finalize(self) -> None:
        if self.failed_count > 0:
            self.overall_status = STATUS_FAILED
            self.summary_message = f"System has {self.failed_count} critical failure(s) preventing Secure Boot."
        elif self.warning_count > 0:
            self.overall_status = STATUS_WARNING
            self.summary_message = f"System is configured with {self.warning_count} warning(s) to review."
        else:
            self.overall_status = STATUS_HEALTHY
            self.summary_message = "All Secure Boot chain components are healthy and fully verified!"


def run_full_health_check() -> HealthCheckResult:
    """
    Executes an in-depth audit of the entire Secure Boot lifecycle and trust chain.
    """
    res = HealthCheckResult()

    # 1. UEFI Platform
    if is_uefi_boot():
        res.add_item("UEFI Boot Mode", STATUS_HEALTHY, "System booted under native UEFI")
    else:
        res.add_item("UEFI Boot Mode", STATUS_FAILED, "Legacy BIOS detected; Secure Boot impossible")

    # 2. efivarfs Interface
    if is_efivars_mounted():
        res.add_item("EFI Variables (efivars)", STATUS_HEALTHY, "Accessible for read/write inspection")
    else:
        res.add_item("EFI Variables (efivars)", STATUS_FAILED, "efivars is unmounted or inaccessible")

    # 3. Secure Boot Enforcement
    sb_active = is_secure_boot_enabled()
    if sb_active:
        res.add_item("Secure Boot Enforcement", STATUS_HEALTHY, "Active and enforcing signatures in hardware")
    else:
        res.add_item(
            "Secure Boot Enforcement",
            STATUS_WARNING,
            "Disabled in firmware. Enable in BIOS settings after setup",
        )

    # 4. Setup Mode Status
    setup_mode = is_setup_mode()
    if setup_mode:
        res.add_item("Firmware Setup Mode", STATUS_CONFIGURED, "Setup Mode active (ready to enroll custom keys)")
    else:
        res.add_item("Firmware Setup Mode", STATUS_HEALTHY, "User Mode active (keys enrolled and locked)")

    # 5. Custom Keys on Disk
    if do_keys_exist():
        inv = inspect_key_inventory()
        all_ready = all(inv.get(db, {}).get("ready", False) for db in ("PK", "KEK", "db"))
        if all_ready:
            res.add_item("Custom Signing Keys", STATUS_HEALTHY, "Valid PK, KEK, and db key-pairs present")
        else:
            res.add_item("Custom Signing Keys", STATUS_WARNING, "Incomplete key database on disk")
    else:
        res.add_item("Custom Signing Keys", STATUS_WARNING, "No custom keys generated yet")

    # 6. ESP Mount State
    esps = find_esp_mounts()
    primary_esp = get_primary_esp_path()
    if esps and primary_esp:
        res.add_item("ESP Mount State", STATUS_HEALTHY, f"Mounted at {primary_esp} ({len(esps)} ESP found)")
    else:
        res.add_item("ESP Mount State", STATUS_FAILED, "No mounted EFI System Partition found")

    # 7. Active Bootloader & Signature
    adapter = get_active_adapter()
    if adapter:
        ver = adapter.verify()
        if ver.get("all_signed", False):
            res.add_item(f"Bootloader ({adapter.display_name})", STATUS_HEALTHY, "EFI binary signed & verified")
        else:
            res.add_item(f"Bootloader ({adapter.display_name})", STATUS_WARNING, "Unsigned or invalid EFI binary")
    else:
        res.add_item("Bootloader Adapter", STATUS_UNSUPPORTED, "Active bootloader is unsupported or unknown")

    # 8. Kernel / UKI Signatures
    k_info = inspect_kernel_configuration()
    ver_status = verify_all_system_files()
    if ver_status.get("all_verified", False):
        k_type = "Unified Kernel Image (UKI)" if k_info.get("uses_uki") else "Traditional Kernel (vmlinuz)"
        res.add_item(f"Kernel Signatures ({k_type})", STATUS_HEALTHY, "All detected kernels verified")
    else:
        res.add_item("Kernel Signatures", STATUS_WARNING, "One or more kernel images are unsigned")

    # 9. Windows Dual-Boot Compatibility
    win = detect_windows()
    if win.get("detected", False):
        res.add_item("Windows Dual-Boot", STATUS_CONFIGURED, "Windows Boot Manager detected (MS certs required)")
    else:
        res.add_item("Windows Dual-Boot", STATUS_HEALTHY, "No Windows installation found (Linux-only chain)")

    # 10. Update Hooks
    hk = inspect_update_hooks()
    if hk.get("is_configured", False):
        res.add_item("Automatic Update Hooks", STATUS_HEALTHY, "Pacman automatic re-signing hook active")
    else:
        res.add_item("Automatic Update Hooks", STATUS_WARNING, "No automatic update hook configured")

    # 11. End-to-End Chain Evaluation
    if sb_active and ver_status.get("all_verified", False) and hk.get("is_configured", False):
        res.add_item("Chain Integrity", STATUS_HEALTHY, "Full end-to-end authenticated boot chain")
    elif not sb_active and ver_status.get("all_verified", False):
        res.add_item(
            "Chain Integrity",
            STATUS_CONFIGURED,
            "Binaries signed and ready; awaiting BIOS Secure Boot activation",
        )
    else:
        res.add_item("Chain Integrity", STATUS_WARNING, "Boot chain incomplete or partially signed")

    res.finalize()
    return res

