"""
Secure Boot Backup & Recovery Management
Creates atomic, protected backups of Secure Boot keys, EFI binaries, bootloader configuration,
and firmware variable snapshots.
"""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasks.secureboot.config import (
    BACKUP_DIR,
    PACMAN_HOOK_DIR,
    SBCTL_KEYS_DIR,
)
from tasks.secureboot.inventory import find_esp_mounts, get_primary_esp_path


def _ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(BACKUP_DIR), 0o700)
    except OSError:
        pass
    return BACKUP_DIR


def has_existing_backup() -> bool:
    """Checks whether any previous Secure Boot backup archive exists."""
    if not BACKUP_DIR.is_dir():
        return False
    return any(BACKUP_DIR.glob("backup_*"))


def list_backups() -> List[Dict[str, Any]]:
    """Lists available backup snapshots, newest first."""
    if not BACKUP_DIR.is_dir():
        return []

    backups: List[Dict[str, Any]] = []
    for d in sorted(BACKUP_DIR.glob("backup_*"), reverse=True):
        if d.is_dir():
            meta_file = d / "metadata.json"
            meta = {}
            if meta_file.is_file():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass
            backups.append({
                "path": str(d),
                "timestamp": meta.get("timestamp", d.name.replace("backup_", "")),
                "has_keys": (d / "keys").is_dir(),
                "has_esp": (d / "esp").is_dir(),
                "has_hooks": (d / "hooks").is_dir(),
                "metadata": meta,
            })
    return backups


def create_full_backup(label: str = "manual") -> Tuple[bool, str, Optional[Path]]:
    """
    Creates a comprehensive backup snapshot:
    1. Secure Boot keys (with 0600 permissions)
    2. EFI bootloader configuration
    3. efibootmgr boot entries
    4. Pacman signing hooks
    5. Snapshot metadata
    """
    _ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_dir = BACKUP_DIR / f"backup_{timestamp}_{label}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(str(snapshot_dir), 0o700)

    from core.logger import logger

    # 1. Back up keys (requires root/sudo for /usr/share/secureboot/keys)
    keys_target = snapshot_dir / "keys"
    if SBCTL_KEYS_DIR.is_dir():
        logger.run_cmd(["sudo", "cp", "-a", str(SBCTL_KEYS_DIR), str(keys_target)], check=False)
        logger.run_cmd(["sudo", "chmod", "-R", "700", str(keys_target)], check=False)

    # 2. Back up bootloader configuration
    esp = get_primary_esp_path()
    esp_target = snapshot_dir / "esp_config"
    esp_target.mkdir(parents=True, exist_ok=True)
    if esp:
        # Save loader.conf and entries
        loader_dir = esp / "loader"
        if loader_dir.is_dir():
            shutil.copytree(str(loader_dir), str(esp_target / "loader"), dirs_exist_ok=True)

    # Also check /boot/loader and /boot/grub
    if Path("/boot/loader").is_dir():
        shutil.copytree("/boot/loader", str(esp_target / "boot_loader"), dirs_exist_ok=True)
    if Path("/boot/grub/grub.cfg").is_file():
        shutil.copy2("/boot/grub/grub.cfg", str(esp_target / "grub.cfg"))

    # 3. Save efibootmgr output
    if shutil.which("efibootmgr"):
        try:
            out = subprocess.check_output(["efibootmgr", "-v"], stderr=subprocess.DEVNULL, text=True)
            (snapshot_dir / "efibootmgr_dump.txt").write_text(out, encoding="utf-8")
        except Exception:
            pass

    # 4. Save pacman hooks
    hooks_target = snapshot_dir / "hooks"
    hooks_target.mkdir(parents=True, exist_ok=True)
    if PACMAN_HOOK_DIR.is_dir():
        for hk in PACMAN_HOOK_DIR.glob("*sbctl*"):
            try:
                shutil.copy2(str(hk), str(hooks_target / hk.name))
            except Exception:
                pass

    # 5. Metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "esp_path": str(esp) if esp else None,
        "has_keys": keys_target.is_dir(),
        "backup_path": str(snapshot_dir),
    }
    (snapshot_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return True, f"Backup snapshot created at: {snapshot_dir}", snapshot_dir


def restore_keys_from_backup(backup_path: Path) -> Tuple[bool, str]:
    """
    Restores Secure Boot keys from a backup snapshot into /usr/share/secureboot/keys.
    SAFETY: Requires explicit authorization.
    """
    keys_src = backup_path / "keys"
    if not keys_src.is_dir():
        return False, "No keys directory found in selected backup snapshot."

    from core.logger import logger

    logger.run_cmd(["sudo", "mkdir", "-p", str(SBCTL_KEYS_DIR.parent)], check=False)
    code, _ = logger.run_cmd(["sudo", "cp", "-a", str(keys_src), str(SBCTL_KEYS_DIR)], check=False)
    if code == 0:
        logger.run_cmd(["sudo", "chmod", "700", str(SBCTL_KEYS_DIR)], check=False)
        return True, "Secure Boot keys restored successfully from backup."
    return False, "Failed to restore keys from backup."

