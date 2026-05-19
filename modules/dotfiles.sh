#!/usr/bin/env bash

section "Installing all the configs and dotfiles..."

if ask_yes_no "Install all dotfiles?"; then
    cd ~
    git clone --depth=1 https://github.com/mnojz/dotfiles.git
    cd dotfiles
    ./install.sh

else
    log "Skipping dotfile installation"
fi