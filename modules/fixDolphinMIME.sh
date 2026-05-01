#!/usr/bin/env bash

section "Fix Dolphin File Associations"

MENU_DIR="/etc/xdg/menus"
ARCH_MENU="$MENU_DIR/arch-applications.menu"
TARGET_MENU="$MENU_DIR/applications.menu"

if [[ -f "$ARCH_MENU" ]]; then
    log "Linking applications.menu → arch-applications.menu (force)"
    sudo ln -sf "$ARCH_MENU" "$TARGET_MENU"
else
    log "arch-applications.menu not found! Skipping symlink step."
fi

log "Removing old cache..."
rm -f ~/.cache/ksycoca6_* || true

log "Rebuilding cache..."
kbuildsycoca6 --noincremental

log "Updating system MIME database..."
sudo update-mime-database /usr/share/mime

DEFAULT_APP=$(xdg-mime query default text/plain || true)
log "Current default: ${DEFAULT_APP:-<none>}"
