#!/usr/bin/env bash

section "Installing core packages"

PACMAN_PKGS=(
    fish fastfetch curl wget unzip p7zip
    bluetui acpi net-tools neovim mpv nautilus
    file-roller kdeconnect evtest xorg-xev
    ffmpegthumbnailer resvg nerd-fonts
    imv android-tools raylib decibels
    eza gedit gnome-system-monitor
    gpu-screen-recorder sushi evince
    zoxide ripgrep fzf cliphist polkit-gnome
    gnome-calculator gnome-font-viewer        
)

AUR_PKGS=(
    helium-browser-bin
    visual-studio-code-bin
    apple-fonts
    font-noto-cjk
    qt6ct-kde
)

install_pacman "${PACMAN_PKGS[@]}"
install_aur "${AUR_PKGS[@]}"
