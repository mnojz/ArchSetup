#!/usr/bin/env bash

section "Optional packages"

log "useful apps" 
log "from pacman\n 1. flatpak\n 2. libreoffice\n 3. yazi\n 4. wine\n 5. winetricks\n 6. qbittorrent\n 7. zed\n 8. pdfarranger\n 9. mousepad"
log "from AUR\n 1. localsend"
if ask_yes_no "Install useful packages?"; then
    install_pacman flatpak libreoffice yazi wine winetricks qbittorrent zed pdfarranger mousepad
    install_aur localsend
else
    log "Skipping useful packages"
fi

log "less useful apps"
log "from pacman\n 1. blender\n 2. kdenlive\n 3. cava\n 4. gaphor\n 5. ghex\n 6. thefuck\n 7. freecad\n 8. gnome-system-monitor\n 9. gnome-calculator\n 10. gnome-font-viewer\n 11. gnome-software"
log "from AUR \n 1. anydesk\n 2. faker\n 3. unimatrix\n 4. peaclock"
if ask_yes_no "Install less useful packages?"; then
    install_pacman blender kdenlive cava gaphor ghex thefuck freecad gnome-system-monitor gnome-calculator gnome-font-viewer gnome-software
    install_aur anydesk faker unimatrix peaclock 
else
    log "Skipping less useful packages"
fi
