#!/usr/bin/env bash

section "Applying config files (dynamic)"

if ask_yes_no "Replace all config files in ~/.config?"; then

    CONFIG_TMP=$(mktemp -d)

    log "Cloning config repo..."

    if ! git clone --depth=1 https://github.com/mnojz/.config.git "$CONFIG_TMP"; then
        log "Failed to clone config repo"
        rm -rf "$CONFIG_TMP"
        return 1 2>/dev/null || exit 1
    fi

    mkdir -p "$HOME/.config"

    for item in "$CONFIG_TMP"/*; do
        name=$(basename "$item")
        target="$HOME/.config/$name"

        log "Replacing $name"

        if [[ -n "$target" && "$target" == "$HOME/.config/"* ]]; then
            rm -rf "$target"
        else
            log "Skipping unsafe path: $target"
            continue
        fi

        cp -r "$item" "$target"
    done

    rm -rf "$CONFIG_TMP"

    log "Config files applied successfully"

else
    log "Skipping config setup"
fi