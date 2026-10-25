#!/usr/bin/env python3
"""
ArchSetup Main Orchestrator
Pure interactive post-installation suite for Arch Linux + Hyprland.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import tui
from core import menu
from core import hardware
from core import auth
from core.pacman import pm
from core.logger import logger
from tasks import (
    aur_bootstrap,
    mirror_ranking,
    package_installer,
    desktop_integration,
    ambxst_shell,
    dotfiles_deploy,
    fluent_uosc,
    system_configuration,
    pacman_tuning,
)

def load_manifest() -> Tuple[Path, List[Dict[str, Any]]]:
    """Loads default packages manifest and merges local overrides if present."""
    manifest_path = PROJECT_ROOT / "packages.json"
    local_manifest = PROJECT_ROOT / "packages.local.json"
    categories = []

    if manifest_path.is_file():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                categories = json.load(f).get("categories", [])
        except Exception as e:
            tui.log_error(f"Failed to read packages.json: {e}")

    if local_manifest.is_file():
        try:
            with open(local_manifest, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                local_cats = local_data.get("categories", [])
                cat_map = {c["id"]: c for c in categories if "id" in c}
                for lc in local_cats:
                    lid = lc.get("id")
                    if lid in cat_map:
                        existing = set(cat_map[lid].get("packages", []))
                        for p in lc.get("packages", []):
                            if p not in existing:
                                cat_map[lid]["packages"].append(p)
                    else:
                        categories.append(lc)
            tui.log_info(f"Merged local custom manifest: [cyan]{local_manifest.name}[/]")
        except Exception as e:
            tui.log_warning(f"Error loading packages.local.json: {e}")

    return manifest_path, categories

# -----------------------------------------------------------------------------
# Modular Action Handlers
# -----------------------------------------------------------------------------

def do_doctor():
    """Runs read-only system diagnostic health checks."""
    tui.show_step_header(1, 1, "System Diagnostic Doctor")
    checks = hardware.run_diagnostics()
    tui.show_diagnostics_table(checks)
    warnings = [c for c in checks if c["status"] in ("WARN", "FAIL")]
    if not warnings:
        tui.log_success("All diagnostic health checks passed successfully!")
    else:
        tui.log_warning(f"Found {len(warnings)} diagnostic item(s) to review.")

def do_pacman_tuning():
    """Enables ParallelDownloads=5, Color, and ILoveCandy in pacman.conf."""
    if not auth.request_sudo_auth("Pacman Turbo Boost"):
        tui.log_warning("Operation cancelled: Sudo authorization not granted.")
        return
    tui.show_step_header(1, 1, "Pacman Parallel Downloads & Visuals Tuning")
    pacman_tuning.run()

def do_mirrors():
    """Benchmarks and ranks Arch mirrors using rate-mirrors."""
    if not auth.request_sudo_auth("Mirrorlist Optimization"):
        tui.log_warning("Operation cancelled: Sudo authorization not granted.")
        return
    tui.show_step_header(1, 1, "Mirrorlist Optimization")
    mirror_ranking.run()

def do_dotfiles():
    """Deploys bundled user dotfiles and syncs Fluent UOSC."""
    tui.show_step_header(1, 2, "Bundled User Dotfiles Deployment")
    dotfiles_deploy.run()
    tui.show_step_header(2, 2, "Fluent UOSC Player Interface")
    fluent_uosc.run()

def do_desktop():
    """Repairs Dolphin actions, KSycoca6 cache, and desktop MIME links."""
    tui.show_step_header(1, 1, "Desktop & MIME Integration")
    desktop_integration.run()

def do_system():
    """Reconfigures initramfs, systemd-boot, Fish shell, and SDDM."""
    if not auth.request_sudo_auth("System Configuration & Hardware Tuning"):
        tui.log_warning("Operation cancelled: Sudo authorization not granted.")
        return
    tui.show_step_header(1, 1, "System Configuration & Hardware Tuning")
    system_configuration.run(PROJECT_ROOT / "assets")

def do_clean_cache():
    """Purges orphaned packages and trims pacman and AUR caches."""
    if not auth.request_sudo_auth("Package Cache & Orphan Cleanup"):
        tui.log_warning("Operation cancelled: Sudo authorization not granted.")
        return
    tui.show_step_header(1, 1, "Package Cache & Orphan Cleanup")

    res = subprocess.run(["pacman", "-Qtdq"], capture_output=True, text=True, check=False)
    orphans = res.stdout.strip().splitlines() if res.stdout.strip() else []
    if orphans:
        tui.log_info(f"Found {len(orphans)} orphaned package(s): {', '.join(orphans[:10])}")
        if tui.prompt_yes_no("Remove orphaned packages?", default=True):
            logger.run_cmd(["sudo", "pacman", "-Rns", "--noconfirm"] + orphans, check=False)
            tui.log_success("Orphaned packages removed")
    else:
        tui.log_success("No orphaned packages found")

    tui.log_running("Cleaning pacman cache...")
    logger.run_cmd(["sudo", "pacman", "-Sc", "--noconfirm"], check=False)
    aur_tool = pm.get_aur_helper()
    if aur_tool:
        tui.log_running(f"Cleaning {aur_tool} cache...")
        logger.run_cmd([aur_tool, "-Sc", "--noconfirm"], check=False)
    tui.log_success("Package cache cleaned successfully")

def do_view_log():
    """Displays the last 35 lines of the most recent installation log."""
    latest_log = logger.get_latest_existing_log()
    if latest_log and latest_log.is_file():
        tui.log_info(f"Most recent log file: [white]{latest_log}[/]")
        content = latest_log.read_text(encoding="utf-8").splitlines()
        last_lines = content[-35:] if len(content) > 35 else content
        from rich.panel import Panel
        tui.console.print(Panel(
            "\n".join(last_lines),
            title=f"[bold cyan]Log Preview (Last {len(last_lines)} lines)[/]",
            border_style="cyan"
        ))
    else:
        tui.log_info(f"Log directory: [white]{logger.log_path_str}[/]")
        tui.log_warning("No previous non-empty installation logs found.")

def do_packages(categories: List[Dict[str, Any]]):
    """Audits installed packages against manifest and offers selective install."""
    audit_results = []
    all_missing = []
    all_installed = 0
    all_total = 0

    for cat in categories:
        if not cat.get("enabled", True):
            continue
        pkgs = cat.get("packages", [])
        installed = [p for p in pkgs if pm.is_installed(p)]
        missing = [p for p in pkgs if not pm.is_installed(p)]
        all_installed += len(installed)
        all_total += len(pkgs)
        all_missing.extend(missing)
        audit_results.append({
            "icon": cat.get("icon", "󰏖"),
            "name": cat.get("name", "Unknown"),
            "total": len(pkgs),
            "installed": len(installed),
            "missing": missing
        })

    tui.show_package_audit_table(audit_results)

    if not all_missing:
        tui.log_success(f"All {all_total} packages across configured categories are already installed!")
        return

    tui.log_warning(f"Found {len(all_missing)} missing package(s) across categories.")
    if tui.prompt_yes_no(f"Install the {len(all_missing)} missing package(s) now?", default=True):
        if not auth.request_sudo_auth("Installing Missing Packages"):
            tui.log_warning("Installation cancelled: Sudo authorization not granted.")
            return
        aur_bootstrap.run()
        package_installer.install_package_batch("Missing Packages", all_missing)
        tui.show_summary_panel(pm.success_packages, pm.skipped_packages, pm.failed_packages, logger.log_path_str)

def do_checklist(categories: List[Dict[str, Any]], user: str, host: str, kernel: str):
    """Interactive multi-select category checklist."""
    selected_cats = menu.interactive_checklist_menu(
        "Select Software Categories to Install",
        categories,
        user=user,
        host=host,
        kernel=kernel
    )
    if selected_cats is None:
        tui.log_dim("Category selection cancelled.")
        return

    chosen = [c for c in selected_cats if c.get("enabled", True)]
    if not chosen:
        tui.log_warning("No categories selected.")
        return

    all_pkgs = []
    for c in chosen:
        all_pkgs.extend(c.get("packages", []))
    missing = [p for p in all_pkgs if not pm.is_installed(p)]

    tui.log_info(f"Selected {len(chosen)} categories ({len(all_pkgs)} total packages)")
    if not missing:
        tui.log_success("All packages in selected categories are already installed!")
        return

    tui.log_warning(f"Found {len(missing)} missing package(s) in selected categories.")
    if tui.prompt_yes_no(f"Install the {len(missing)} missing package(s) now?", default=True):
        if not auth.request_sudo_auth("Installing Selected Categories"):
            tui.log_warning("Installation cancelled: Sudo authorization not granted.")
            return
        aur_bootstrap.run()
        package_installer.install_package_batch("Selected Categories", missing)
        tui.show_summary_panel(pm.success_packages, pm.skipped_packages, pm.failed_packages, logger.log_path_str)

def do_full(manifest_path: Path, categories: List[Dict[str, Any]]):
    """Executes the complete 8-step post-installation pipeline."""
    def has_network() -> bool:
        import socket
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=3)
            return True
        except OSError:
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=3)
                return True
            except OSError:
                return False

    if not has_network():
        tui.log_warning("No active internet connection detected!")
        tui.log_dim("Please connect to Wi-Fi/Ethernet before full installation.")
        if not tui.prompt_yes_no("Proceed anyway without verified internet?", default=False):
            tui.log_error("Installation aborted.")
            return

    if not auth.request_sudo_auth("Full Post-Installation Suite"):
        tui.log_warning("Full installation cancelled: Sudo authorization not granted.")
        return

    TOTAL_STEPS = 9
    current_step = 1

    # Step 1: Pacman Turbo Boost
    tui.show_step_header(current_step, TOTAL_STEPS, "Pacman Parallel Downloads & Visuals Tuning")
    pacman_tuning.run()
    current_step += 1

    # Step 2: AUR Helper
    tui.show_step_header(current_step, TOTAL_STEPS, "AUR Package Manager Bootstrap")
    aur_bootstrap.run()
    current_step += 1

    # Step 3: Mirrors
    tui.show_step_header(current_step, TOTAL_STEPS, "Mirrorlist Optimization")
    mirror_ranking.run()
    current_step += 1

    # Step 4: Packages
    tui.show_step_header(current_step, TOTAL_STEPS, "Software Packages Installation")
    tui.show_manifest_table(categories)
    package_installer.run(manifest_path, categories_list=categories)
    current_step += 1

    # Step 5: Desktop & MIME
    tui.show_step_header(current_step, TOTAL_STEPS, "Desktop & MIME Integration")
    desktop_integration.run()
    current_step += 1

    # Step 6: Ambxst Shell
    tui.show_step_header(current_step, TOTAL_STEPS, "Ambxst Shell Environment")
    ambxst_shell.run()
    current_step += 1

    # Step 7: Dotfiles
    tui.show_step_header(current_step, TOTAL_STEPS, "Bundled User Dotfiles & Styling")
    dotfiles_deploy.run()
    current_step += 1

    # Step 8: Fluent UOSC
    tui.show_step_header(current_step, TOTAL_STEPS, "Fluent UOSC Player Interface")
    fluent_uosc.run()
    current_step += 1

    # Step 9: System Tuning
    tui.show_step_header(current_step, TOTAL_STEPS, "System Configuration & Hardware Tuning")
    system_configuration.run(PROJECT_ROOT / "assets")

    # Post-Hooks
    if shutil_which := shutil.which("xdg-user-dirs-update"):
        subprocess.run([shutil_which], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if shutil_which := shutil.which("hyprctl"):
        subprocess.run([shutil_which, "reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Summary Panel
    tui.show_summary_panel(
        pm.success_packages,
        pm.skipped_packages,
        pm.failed_packages,
        logger.log_path_str
    )

    if tui.prompt_yes_no("Reboot system now to apply kernel, boot, and theme changes?", default=False):
        tui.log_running("Rebooting system...")
        subprocess.run(["sudo", "reboot"])
    else:
        tui.log_info("Reboot postponed. Enjoy your new Arch Linux + Hyprland setup!")


def main():
    if not sys.stdin.isatty():
        tui.log_error("ArchSetup requires an interactive terminal (TTY) for keyboard navigation.")
        sys.exit(1)

    # System metadata
    user = os.environ.get("USER", os.getlogin() if hasattr(os, "getlogin") else "user")
    host = platform.node()
    kernel = platform.release()

    manifest_path, categories = load_manifest()

    menu_items = [
        {
            "id": "full",
            "icon": "󰑣",
            "title": "Full Installation Suite",
            "tag": "All-in-One",
            "sudo": True,
            "desc": "Runs the complete automated post-installation pipeline from start to finish.",
            "details": "Executes all 9 sequential phases: pacman turbo boost, yay bootstrap, mirrorlist ranking, package manifests, Dolphin MIME integration, Ambxst shell, bundled dotfiles, Fluent UOSC, and system/boot configuration."
        },
        {
            "id": "packages",
            "icon": "󰏖",
            "title": "Audit & Sync Packages",
            "tag": "Package Mgmt",
            "sudo": False,
            "desc": "Audits manifest packages against currently installed packages.",
            "details": "Scans all 7 categories via in-memory cache in <0.05s. Displays installed counts and offers to selectively install any missing software."
        },
        {
            "id": "categories",
            "icon": "󰒅",
            "title": "Category Checklist",
            "tag": "Selective",
            "sudo": False,
            "desc": "Interactive multi-select checklist to install specific categories.",
            "details": "Toggle categories (Shell, Hyprland, Multimedia, Apps, Themes, Drivers, Gaming) with Space, then installs only the packages in selected categories."
        },
        {
            "id": "doctor",
            "icon": "󰓅",
            "title": "System Diagnostic Doctor",
            "tag": "Diagnostics",
            "sudo": False,
            "desc": "Comprehensive read-only subsystem and hardware health check.",
            "details": "Validates active Hyprland session, PipeWire & WirePlumber audio binaries, CPU microcode (Intel/AMD), VA-API acceleration, and pacman settings."
        },
        {
            "id": "tune_pacman",
            "icon": "󰛄",
            "title": "Pacman Turbo Boost",
            "tag": "Optimization",
            "sudo": True,
            "desc": "Accelerates pacman downloads with 5 concurrent parallel streams.",
            "details": "Enables ParallelDownloads = 5, Color output, and ILoveCandy animated progress bar in /etc/pacman.conf with automatic safety backup."
        },
        {
            "id": "mirrors",
            "icon": "󰖟",
            "title": "Mirrorlist Optimization",
            "tag": "Networking",
            "sudo": True,
            "desc": "Benchmarks and ranks fastest pacman mirrors via rate-mirrors.",
            "details": "Tests speed and latency of worldwide Arch mirrors, applies the fastest mirrors to /etc/pacman.d/mirrorlist, and synchronizes package databases."
        },
        {
            "id": "dotfiles",
            "icon": "󰏔",
            "title": "Deploy User Dotfiles",
            "tag": "Personalization",
            "sudo": False,
            "desc": "Deploys bundled Hyprland, Kitty, Fish, and desktop dotfiles via GNU Stow.",
            "details": "Links bundled user dotfiles directly into $HOME using GNU Stow. Edits made in ~/.config automatically stay in sync with the ArchSetup dotfiles module."
        },
        {
            "id": "desktop",
            "icon": "󰘚",
            "title": "Desktop & MIME Integration",
            "tag": "Desktop Fix",
            "sudo": False,
            "desc": "Repairs Dolphin file associations, menus, and rebuilds KSycoca6 cache.",
            "details": "Fixes broken file associations for Dolphin, registers XDG MIME types, generates system application desktop menus, and clears stale KDE Sycoca caches."
        },
        {
            "id": "system",
            "icon": "󰒓",
            "title": "System Tuning & Bootloader",
            "tag": "Hardware & Boot",
            "sudo": True,
            "desc": "Configures initramfs, bootloader kernel cmdline, SDDM, and Fish shell.",
            "details": "Preserves disk encryption (LUKS/LVM) hooks while updating mkinitcpio.conf, injects nvidia_drm.modeset=1 conditionally, applies Silent SDDM theme, and sets Fish shell."
        },
        {
            "id": "cleanup",
            "icon": "󰃢",
            "title": "Maintenance Cache Cleanup",
            "tag": "Maintenance",
            "sudo": True,
            "desc": "Removes orphaned packages and clears pacman and AUR caches.",
            "details": "Identifies unneeded orphaned dependencies via pacman -Qtdq with user confirmation, and runs cache trimming on pacman and yay directories to free up disk storage."
        },
        {
            "id": "log",
            "icon": "󰈙",
            "title": "View Installation Logs",
            "tag": "Logging",
            "sudo": False,
            "desc": "Inspects recent installation and execution log output.",
            "details": "Displays the last 35 lines of the most recent setup session log file inside a styled preview card, including exact command outputs and timestamps."
        },
        {
            "id": "quit",
            "icon": "󰈆",
            "title": "Exit Setup",
            "tag": "Quit",
            "sudo": False,
            "desc": "Exits ArchSetup and returns to your shell prompt.",
            "details": "Restores cursor and terminal settings cleanly and terminates execution."
        }
    ]

    while True:
        choice = menu.interactive_select_menu(
            "Arch Linux Setup Main Menu",
            menu_items,
            user=user,
            host=host,
            kernel=kernel
        )

        if choice == "quit":
            tui.log_info("Exited ArchSetup. Goodbye!")
            sys.exit(0)

        try:
            if choice == "full":
                do_full(manifest_path, categories)
            elif choice == "packages":
                do_packages(categories)
            elif choice == "categories":
                do_checklist(categories, user=user, host=host, kernel=kernel)
            elif choice == "doctor":
                do_doctor()
            elif choice == "tune_pacman":
                do_pacman_tuning()
            elif choice == "mirrors":
                do_mirrors()
            elif choice == "dotfiles":
                do_dotfiles()
            elif choice == "desktop":
                do_desktop()
            elif choice == "system":
                do_system()
            elif choice == "cleanup":
                do_clean_cache()
            elif choice == "log":
                do_view_log()
        except KeyboardInterrupt:
            tui.console.print()
            tui.log_warning("Operation interrupted by user.")

        menu.pause_for_return("Press any key to return to the main menu...")


if __name__ == "__main__":
    main()
