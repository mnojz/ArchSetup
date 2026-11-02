"""
Task: System Tuning & Hardware Configuration
Applies mkinitcpio, systemd-boot, Fish shell, and SDDM theming.
"""

import os
import getpass
import pwd
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from core.tui import log_info, log_success, log_warning, log_running, log_dim, log_error
from core.logger import logger
from core.pacman import pm
from core.hardware import detect_gpu

def run(assets_dir: Path, auto_confirm: bool = False) -> bool:
    try:
        return _configure(assets_dir, auto_confirm)
    except (OSError, subprocess.SubprocessError) as exc:
        log_error(f"System configuration stopped: {exc}. Check {logger.log_path_str}")
        return False


def _configure(assets_dir: Path, auto_confirm: bool = False) -> bool:
    user = getpass.getuser()

    # Detect hardware for conditional options
    gpu_list = detect_gpu()
    has_nvidia = any(g["type"] == "NVIDIA" for g in gpu_list)

    # 1. Conflicting Package Removal
    conflicting = ["dunst"]
    to_remove = [p for p in conflicting if pm.is_installed(p)]
    if to_remove:
        log_running(f"Removing conflicting packages: {', '.join(to_remove)}...")
        logger.run_cmd(["sudo", "pacman", "-Rns", "--noconfirm"] + to_remove)
        log_success("Conflicting packages removed")

    # 2. Default User Shell (Fish)
    fish_bin = shutil.which("fish")
    if fish_bin:
        try:
            current_shell = pwd.getpwnam(user).pw_shell
            if current_shell != fish_bin:
                log_running(f"Configuring Fish as default shell for {user}...")
                with open("/etc/shells", "r", encoding="utf-8") as f:
                    shells = f.read()
                if fish_bin not in shells:
                    logger.run_cmd(["bash", "-c", f"echo {fish_bin} | sudo tee -a /etc/shells"])
                logger.run_cmd(["sudo", "chsh", "-s", fish_bin, user])
                log_success("Default shell switched to Fish")
            else:
                log_dim("Fish is already the default shell")
        except KeyError:
            log_error(f"User account not found: {user}")
            return False

    # Preserve the installed boot/storage configuration in its entirety. A generic
    # template cannot safely reconstruct encryption, RAID, resume or custom hooks.
    system_mkinit = Path("/etc/mkinitcpio.conf")
    if not system_mkinit.is_file():
        log_error("Existing /etc/mkinitcpio.conf not found; refusing to generate a replacement.")
        return False
    backup_file = f"{system_mkinit}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    logger.run_cmd(["sudo", "cp", "-p", str(system_mkinit), backup_file])
    log_info(f"Preserving existing initramfs configuration; backup: {backup_file}")
    log_running("Regenerating initramfs images (mkinitcpio -P)...")
    code, _ = logger.run_cmd(["sudo", "mkinitcpio", "-P"], check=False)
    if code != 0:
        log_error(
            "Initramfs rebuild failed. Boot configuration changes stopped; no reboot will be offered. "
            f"The original configuration remains at {system_mkinit} and {backup_file}. "
            "Repair the reported build error and successfully run sudo mkinitcpio -P before rebooting."
        )
        return False
    log_success("initramfs regenerated successfully")

    # 4. systemd-boot Configuration
    boot_loader_dir = Path("/boot/loader")
    if boot_loader_dir.is_dir():
        log_running("systemd-boot detected; updating bootloader parameters...")
        loader_asset = assets_dir / "boot/loader.conf"
        if loader_asset.is_file():
            logger.run_cmd(["sudo", "cp", str(loader_asset), "/boot/loader/loader.conf"])

        entries_dir = boot_loader_dir / "entries"
        if entries_dir.is_dir():
            entries = list(entries_dir.glob("*.conf"))
            if entries:
                # Prefer primary entry over fallback entries
                non_fallback = [e for e in entries if "fallback" not in e.name.lower()]
                entry_file = non_fallback[0] if non_fallback else entries[0]
                backup_entry = f"{entry_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                logger.run_cmd(["sudo", "cp", str(entry_file), backup_entry])

                extra_opts_list = ["quiet", "splash", "loglevel=3", "systemd.show_status=error", "rd.udev.log_level=3", "vt.global_cursor_default=0"]
                if has_nvidia:
                    extra_opts_list.append("nvidia_drm.modeset=1")
                    log_info("Detected NVIDIA GPU: added nvidia_drm.modeset=1 to kernel cmdline")
                extra_opts = " ".join(extra_opts_list)
                sed_script = f"/^options / {{ s/quiet//g; s/splash//g; s/loglevel=3//g; s/systemd.show_status=error//g; s/rd.udev.log_level=3//g; s/vt.global_cursor_default=0//g; s/nvidia_drm.modeset=1//g; s/[[:space:]]\\+/ /g; s/[[:space:]]$//; s/$/ {extra_opts}/ }}"
                logger.run_cmd(["sudo", "sed", "-i", sed_script, str(entry_file)])
                log_success(f"Kernel options updated in {entry_file.name}")
    else:
        log_dim("systemd-boot not detected; skipping bootloader options")

    # 5. SDDM Display Manager Setup
    if shutil.which("sddm"):
        log_running("Configuring SDDM service & theme...")
        logger.run_cmd(["sudo", "mkdir", "-p", "/etc/systemd/system/sddm.service.d"])
        logger.run_cmd(["sudo", "mkdir", "-p", "/etc/sddm.conf.d"])

        override_asset = assets_dir / "sddm/override.conf"
        if override_asset.is_file():
            logger.run_cmd(["sudo", "cp", str(override_asset), "/etc/systemd/system/sddm.service.d/override.conf"])

        face_icon = assets_dir / "sddm/.face.icon"
        if face_icon.is_file():
            shutil.copy(face_icon, Path.home() / ".face.icon")

        logger.run_cmd(["bash", "-c", "echo -e '[Theme]\nCurrent=silent' | sudo tee /etc/sddm.conf.d/theme.conf >/dev/null"])
        logger.run_cmd(["bash", "-c", "echo -e '[General]\nNumlock=on' | sudo tee /etc/sddm.conf.d/general.conf >/dev/null"])

        silent_theme_dir = Path("/usr/share/sddm/themes/silent")
        if silent_theme_dir.is_dir():
            metadata_asset = assets_dir / "sddm/metadata.desktop"
            if metadata_asset.is_file():
                logger.run_cmd(["sudo", "cp", str(metadata_asset), str(silent_theme_dir / "metadata.desktop")])

            avatar_script = silent_theme_dir / "change_avatar.sh"
            if avatar_script.is_file() and face_icon.is_file():
                logger.run_cmd(["sudo", str(avatar_script), user, str(face_icon)])
            log_success("SDDM Silent theme & avatar configured")
        else:
            log_warning("SDDM silent theme directory not found")

        logger.run_cmd(["sudo", "systemctl", "daemon-reload"])
        logger.run_cmd(["sudo", "systemctl", "enable", "sddm"])

        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
            log_info("SDDM enabled. Service restart deferred to reboot (protecting current GUI session).")
        else:
            logger.run_cmd(["sudo", "systemctl", "restart", "sddm"])
    else:
        log_dim("SDDM not installed; skipping display manager setup")

    return True

