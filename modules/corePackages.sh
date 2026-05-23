#!/usr/bin/env bash

section "Installing core packages"

PACMAN_PKGS=(
    fish fastfetch curl wget unzip p7zip polkit-gnome
    bluetui acpi net-tools neovim mpv cliphist fzf rsync
    kdeconnect sshfs evtest xorg-xev ripgrep zoxide evince
    ffmpegthumbnailer resvg nerd-fonts mousepad gnome-keyring
    imv android-tools raylib decibels pdfarranger xdg-user-dirs 
    eza archlinux-xdg-menu gpu-screen-recorder plymouth ark
    intel-media-driver libva-nvidia-driver libva-utils starship
    hyprpicker 
)

AUR_PKGS=(
    brave-origin-beta-bin
    visual-studio-code-bin
    apple-fonts pacseek
    font-noto-cjk frameworkintegration darkly-bin
    qt6ct-kde kora-icon-theme
    sddm-silent-theme
)

install_pacman "${PACMAN_PKGS[@]}"
install_aur "${AUR_PKGS[@]}"
