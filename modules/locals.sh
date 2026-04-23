#!/usr/bin/env bash

section "Installing local scripts"

if ask_yes_no "Install local scripts to ~/.local/bin/scripts?"; then

    LOCAL_TMP=$(mktemp -d)

    log "Cloning local repo..."

    if ! git clone --depth=1 https://github.com/mnojz/.local.git "$LOCAL_TMP"; then
        log "Failed to clone repo"
        rm -rf "$LOCAL_TMP"
        return 1 2>/dev/null || exit 1
    fi

    SRC="$LOCAL_TMP/bin/scripts"
    DEST="$HOME/.local/bin/scripts"

    if [ -d "$SRC" ]; then
        log "Installing scripts folder"

        mkdir -p "$HOME/.local/bin"

        # safety check
        if [[ -n "$DEST" && "$DEST" == "$HOME/.local/"* ]]; then
            rm -rf "$DEST"
        else
            log "Skipping unsafe path: $DEST"
        fi

        cp -r "$SRC" "$DEST"
        chmod -R +x "$DEST"

        log "Local scripts installed"
    else
        log "scripts folder not found in repo"
    fi

    rm -rf "$LOCAL_TMP"

else
    log "Skipping local scripts installation"
fi