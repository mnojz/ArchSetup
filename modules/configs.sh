#!/usr/bin/env bash

section "Applying config files (dynamic)"

if ask_yes_no "Replace managed config files in ~/.config?"; then

    CONFIG_TMP=$(mktemp -d)

    # Always cleanup temp dir on exit/interruption
    trap 'rm -rf "$CONFIG_TMP"' EXIT

    log "Cloning config repo..."

    if ! git clone --depth=1 https://github.com/mnojz/.config.git "$CONFIG_TMP"; then
        log "Failed to clone config repo"
        return 1 2>/dev/null || exit 1
    fi

    mkdir -p "$HOME/.config"

    log "Syncing config files..."

    for item in "$CONFIG_TMP"/*; do

        # Skip if glob matches nothing
        [[ -e "$item" ]] || continue

        name=$(basename "$item")
        target="$HOME/.config/$name"

        log "Syncing $name"

        # Directory
        if [[ -d "$item" ]]; then

            mkdir -p "$target"

            rsync -a --delete \
                "$item"/ \
                "$target"/

        # File
        elif [[ -f "$item" ]]; then

            rsync -a \
                "$item" \
                "$target"

        else
            log "Skipping unsupported item: $name"
        fi

    done

    log "Config files applied successfully"

else
    log "Skipping config setup"
fi