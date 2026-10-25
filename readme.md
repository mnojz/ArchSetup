# 🚀 ArchSetup: Arch Linux + Hyprland Post-Install Suite

[![Arch Linux](https://img.shields.io/badge/Arch_Linux-1793D1?style=for-the-badge&logo=arch-linux&logoColor=white)](https://archlinux.org)
[![Hyprland](https://img.shields.io/badge/Hyprland-00A896?style=for-the-badge&logo=wayland&logoColor=white)](https://hyprland.org)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Rich TUI](https://img.shields.io/badge/TUI-Rich_Framework-magenta?style=for-the-badge&logo=gnubash&logoColor=white)](https://github.com/Textualize/rich)
[![Wayland](https://img.shields.io/badge/Display-Wayland-FFA500?style=for-the-badge&logo=wayland&logoColor=white)](https://wayland.freedesktop.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> Reproducible, fast, and visually stunning automation suite that turns a minimal Arch Linux installation into a fully configured, daily-driver Hyprland workstation with a single command.

---

## 🎨 Interactive TUI Showcase

ArchSetup features a fully interactive keyboard-driven TUI engine built with native ANSI escape sequence handling. Simply run the launcher and navigate with `↑/↓` or `j/k`.

### Main Action Menu

```text
  ╭─╮┬─╮╭─╮┬ ┬   ╭─╮┌─┐┌┬┐┬ ┬┌─┐   User:   manoj
  ├─┤├┬╯│  ├─┤   ╰─╮├┤  │ │ │├─┘   Host:   archlinux
  ┴ ┴┴└─╰─╯┴ ┴   ╰─╯└─┘ ┴ └─┘┴     Kernel: 7.2.11-arch1-1

                        Arch Linux Setup Main Menu                        
╭──────────────────────────────────────┬────────────────────┬────────────╮
│ Action                               │ Category           │ Privilege  │
├──────────────────────────────────────┼────────────────────┼────────────┤
│ ▸ 󰑣  Full Installation Suite         │ All-in-One         │    Sudo    │
│   󰏖  Audit & Sync Packages           │ Package Mgmt       │    User    │
│   󰒅  Category Checklist              │ Selective          │    User    │
│   󰓅  System Diagnostic Doctor        │ Diagnostics        │    User    │
│   󰛄  Pacman Turbo Boost              │ Optimization       │    Sudo    │
│   󰖟  Mirrorlist Optimization         │ Networking         │    Sudo    │
│   󰏔  Deploy User Dotfiles            │ Personalization    │    User    │
│   󰘚  Desktop & MIME Integration      │ Desktop Fix        │    User    │
│   󰒓  System Tuning & Bootloader      │ Hardware & Boot    │    Sudo    │
│   󰃢  Maintenance Cache Cleanup       │ Maintenance        │    Sudo    │
│   󰈙  View Installation Logs          │ Logging            │    User    │
│   󰈆  Exit Setup                      │ Quit               │    User    │
╰──────────────────────────────────────┴────────────────────┴────────────╯
╭────────────── Option Details • 󰑣 Full Installation Suite ──────────────╮
│  Runs the complete automated post-installation pipeline from start to  │
│  finish.                                                               │
│                                                                        │
│  Executes all 9 sequential phases: pacman turbo boost, yay bootstrap,  │
│  mirrorlist ranking, package manifests, Dolphin MIME integration,      │
│  Ambxst shell, bundled dotfiles, Fluent UOSC, and system configuration.│
│                                                                        │
│  Privilege: Sudo Elevation Required   •   Category: All-in-One         │
╰────────────────────────────────────────────────────────────────────────╯
  Navigation: ↑/↓ or j/k • Enter Select • q Exit
```

### Multi-Select Category Checklist

Use `Space` to toggle individual categories, `a` to toggle all, and `Enter` to install missing packages:

```text
                  Select Software Categories to Install                   
╭──────┬──────────────────────────────────┬──────────────┬───────────────╮
│ Sel  │ Category                         │     Packages │    Status     │
├──────┼──────────────────────────────────┼──────────────┼───────────────┤
│  󰄲   │ ▸   Shell & CLI Productivity    │      17 pkgs │   Included    │
│  󰄲   │   󰖲  Hyprland & Desktop System   │       8 pkgs │   Included    │
│  󰄲   │     Multimedia & Creative       │       8 pkgs │   Included    │
│  󰄱   │   󰊴  Gaming & Compatibility      │       2 pkgs │   Excluded    │
╰──────┴──────────────────────────────────┴──────────────┴───────────────╯
╭────────── Category Details • 󰏖 Shell & CLI Productivity ───────────────╮
│  Modern shells, prompt, fetch, editors, search tools                   │
│                                                                        │
│  Packages (17): fish, starship, fastfetch, eza, zoxide, fzf...         │
│                                                                        │
│  Status: Selected for installation   •   Toggle with Space             │
╰────────────────────────────────────────────────────────────────────────╯
  Navigation: ↑/↓ or j/k • Space Toggle • a Toggle All • Enter Confirm • q Cancel
```

---

## ⚡ Key Highlights

- **Interactive Arrow-Key Navigation**: Native raw-terminal input handling (`↑/↓`, `j/k`, `Space`, `Enter`) with zero extra runtime requirements.
- **System Diagnostic Doctor**: Built-in subsystem health checker validating Hyprland, PipeWire/WirePlumber, CPU microcode, VA-API acceleration, sudo, and AUR helpers.
- **Hardware & GPU Auto-Detection**: Dynamically inspects CPU vendor (Intel vs AMD microcode) and GPU controllers (NVIDIA `nvidia_drm.modeset=1`, Intel VA-API, AMD Mesa).
- **Pacman Turbo Boost**: Accelerates downloads up to 5x with `ParallelDownloads = 5`, `Color`, and `ILoveCandy` progress styling.
- **Local Manifest Overrides (`packages.local.json`)**: Add personal software packages or custom categories without dirtying git tracking.
- **Hybrid Package Router**: Checks official sync databases first, with seamless fallback to AUR (`yay`/`paru`).
- **In-Memory Cache Scanning**: Inspects installed packages in under 0.05 seconds via `pacman -Qq`.
- **Zero-Crash Safety Engineering**:
  - Automatically preserves disk encryption (`encrypt`/`sd-encrypt`) and LVM hooks in `mkinitcpio.conf`.
  - Non-blocking flags (`--answerclean None --answerdiff None`) prevent background AUR build hangs.
  - Active display server protection prevents compositor shutdowns while running under Wayland/X11.
  - Background sudo keepalive loop ensures credentials do not expire during long compilation steps.

---

## 🚀 Quick Start

### Option A: One-Line Remote Launch (Recommended)

Run the remote bootstrapper directly on a fresh Arch Linux installation:

```bash
curl -sL mnojz.github.io/ArchSetup/install.sh | bash
```

### Option B: Manual Git Clone

```bash
git clone https://github.com/mnojz/ArchSetup.git
cd ArchSetup
./setup.sh
```

---

## 🛡️ Fresh-Install Hardening

ArchSetup was audited and tested specifically to prevent common post-install failures:

> [!IMPORTANT]
> **Disk Encryption (LUKS) Preservation**  
> If your Arch install uses full disk encryption (`encrypt` / `sd-encrypt`) or LVM, replacing `mkinitcpio.conf` blindly causes an unbootable system. ArchSetup automatically detects active encryption hooks in `/etc/mkinitcpio.conf` and preserves them when rebuilding initramfs.

> [!NOTE]
> **Non-Interactive AUR Builds**  
> By default, `yay` prompts for CleanBuild and Diff reviews, which causes background shell scripts to hang indefinitely. ArchSetup invokes `yay` with `--answerclean None --answerdiff None --noconfirm` to guarantee uninterrupted automated execution.

> [!WARNING]
> **Display Server Protection**  
> Restarting SDDM from inside an active graphical session terminates your Wayland compositor and abruptly kills your terminal window. ArchSetup detects active `$WAYLAND_DISPLAY` or `$DISPLAY` environments and defers display manager restarts to the final system reboot.

---

## 🛠️ Customization Guide

### Local Custom Manifest (`packages.local.json`)

To add your own personal packages or categories without modifying git-tracked `packages.json`, simply create a `packages.local.json` file in the project root:

```json
{
  "categories": [
    {
      "id": "personal_tools",
      "name": "My Personal Tools",
      "icon": "🛠️",
      "description": "Custom utilities and developer tools",
      "packages": [
        "tmux",
        "btop",
        "lazygit"
      ]
    }
  ]
}
```

ArchSetup automatically detects and merges `packages.local.json` at runtime during all inspection, audit, and installation steps.

---

## 📜 License

Distributed under the **MIT License**. See the repository root for details.

- Designed with ❤️ for **Arch Linux** and **Hyprland**.
- Dotfiles: Bundled in `dotfiles/` module (managed via GNU Stow)
- MPV Theme: [`mnojz/fluent_UOSC`](https://github.com/mnojz/fluent_UOSC)
- SDDM Theme: [`uiriansan/SilentSDDM`](https://github.com/uiriansan/SilentSDDM)
- TUI powered by [Textualize/rich](https://github.com/Textualize/rich).
