"""
Bootloader Adapter Registry
"""

from typing import Any, Dict, List, Optional

from tasks.secureboot.adapters.common import BootloaderAdapter
from tasks.secureboot.adapters.grub import GrubAdapter
from tasks.secureboot.adapters.limine import LimineAdapter
from tasks.secureboot.adapters.refind import RefindAdapter
from tasks.secureboot.adapters.systemd_boot import SystemdBootAdapter

ALL_ADAPTERS: List[BootloaderAdapter] = [
    SystemdBootAdapter(),
    GrubAdapter(),
    RefindAdapter(),
    LimineAdapter(),
]


def get_all_adapters() -> List[BootloaderAdapter]:
    """Returns all available bootloader adapters."""
    return list(ALL_ADAPTERS)


def get_active_adapter(inventory: Optional[Dict[str, Any]] = None) -> Optional[BootloaderAdapter]:
    """
    Returns the adapter matching the active bootloader, or None if unrecognized.
    """
    if inventory is None:
        from tasks.secureboot.inventory import inspect_full_inventory
        inventory = inspect_full_inventory()

    for adapter in ALL_ADAPTERS:
        if adapter.detect(inventory):
            return adapter
    return None

