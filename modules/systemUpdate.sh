#!/usr/bin/env bash

section "System update"

if ask_yes_no "Run full system update now?"; then
    log "Updating system..."
    sudo pacman -Syu --noconfirm
else
    log "Skipping system update"
fi