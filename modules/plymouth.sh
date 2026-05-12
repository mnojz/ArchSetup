#!/usr/bin/env bash

section "installing plymouth theme"

git clone --depth 1 https://github.com/catppuccin/plymouth.git
cd plymouth/theme
sudo cp -r catppuccin-mocha/ /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R catppuccin-mocha
