"""
Secure Boot Diagnostic Report Generator
Compiles system inspection, firmware variables, trust chain verification, and recovery diagnostics
into formatted text and JSON reports.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from tasks.secureboot.config import REPORT_DIR
from tasks.secureboot.firmware import inspect_firmware
from tasks.secureboot.inventory import inspect_full_inventory
from tasks.secureboot.keys import inspect_key_inventory
from tasks.secureboot.recovery import diagnose_system
from tasks.secureboot.signing import verify_all_system_files
from tasks.secureboot.updates import inspect_update_hooks
from tasks.secureboot.verification import run_full_health_check


def generate_diagnostic_report() -> Tuple[str, Path]:
    """
    Compiles a comprehensive diagnostic report and writes it to disk.
    Returns (report_text, report_file_path).
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"report_{file_timestamp}.txt"

    fw = inspect_firmware()
    inv = inspect_full_inventory()
    keys = inspect_key_inventory()
    ver = verify_all_system_files()
    hk = inspect_update_hooks()
    health = run_full_health_check()
    issues = diagnose_system()

    lines = [
        "=" * 72,
        " ARCHSETUP SECURE BOOT DIAGNOSTIC REPORT",
        f" Generated: {timestamp_str}",
        "=" * 72,
        "",
        "--- [1] FIRMWARE & PLATFORM ---",
        f" UEFI Boot Mode:          {'YES' if fw.get('is_uefi') else 'NO (Legacy BIOS)'}",
        f" EFI Variables Mounted:   {'YES' if fw.get('efivars_accessible') else 'NO'}",
        f" Secure Boot Enforcing:   {'ENABLED' if fw.get('secure_boot_enabled') else 'DISABLED'}",
        f" Setup Mode:              {'ACTIVE' if fw.get('setup_mode') else 'USER MODE'}",
        f" Firmware Vendor:         {fw.get('vendor', 'Unknown')}",
        f" BIOS Version:            {fw.get('bios_version', 'Unknown')}",
        "",
        "--- [2] EFI SYSTEM PARTITIONS (ESP) ---",
        f" Primary ESP Mount:       {inv.get('primary_esp', 'None found')}",
    ]

    for esp in inv.get("esps", []):
        lines.append(f"   • {esp.get('mountpoint')} ({esp.get('fstype')}, Free: {esp.get('free_space_bytes', 0) // (1024*1024)} MB)")

    lines.extend([
        "",
        "--- [3] BOOTLOADER INTEGRATION ---",
        f" Active Bootloader:       {inv.get('bootloader', {}).get('name', 'Unknown')}",
        f" Details:                 {inv.get('bootloader', {}).get('details', 'N/A')}",
        f" Config File:             {inv.get('bootloader', {}).get('config_path', 'N/A')}",
        "",
        "--- [4] KERNEL & UKI CONFIGURATION ---",
        f" Uses UKI:                {'YES' if inv.get('uses_uki') else 'NO (Traditional vmlinuz)'}",
    ])

    for k in inv.get("kernels", []):
        lines.append(f"   • Traditional Kernel: {k.get('name')} -> {k.get('vmlinuz_path')}")
    for u in inv.get("ukis", []):
        lines.append(f"   • UKI Image: {u.get('name')} -> {u.get('path')} ({u.get('size_bytes', 0) // 1024} KB)")

    lines.extend([
        "",
        "--- [5] WINDOWS DUAL-BOOT ---",
        f" Windows Detected:        {'YES' if inv.get('windows', {}).get('detected') else 'NO'}",
    ])
    if inv.get("windows", {}).get("bootmgr_path"):
        lines.append(f" Windows Boot Manager:    {inv.get('windows', {}).get('bootmgr_path')}")

    lines.extend([
        "",
        "--- [6] SECURE BOOT KEYS ---",
    ])
    for db_name, data in keys.items():
        cert_st = "Present" if data.get("has_certificate") else "Missing"
        key_st = "Present (0600)" if data.get("has_private_key") else "Missing"
        lines.append(f"   • {db_name:4}: Cert={cert_st:<10} PrivateKey={key_st}")

    lines.extend([
        "",
        "--- [7] SIGNATURE VERIFICATION ---",
        f" All Files Verified:      {'YES' if ver.get('all_verified') else 'NO'}",
        f" Verified Count:          {ver.get('verified_count', 0)} / {ver.get('total_count', 0)}",
    ])
    for fpath, ok in ver.get("results", {}).items():
        lines.append(f"   [{'PASS' if ok else 'FAIL'}] {fpath}")

    lines.extend([
        "",
        "--- [8] AUTOMATIC UPDATE HOOKS ---",
        f" Pacman Hook Installed:   {'YES' if hk.get('hook_installed') else 'NO'}",
        f" Hook Path:               {hk.get('hook_path')}",
        "",
        "--- [9] OVERALL HEALTH SUMMARY ---",
        f" Status:                  {health.overall_status}",
        f" Summary:                 {health.summary_message}",
        f" Checks Passed:           {health.passed_count}",
        f" Warnings:                {health.warning_count}",
        f" Failures:                {health.failed_count}",
    ])

    if issues:
        lines.extend([
            "",
            "--- [10] DIAGNOSED ISSUES & RECOVERY ACTIONS ---",
        ])
        for idx, iss in enumerate(issues, 1):
            lines.append(f"\nIssue #{idx}: [{iss.get('severity')}] {iss.get('title')}")
            lines.append(f"  Description: {iss.get('description')}")
            lines.append("  Recovery Steps:")
            for step in iss.get("recovery_steps", []):
                lines.append(f"    - {step}")

    lines.append("\n" + "=" * 72 + "\n")

    report_content = "\n".join(lines)
    report_file.write_text(report_content, encoding="utf-8")

    return report_content, report_file

