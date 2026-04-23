#!/usr/bin/env bash

section "Optional packages"

if ask_yes_no "Install optional packages?"; then
    install_pacman flatpak libreoffice blender kdenlive cava gaphor ghex yazi wine winetricks thefuck freecad
    install_aur anydesk pamac faker unimatrix peaclock localsend
else
    log "Skipping optional packages"
fi


# ========= flatpak =========
section "Setting up flatpak"

if ask_yes_no "Install Flatpak apps?"; then

    if ! command -v flatpak &>/dev/null; then
        log "Installing flatpak"
        sudo pacman -S --needed --noconfirm flatpak
    else
        log "flatpak already installed"
    fi

    log "Adding Flathub remote"
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

    log "Installing flatpak apps"
    flatpak install -y --noninteractive flathub \
        com.stremio.Stremio \
        org.gnome.Snapshot \
        org.gnome.gitlab.YaLTeR.VideoTrimmer || true

else
    log "Skipping flatpak setup"
fi