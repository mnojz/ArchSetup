"""
ArchSetup Privilege Elevation & Sudo Authentication Manager
Provides in-TUI password prompting, background keepalive, and graceful failure handling.
"""

import os
import sys
import getpass
import subprocess
from typing import Optional
from core import tui

_keepalive_proc: Optional[subprocess.Popen] = None

def is_sudo_active() -> bool:
    """Checks if sudo credential timestamp is currently active and valid."""
    try:
        res = subprocess.run(
            ["sudo", "-n", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False

def start_keepalive():
    """Starts background sudo keepalive if not already running."""
    global _keepalive_proc
    if _keepalive_proc and _keepalive_proc.poll() is None:
        return
    try:
        _keepalive_proc = subprocess.Popen(
            ["bash", "-c", "while true; do sudo -n true 2>/dev/null; sleep 50; kill -0 $$ 2>/dev/null || exit; done"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def request_sudo_auth(action_name: str = "this operation", max_attempts: int = 3) -> bool:
    """
    Prompts for sudo password inside the application TUI.
    Returns True if authentication succeeds, False if cancelled or failed.
    Never exits the script on error; control returns to the caller.
    """
    if is_sudo_active():
        start_keepalive()
        return True

    user = os.environ.get("USER", os.getlogin() if hasattr(os, "getlogin") else "user")

    from rich.panel import Panel
    from rich import box

    panel = Panel(
        f"[bold white]Root privileges are required for:[/] [bold cyan]{action_name}[/]\n"
        f"[dim]User:[/] [cyan]{user}[/]  •  [dim]Press [bold yellow]Ctrl+C[/] to cancel and return to menu",
        title="[bold yellow]󰌾 Sudo Authentication Required[/]",
        box=box.ROUNDED,
        border_style="yellow",
        width=tui.get_terminal_width(),
        padding=(0, 2)
    )

    tui.console.print()
    tui.console.print(panel)

    for attempt in range(1, max_attempts + 1):
        try:
            prompt_str = f"  [bold cyan]󰌆 Password for {user}: [/]"
            tui.console.print(prompt_str, end="")
            sys.stdout.flush()

            # Read password securely without terminal echo
            password = getpass.getpass(prompt="")

            if not password:
                tui.log_warning("No password entered. Authentication cancelled.")
                return False

            # Verify password using sudo -S -v
            proc = subprocess.run(
                ["sudo", "-S", "-v"],
                input=password + "\n",
                text=True,
                capture_output=True,
                check=False
            )

            if proc.returncode == 0:
                tui.log_success("Sudo credentials verified and session activated.")
                start_keepalive()
                return True
            else:
                remaining = max_attempts - attempt
                if remaining > 0:
                    tui.log_error(f"Incorrect password. Please try again ({remaining} attempt{'s' if remaining > 1 else ''} left).")
                else:
                    tui.log_error("Authentication failed: too many incorrect attempts.")
                    return False

        except (KeyboardInterrupt, EOFError):
            tui.console.print()
            tui.log_warning("Authentication cancelled by user.")
            return False

    return False

