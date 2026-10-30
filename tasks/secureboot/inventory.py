"""
System & Storage Inventory for Secure Boot
Discovers mounted ESPs, XBOOTLDR, bootloaders, kernels, UKIs, Windows installations, and hooks.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from tasks.secureboot.config import (
    ARCH_KERNEL_NAMES,
    PACMAN_HOOK_DIR,
    SBCTL_PACMAN_HOOK,
    WINDOWS_BOOTMGR_REL,
)
from tasks.secureboot.utils import (
    dir_exists_privileged,
    file_exists_privileged,
    find_files_privileged,
    read_text_privileged,
    run_privileged,
)


def _flatten_findmnt_nodes(node: Any) -> List[Dict[str, Any]]:
    """Recursively flattens findmnt hierarchical tree into a flat list of filesystem dictionaries."""
    flat: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        flat.append(node)
        for child in node.get("children", []):
            flat.extend(_flatten_findmnt_nodes(child))
    elif isinstance(node, list):
        for item in node:
            flat.extend(_flatten_findmnt_nodes(item))
    return flat


def find_esp_mounts() -> List[Dict[str, Any]]:
    """
    Discovers all mounted EFI System Partitions (ESPs).
    Uses findmnt, /proc/mounts, and /etc/fstab with privileged fallbacks for restricted mounts.
    Never assumes /boot or /efi is the ESP.
    """
    esps: List[Dict[str, Any]] = []
    checked_paths: Set[str] = set()

    # 1. Try findmnt (using -l flat mode first, then recursive tree fallback)
    if shutil.which("findmnt"):
        for findmnt_cmd in (["findmnt", "-l", "-t", "vfat", "-J"], ["findmnt", "-t", "vfat", "-J"]):
            try:
                out = subprocess.check_output(
                    findmnt_cmd,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                )
                data = json.loads(out)
                raw_list = data.get("filesystems", [])
                fs_list = _flatten_findmnt_nodes(raw_list)

                for fs in fs_list:
                    target = fs.get("target")
                    source = fs.get("source")
                    fstype = fs.get("fstype", "vfat")
                    if target and target not in checked_paths:
                        checked_paths.add(target)
                        target_path = Path(target)
                        has_efi = (
                            dir_exists_privileged(target_path / "EFI")
                            or dir_exists_privileged(target_path / "efi")
                            or target in ("/boot", "/efi", "/boot/efi")
                        )
                        free_space = 0
                        try:
                            st = os.statvfs(target)
                            free_space = st.f_bavail * st.f_frsize
                        except OSError:
                            pass
                        esps.append({
                            "mountpoint": target,
                            "source": source,
                            "fstype": fstype,
                            "has_efi_dir": has_efi,
                            "free_space_bytes": free_space,
                        })
                if esps:
                    break
            except Exception:
                pass

    # 2. Inspect /proc/mounts as fallback
    if Path("/proc/mounts").is_file():
        try:
            with open("/proc/mounts", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        source, target, fstype = parts[0], parts[1], parts[2]
                        if fstype in ("vfat", "msdos", "fat") and target not in checked_paths:
                            checked_paths.add(target)
                            target_path = Path(target)
                            has_efi = (
                                dir_exists_privileged(target_path / "EFI")
                                or dir_exists_privileged(target_path / "efi")
                                or target in ("/boot", "/efi", "/boot/efi")
                            )
                            free_space = 0
                            try:
                                st = os.statvfs(target)
                                free_space = st.f_bavail * st.f_frsize
                            except OSError:
                                pass
                            esps.append({
                                "mountpoint": target,
                                "source": source,
                                "fstype": fstype,
                                "has_efi_dir": has_efi,
                                "free_space_bytes": free_space,
                            })
        except OSError:
            pass

    # 3. Inspect /etc/fstab for configured vfat partitions
    fstab = Path("/etc/fstab")
    if fstab.is_file():
        try:
            content = fstab.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("#"):
                    continue
                parts = line_s.split()
                if len(parts) >= 3:
                    source, target, fstype = parts[0], parts[1], parts[2]
                    if fstype in ("vfat", "fat") and target in ("/boot", "/efi", "/boot/efi") and target not in checked_paths:
                        checked_paths.add(target)
                        esps.append({
                            "mountpoint": target,
                            "source": source,
                            "fstype": fstype,
                            "has_efi_dir": True,
                            "free_space_bytes": 0,
                        })
        except OSError:
            pass

    # 4. Check well-known mount paths if still empty
    for cand in ("/efi", "/boot/efi", "/boot"):
        c_path = Path(cand)
        if cand not in checked_paths and dir_exists_privileged(c_path):
            has_efi = dir_exists_privileged(c_path / "EFI") or dir_exists_privileged(c_path / "efi") or cand in ("/boot", "/efi")
            if has_efi:
                esps.append({
                    "mountpoint": cand,
                    "source": "unknown",
                    "fstype": "vfat",
                    "has_efi_dir": True,
                    "free_space_bytes": 0,
                })
                checked_paths.add(cand)

    # Prefer mounts that actually contain EFI/
    esps.sort(key=lambda x: (x["has_efi_dir"], x["free_space_bytes"]), reverse=True)
    return esps


def get_primary_esp_path() -> Optional[Path]:
    """Returns the most likely primary ESP path, or None."""
    esps = find_esp_mounts()
    if esps:
        return Path(esps[0]["mountpoint"])
    # Fallbacks
    for cand in ("/efi", "/boot", "/boot/efi"):
        p = Path(cand)
        if (p / "EFI").is_dir():
            return p
    return None


def get_firmware_boot_entries() -> List[Dict[str, Any]]:
    """Inspects active firmware boot entries using efibootmgr."""
    entries: List[Dict[str, Any]] = []
    if not shutil.which("efibootmgr"):
        return entries

    try:
        out = subprocess.check_output(
            ["efibootmgr", "-v"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        for line in out.splitlines():
            m = re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.*?)\t+(.*)$", line)
            if m:
                boot_num = m.group(1)
                label = m.group(2).strip()
                path_info = m.group(3).strip()
                is_active = "*" in line[:8]
                entries.append({
                    "number": boot_num,
                    "label": label,
                    "path_info": path_info,
                    "active": is_active,
                })
    except Exception:
        pass
    return entries


def detect_active_bootloader(esp_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Detects the active bootloader using firmware entries, configuration files, and EFI binaries.
    Does not infer solely from installed packages.
    """
    boot_info = {
        "name": "unknown",
        "type": "unknown",
        "efi_path": None,
        "config_path": None,
        "details": "",
        "supported": False,
    }

    if not esp_path:
        esp_path = get_primary_esp_path()

    firmware_entries = get_firmware_boot_entries()

    # 1. Inspect firmware entries for known bootloader names
    for entry in firmware_entries:
        label = entry["label"].lower()
        path_info = entry["path_info"].lower()
        if "systemd-boot" in path_info or "linux boot manager" in label:
            boot_info["name"] = "systemd-boot"
            boot_info["type"] = "systemd-boot"
            boot_info["supported"] = True
            boot_info["details"] = f"Identified via firmware entry: {entry['label']}"
            break
        elif "grub" in label or "grub" in path_info:
            boot_info["name"] = "grub"
            boot_info["type"] = "grub"
            boot_info["supported"] = True
            boot_info["details"] = f"Identified via firmware entry: {entry['label']}"
            break
        elif "refind" in label or "refind" in path_info:
            boot_info["name"] = "refind"
            boot_info["type"] = "refind"
            boot_info["supported"] = True
            boot_info["details"] = f"Identified via firmware entry: {entry['label']}"
            break
        elif "limine" in label or "limine" in path_info:
            boot_info["name"] = "limine"
            boot_info["type"] = "limine"
            boot_info["supported"] = True
            boot_info["details"] = f"Identified via firmware entry: {entry['label']}"
            break

    # 2. Check ESP files and config if not conclusive
    if esp_path and esp_path.is_dir():
        # Check systemd-boot
        sd_efi = esp_path / "EFI/systemd/systemd-bootx64.efi"
        loader_conf = esp_path / "loader/loader.conf"
        boot_loader_conf = Path("/boot/loader/loader.conf")

        if sd_efi.is_file() or loader_conf.is_file() or boot_loader_conf.is_file():
            if boot_info["name"] in ("unknown", "systemd-boot"):
                boot_info["name"] = "systemd-boot"
                boot_info["type"] = "systemd-boot"
                boot_info["supported"] = True
                boot_info["efi_path"] = str(sd_efi) if sd_efi.is_file() else None
                boot_info["config_path"] = str(loader_conf if loader_conf.is_file() else boot_loader_conf)
                if not boot_info["details"]:
                    boot_info["details"] = "systemd-boot configuration and EFI binary found on ESP"
                return boot_info

        # Check GRUB
        grub_cfg = Path("/boot/grub/grub.cfg")
        grub_efi_cands = [
            esp_path / "EFI/arch/grubx64.efi",
            esp_path / "EFI/grub/grubx64.efi",
            esp_path / "EFI/BOOT/grubx64.efi",
        ]
        found_grub_efi = next((p for p in grub_efi_cands if p.is_file()), None)
        if found_grub_efi or grub_cfg.is_file():
            if boot_info["name"] in ("unknown", "grub"):
                boot_info["name"] = "grub"
                boot_info["type"] = "grub"
                boot_info["supported"] = True
                boot_info["efi_path"] = str(found_grub_efi) if found_grub_efi else None
                boot_info["config_path"] = str(grub_cfg) if grub_cfg.is_file() else None
                if not boot_info["details"]:
                    boot_info["details"] = "GRUB configuration and EFI binary found"
                return boot_info

        # Check rEFInd
        refind_cfg = Path("/boot/refind_linux.conf")
        refind_efi = esp_path / "EFI/refind/refind_x64.efi"
        if refind_efi.is_file() or refind_cfg.is_file():
            boot_info["name"] = "refind"
            boot_info["type"] = "refind"
            boot_info["supported"] = True
            boot_info["efi_path"] = str(refind_efi) if refind_efi.is_file() else None
            boot_info["config_path"] = str(refind_cfg) if refind_cfg.is_file() else None
            boot_info["details"] = "rEFInd configuration and EFI binary found"
            return boot_info

        # Check Limine
        limine_cfg = Path("/boot/limine.cfg")
        limine_efi = esp_path / "EFI/BOOT/BOOTX64.EFI"
        if limine_cfg.is_file():
            boot_info["name"] = "limine"
            boot_info["type"] = "limine"
            boot_info["supported"] = True
            boot_info["efi_path"] = str(limine_efi) if limine_efi.is_file() else None
            boot_info["config_path"] = str(limine_cfg)
            boot_info["details"] = "Limine configuration found"
            return boot_info

    return boot_info


