#!/usr/bin/env bash

section "Installing YTD Protocol"

if ask_yes_no "Install YTD protocol handler?"; then

    YTD_TMP=$(mktemp -d)

    log "Cloning repository..."
    if ! git clone --depth=1 https://github.com/mnojz/easy-ytd-protocol.git "$YTD_TMP"; then
        log "Failed to clone repository"
        rm -rf "$YTD_TMP"
        return 1 2>/dev/null || exit 1
    fi

    if [ -f "$YTD_TMP/install.sh" ]; then
        (
            cd "$YTD_TMP"
            bash ./install.sh
        )
        log "YTD protocol installed"
    else
        log "install.sh not found in easy-ytd-protocol"
        rm -rf "$YTD_TMP"
        return 1 2>/dev/null || exit 1
    fi

    rm -rf "$YTD_TMP"

else
    log "Skipping YTD protocol installation"
fi