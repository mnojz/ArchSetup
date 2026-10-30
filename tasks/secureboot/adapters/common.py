"""
Base Bootloader Adapter Interface
Defines the standard contract for bootloader-specific Secure Boot operations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class BootloaderAdapter(ABC):
    """Abstract base class for bootloader Secure Boot integration."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the bootloader (e.g., 'systemd-boot', 'grub', 'refind', 'limine')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for TUI display."""
        pass

    @abstractmethod
    def detect(self, inventory: Dict[str, Any]) -> bool:
        """Determines whether this bootloader is currently active on the system."""
        pass

    @abstractmethod
    def inspect(self) -> Dict[str, Any]:
        """Inspects bootloader configuration, EFI executables, and signing status."""
        pass

    @abstractmethod
    def get_signable_files(self) -> List[Path]:
        """Returns the list of EFI executable files that need to be signed for this bootloader."""
        pass

    @abstractmethod
    def prepare(self) -> Tuple[bool, str]:
        """Prepares any bootloader configuration changes required for Secure Boot."""
        pass

    @abstractmethod
    def sign(self) -> Tuple[bool, str]:
        """Signs the bootloader EFI executable(s) using sbctl and registers them."""
        pass

    def sign_binaries(self) -> Tuple[bool, str]:
        """Convenience alias for sign()."""
        return self.sign()

    @abstractmethod
    def verify(self) -> Dict[str, Any]:
        """Verifies the signatures of all bootloader-specific EFI executables."""
        pass

    @abstractmethod
    def configure_updates(self) -> Tuple[bool, str]:
        """Configures automated update handling (e.g. systemd-boot .efi.signed hooks)."""
        pass

    @abstractmethod
    def remove_integration(self) -> Tuple[bool, str]:
        """Safely removes bootloader-specific integrations without damaging the bootloader."""
        pass

