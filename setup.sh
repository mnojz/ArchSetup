#!/usr/bin/env bash
# ==============================================================================
# ArchSetup: Modern TUI Post-Installation Suite for Arch Linux + Hyprland
# ==============================================================================
set -euo pipefail

main() {
    # Safety check: Do not execute directly as root
    if [[ "${EUID}" -eq 0 ]]; then
        echo -e "\e[31m[ERROR]\e[0m Please run this script as your regular user, not root."
        echo -e "        Root permissions will be requested automatically via sudo when necessary."
        exit 1
    fi

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
    REPO_URL="https://github.com/mnojz/ArchSetup.git"
    TARGET_DIR="${HOME}/ArchSetup"

    # If running remotely / piped (core/main.py not found in script dir), bootstrap & clone
    if [[ ! -f "${SCRIPT_DIR}/core/main.py" ]]; then
        echo -e "\e[36m[INFO]\e[0m Remote execution detected. Bootstrapping ArchSetup..."

        if ! command -v git &>/dev/null; then
            echo -e "\e[36m[INFO]\e[0m Installing git and bootstrap dependencies..."
            if [[ -r /dev/tty ]]; then
                sudo pacman -Sy --needed --noconfirm git python python-rich base-devel < /dev/tty
            else
                sudo pacman -Sy --needed --noconfirm git python python-rich base-devel
            fi
        fi

        if [[ -d "${TARGET_DIR}/.git" ]]; then
            echo -e "\e[36m[INFO]\e[0m Updating existing repository in ${TARGET_DIR}..."
            git -C "${TARGET_DIR}" pull --ff-only 2>/dev/null || true
        else
            echo -e "\e[36m[INFO]\e[0m Cloning repository to ${TARGET_DIR}..."
            git clone "${REPO_URL}" "${TARGET_DIR}"
        fi

        cd "${TARGET_DIR}"
        if [[ -r /dev/tty ]]; then
            exec bash "${TARGET_DIR}/setup.sh" "$@" < /dev/tty
        else
            exec bash "${TARGET_DIR}/setup.sh" "$@"
        fi
    fi

    # Ensure essential bootstrap tools and TUI runtime are available
    BOOTSTRAP_PKGS=()
    for pkg in python python-rich git base-devel; do
        if ! pacman -Qi "${pkg}" &>/dev/null; then
            BOOTSTRAP_PKGS+=("${pkg}")
        fi
    done

    if [[ ${#BOOTSTRAP_PKGS[@]} -gt 0 ]]; then
        echo -e "\e[36m[INFO]\e[0m Initializing pacman databases and installing bootstrap tools: ${BOOTSTRAP_PKGS[*]}..."
        if [[ -r /dev/tty ]]; then
            sudo pacman -Sy --needed --noconfirm "${BOOTSTRAP_PKGS[@]}" < /dev/tty
        else
            sudo pacman -Sy --needed --noconfirm "${BOOTSTRAP_PKGS[@]}"
        fi
    fi

    # Launch Python orchestrator with all arguments preserved
    if [[ -r /dev/tty ]]; then
        exec python3 "${SCRIPT_DIR}/core/main.py" "$@" < /dev/tty
    else
        exec python3 "${SCRIPT_DIR}/core/main.py" "$@"
    fi
}

main "$@"
