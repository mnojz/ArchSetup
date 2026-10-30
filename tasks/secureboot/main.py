"""
Secure Boot TUI Submenu & Action Orchestrator
Provides interactive keyboard-driven menus matching ArchSetup design language,
guiding the user through initial setup, key management, signing, enrollment, and recovery.
"""

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import box
from rich.panel import Panel
from rich.table import Table

from core import auth, menu, tui
from core.logger import logger
from core.pacman import pm
from tasks.secureboot import (
    backup,
    enrollment,
    firmware,
    inventory,
    kernel,
    keys,
    preflight,
    recovery,
    report,
    signing,
    updates,
    verification,
)
from tasks.secureboot.adapters import get_active_adapter, get_all_adapters
from tasks.secureboot.config import MODULE_NAME, MODULE_VERSION


def _ensure_sbctl_installed() -> bool:
    """Verifies sbctl is installed, offering automated installation via pacman if missing."""
    if shutil.which("sbctl"):
        return True

    tui.log_warning("sbctl is required for Secure Boot management but is not installed.")
    if tui.prompt_yes_no("Install sbctl now via pacman?", default=True):
        if not auth.request_sudo_auth("Installing sbctl"):
            tui.log_error("Sudo authorization not granted. Cannot install sbctl.")
            return False
        tui.log_running("Installing sbctl package...")
        if pm.install_package("sbctl"):
            tui.log_success("sbctl installed successfully.")
            return True
        else:
            tui.log_error("Failed to install sbctl. Please install it manually with: sudo pacman -S sbctl")
            return False
    return False


# ---------------------------------------------------------------------------
# Action: 1. System Overview
# ---------------------------------------------------------------------------
def do_overview() -> None:
    tui.show_step_header(1, 1, "Secure Boot System Overview")
    pref = preflight.run_preflight()

    width = tui.get_terminal_width()
    table = Table(
        title="[bold cyan]UEFI Platform & Firmware State[/]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        width=width,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("Property", style="bold white", width=28)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Details", style="dim")

    for ch in pref.checks:
        st = ch.get("status", "INFO")
        if st in ("HEALTHY", "PASS"):
            st_text = "[bold green]✔ OK[/]"
        elif st in ("WARNING", "WARN"):
            st_text = "[bold yellow]⚠ WARN[/]"
        elif st in ("FAILED", "FAIL"):
            st_text = "[bold red]✖ FAIL[/]"
        else:
            st_text = "[bold cyan]ℹ INFO[/]"
        table.add_row(ch.get("name", ""), st_text, ch.get("details", ""))

    tui.console.print(table)
    tui.console.print()

    # Storage & Bootloader table
    inv = inventory.inspect_full_inventory()
    bl = inv.get("bootloader", {})
    tui.log_info(f"Primary ESP: [cyan]{inv.get('primary_esp', 'None')}[/]")
    tui.log_info(f"Active Bootloader: [bold cyan]{bl.get('name', 'Unknown')}[/] ({bl.get('details', '')})")
    tui.log_info(f"Kernel Format: [bold cyan]{'Unified Kernel Image (UKI)' if inv.get('uses_uki') else 'Traditional vmlinuz + initramfs'}[/]")

    win = inv.get("windows", {})
    if win.get("detected"):
        tui.log_warning("Windows Boot Manager detected: dual-boot preservation is active.")
    else:
        tui.log_info("Linux-only system detected.")


