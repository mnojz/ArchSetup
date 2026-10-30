"""
Automatic Update Integration
Manages pacman hooks and system integration so kernel, UKI, and bootloader updates
are automatically signed without manual intervention.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.config import PACMAN_HOOK_DIR, SBCTL_PACMAN_HOOK

SBCTL_HOOK_CONTENT = """[Trigger]
Operation = Upgrade
Operation = Install
Type = Package
Target = linux
Target = linux-lts
Target = linux-zen
Target = linux-hardened
Target = systemd
Target = systemd-libs
Target = sbctl

[Action]
Description = Automatically re-signing Secure Boot bootloader and kernel binaries...
When = PostTransaction
Exec = /usr/bin/sbctl sign-all
Depends = sbctl
"""


def inspect_update_hooks() -> Dict[str, Any]:
    """Inspects status of automatic update signing hooks."""
    hook_present = SBCTL_PACMAN_HOOK.is_file()
    other_hooks: List[str] = []

    if PACMAN_HOOK_DIR.is_dir():
        for hk in PACMAN_HOOK_DIR.glob("*.hook"):
            if hk != SBCTL_PACMAN_HOOK:
                try:
                    content = hk.read_text(encoding="utf-8", errors="ignore")
                    if "sbctl" in content or "sbsign" in content:
                        other_hooks.append(hk.name)
                except OSError:
                    pass

    return {
        "hook_installed": hook_present,
        "hook_path": str(SBCTL_PACMAN_HOOK),
        "other_signing_hooks": other_hooks,
        "is_configured": hook_present or len(other_hooks) > 0,
    }


def install_update_hooks() -> Tuple[bool, str]:
    """
    Installs the 99-sbctl-resign.hook pacman hook to ensure any system update
    automatically re-signs the entire boot chain.
    """
    from core.logger import logger

    # Ensure pacman hook directory exists
    logger.run_cmd(["sudo", "mkdir", "-p", str(PACMAN_HOOK_DIR)], check=False)

    import tempfile
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        tf.write(SBCTL_HOOK_CONTENT)
        temp_hook = tf.name

    code, _ = logger.run_cmd(["sudo", "cp", temp_hook, str(SBCTL_PACMAN_HOOK)], check=False)
    logger.run_cmd(["sudo", "chmod", "644", str(SBCTL_PACMAN_HOOK)], check=False)
    Path(temp_hook).unlink(missing_ok=True)

    if code == 0:
        return True, "Pacman automatic re-signing hook installed successfully."
    return False, "Failed to install pacman re-signing hook."


def remove_update_hooks() -> Tuple[bool, str]:
    """Safely removes ONLY the pacman hook installed by this module."""
    if SBCTL_PACMAN_HOOK.is_file():
        from core.logger import logger
        code, _ = logger.run_cmd(["sudo", "rm", "-f", str(SBCTL_PACMAN_HOOK)], check=False)
        if code == 0:
            return True, "Pacman signing hook removed successfully."
        return False, "Failed to remove pacman signing hook."
    return True, "No hook file found to remove."

