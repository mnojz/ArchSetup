#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/modules/helpers.sh"

source "$SCRIPT_DIR/modules/yayInstall.sh"          # good
source "$SCRIPT_DIR/modules/mirrors.sh"             # good
source "$SCRIPT_DIR/modules/systemUpdate.sh"        # good
source "$SCRIPT_DIR/modules/corePackages.sh"        # good
source "$SCRIPT_DIR/modules/fixDolphinMIME.sh"      # good
source "$SCRIPT_DIR/modules/ambxst.sh"              # good
source "$SCRIPT_DIR/modules/configs.sh"             # good
source "$SCRIPT_DIR/modules/locals.sh"              # good
source "$SCRIPT_DIR/modules/dotfiles.sh"            # good
source "$SCRIPT_DIR/modules/ytd.sh"                 # good
source "$SCRIPT_DIR/modules/optionalPackages.sh"    # good

hyprctl reload

section "Done!"
echo -e "\e[32mSystem setup complete. Reboot recommended.\e[0m"