# ---------------------------------------------------------------------------
# Action: 2. Initial Secure Boot Setup (Guided Wizard)
# ---------------------------------------------------------------------------
def do_initial_setup(auto_confirm: bool = False) -> None:
    tui.show_step_header(1, 5, "Initial Secure Boot Setup Wizard")

    tui.console.print(
        Panel(
            "[bold bright_white]This guided wizard configures end-to-end Secure Boot for Arch Linux:\n\n"
            "  1. System Pre-flight & Pre-condition Inspection\n"
            "  2. Custom Secure Boot Key Generation (sbctl)\n"
            "  3. Bootloader & Kernel Binary Signing & Database Registration\n"
            "  4. Automatic Re-Signing Hook Installation\n"
            "  5. Firmware Key Enrollment (with Windows Dual-Boot & BitLocker Protection)[/]",
            title="[bold magenta]◆[/] [bold cyan]Secure Boot Setup Plan[/] [bold magenta]◆[/]",
            box=box.ROUNDED,
            border_style="cyan",
            width=tui.get_terminal_width(),
            padding=(0, 2),
        )
    )

    if not _ensure_sbctl_installed():
        return

    # Check setup mode
    if not firmware.is_setup_mode():
        tui.console.print()
        tui.log_warning("Firmware is currently in USER MODE (Setup Mode is inactive).")
        tui.console.print(
            Panel(
                "[bold yellow]Your UEFI firmware already has keys locked in NVRAM.\n\n"
                "To enroll custom keys, you must first put your firmware into Setup Mode:\n"
                "1. Reboot your PC and press F2 / Del / F12 to enter BIOS settings.\n"
                "2. Find 'Secure Boot' settings and choose 'Erase / Clear Keys' or 'Enter Setup Mode'.\n"
                "3. Save and reboot into Arch Linux, then run this wizard again.[/]",
                title="[bold yellow]⚠ Action Required in BIOS/UEFI[/]",
                box=box.ROUNDED,
                border_style="yellow",
                width=tui.get_terminal_width(),
                padding=(0, 2),
            )
        )
        if not tui.prompt_yes_no("Proceed with key generation and binary signing anyway (deferring enrollment)?", default=True):
            return

    if not auth.request_sudo_auth("Secure Boot Setup"):
        tui.log_error("Sudo authorization not granted. Aborting setup.")
        return

    # Phase 1: Key Generation
    tui.show_step_header(2, 5, "Key Management & Generation")
    if keys.do_keys_exist():
        tui.log_success("Custom Secure Boot keys already exist on disk. Preserving existing keys.")
    else:
        tui.log_running("Generating custom Secure Boot keys using sbctl...")
        ok, msg = keys.create_keys()
        if ok:
            tui.log_success(msg)
        else:
            tui.log_error(f"Key generation failed: {msg}")
            return

    # Safety Backup
    tui.log_running("Creating safety backup of keys and bootloader configuration...")
    backup.create_full_backup("initial_setup")
    tui.log_success("Safety backup created.")

    # Phase 2: Binary Signing
    tui.show_step_header(3, 5, "Bootloader & Kernel Signing")
    tui.log_running("Discovering and signing bootloader and kernel binaries...")
    ok, signed, failed = signing.auto_discover_and_sign_all()
    for s in signed:
        tui.log_success(f"Signed and registered: [white]{s}[/]")
    for f in failed:
        tui.log_error(f"Signing error: {f}")

    if failed:
        tui.log_error("One or more required boot files could not be signed. Halting before enrollment.")
        return

    # Verify signatures
    ver = signing.verify_all_system_files()
    if not ver.get("all_verified", False):
        tui.log_error("Signature verification failed. Cannot proceed to firmware enrollment.")
        return
    tui.log_success(f"All {ver.get('verified_count', 0)} detected boot binaries verified successfully.")

    # Phase 3: Automatic Updates
    tui.show_step_header(4, 5, "Automatic Update Integration")
    ok, msg = updates.install_update_hooks()
    if ok:
        tui.log_success(msg)
    else:
        tui.log_warning(f"Could not install pacman hook: {msg}")

    # Phase 4: Firmware Enrollment
    tui.show_step_header(5, 5, "Firmware Key Enrollment")
    if not firmware.is_setup_mode():
        tui.log_warning("Enrollment deferred: Firmware is not in Setup Mode.")
        tui.log_info("Your binaries are signed and update hooks are ready. Clear keys in BIOS to enroll.")
        return

    win = inventory.detect_windows()
    include_ms = True
    if win.get("detected"):
        tui.console.print(
            Panel(
                "[bold yellow]WINDOWS DUAL-BOOT DETECTED:\n\n"
                "• Microsoft certificates will be enrolled alongside your custom keys.\n"
                "• BitLocker Warning: If BitLocker is active on Windows, have your 48-digit "
                "recovery key ready at hand before proceeding![/]",
                title="[bold yellow]⚠ Windows & BitLocker Compatibility Notice[/]",
                box=box.ROUNDED,
                border_style="yellow",
                width=tui.get_terminal_width(),
                padding=(0, 2),
            )
        )
        include_ms = tui.prompt_yes_no("Enroll Microsoft certificates for Windows & Option ROM compatibility?", default=True)

    tui.console.print()
    tui.log_warning("HIGH-RISK OPERATION: You are about to enroll custom Secure Boot keys into firmware NVRAM.")
    if not tui.prompt_yes_no("Proceed with firmware key enrollment now?", default=False):
        tui.log_info("Firmware enrollment cancelled by user. Binaries remain signed on disk.")
        return

    tui.log_running("Enrolling keys into firmware via sbctl...")
    ok, msg = enrollment.execute_enrollment(include_microsoft=include_ms)
    if ok:
        tui.console.print()
        tui.console.print(
            Panel(
                f"[bold green]✔ {msg}[/]",
                title="[bold green]Secure Boot Setup Complete[/]",
                box=box.ROUNDED,
                border_style="green",
                width=tui.get_terminal_width(),
                padding=(1, 2),
            )
        )
    else:
        tui.log_error(f"Enrollment failed: {msg}")


