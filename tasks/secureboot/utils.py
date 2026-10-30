"""
Privileged Execution & Filesystem Helpers for Secure Boot
Provides safe elevation fallbacks for inspecting and querying files in root-restricted
directories (e.g. /boot mounted with dmask=0077, efivarfs, /usr/share/secureboot).
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def run_privileged(cmd: List[str], timeout: int = 15) -> Tuple[int, str, str]:
    """
    Executes a command with sudo if the current process is not root.
    Uses non-interactive sudo (-n) to prevent hangs or unstyled terminal password prompts.
    Returns (returncode, stdout, stderr).
    """
    if os.geteuid() == 0:
        full_cmd = list(cmd)
    else:
        full_cmd = ["sudo", "-n"] + list(cmd)

    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def file_exists_privileged(path: Path) -> bool:
    """
    Checks if a file exists, gracefully falling back to a privileged test if
    permission to traverse the parent directory (e.g. /boot with dmask=0077) is denied.
    """
    try:
        if path.is_file():
            return True
    except (PermissionError, OSError):
        pass

    code, _, _ = run_privileged(["test", "-f", str(path)])
    return code == 0


def dir_exists_privileged(path: Path) -> bool:
    """Checks if a directory exists, falling back to privileged test on PermissionError."""
    try:
        if path.is_dir():
            return True
    except (PermissionError, OSError):
        pass

    code, _, _ = run_privileged(["test", "-d", str(path)])
    return code == 0


def find_files_privileged(directory: Path, pattern: str) -> List[Path]:
    """
    Finds files matching pattern under directory, using sudo find if normal glob fails with PermissionError.
    """
    results: List[Path] = []
    try:
        if directory.is_dir():
            for p in directory.glob(pattern):
                if p.is_file():
                    results.append(p)
            return results
    except (PermissionError, OSError):
        pass

    # Privileged fallback
    code, stdout, _ = run_privileged(["find", str(directory), "-maxdepth", "3", "-name", pattern])
    if code == 0:
        for line in stdout.splitlines():
            line_s = line.strip()
            if line_s:
                results.append(Path(line_s))

    return results


def read_text_privileged(path: Path) -> Optional[str]:
    """Reads a text file, falling back to sudo cat if permission denied."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (PermissionError, OSError):
        pass

    code, stdout, _ = run_privileged(["cat", str(path)])
    if code == 0:
        return stdout
    return None

