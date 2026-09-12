#!/usr/bin/env bash

section "Installing core packages"

PACMAN_PKGS=(
    zsh fastfetch curl wget unzip p7zip polkit-gnome gnome-software 
    bluetui acpi net-tools neovim mpv cliphist fzf mousepad 
    kdeconnect sshfs evtest xorg-xev ripgrep zoxide evince gnome-calculator
    ffmpegthumbnailer resvg nerd-fonts mousepad gnome-keyring flatpak 
    eog android-tools raylib amberol pdfarranger xdg-user-dirs onlyoffice-bin
    eza archlinux-xdg-menu gpu-screen-recorder plymouth ark pdfarranger 
    intel-media-driver libva-nvidia-driver libva-utils starship man
    hyprpicker yazi wine winetricks qbittorrent cava gaphor ghex linux-headers
)

AUR_PKGS=(
    brave-origin-bin mcontrolcenter-bin
    visual-studio-code-bin mpv-mpris
    pacseek peaclock msi-ec-dkms-git
    frameworkintegration darkly-bin
    qt6ct-kde colloid-icon-theme-git
    sddm-silent-theme unimatrix 
)

install_pacman "${PACMAN_PKGS[@]}"
install_aur "${AUR_PKGS[@]}"
