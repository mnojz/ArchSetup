#!/usr/bin/env bash

section "Installing yay"

if ! command -v yay &>/dev/null; then
    sudo pacman -S --needed --noconfirm git base-devel

    TMP_DIR=$(mktemp -d)
    git clone https://aur.archlinux.org/yay-bin.git "$TMP_DIR"

    (
        cd "$TMP_DIR"
        makepkg -si --noconfirm
    )

    rm -rf "$TMP_DIR"
else
    log "yay already installed"
fi