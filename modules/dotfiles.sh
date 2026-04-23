#!/usr/bin/env bash

section "Installing mpv uosc + NvChad"

if ask_yes_no "Install mpv uosc and NvChad?"; then

    log "Installing mpv uosc..."
    bash -c "$(curl -fsSL https://raw.githubusercontent.com/tomasklaen/uosc/HEAD/installers/unix.sh)"

    if [ ! -d "$HOME/.config/nvim" ]; then
        log "Cloning NvChad..."
        git clone https://github.com/NvChad/starter ~/.config/nvim
    else
        log "nvim config exists, skipping"
    fi

else
    log "Skipping mpv uosc and NvChad"
fi