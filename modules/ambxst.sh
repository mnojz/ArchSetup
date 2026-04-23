#!/usr/bin/env bash

section "Installing ambxst"

if ask_yes_no "Install ambxst shell?"; then
    if ! command -v ambxst &>/dev/null; then
        log "Installing ambxst..."
        curl -fsSL https://get.axeni.de/ambxst | sh
    else
        log "ambxst already installed"
    fi
else
    log "Skipping ambxst installation"
fi