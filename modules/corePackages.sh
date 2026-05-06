#!/usr/bin/env bash

section "Installing core packages"

PACMAN_PKGS=(
    fish fastfetch curl wget unzip p7zip polkit-gnome
    bluetui acpi net-tools neovim mpv cliphist fzf
    kdeconnect evtest xorg-xev ripgrep zoxide evince
    ffmpegthumbnailer resvg nerd-fonts mousepad
    imv android-tools raylib decibels pdfarranger
    eza archlinux-xdg-menu gpu-screen-recorder                    
)

AUR_PKGS=(
    brave-origin-beta-bin
    visual-studio-code-bin
    apple-fonts pacseek
    font-noto-cjk darkly-bin
    qt6ct-kde kora-icon-theme
)

install_pacman "${PACMAN_PKGS[@]}"
install_aur "${AUR_PKGS[@]}"
