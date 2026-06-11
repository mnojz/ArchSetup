#!/usr/bin/env bash

section "Installing core packages"

PACMAN_PKGS=(
    fish fastfetch curl wget unzip p7zip polkit-gnome gnome-software 
    bluetui acpi net-tools neovim mpv cliphist fzf rsync mousepad 
    kdeconnect sshfs evtest xorg-xev ripgrep zoxide evince gnome-calculator
    ffmpegthumbnailer resvg nerd-fonts mousepad gnome-keyring flatpak 
    imv android-tools raylib decibels pdfarranger xdg-user-dirs libreoffice
    eza archlinux-xdg-menu gpu-screen-recorder plymouth ark pdfarranger 
    intel-media-driver libva-nvidia-driver libva-utils starship man
    hyprpicker yazi wine winetricks qbittorrent cava gaphor ghex
)

AUR_PKGS=(
    brave-origin-bin
    vscodium-bin
    apple-fonts pacseek peaclock
    frameworkintegration darkly-bin
    qt6ct-kde kora-icon-theme
    sddm-silent-theme unimatrix 
)

install_pacman "${PACMAN_PKGS[@]}"
install_aur "${AUR_PKGS[@]}"
