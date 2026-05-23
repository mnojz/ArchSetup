#!/usr/bin/env bash

section "removing conflicting packages"

yay -Rns --noconfirm --removemake network-manager-applet blueman dunst 


# SDDM configs
MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ensure config dir
sudo mkdir -p /etc/sddm.conf.d

# set theme
echo -e "[Theme]\nCurrent=silent" | sudo tee /etc/sddm.conf.d/theme.conf >/dev/null

# ensure theme exists before copying
if [[ -d /usr/share/sddm/themes/silent ]]; then
    sudo cp "$MODULE_DIR/assets/metadata.desktop" \
        /usr/share/sddm/themes/silent/metadata.desktop
else
    echo "SDDM silent theme not found. Install sddm-silent-theme first."
fi

# restart display manager
sudo systemctl restart sddm