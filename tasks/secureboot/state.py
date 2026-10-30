"""
Secure Boot State Management & Operation Journal
Maintains observed vs desired state and provides idempotent operation tracking.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tasks.secureboot.config import (
    JOURNAL_DIR,
    STATE_DIR,
)


def _ensure_dir(d: Path) -> None:
    """Create directory with restrictive permissions if it does not exist."""
    try:
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(str(d), 0o700)
    except OSError:
        pass


class ObservedState:
    """Snapshot of the actual machine state — always built from live inspection."""

    def __init__(self) -> None:
        # UEFI / firmware
        self.is_uefi: bool = False
        self.efivars_accessible: bool = False
        self.secure_boot_enabled: bool = False
        self.setup_mode: bool = False

        # sbctl
        self.sbctl_installed: bool = False
        self.sbctl_version: str = ""

        # Keys
        self.keys_exist: bool = False
        self.keys_enrolled: bool = False
        self.key_details: Dict[str, Any] = {}

        # ESP / filesystems
        self.esp_partitions: List[Dict[str, str]] = []
        self.xbootldr_partitions: List[Dict[str, str]] = []

        # Bootloader
        self.active_bootloader: str = ""
        self.bootloader_details: Dict[str, Any] = {}

        # Kernels / UKIs
        self.installed_kernels: List[str] = []
        self.unified_kernel_images: List[Dict[str, str]] = []
        self.uses_uki: bool = False

        # Signing
        self.signed_files: List[Dict[str, Any]] = []
        self.signing_hooks_present: bool = False
        self.signing_hooks: List[Dict[str, str]] = []

        # Windows
        self.windows_detected: bool = False
        self.windows_efi_path: str = ""
        self.ms_certs_enrolled: Dict[str, bool] = {}

        # Tools
        self.available_tools: Dict[str, bool] = {}

        # Arch Linux
        self.is_arch: bool = False

        # Disk space (bytes available on ESP)
        self.esp_free_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for reporting."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class DesiredState:
    """Target configuration the user wants to achieve."""

    def __init__(self) -> None:
        self.keys_generated: bool = True
        self.keys_enrolled: bool = True
        self.sign_bootloader: bool = True
        self.sign_kernels: bool = True
        self.install_hooks: bool = True
        self.enroll_ms_certs: bool = False  # User must opt in
        self.target_bootloader: str = ""  # Auto-detected unless overridden

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class ExecutionPlan:
    """Compares observed and desired states to produce a list of required actions."""

    def __init__(self, observed: ObservedState, desired: DesiredState) -> None:
        self.observed = observed
        self.desired = desired
        self.actions: List[Dict[str, Any]] = []
        self._compute()

    def _compute(self) -> None:
        """Determine actions needed to reach desired state from observed state."""
        o = self.observed
        d = self.desired

        # Key generation
        if d.keys_generated and not o.keys_exist:
            self.actions.append({
                "type": "generate_keys",
                "reason": "No Secure Boot keys found",
                "risk": "low",
            })
        elif d.keys_generated and o.keys_exist:
            self.actions.append({
                "type": "skip_key_generation",
                "reason": "Valid keys already exist — preserving",
                "risk": "none",
            })

        # Signing
        if d.sign_bootloader and o.active_bootloader:
            self.actions.append({
                "type": "sign_bootloader",
                "reason": f"Sign {o.active_bootloader} EFI files",
                "risk": "low",
            })

        if d.sign_kernels and o.installed_kernels:
            self.actions.append({
                "type": "sign_kernels",
                "reason": f"Sign {len(o.installed_kernels)} kernel(s) / UKI(s)",
                "risk": "low",
            })

        # Microsoft certificates
        if d.enroll_ms_certs and not all(o.ms_certs_enrolled.values()):
            self.actions.append({
                "type": "enroll_ms_certs",
                "reason": "Enroll Microsoft certificates for Windows compatibility",
                "risk": "medium",
            })

        # Hooks
        if d.install_hooks and not o.signing_hooks_present:
            self.actions.append({
                "type": "install_hooks",
                "reason": "Install automatic signing hooks for kernel/bootloader updates",
                "risk": "low",
            })
        elif d.install_hooks and o.signing_hooks_present:
            self.actions.append({
                "type": "verify_hooks",
                "reason": "Signing hooks already present — verifying",
                "risk": "none",
            })

        # Enrollment
        if d.keys_enrolled and not o.keys_enrolled:
            self.actions.append({
                "type": "enroll_keys",
                "reason": "Enroll keys into firmware",
                "risk": "high",
            })
        elif d.keys_enrolled and o.keys_enrolled:
            self.actions.append({
                "type": "skip_enrollment",
                "reason": "Keys already enrolled in firmware",
                "risk": "none",
            })

    def get_actions(self) -> List[Dict[str, Any]]:
        return [a for a in self.actions if a["risk"] != "none"]

    def get_skipped(self) -> List[Dict[str, Any]]:
        return [a for a in self.actions if a["risk"] == "none"]

    def has_high_risk(self) -> bool:
        return any(a["risk"] == "high" for a in self.actions)


class OperationJournal:
    """Persistent operation log for diagnosing and resuming interrupted operations."""

    def __init__(self) -> None:
        _ensure_dir(JOURNAL_DIR)
        self._journal_file = (
            JOURNAL_DIR / f"journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        self._entries: List[Dict[str, Any]] = []

    @property
    def journal_path(self) -> Path:
        return self._journal_file

    def record(
        self,
        operation: str,
        status: str,
        details: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an operation record to the journal."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "status": status,
            "details": details,
        }
        if metadata:
            # Never include private key material
            safe_meta = {
                k: v for k, v in metadata.items()
                if "private" not in k.lower() and "secret" not in k.lower() and "password" not in k.lower()
            }
            entry["metadata"] = safe_meta

        self._entries.append(entry)
        self._flush_entry(entry)

    def _flush_entry(self, entry: Dict[str, Any]) -> None:
        """Write a single entry to the journal file."""
        try:
            with open(self._journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass

    def get_entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    @staticmethod
    def load_latest() -> Optional["OperationJournal"]:
        """Load the most recent journal file for inspection."""
        if not JOURNAL_DIR.is_dir():
            return None
        journals = sorted(JOURNAL_DIR.glob("journal_*.jsonl"), reverse=True)
        if not journals:
            return None
        journal = OperationJournal.__new__(OperationJournal)
        journal._journal_file = journals[0]
        journal._entries = []
        try:
            with open(journals[0], "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        journal._entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
        return journal

    @staticmethod
    def list_journals() -> List[Path]:
        """Return all journal files, newest first."""
        if not JOURNAL_DIR.is_dir():
            return []
        return sorted(JOURNAL_DIR.glob("journal_*.jsonl"), reverse=True)

