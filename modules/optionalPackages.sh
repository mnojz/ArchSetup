#!/usr/bin/env bash

section "Optional packages"

if ask_yes_no "Install useful packages?"; then
    install_pacman flatpak libreoffice yazi wine winetricks qbittorrent zed pdfarranger mousepad gnome-software gnome-calculator cava gaphor ghex
    install_aur unimatrix peaclock
else
    log "Skipping useful packages"
fi