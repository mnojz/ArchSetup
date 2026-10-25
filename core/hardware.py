"""
ArchSetup Hardware & System Detection Engine
Detects CPU architecture/microcode, GPU drivers, audio stack, and battery/power profiles.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any

def detect_cpu() -> Dict[str, Any]:
    info = {"vendor": "Unknown", "model": "Unknown", "microcode_pkg": None}
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            content = f.read()
            for line in content.splitlines():
                if "vendor_id" in line:
                    if "GenuineIntel" in line:
                        info["vendor"] = "Intel"
                        info["microcode_pkg"] = "intel-ucode"
                    elif "AuthenticAMD" in line:
                        info["vendor"] = "AMD"
                        info["microcode_pkg"] = "amd-ucode"
                if "model name" in line and info["model"] == "Unknown":
                    info["model"] = line.split(":", 1)[1].strip()
    except Exception:
        pass
    return info

def detect_gpu() -> List[Dict[str, str]]:
    gpus = []
    try:
        res = subprocess.run(["lspci"], capture_output=True, text=True, check=False)
        for line in res.stdout.splitlines():
            line_lower = line.lower()
            if any(k in line_lower for k in ("vga compatible controller", "3d controller", "display controller")):
                gpu_info = {"raw": line.split(":", 2)[-1].strip(), "type": "Generic", "driver_pkgs": []}
                if "nvidia" in line_lower:
                    gpu_info["type"] = "NVIDIA"
                    gpu_info["driver_pkgs"] = ["libva-nvidia-driver", "nvidia-utils"]
                elif "intel" in line_lower:
                    gpu_info["type"] = "Intel"
                    gpu_info["driver_pkgs"] = ["intel-media-driver", "vulkan-intel"]
                elif "amd" in line_lower or "ati" in line_lower:
                    gpu_info["type"] = "AMD"
                    gpu_info["driver_pkgs"] = ["vulkan-radeon", "libva-mesa-driver"]
                gpus.append(gpu_info)
    except Exception:
        pass
    return gpus

def detect_chassis() -> Dict[str, Any]:
    power_dir = Path("/sys/class/power_supply")
    has_battery = False
    if power_dir.is_dir():
        for b in power_dir.iterdir():
            if b.name.startswith("BAT"):
                has_battery = True
                break
    return {
        "is_laptop": has_battery,
        "recommended_power": "power-profiles-daemon" if has_battery else None
    }

def run_diagnostics() -> List[Dict[str, Any]]:
    """Runs a full suite of system diagnostic checks (Doctor mode)."""
    checks = []

    # 1. Wayland / Hyprland
    is_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    is_hypr = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    checks.append({
        "name": "Compositor (Hyprland / Wayland)",
        "status": "PASS" if is_hypr else ("WARN" if is_wayland else "INFO"),
        "details": "Hyprland session active" if is_hypr else ("Wayland running (non-Hyprland)" if is_wayland else "TTY / Console session")
    })

    # 2. Audio Subsystem (PipeWire)
    pw_ok = shutil.which("pipewire") is not None
    wp_ok = shutil.which("wireplumber") is not None
    checks.append({
        "name": "Audio Stack (PipeWire & WirePlumber)",
        "status": "PASS" if (pw_ok and wp_ok) else "WARN",
        "details": "PipeWire & WirePlumber binaries present" if (pw_ok and wp_ok) else "Missing PipeWire/WirePlumber"
    })

    # 3. CPU Microcode
    cpu = detect_cpu()
    ucode = cpu.get("microcode_pkg")
    ucode_installed = False
    if ucode:
        res = subprocess.run(["pacman", "-Qi", ucode], capture_output=True, check=False)
        ucode_installed = (res.returncode == 0)
    checks.append({
        "name": f"CPU Microcode ({cpu['vendor']})",
        "status": "PASS" if ucode_installed else "WARN",
        "details": f"{ucode} is installed" if ucode_installed else f"Missing {ucode} package"
    })

    # 4. Hardware Acceleration (VA-API)
    vainfo = shutil.which("vainfo")
    va_status = "INFO"
    va_details = "vainfo tool not installed (libva-utils)"
    if vainfo:
        res = subprocess.run(["vainfo"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            va_status = "PASS"
            va_details = "VA-API hardware acceleration driver loaded"
        else:
            va_status = "WARN"
            va_details = "VA-API driver reported initialization warning"
    checks.append({
        "name": "Hardware Video Acceleration",
        "status": va_status,
        "details": va_details
    })

    # 5. Pacman Parallel Downloads
    p_conf = Path("/etc/pacman.conf")
    parallel_ok = False
    if p_conf.exists():
        content = p_conf.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            line_s = line.strip()
            if line_s.startswith("ParallelDownloads") and not line_s.startswith("#"):
                parallel_ok = True
                break
    checks.append({
        "name": "Pacman Parallel Downloads",
        "status": "PASS" if parallel_ok else "WARN",
        "details": "Parallel downloads enabled" if parallel_ok else "Single-threaded (can be accelerated)"
    })

    # 6. Sudoers & Privilege Escalation
    sudo_ok = shutil.which("sudo") is not None
    checks.append({
        "name": "Privilege Escalation (sudo)",
        "status": "PASS" if sudo_ok else "FAIL",
        "details": "sudo is available" if sudo_ok else "sudo not found in PATH"
    })

    # 7. AUR Helper
    aur_tool = "yay" if shutil.which("yay") else ("paru" if shutil.which("paru") else None)
    checks.append({
        "name": "AUR Helper (yay / paru)",
        "status": "PASS" if aur_tool else "WARN",
        "details": f"Active helper: {aur_tool}" if aur_tool else "No AUR helper detected"
    })

    return checks