# ---------------------------------------------------------------------------
# Action: 3. Key Management
# ---------------------------------------------------------------------------
def do_key_management() -> None:
    tui.show_step_header(1, 1, "Secure Boot Key Management")
    if not _ensure_sbctl_installed():
        return

    inv = keys.inspect_key_inventory()
    width = tui.get_terminal_width()

    table = Table(
        title="[bold cyan]Secure Boot Key Databases[/]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        width=width,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("Database", style="bold white", width=12)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Certificate", style="dim", width=24)
    table.add_column("Private Key", style="dim")

    for db_name, d in inv.items():
        st = "[bold green]Ready[/]" if d.get("ready") else "[dim yellow]Missing[/]"
        cert_p = d.get("certificate_path") or "None"
        key_p = d.get("private_key_path") or "None"
        if d.get("has_private_key"):
            key_p = f"{key_p} (0600)"
        table.add_row(db_name, st, Path(cert_p).name if cert_p != "None" else "None", Path(key_p).name if key_p != "None" else "None")

    tui.console.print(table)
    tui.console.print()

    if not keys.do_keys_exist():
        if tui.prompt_yes_no("No keys exist. Generate a new key pair now?", default=True):
            if auth.request_sudo_auth("Generating Secure Boot Keys"):
                ok, msg = keys.create_keys()
                if ok:
                    tui.log_success(msg)
                else:
                    tui.log_error(msg)
    else:
        tui.log_success("Custom keys exist and are protected.")
        if tui.prompt_yes_no("Create a secure backup snapshot of your keys now?", default=False):
            if auth.request_sudo_auth("Backing up Keys"):
                ok, msg, _ = backup.create_full_backup("key_backup")
                if ok:
                    tui.log_success(msg)


