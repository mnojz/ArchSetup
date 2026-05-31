#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# contains helper functions like log, section, ask_yes_no, pkg_installed, install_pacman, install_aur
source "$SCRIPT_DIR/modules/helpers.sh"
# actual modules to perform tasks
source "$SCRIPT_DIR/modules/yayInstall.sh"          # install yay AUR helper
source "$SCRIPT_DIR/modules/mirrors.sh"             # update mirrorlist
source "$SCRIPT_DIR/modules/systemUpdate.sh"        # update system
source "$SCRIPT_DIR/modules/corePackages.sh"        # install core packages for my setup
source "$SCRIPT_DIR/modules/fixDolphinMIME.sh"      # fix dolphin mimetype issue
source "$SCRIPT_DIR/modules/ambxst.sh"              # install ambxst shell
source "$SCRIPT_DIR/modules/dotfiles.sh"            # installing dotfiles like mpv uosc and NvChad
source "$SCRIPT_DIR/modules/ytd.sh"                 # install ytd protocol handler
source "$SCRIPT_DIR/modules/cleanup.sh"             # remove conflicting packages

xdg-user-dirs-update
hyprctl reload

section "Done!"
echo -e "\e[32mSystem setup complete. Reboot recommended.\e[0m"
