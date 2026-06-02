#!/usr/bin/env bash

section "removing conflicting packages"

yay -Rns --noconfirm --removemake network-manager-applet blueman dunst 

chsh -s /bin/fish $USER

# mkinitcpio
sudo cp "$MODULE_DIR/assets/mkinitcpio.conf" /etc/mkinitcpio.conf

# systemd-boot loader config
sudo cp "$MODULE_DIR/assets/loader.conf" /boot/loader/loader.conf

# boot entry config
ENTRY_FILE=$(find /boot/loader/entries -maxdepth 1 -name "*.conf" | head -n1)

EXTRA_OPTS=" quiet splash loglevel=3 systemd.show_status=error rd.udev.log_level=3 vt.global_cursor_default=0 nvidia_drm.modeset=1"

if [[ -n "$ENTRY_FILE" ]]; then
    sudo sed -i "/^options / {
        s/quiet//g;
        s/splash//g;
        s/loglevel=3//g;
        s/systemd.show_status=error//g;
        s/rd.udev.log_level=3//g;
        s/vt.global_cursor_default=0//g;
        s/nvidia_drm.modeset=1//g;
        s/[[:space:]]\+/ /g;
        s/[[:space:]]$//;
        s/$/ $EXTRA_OPTS/
    }" "$ENTRY_FILE"
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