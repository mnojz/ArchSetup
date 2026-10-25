#!/usr/bin/env bash
# ==============================================================================
# ArchSetup: One-Line Remote Installer & Bootstrapper
# ==============================================================================
# Usage:
#   curl -sL mnojz.github.io/ArchSetup/install.sh | bash
#   or
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/mnojz/ArchSetup/main/install.sh)"
# ==============================================================================
set -euo pipefail

main() {
    # Safety check: Do not execute directly as root
    if [[ "${EUID}" -eq 0 ]]; then
        echo -e "\e[31m[ERROR]\e[0m Please run this script as your regular user, not root."
        echo -e "        Root permissions will be requested automatically via sudo when necessary."
        exit 1
    fi

    REPO_URL="https://github.com/mnojz/ArchSetup.git"
    TARGET_DIR="${HOME}/ArchSetup"

    echo -e "\e[1;36m::\e[0m \e[1mArchSetup One-Line Bootstrapper\e[0m"

    # Ensure essential bootstrap tools exist before cloning
    BOOTSTRAP_PKGS=()
    for pkg in git python python-rich base-devel; do
        if ! pacman -Qi "${pkg}" &>/dev/null; then
            BOOTSTRAP_PKGS+=("${pkg}")
        fi
    done

    if [[ ${#BOOTSTRAP_PKGS[@]} -gt 0 ]]; then
        echo -e "\e[36m[INFO]\e[0m Installing bootstrap dependencies: ${BOOTSTRAP_PKGS[*]}..."
        if [[ -r /dev/tty ]]; then
            sudo pacman -Sy --needed --noconfirm "${BOOTSTRAP_PKGS[@]}" < /dev/tty
        else
            sudo pacman -Sy --needed --noconfirm "${BOOTSTRAP_PKGS[@]}"
        fi
    fi

    # Clone or update repository
    if [[ -d "${TARGET_DIR}/.git" ]]; then
        echo -e "\e[36m[INFO]\e[0m Updating existing repository in ${TARGET_DIR}..."
        git -C "${TARGET_DIR}" pull --ff-only 2>/dev/null || true
    else
        echo -e "\e[36m[INFO]\e[0m Cloning ArchSetup repository to ${TARGET_DIR}..."
        git clone "${REPO_URL}" "${TARGET_DIR}"
    fi

    cd "${TARGET_DIR}"
    if [[ -r /dev/tty ]]; then
        exec bash "${TARGET_DIR}/setup.sh" "$@" < /dev/tty
    else
        exec bash "${TARGET_DIR}/setup.sh" "$@"
    fi
}

main "$@"
