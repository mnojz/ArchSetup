"""
ArchSetup Modular Installation Tasks
"""

from tasks import (
    pacman_tuning,
    aur_bootstrap,
    mirror_ranking,
    package_installer,
    desktop_integration,
    ambxst_shell,
    dotfiles_deploy,
    system_configuration,
    secureboot,
)

__all__ = [
    "pacman_tuning",
    "aur_bootstrap",
    "mirror_ranking",
    "package_installer",
    "desktop_integration",
    "ambxst_shell",
    "dotfiles_deploy",
    "system_configuration",
    "secureboot",
]
