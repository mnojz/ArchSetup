#!/usr/bin/env python3
"""
ArchSetup Main Orchestrator
Modular, interactive post-installation suite for Arch Linux + Hyprland.
"""

import os
import sys
import json
import shutil
import argparse
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
from core.pacman import pm
from core.logger import logger
from tasks import (
    aur_bootstrap,
    mirror_ranking,
    package_installer,
    desktop_integration,
    ambxst_shell,
    dotfiles_deploy,
    system_configuration,
    pacman_tuning,
)

def keep_sudo_alive():
    """Runs a background loop to keep sudo credentials fresh."""
    try:
        subprocess.run(["sudo", "-v"], check=True)
        # Background keepalive
        subprocess.Popen(
            ["bash", "-c", "while true; do sudo -n true; sleep 60; kill -0 $$ || exit; done"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

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

def main():
    parser = argparse.ArgumentParser(
        description="ArchSetup: Modern Post-Installation Suite for Arch Linux + Hyprland",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # Global modifiers
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm all interactive prompts with defaults")
    parser.add_argument("--dry-run", "--check", action="store_true", help="Inspect manifest and packages without making changes")
    parser.add_argument("-c", "--category", type=str, metavar="CAT",
                        help="Filter execution or audit to a specific category (e.g. gaming, multimedia, shell_cli)")
    parser.add_argument("--menu", action="store_true", help="Force launch the interactive arrow-navigable menu")

    # Modular standalone actions
    parser.add_argument("-p", "--packages-only", "--sync-packages", action="store_true",
                        help="Audit packages, compare with manifest, and optionally install missing packages")
    parser.add_argument("-m", "--mirrors-only", "--update-mirrors", action="store_true",
                        help="Benchmark and rank Arch pacman mirrors using rate-mirrors")
    parser.add_argument("-d", "--dotfiles-only", "--sync-dotfiles", action="store_true",
                        help="Pull latest dotfiles from GitHub and apply configurations")
    parser.add_argument("-s", "--system-only", "--tune-system", action="store_true",
                        help="Re-apply system configurations (mkinitcpio, bootloader, SDDM, MPV)")
    parser.add_argument("--desktop-only", "--fix-mime", action="store_true",
                        help="Repair Dolphin file associations, menus, and rebuild KSycoca6 cache")
    parser.add_argument("--doctor", action="store_true",
                        help="Run system diagnostic health check (Hyprland, PipeWire, drivers, microcode)")
    parser.add_argument("--tune-pacman", action="store_true",
                        help="Accelerate package downloads with parallel streams (ParallelDownloads=5)")
    parser.add_argument("--clean-cache", action="store_true",
                        help="Clean pacman/yay package cache and remove orphaned packages")
    parser.add_argument("-l", "--view-log", action="store_true",
                        help="Display the most recent installation log preview")
    parser.add_argument("--full", action="store_true",
                        help="Run the complete automated end-to-end installation pipeline")

    # Skip flags for full installation
    parser.add_argument("--skip-mirrors", action="store_true", help="Skip mirrorlist ranking during full run")
    parser.add_argument("--skip-dotfiles", action="store_true", help="Skip dotfiles deployment during full run")
    parser.add_argument("--skip-system", action="store_true", help="Skip system & boot tuning during full run")

    args = parser.parse_args()

    # System metadata
    user = os.environ.get("USER", os.getlogin() if hasattr(os, "getlogin") else "user")
    host = platform.node()
    kernel = platform.release()

    manifest_path, categories = load_manifest()

    # Determine whether to trigger the Interactive Navigation Menu
    action_flags = [
        args.packages_only,
        args.mirrors_only,
        args.dotfiles_only,
        args.system_only,
        args.desktop_only,
        args.doctor,
        args.tune_pacman,
        args.clean_cache,
        args.view_log,
        args.dry_run,
        args.full
    ]

    has_explicit_action = any(action_flags)
    is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if (not has_explicit_action and is_interactive and not args.yes) or args.menu:
        # Render Visual Banner
        tui.show_banner(user, host, kernel)

        menu_options = [
            ("full", "🚀 Full Installation Suite", "Run complete post-install pipeline (all 8 steps)"),
            ("packages", "📦 Audit & Sync Packages", "Compare installed vs manifest packages and sync missing"),
            ("categories", "📋 Category Checklist", "Choose specific package categories interactively"),
            ("doctor", "🩺 System Diagnostic Doctor", "Audit Hyprland, audio, microcode, drivers, and services"),
            ("tune_pacman", "⚡ Pacman Turbo Boost", "Enable 5x parallel downloads, color, and ILoveCandy"),
            ("mirrors", "🌐 Mirrorlist Optimization", "Benchmark and rank fastest pacman mirrors"),
            ("dotfiles", "🎨 Deploy Dotfiles", "Pull and configure personal Hyprland & app dotfiles"),
            ("desktop", "🛠️ Desktop & MIME Integration", "Repair Dolphin associations, KSycoca6, and icon cache"),
            ("system", "⚙️ System Tuning & Bootloader", "Configure mkinitcpio, systemd-boot, and SDDM theme"),
            ("cleanup", "🧹 Maintenance Cache Cleanup", "Clean pacman/yay package cache and purge orphans"),
            ("log", "📜 View Installation Logs", "Inspect recent terminal log outputs"),
            ("quit", "🚪 Exit", "Exit setup"),
        ]

        choice = menu.interactive_select_menu("Arch Linux Setup Main Menu", menu_options)

        if choice == "quit":
            tui.log_info("Exited ArchSetup. Goodbye!")
            sys.exit(0)
        elif choice == "full":
            args.full = True
        elif choice == "packages":
            args.packages_only = True
        elif choice == "categories":
            selected_cats = menu.interactive_checklist_menu("Select Software Categories to Install", categories)
            chosen = [c for c in selected_cats if c.get("enabled", True)]
            if not chosen:
                tui.log_warning("No categories selected.")
                sys.exit(0)

            all_pkgs = []
            for c in chosen:
                all_pkgs.extend(c.get("packages", []))
            missing = [p for p in all_pkgs if not pm.is_installed(p)]

            tui.log_info(f"Selected {len(chosen)} categories ({len(all_pkgs)} total packages)")
            if not missing:
                tui.log_success("All packages in selected categories are already installed!")
                sys.exit(0)

            tui.log_warning(f"Found {len(missing)} missing package(s) in selected categories.")
            if tui.prompt_yes_no(f"Install the {len(missing)} missing package(s) now?", default=True, auto_confirm=args.yes):
                tui.log_running("Verifying sudo authentication...")
                keep_sudo_alive()
                aur_bootstrap.run(auto_confirm=args.yes)
                package_installer.install_package_batch("Selected Categories", missing)
                tui.show_summary_panel(pm.success_packages, pm.skipped_packages, pm.failed_packages, logger.log_path_str)
            sys.exit(0)
        elif choice == "doctor":
            args.doctor = True
        elif choice == "tune_pacman":
            args.tune_pacman = True
        elif choice == "mirrors":
            args.mirrors_only = True
        elif choice == "dotfiles":
            args.dotfiles_only = True
        elif choice == "desktop":
            args.desktop_only = True
        elif choice == "system":
            args.system_only = True
        elif choice == "cleanup":
            args.clean_cache = True
        elif choice == "log":
            args.view_log = True

    # Render Visual Banner if not rendered yet
    if not (not has_explicit_action and is_interactive and not args.yes) and not args.menu:
        tui.show_banner(user, host, kernel)

    # -------------------------------------------------------------------------
    # Action: View Log
    # -------------------------------------------------------------------------
    if args.view_log:
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
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Diagnostic Doctor
    # -------------------------------------------------------------------------
    if args.doctor:
        tui.show_step_header(1, 1, "System Diagnostic Doctor")
        checks = hardware.run_diagnostics()
        tui.show_diagnostics_table(checks)
        warnings = [c for c in checks if c["status"] in ("WARN", "FAIL")]
        if not warnings:
            tui.log_success("All diagnostic health checks passed successfully!")
        else:
            tui.log_warning(f"Found {len(warnings)} diagnostic item(s) to review.")
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Pacman Turbo Tuning
    # -------------------------------------------------------------------------
    if args.tune_pacman:
        tui.log_running("Verifying sudo authentication...")
        keep_sudo_alive()
        tui.show_step_header(1, 1, "Pacman Parallel Downloads & Visuals Tuning")
        pacman_tuning.run(auto_confirm=args.yes)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Clean Package Cache & Orphans
    # -------------------------------------------------------------------------
    if args.clean_cache:
        tui.log_running("Verifying sudo authentication...")
        keep_sudo_alive()
        tui.show_step_header(1, 1, "Package Cache & Orphan Cleanup")

        res = subprocess.run(["pacman", "-Qtdq"], capture_output=True, text=True, check=False)
        orphans = res.stdout.strip().splitlines() if res.stdout.strip() else []
        if orphans:
            tui.log_info(f"Found {len(orphans)} orphaned package(s): {', '.join(orphans[:10])}")
            if tui.prompt_yes_no("Remove orphaned packages?", default=True, auto_confirm=args.yes):
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
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Mirrors Only
    # -------------------------------------------------------------------------
    if args.mirrors_only:
        tui.log_running("Verifying sudo authentication...")
        keep_sudo_alive()
        tui.show_step_header(1, 1, "Mirrorlist Optimization")
        mirror_ranking.run(auto_confirm=args.yes)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Dotfiles Only
    # -------------------------------------------------------------------------
    if args.dotfiles_only:
        tui.show_step_header(1, 1, "User Dotfiles Deployment")
        dotfiles_deploy.run(auto_confirm=args.yes)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Desktop / MIME Repair Only
    # -------------------------------------------------------------------------
    if args.desktop_only:
        tui.log_running("Verifying sudo authentication...")
        keep_sudo_alive()
        tui.show_step_header(1, 1, "Desktop & MIME Integration")
        desktop_integration.run(auto_confirm=args.yes)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: System Tuning Only
    # -------------------------------------------------------------------------
    if args.system_only:
        tui.log_running("Verifying sudo authentication...")
        keep_sudo_alive()
        tui.show_step_header(1, 1, "System Configuration & Hardware Tuning")
        system_configuration.run(PROJECT_ROOT / "assets", auto_confirm=args.yes)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Package Audit & Selective Sync Mode
    # -------------------------------------------------------------------------
    if args.packages_only:
        filtered_categories = categories
        if args.category:
            cat_filter = args.category.lower()
            filtered_categories = [
                c for c in categories
                if cat_filter in c.get("id", "").lower() or cat_filter in c.get("name", "").lower()
            ]
            if not filtered_categories:
                tui.log_error(f"No category matching '{args.category}' found in packages.json")
                sys.exit(1)

        audit_results = []
        all_missing = []
        all_installed = 0
        all_total = 0

        for cat in filtered_categories:
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
            tui.log_success(f"All {all_total} packages in audited categories are already installed!")
            sys.exit(0)

        tui.log_warning(f"Found {len(all_missing)} missing package(s) across selected categories.")
        if tui.prompt_yes_no(f"Install the {len(all_missing)} missing package(s) now?", default=True, auto_confirm=args.yes):
            tui.log_running("Verifying sudo authentication...")
            keep_sudo_alive()
            aur_bootstrap.run(auto_confirm=args.yes)
            package_installer.install_package_batch("Missing Packages", all_missing)
            tui.show_summary_panel(pm.success_packages, pm.skipped_packages, pm.failed_packages, logger.log_path_str)
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Action: Dry-Run Inspection
    # -------------------------------------------------------------------------
    if args.dry_run:
        tui.show_manifest_table(categories)
        all_pkgs = []
        for cat in categories:
            if cat.get("enabled", True):
                all_pkgs.extend(cat.get("packages", []))

        installed = [p for p in all_pkgs if pm.is_installed(p)]
        pending = [p for p in all_pkgs if not pm.is_installed(p)]

        from rich.panel import Panel
        from rich import box
        summary_text = (
            f"[bold]Total Configured:[/]  [white]{len(all_pkgs)} packages[/]\n"
            f"[bold]Already Installed:[/] [green]{len(installed)} packages[/]\n"
            f"[bold]Pending Install:[/]   [yellow]{len(pending)} packages[/]"
        )
        tui.console.print(Panel(
            summary_text,
            title="[bold cyan]Dry-Run Inspection[/]",
            box=box.ROUNDED,
            border_style="cyan",
            width=tui.get_terminal_width(),
            padding=(0, 2)
        ))
        tui.console.print()
        tui.log_success("Inspection complete. No changes were made to your system.")
        sys.exit(0)

    # -------------------------------------------------------------------------
    # Full Installation Pipeline
    # -------------------------------------------------------------------------
    # Check network connectivity
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
        tui.log_dim("Please connect to Wi-Fi/Ethernet (e.g. via iwctl or nmcli) before installation.")
        if not tui.prompt_yes_no("Proceed anyway without verified internet?", default=False, auto_confirm=args.yes):
            tui.log_error("Installation aborted. Connect to internet and try again.")
            sys.exit(1)

    # Elevate sudo
    tui.log_running("Verifying sudo authentication...")
    keep_sudo_alive()

    TOTAL_STEPS = 8
    current_step = 1

    # Step 1: Pacman Turbo Boost
    tui.show_step_header(current_step, TOTAL_STEPS, "Pacman Parallel Downloads & Visuals Tuning")
    pacman_tuning.run(auto_confirm=args.yes)
    current_step += 1

    # Step 2: AUR Helper
    tui.show_step_header(current_step, TOTAL_STEPS, "AUR Package Manager Bootstrap")
    aur_bootstrap.run(auto_confirm=args.yes)
    current_step += 1

    # Step 3: Mirrors
    tui.show_step_header(current_step, TOTAL_STEPS, "Mirrorlist Optimization")
    if not args.skip_mirrors:
        mirror_ranking.run(auto_confirm=args.yes)
    else:
        tui.log_info("Mirror optimization skipped by flag")
    current_step += 1

    # Step 4: Packages
    tui.show_step_header(current_step, TOTAL_STEPS, "Software Packages Installation")
    tui.show_manifest_table(categories)
    package_installer.run(manifest_path, auto_confirm=args.yes, target_category=args.category, categories_list=categories)
    current_step += 1

    # Step 5: Desktop & MIME
    tui.show_step_header(current_step, TOTAL_STEPS, "Desktop & MIME Integration")
    desktop_integration.run(auto_confirm=args.yes)
    current_step += 1

    # Step 6: Ambxst Shell
    tui.show_step_header(current_step, TOTAL_STEPS, "Ambxst Shell Environment")
    ambxst_shell.run(auto_confirm=args.yes)
    current_step += 1

    # Step 7: Dotfiles
    tui.show_step_header(current_step, TOTAL_STEPS, "User Dotfiles & Styling")
    if not args.skip_dotfiles:
        dotfiles_deploy.run(auto_confirm=args.yes)
    else:
        tui.log_info("Dotfiles installation skipped by flag")
    current_step += 1

    # Step 8: System Tuning
    tui.show_step_header(current_step, TOTAL_STEPS, "System Configuration & Hardware Tuning")
    if not args.skip_system:
        system_configuration.run(PROJECT_ROOT / "assets", auto_confirm=args.yes)
    else:
        tui.log_info("System tuning skipped by flag")

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

    if tui.prompt_yes_no("Reboot system now to apply kernel, boot, and theme changes?", default=False, auto_confirm=args.yes):
        tui.log_running("Rebooting system...")
        subprocess.run(["sudo", "reboot"])
    else:
        tui.log_info("Reboot postponed. Enjoy your new Arch Linux + Hyprland setup!")

if __name__ == "__main__":
    main()
