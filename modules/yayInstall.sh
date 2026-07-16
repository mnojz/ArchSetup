#!/usr/bin/env bash

section "Installing yay"

if ! command -v yay &>/dev/null; then
    install_pacman git base-devel

    if ! command -v git &>/dev/null; then
        log "Skipping yay installation because git is unavailable"
        return 0 2>/dev/null || exit 0
    fi

    TMP_DIR=$(mktemp -d)
    if ! git clone https://aur.archlinux.org/yay-bin.git "$TMP_DIR"; then
        log "Failed to clone yay-bin; skipping yay installation"
        rm -rf "$TMP_DIR"
        return 0 2>/dev/null || exit 0
    fi

    (
        cd "$TMP_DIR"
        makepkg -si --noconfirm || log "Failed to build/install yay-bin; skipping"
    )

    rm -rf "$TMP_DIR"
else
    log "yay already installed"
fi