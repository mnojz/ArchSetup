#!/usr/bin/env bash

log() {
    echo -e "\e[36m[INFO]\e[0m $1"
}

section() {
	echo -e "\n\e[34m================================\e[0m"
	echo -e "\e[32m$1\e[0m"
	echo -e "\e[34m================================\e[0m"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"   # default = y
    local input=""

    if ! read -r -t 60 -p "$prompt [Y/n]: " input; then
        printf '\n'
        input=""
    fi

    # trim whitespace
    input="$(printf '%s' "$input" | xargs)"

    # apply default if empty
    input=${input:-$default}

    # normalize
    input=${input,,}

    case "$input" in
        y|yes) return 0 ;;
        n|no)  return 1 ;;
        *)
            log "Invalid input '$input' (expected y/yes or n/no)"
            return 1
            ;;
    esac
}

pkg_installed() {
	pacman -Qi "$1" &>/dev/null
}

install_pacman() {
    for pkg in "$@"; do
        if ! pkg_installed "$pkg"; then
            log "Installing $pkg"
            sudo pacman -S --noconfirm --needed "$pkg" || {
                log "Failed to install $pkg"
                return 1
            }
        else
            log "$pkg already installed"
        fi
    done
}

install_aur() {
    for pkg in "$@"; do
        if ! pkg_installed "$pkg"; then
            log "Installing $pkg (AUR)"
            yay -S --noconfirm --needed "$pkg" || {
                log "Failed to install $pkg from AUR"
                return 1
            }
        else
            log "$pkg already installed"
        fi
    done
}
