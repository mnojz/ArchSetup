"""
Interactive Terminal Menu Engine
Provides arrow-key and vim-key (j/k) navigable menus and multi-select checklists.
"""

import sys
import tty
import termios
from typing import List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console(highlight=False)

def read_key() -> str:
    """Reads a single keypress or ANSI escape sequence from stdin."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                ch3 = sys.stdin.read(1)
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(ch3, "ESC")
            return "ESC"
        elif ch in ("\r", "\n"):
            return "ENTER"
        elif ch == " ":
            return "SPACE"
        elif ch == "\x03":
            return "CTRL_C"
        elif ch in ("k", "K"):
            return "UP"
        elif ch in ("j", "J"):
            return "DOWN"
        elif ch in ("q", "Q"):
            return "QUIT"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def interactive_select_menu(title: str, options: List[Tuple[str, str, str]]) -> str:
    """
    Renders an interactive arrow-navigable menu.
    options format: [(key_id, label, description)]
    """
    selected_idx = 0
    num_opts = len(options)

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            # Build menu table
            table = Table(
                title=f"[bold cyan]{title}[/]",
                box=box.ROUNDED,
                border_style="magenta",
                header_style="bold cyan",
                expand=True
            )
            table.add_column("Pointer", justify="center", width=4)
            table.add_column("Action", style="bold white", width=30)
            table.add_column("Description", style="dim")

            for idx, (opt_id, label, desc) in enumerate(options):
                if idx == selected_idx:
                    table.add_row(
                        "[bold cyan]➜[/]",
                        f"[bold cyan reverse] {label} [/]",
                        f"[bold white]{desc}[/]"
                    )
                else:
                    table.add_row(
                        " ",
                        f"  {label}",
                        desc
                    )

            # Clear screen area or render
            console.clear()
            console.print("[bold cyan]  ArchSetup[/] [magenta]•[/] [dim]Post-Installation Suite for Arch Linux + Hyprland[/]\n")
            console.print(table)
            console.print("  [dim]Navigation:[/] [bold cyan]↑/↓[/] or [bold cyan]j/k[/] [dim]•[/] [bold cyan]Enter[/] [dim]Select •[/] [bold cyan]q[/] [dim]Exit[/]\n")

            key = read_key()
            if key in ("UP",):
                selected_idx = (selected_idx - 1) % num_opts
            elif key in ("DOWN",):
                selected_idx = (selected_idx + 1) % num_opts
            elif key in ("ENTER",):
                return options[selected_idx][0]
            elif key in ("QUIT", "ESC", "CTRL_C"):
                return "quit"
    finally:
        # Restore cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def interactive_checklist_menu(title: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Renders a multi-select checkbox menu for categories or packages.
    Items format: [{'id': ..., 'name': ..., 'enabled': bool, 'packages': [...]}]
    """
    selected_idx = 0
    num_items = len(items)

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            table = Table(
                title=f"[bold cyan]{title}[/]",
                box=box.ROUNDED,
                border_style="magenta",
                header_style="bold cyan",
                expand=True
            )
            table.add_column("Pointer", justify="center", width=4)
            table.add_column("Selected", justify="center", width=10)
            table.add_column("Category", style="bold white", width=28)
            table.add_column("Count", justify="right", width=10)
            table.add_column("Description", style="dim")

            for idx, it in enumerate(items):
                is_selected = it.get("enabled", True)
                check_icon = "[bold green][✔][/]" if is_selected else "[dim][ ][/]"
                count_str = f"{len(it.get('packages', []))} pkgs"
                
                if idx == selected_idx:
                    table.add_row(
                        "[bold cyan]➜[/]",
                        check_icon,
                        f"[bold cyan reverse] {it['name']} [/]",
                        count_str,
                        it.get("description", "")
                    )
                else:
                    table.add_row(
                        " ",
                        check_icon,
                        f"  {it['name']}",
                        count_str,
                        it.get("description", "")
                    )

            console.clear()
            console.print("[bold cyan]  ArchSetup[/] [magenta]•[/] [dim]Package Category Checklist Selector[/]\n")
            console.print(table)
            console.print("  [dim]Navigation:[/] [bold cyan]↑/↓[/] or [bold cyan]j/k[/] [dim]•[/] [bold cyan]Space[/] [dim]Toggle •[/] [bold cyan]a[/] [dim]Toggle All •[/] [bold cyan]Enter[/] [dim]Confirm •[/] [bold cyan]q[/] [dim]Cancel[/]\n")

            key = read_key()
            if key in ("UP",):
                selected_idx = (selected_idx - 1) % num_items
            elif key in ("DOWN",):
                selected_idx = (selected_idx + 1) % num_items
            elif key in ("SPACE",):
                items[selected_idx]["enabled"] = not items[selected_idx].get("enabled", True)
            elif key in ("a", "A"):
                all_on = all(it.get("enabled", True) for it in items)
                for it in items:
                    it["enabled"] = not all_on
            elif key in ("ENTER",):
                return items
            elif key in ("QUIT", "ESC", "CTRL_C"):
                return items
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