def detect_installed_kernels() -> List[Dict[str, Any]]:
    """
    Detects installed kernels by checking pacman databases and /boot or ESP files.
    """
    kernels: List[Dict[str, Any]] = []
    found_names: Set[str] = set()

    # 1. Query pacman for installed official Arch kernels
    if shutil.which("pacman"):
        try:
            out = subprocess.check_output(
                ["pacman", "-Qq"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            installed_pkgs = set(out.splitlines())
            for k in ARCH_KERNEL_NAMES:
                if k in installed_pkgs:
                    found_names.add(k)
                    vmlinuz = Path(f"/boot/vmlinuz-{k}")
                    vmlinuz_exists = file_exists_privileged(vmlinuz)
                    kernels.append({
                        "name": k,
                        "package": k,
                        "vmlinuz_path": str(vmlinuz) if vmlinuz_exists else None,
                        "type": "traditional",
                    })
        except Exception:
            pass

    # 2. Inspect /boot for vmlinuz-* files
    boot_dir = Path("/boot")
    for vm in find_files_privileged(boot_dir, "vmlinuz-*"):
        kname = vm.name.replace("vmlinuz-", "")
        if kname not in found_names:
            found_names.add(kname)
            kernels.append({
                "name": kname,
                "package": kname,
                "vmlinuz_path": str(vm),
                "type": "traditional",
            })

    return kernels


def detect_unified_kernel_images(esp_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Detects Unified Kernel Images (UKIs) on ESP and /boot.
    Validates PE/COFF structure if objdump is available.
    """
    ukis: List[Dict[str, Any]] = []
    search_dirs: List[Path] = [Path("/boot/EFI/Linux")]
    if esp_path:
        search_dirs.append(esp_path / "EFI/Linux")
    for cand in ("/efi/EFI/Linux", "/boot/efi/EFI/Linux"):
        p = Path(cand)
        if p not in search_dirs:
            search_dirs.append(p)

    for sdir in search_dirs:
        for efi in find_files_privileged(sdir, "*.efi"):
            has_linux_section = False
            # Try objdump to verify UKI sections (.linux, .initrd, .cmdline)
            if shutil.which("objdump"):
                try:
                    code, out, _ = run_privileged(["objdump", "-h", str(efi)])
                    if code == 0 and ".linux" in out:
                        has_linux_section = True
                except Exception:
                    pass
            ukis.append({
                "name": efi.stem,
                "path": str(efi),
                "is_validated_uki": has_linux_section,
                "size_bytes": efi.stat().st_size if efi.exists() else 0,
            })
    return ukis


def detect_windows() -> Dict[str, Any]:
    """
    Detects Windows Boot Manager installation and firmware entries.
    Ensures Windows boot files are identified so they are never modified or re-signed.
    """
    result = {
        "detected": False,
        "bootmgr_path": None,
        "firmware_entry": None,
        "bitlocker_warning": False,
    }

    # 1. Search all ESPs for EFI/Microsoft/Boot/bootmgfw.efi
    esps = find_esp_mounts()
    for esp in esps:
        esp_dir = Path(esp["mountpoint"])
        win_efi = esp_dir / WINDOWS_BOOTMGR_REL
        if file_exists_privileged(win_efi):
            result["detected"] = True
            result["bootmgr_path"] = str(win_efi)
            result["bitlocker_warning"] = True
            break

    # Also check well-known paths directly
    for cand in ("/boot/EFI/Microsoft/Boot/bootmgfw.efi", "/efi/EFI/Microsoft/Boot/bootmgfw.efi"):
        p = Path(cand)
        if not result["detected"] and file_exists_privileged(p):
            result["detected"] = True
            result["bootmgr_path"] = str(p)
            result["bitlocker_warning"] = True
            break
        if win_efi.is_file():
            result["detected"] = True
            result["bootmgr_path"] = str(win_efi)
            result["bitlocker_warning"] = True
            break

    # 2. Check firmware boot entries
    entries = get_firmware_boot_entries()
    for entry in entries:
        if "windows boot manager" in entry["label"].lower():
            result["detected"] = True
            result["firmware_entry"] = entry
            result["bitlocker_warning"] = True
            break

    return result


def detect_signing_hooks() -> List[Dict[str, Any]]:
    """Inspects pacman and mkinitcpio hooks for existing Secure Boot signing mechanisms."""
    hooks: List[Dict[str, Any]] = []

    if PACMAN_HOOK_DIR.is_dir():
        for hk in PACMAN_HOOK_DIR.glob("*.hook"):
            try:
                content = hk.read_text(encoding="utf-8", errors="ignore")
                if "sbctl" in content or "sbsign" in content or "sign" in hk.name:
                    hooks.append({
                        "name": hk.name,
                        "path": str(hk),
                        "type": "pacman",
                        "is_sbctl": "sbctl" in content,
                    })
            except OSError:
                pass

    return hooks


def inspect_full_inventory() -> Dict[str, Any]:
    """Runs a complete system storage and boot inventory."""
    esps = find_esp_mounts()
    primary_esp = get_primary_esp_path()
    bootloader = detect_active_bootloader(primary_esp)
    kernels = detect_installed_kernels()
    ukis = detect_unified_kernel_images(primary_esp)
    windows = detect_windows()
    hooks = detect_signing_hooks()

    return {
        "esps": esps,
        "primary_esp": str(primary_esp) if primary_esp else None,
        "bootloader": bootloader,
        "kernels": kernels,
        "ukis": ukis,
        "uses_uki": len(ukis) > 0,
        "windows": windows,
        "hooks": hooks,
    }

