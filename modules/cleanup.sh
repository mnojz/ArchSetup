#!/usr/bin/env bash

set -euo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

section "Removing conflicting packages"

REMOVE_PKGS=(
    network-manager-applet
    blueman
    dunst
)

mapfile -t INSTALLED_REMOVE_PKGS < <(
    pacman -Qq "${REMOVE_PKGS[@]}" 2>/dev/null || true
)

if [[ ${#INSTALLED_REMOVE_PKGS[@]} -gt 0 ]]; then
    yay -Rns --noconfirm --removemake "${INSTALLED_REMOVE_PKGS[@]}"
else
    log "No conflicting packages installed; skipping removal"
fi

# ---------------------------------------------------------------------
# Default shell
# ---------------------------------------------------------------------

chsh -s /bin/fish "$USER"

# ---------------------------------------------------------------------
# udev rules and power-event 
# ---------------------------------------------------------------------

# sudo cp "$MODULE_DIR/assets/99-msi-ec.rules" /etc/udev/rules.d/99-msi-ec.rules
# sudo cp "$MODULE_DIR/assets/power-event.sh" /usr/local/bin/power-event.sh

# ---------------------------------------------------------------------
# mkinitcpio
# ---------------------------------------------------------------------

sudo cp "$MODULE_DIR/assets/mkinitcpio.conf" /etc/mkinitcpio.conf

# regenerate initramfs
sudo mkinitcpio -P

# ---------------------------------------------------------------------
# systemd-boot
# ---------------------------------------------------------------------

sudo cp "$MODULE_DIR/assets/loader.conf" \
    /boot/loader/loader.conf

ENTRY_FILE=$(sudo find /boot/loader/entries -maxdepth 1 -name "*.conf" | head -n1)

EXTRA_OPTS="quiet splash loglevel=3 systemd.show_status=error rd.udev.log_level=3 vt.global_cursor_default=0 nvidia_drm.modeset=1"

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

# ---------------------------------------------------------------------
# SDDM
# ---------------------------------------------------------------------

sudo mkdir -p /etc/systemd/system/sddm.service.d
sudo mkdir -p /etc/sddm.conf.d

sudo cp "$MODULE_DIR/assets/override.conf" \
    /etc/systemd/system/sddm.service.d/override.conf

cp "$MODULE_DIR/assets/.face.icon" "$HOME/.face.icon"

sudo tee /etc/sddm.conf.d/theme.conf >/dev/null <<'EOF'
[Theme]
Current=silent
EOF

sudo tee /etc/sddm.conf.d/general.conf >/dev/null <<'EOF'
[General]
Numlock=on
EOF

if [[ -d /usr/share/sddm/themes/silent ]]; then
    sudo cp \
        "$MODULE_DIR/assets/metadata.desktop" \
        /usr/share/sddm/themes/silent/metadata.desktop

    sudo /usr/share/sddm/themes/silent/change_avatar.sh \
        "$USER" \
        "$MODULE_DIR/assets/.face.icon"
else
    echo "SDDM silent theme not found. Install sddm-silent-theme first."
fi

# Reload systemd because a service override was installed
sudo systemctl daemon-reload

# Restart SDDM last
sudo systemctl restart sddm