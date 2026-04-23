#!/usr/bin/env bash

section "Mirror optimization (rate-mirrors)"

if ask_yes_no "Optimize mirrors now?"; then

    if ! command -v rate-mirrors &>/dev/null; then
        log "Installing rate-mirrors (AUR)"
        install_aur rate-mirrors
    else
        log "rate-mirrors already installed"
    fi

    # backup (safe)
    sudo cp /etc/pacman.d/mirrorlist /etc/pacman.d/mirrorlist.backup 2>/dev/null || true

    log "Updating mirrorlist using rate-mirrors"

    if rate-mirrors --protocol https --latest 20 arch | sudo tee /etc/pacman.d/mirrorlist >/dev/null; then
        log "Mirrorlist updated successfully"
    else
        log "rate-mirrors failed"
        return 1 2>/dev/null || exit 1
    fi

else
    log "Skipping mirror optimization"
fi