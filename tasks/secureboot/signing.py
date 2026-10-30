"""
EFI Signing Engine
Uses sbctl as the primary signing backend. Manages registered signable files,
orchestrates batch signing, validates PE signatures, and protects Windows binaries.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.adapters import get_active_adapter
from tasks.secureboot.config import WINDOWS_BOOTMGR_REL
from tasks.secureboot.inventory import find_esp_mounts, get_primary_esp_path
from tasks.secureboot.kernel import get_signable_kernel_files


def is_windows_binary(path: Path) -> bool:
    """Checks whether a file path points to a Windows EFI binary that must never be re-signed."""
    norm = str(path).lower().replace("\\", "/")
    return "microsoft" in norm or "bootmgfw.efi" in norm


def list_registered_files() -> List[Dict[str, Any]]:
    """
    Returns files currently registered in sbctl's database via `sbctl list-files`.
    """
    files: List[Dict[str, Any]] = []
    if not shutil.which("sbctl"):
        return files

    # Try JSON output first if supported
    try:
        out = subprocess.check_output(
            ["sbctl", "list-files", "--json"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        data = json.loads(out)
        if isinstance(data, list):
            for item in data:
                files.append({
                    "path": item.get("path", ""),
                    "signed": item.get("is_signed", False),
                })
            return files
    except Exception:
        pass

    # Fallback to text parsing
    try:
        out = subprocess.check_output(
            ["sbctl", "list-files"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        for line in out.splitlines():
            line_s = line.strip()
            if not line_s or line_s.startswith("File"):
                continue
            # sbctl format: "/boot/vmlinuz-linux is signed" or similar
            parts = line_s.split()
            if parts:
                fpath = parts[0]
                is_signed = "is signed" in line_s or "✓" in line_s
                files.append({
                    "path": fpath,
                    "signed": is_signed,
                })
    except Exception:
        pass

    return files


def sign_file(file_path: Path, register: bool = True) -> Tuple[bool, str]:
    """
    Signs a single EFI executable using sbctl.
    SAFETY: Refuses to sign Windows binaries.
    """
    if is_windows_binary(file_path):
        return False, f"Refusing to modify Windows binary: {file_path}"

    if not file_path.is_file():
        return False, f"File does not exist: {file_path}"

    if not shutil.which("sbctl"):
        return False, "sbctl is not installed."

    from core.logger import logger

    cmd = ["sudo", "sbctl", "sign"]
    if register:
        cmd.append("-s")
    cmd.append(str(file_path))

    code, _ = logger.run_cmd(cmd, check=False)
    if code == 0:
        return True, f"Successfully signed: {file_path}"
    return False, f"sbctl sign exited with code {code} for {file_path}"


def sign_all_registered() -> Tuple[bool, str]:
    """Signs all files registered in sbctl's database (`sbctl sign-all`)."""
    if not shutil.which("sbctl"):
        return False, "sbctl is not installed."

    from core.logger import logger

    code, _ = logger.run_cmd(["sudo", "sbctl", "sign-all"], check=False)
    if code == 0:
        return True, "All registered files signed successfully."
    return False, f"sbctl sign-all exited with code {code}."


def verify_all_system_files() -> Dict[str, Any]:
    """
    Comprehensive verification of all bootloader and kernel executables.
    Queries `sbctl verify` or checks each detected file.
    """
    verification_results: Dict[str, bool] = {}
    missing_files: List[str] = []

    # Gather all bootloader files
    adapter = get_active_adapter()
    boot_files = adapter.get_signable_files() if adapter else []

    # Gather kernel files
    kernel_files = get_signable_kernel_files()

    all_targets = list(set(boot_files + kernel_files))

    if not shutil.which("sbctl"):
        return {
            "all_verified": False,
            "results": {str(f): False for f in all_targets},
            "missing": [],
            "sbctl_available": False,
        }

    for target in all_targets:
        if not target.is_file():
            missing_files.append(str(target))
            verification_results[str(target)] = False
            continue

        try:
            code = subprocess.run(
                ["sbctl", "verify", str(target)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode
            verification_results[str(target)] = (code == 0)
        except Exception:
            verification_results[str(target)] = False

    all_ok = len(verification_results) > 0 and all(verification_results.values()) and len(missing_files) == 0

    return {
        "all_verified": all_ok,
        "results": verification_results,
        "missing": missing_files,
        "sbctl_available": True,
        "verified_count": sum(1 for v in verification_results.values() if v),
        "total_count": len(verification_results),
    }


def auto_discover_and_sign_all() -> Tuple[bool, List[str], List[str]]:
    """
    Discovers all active bootloader and kernel binaries, signs them, and registers them.
    Returns (overall_success, list_of_signed, list_of_failed).
    """
    signed: List[str] = []
    failed: List[str] = []

    adapter = get_active_adapter()
    targets: List[Path] = []

    if adapter:
        targets.extend(adapter.get_signable_files())
    targets.extend(get_signable_kernel_files())

    # Filter out duplicates and Windows files
    valid_targets: List[Path] = []
    seen: set = set()
    for t in targets:
        st = str(t)
        if st not in seen and not is_windows_binary(t):
            seen.add(st)
            valid_targets.append(t)

    for t in valid_targets:
        ok, msg = sign_file(t, register=True)
        if ok:
            signed.append(str(t))
        else:
            failed.append(f"{t}: {msg}")

    success = len(signed) > 0 and len(failed) == 0
    return success, signed, failed

