#!/usr/bin/env bash

section "removing conflicting packages"

yay -Rns --noconfirm --removemake network-manager-applet blueman dunst 

chsh -s /bin/fish $USER

# mkinitcpio
sudo cp "$MODULE_DIR/assets/mkinitcpio.conf" /etc/mkinitcpio.conf

# systemd-boot loader config
sudo cp "$MODULE_DIR/assets/loader.conf" /boot/loader/loader.conf

# boot entry (arch.conf contents -> existing entry)
ENTRY_FILE=$(find /boot/loader/entries -maxdepth 1 -name "*.conf" | head -n1)

if [[ -n "$ENTRY_FILE" ]]; then
    sudo cp "$MODULE_DIR/assets/arch.conf" "$ENTRY_FILE"
else
    echo "No boot entry found in /boot/loader/entries"
fi

# regenerate initramfs
sudo mkinitcpio -P

# SDDM configs
MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# copy .face.icon to home dir
cp "$MODULE_DIR/assets/.face.icon" ~/.face.icon

# ensure config dir
sudo mkdir -p /etc/sddm.conf.d

# set theme
echo -e "[Theme]\nCurrent=silent" | sudo tee /etc/sddm.conf.d/theme.conf >/dev/null

# ensure theme exists before copying
if [[ -d /usr/share/sddm/themes/silent ]]; then
    sudo cp "$MODULE_DIR/assets/metadata.desktop" /usr/share/sddm/themes/silent/metadata.desktop
    sudo /usr/share/sddm/themes/silent/change_avatar.sh $USER "$MODULE_DIR/assets/.face.icon"
else
    echo "SDDM silent theme not found. Install sddm-silent-theme first."
fi

# restart display manager
sudo systemctl restart sddm