# ---------------------------------------------------------------------------
# Action: 4. Bootloader Management
# ---------------------------------------------------------------------------
def do_bootloader_management() -> None:
    tui.show_step_header(1, 1, "Bootloader Management")
    adapter = get_active_adapter()
    if not adapter:
        tui.log_error("Could not detect a supported active bootloader.")
        return

    info = adapter.inspect()
    tui.log_info(f"Active Adapter: [bold cyan]{adapter.display_name}[/]")
    tui.log_info(f"Chain Architecture: [white]{info.get('chain_notes', '')}[/]")

    files = info.get("signable_files", [])
    if files:
        tui.log_info("Signable EFI files:")
        for f in files:
            tui.log_dim(f"• {f}")

    ver = adapter.verify()
    if ver.get("all_signed"):
        tui.log_success("Bootloader EFI executables are signed and verified.")
    else:
        tui.log_warning("Bootloader EFI executables are unsigned or modified.")
        if tui.prompt_yes_no("Sign and register bootloader executables now?", default=True):
            if auth.request_sudo_auth("Signing Bootloader"):
                ok, msg = adapter.sign()
                if ok:
                    tui.log_success(msg)
                else:
                    tui.log_error(msg)


# ---------------------------------------------------------------------------
# Action: 5. Kernel & EFI Signing
# ---------------------------------------------------------------------------
def do_signing() -> None:
    tui.show_step_header(1, 1, "Kernel & EFI Binary Signing")
    if not _ensure_sbctl_installed():
        return

    k_info = kernel.inspect_kernel_configuration()
    tui.log_info(f"Kernel Configuration: [bold cyan]{'Unified Kernel Image (UKI)' if k_info.get('uses_uki') else 'Traditional Linux Image (vmlinuz)'}[/]")

    if k_info.get("tamper_warning"):
        tui.log_warning(k_info["tamper_warning"])

    ver = signing.verify_all_system_files()
    width = tui.get_terminal_width()

    table = Table(
        title="[bold cyan]System EFI Executables & Signatures[/]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        width=width,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("File Path", style="bold white", width=50)
    table.add_column("Signature", justify="center", width=14)

    for fpath, is_signed in ver.get("results", {}).items():
        st = "[bold green]✔ Valid[/]" if is_signed else "[bold red]✖ Unsigned[/]"
        table.add_row(fpath, st)

    tui.console.print(table)
    tui.console.print()

    if not ver.get("all_verified", False):
        if tui.prompt_yes_no("Sign and register all unsigned binaries now?", default=True):
            if auth.request_sudo_auth("Signing Binaries"):
                ok, signed, failed = signing.auto_discover_and_sign_all()
                for s in signed:
                    tui.log_success(f"Signed: {s}")
                for f in failed:
                    tui.log_error(f"Failed: {f}")
    else:
        tui.log_success("All detected boot binaries possess valid Secure Boot signatures.")


# ---------------------------------------------------------------------------
# Action: 6. Update Automation
# ---------------------------------------------------------------------------
def do_updates() -> None:
    tui.show_step_header(1, 1, "Automatic Update Integration")
    hk_info = updates.inspect_update_hooks()

    if hk_info.get("hook_installed"):
        tui.log_success(f"Pacman re-signing hook is installed: [white]{hk_info['hook_path']}[/]")
        if tui.prompt_yes_no("Re-install / refresh the pacman signing hook?", default=False):
            if auth.request_sudo_auth("Updating Hook"):
                ok, msg = updates.install_update_hooks()
                if ok:
                    tui.log_success(msg)
                else:
                    tui.log_error(msg)
    else:
        tui.log_warning("Pacman automatic re-signing hook is not installed.")
        if tui.prompt_yes_no("Install automatic pacman re-signing hook now?", default=True):
            if auth.request_sudo_auth("Installing Hook"):
                ok, msg = updates.install_update_hooks()
                if ok:
                    tui.log_success(msg)
                else:
                    tui.log_error(msg)


# ---------------------------------------------------------------------------
# Action: 7. Health Check
# ---------------------------------------------------------------------------
def do_health_check() -> None:
    tui.show_step_header(1, 1, "Secure Boot End-to-End Health Check")
    health = verification.run_full_health_check()

    width = tui.get_terminal_width()
    table = Table(
        title="[bold cyan]Secure Boot Trust Chain Audit[/]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        width=width,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("Subsystem / Component", style="bold white", width=34)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Diagnostic Details", style="dim")

    for ch in health.checks:
        st = ch.get("status")
        if st in ("HEALTHY", "CONFIGURED"):
            st_text = "[bold green]✔ PASS[/]" if st == "HEALTHY" else "[bold cyan]ℹ READY[/]"
        elif st == "WARNING":
            st_text = "[bold yellow]⚠ WARN[/]"
        else:
            st_text = "[bold red]✖ FAIL[/]"
        table.add_row(ch.get("component"), st_text, ch.get("details"))

    tui.console.print(table)
    tui.console.print()

    if health.overall_status == "HEALTHY":
        tui.log_success(health.summary_message)
    elif health.overall_status == "WARNING":
        tui.log_warning(health.summary_message)
    else:
        tui.log_error(health.summary_message)


# ---------------------------------------------------------------------------
# Action: 8. Recovery Center
# ---------------------------------------------------------------------------
def do_recovery() -> None:
    tui.show_step_header(1, 1, "Secure Boot Recovery Center")
    issues = recovery.diagnose_system()

    if not issues:
        tui.log_success("No system failures or recovery issues diagnosed. The Secure Boot chain is intact!")
        return

    tui.log_warning(f"Diagnosed {len(issues)} issue(s) requiring attention:")
    for idx, iss in enumerate(issues, 1):
        tui.console.print()
        tui.console.print(
            Panel(
                f"[bold red]Severity:[/] {iss.get('severity')}\n\n"
                f"[white]{iss.get('description')}[/]\n\n"
                f"[bold cyan]Actionable Recovery Steps:[/]\n"
                + "\n".join(f"  • {s}" for s in iss.get("recovery_steps", [])),
                title=f"[bold yellow]Issue #{idx}: {iss.get('title')}[/]",
                box=box.ROUNDED,
                border_style="yellow",
                width=tui.get_terminal_width(),
                padding=(0, 2),
            )
        )


# ---------------------------------------------------------------------------
# Action: 9. Logs & Reports
# ---------------------------------------------------------------------------
def do_reports() -> None:
    tui.show_step_header(1, 1, "Diagnostic Reports & Logs")
    tui.log_running("Compiling diagnostic report...")
    content, path = report.generate_diagnostic_report()
    tui.log_success(f"Report generated: [white]{path}[/]")

    lines = content.splitlines()
    preview = lines[:35] if len(lines) > 35 else lines
    tui.console.print(
        Panel(
            "\n".join(preview),
            title=f"[bold cyan]Diagnostic Report Preview (First {len(preview)} lines)[/]",
            box=box.ROUNDED,
            border_style="cyan",
            width=tui.get_terminal_width(),
            padding=(0, 1),
        )
    )


# ---------------------------------------------------------------------------
# Submenu Entry Point & Loop
# ---------------------------------------------------------------------------
def run(auto_confirm: bool = False) -> bool:
    """
    Main interactive entry point for the Secure Boot Management subsystem.
    Renders the dedicated submenu using ArchSetup's native interactive menu engine.
    """
    user = os.environ.get("USER", "user")
    host = platform.node()
    kernel_release = platform.release()

    submenu_items = [
        {
            "id": "overview",
            "icon": "󰍹",
            "title": "System Overview",
            "tag": "Inspection",
            "sudo": False,
            "desc": "Inspects UEFI firmware, Setup Mode, ESP partitions, and tools.",
            "details": "Performs read-only inspection of efivarfs, sbctl version, bootloader, kernels, and Windows installation without making any system changes."
        },
        {
            "id": "initial_setup",
            "icon": "󰌌",
            "title": "Initial Secure Boot Setup",
            "tag": "Setup",
            "sudo": True,
            "desc": "End-to-end guided setup: keys, signing, hooks, and firmware enrollment.",
            "details": "Walks through the entire 5-step lifecycle: preflight validation, key creation, binary signing, update hook installation, and firmware key enrollment."
        },
        {
            "id": "keys",
            "icon": "󰌆",
            "title": "Key Management",
            "tag": "Keys",
            "sudo": True,
            "desc": "Manage PK, KEK, and db custom keys, backups, and exports.",
            "details": "View key database inventories, generate new key-pairs, create protected backups, and inspect enrolled firmware certificates."
        },
        {
            "id": "bootloader",
            "icon": "󰒓",
            "title": "Bootloader Management",
            "tag": "Boot",
            "sudo": True,
            "desc": "Inspect and sign active bootloader (systemd-boot, GRUB, rEFInd, Limine).",
            "details": "Discovers active bootloader EFI files, registers them in sbctl database, verifies existing signatures, and configures update handling."
        },
        {
            "id": "signing",
            "icon": "󰏗",
            "title": "Kernel & EFI Signing",
            "tag": "Signing",
            "sudo": True,
            "desc": "Sign and verify all kernels, UKIs, and EFI applications.",
            "details": "Verifies PE/COFF signatures across /boot and ESP. Signs traditional vmlinuz kernels and UKIs with custom keys."
        },
        {
            "id": "updates",
            "icon": "󰓦",
            "title": "Update Automation",
            "tag": "Hooks",
            "sudo": True,
            "desc": "Install or refresh pacman automatic re-signing hooks.",
            "details": "Configures /etc/pacman.d/hooks/99-sbctl-resign.hook so system updates to linux, systemd, or sbctl automatically re-sign all binaries."
        },
        {
            "id": "health",
            "icon": "󰓅",
            "title": "Health Check",
            "tag": "Diagnostics",
            "sudo": False,
            "desc": "Comprehensive 11-point Secure Boot trust chain audit.",
            "details": "Evaluates firmware state, key enrollment, bootloader signatures, kernel integrity, Windows safety, and pacman hooks."
        },
        {
            "id": "recovery",
            "icon": "󰣐",
            "title": "Recovery Center",
            "tag": "Recovery",
            "sudo": False,
            "desc": "Guided diagnostics and recovery recommendations for broken chains.",
            "details": "Provides actionable step-by-step guidance for BIOS Setup Mode, unsigned files, missing hooks, or Windows dual-boot issues."
        },
        {
            "id": "reports",
            "icon": "󰈙",
            "title": "Logs & Diagnostic Reports",
            "tag": "Logging",
            "sudo": False,
            "desc": "Generate and view comprehensive diagnostic reports.",
            "details": "Compiles firmware variables, disk layout, signatures, and health status into persistent report files."
        },
        {
            "id": "back",
            "icon": "󰌍",
            "title": "Back to Main Menu",
            "tag": "Navigation",
            "sudo": False,
            "desc": "Returns to the primary ArchSetup menu.",
            "details": "Preserves state and restores main menu navigation."
        },
    ]

    while True:
        choice = menu.interactive_select_menu(
            "Secure Boot Management",
            submenu_items,
            user=user,
            host=host,
            kernel=kernel_release,
        )

        if choice in ("back", "quit"):
            break

        try:
            if choice == "overview":
                do_overview()
            elif choice == "initial_setup":
                do_initial_setup(auto_confirm=auto_confirm)
            elif choice == "keys":
                do_key_management()
            elif choice == "bootloader":
                do_bootloader_management()
            elif choice == "signing":
                do_signing()
            elif choice == "updates":
                do_updates()
            elif choice == "health":
                do_health_check()
            elif choice == "recovery":
                do_recovery()
            elif choice == "reports":
                do_reports()
        except KeyboardInterrupt:
            tui.console.print()
            tui.log_warning("Operation cancelled by user.")

        menu.pause_for_return("Press any key to return to the Secure Boot menu...")

    return True

