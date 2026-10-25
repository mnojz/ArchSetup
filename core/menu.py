"""
Interactive Terminal Menu Engine
Provides arrow-key and vim-key (j/k) navigable compact menus with dynamic description cards.
"""

import sys
import tty
import termios
import shutil
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console(highlight=False)

# Vibrant color palettes for action icons and categories
ICON_COLORS = {
    "full": "bold magenta",
    "packages": "bold blue",
    "categories": "bold yellow",
    "doctor": "bold green",
    "tune_pacman": "bold bright_yellow",
    "mirrors": "bold cyan",
    "dotfiles": "bold bright_magenta",
    "desktop": "bold bright_blue",
    "system": "bold bright_cyan",
    "cleanup": "bold bright_red",
    "log": "bold bright_green",
    "quit": "bold red",
}

CATEGORY_COLORS = {
    "All-in-One": "bold magenta",
    "Package Mgmt": "cyan",
    "Selective": "yellow",
    "Diagnostics": "green",
    "Optimization": "bright_yellow",
    "Networking": "cyan",
    "Personalization": "bright_magenta",
    "Desktop Fix": "bright_blue",
    "Hardware & Boot": "bright_cyan",
    "Maintenance": "bright_red",
    "Logging": "bright_green",
    "Quit": "red",
}

CAT_ICON_COLORS = {
    "shell_cli": "cyan",
    "hyprland_desktop": "magenta",
    "multimedia": "yellow",
    "applications": "blue",
    "themes_fonts": "bright_magenta",
    "hardware_network": "bright_cyan",
    "gaming": "bright_red",
}

def get_menu_width() -> int:
    """Returns a comfortable, compact width for the menu."""
    cols = shutil.get_terminal_size((80, 24)).columns
    return max(60, min(cols - 2, 74))

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

def render_ascii_header(user: str, host: str, kernel: str, width: int):
    """Renders the wireframe ASCII logo and system metadata in a compact 3-line layout."""
    lines = [
        f"  [bold cyan]╭─╮┬─╮╭─╮┬ ┬   ╭─╮┌─┐┌┬┐┬ ┬┌─┐[/]   [bold magenta]User:[/]   [bold green]{user}[/]",
        f"  [bold cyan]├─┤├┬╯│  ├─┤   ╰─╮├┤  │ │ │├─┘[/]   [bold magenta]Host:[/]   [bold yellow]{host}[/]",
        f"  [bold cyan]┴ ┴┴└─╰─╯┴ ┴   ╰─╯└─┘ ┴ └─┘┴  [/]   [bold magenta]Kernel:[/] [bold cyan]{kernel}[/]"
    ]
    console.print("\n".join(lines))
    console.print()

def interactive_select_menu(
    title: str,
    items: List[Dict[str, Any]],
    user: str = "user",
    host: str = "archlinux",
    kernel: str = "linux"
) -> str:
    """
    Renders an interactive, compact arrow-navigable menu with colorful icons,
    vibrant categories, and dynamic description panel.
    """
    selected_idx = 0
    num_opts = len(items)
    width = get_menu_width()

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            console.clear()
            render_ascii_header(user, host, kernel, width)

            # Compact 3-Column Action Selection Table (No Ptr column)
            table = Table(
                title=f"[bold magenta]◆[/] [bold cyan]{title}[/][bold magenta] ◆[/]",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold magenta",
                width=width,
                padding=(0, 1),
                expand=False
            )
            table.add_column("Action", width=38)
            table.add_column("Category", width=20)
            table.add_column("Privilege", justify="center", width=12)

            for idx, it in enumerate(items):
                item_id = it.get("id", "")
                icon = it.get("icon", "•")
                title_str = it.get("title", "Option")
                tag_str = it.get("tag", "")
                is_sudo = it.get("sudo", False)

                icon_color = it.get("icon_color") or ICON_COLORS.get(item_id, "bold cyan")
                tag_color = CATEGORY_COLORS.get(tag_str, "cyan")

                # The icon is colored distinctly from the text!
                styled_icon = f"[{icon_color}]{icon}[/]"

                if idx == selected_idx:
                    # Neutral slate highlight with high contrast text
                    table.add_row(
                        f"[bold cyan]▸[/] {styled_icon}  [bold bright_white]{title_str}[/]",
                        f"[bold {tag_color}]{tag_str}[/]",
                        f"[bold red]Sudo[/]" if is_sudo else f"[bold green]User[/]",
                        style="on #2d3340"
                    )
                else:
                    priv_badge = f"[dim red]Sudo[/]" if is_sudo else f"[dim green]User[/]"
                    table.add_row(
                        f"  {styled_icon}  [white]{title_str}[/]",
                        f"[{tag_color}]{tag_str}[/]",
                        priv_badge
                    )

            console.print(table)

            # Dynamic Real-Time Description Box
            sel = items[selected_idx]
            sel_id = sel.get("id", "")
            icon_col = sel.get("icon_color") or ICON_COLORS.get(sel_id, "bold cyan")
            cat_col = CATEGORY_COLORS.get(sel.get("tag", ""), "cyan")

            privilege_label = "[bold red]Sudo Elevation Required[/]" if sel.get("sudo", False) else "[bold green]Standard User (No Sudo)[/]"
            desc_lines = [
                f"[bold bright_white]{sel.get('desc', '')}[/]\n",
                f"[white]{sel.get('details', '')}[/]\n",
                f"[bold magenta]Privilege:[/] {privilege_label}   [dim]•[/]   [bold magenta]Category:[/] [bold {cat_col}]{sel.get('tag', '')}[/]"
            ]

            desc_panel = Panel(
                "\n".join(desc_lines),
                title=f"[bold magenta]◆[/] [bold cyan]Option Details[/] [dim]•[/] [{icon_col}]{sel.get('icon', '')}[/] [bold white]{sel.get('title', '')}[/] [bold magenta]◆[/]",
                box=box.ROUNDED,
                border_style="magenta",
                width=width,
                padding=(0, 2)
            )
            console.print(desc_panel)
            console.print("  [bold yellow]Navigation:[/] [bold cyan]↑/↓[/] [dim]or[/] [bold cyan]j/k[/] [dim]•[/] [bold green]Enter[/] [dim]Select •[/] [bold red]q[/] [dim]Exit[/]\n")

            key = read_key()
            if key in ("UP",):
                selected_idx = (selected_idx - 1) % num_opts
            elif key in ("DOWN",):
                selected_idx = (selected_idx + 1) % num_opts
            elif key in ("ENTER",):
                return items[selected_idx]["id"]
            elif key in ("QUIT", "ESC", "CTRL_C"):
                return "quit"
    finally:
        # Restore cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def interactive_checklist_menu(
    title: str,
    items: List[Dict[str, Any]],
    user: str = "user",
    host: str = "archlinux",
    kernel: str = "linux"
) -> Optional[List[Dict[str, Any]]]:
    """
    Renders a compact multi-select checkbox menu for categories
    with vibrant category icons and a dynamic description panel.
    """
    selected_idx = 0
    num_items = len(items)
    width = get_menu_width()

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            console.clear()
            render_ascii_header(user, host, kernel, width)

            table = Table(
                title=f"[bold magenta]◆[/] [bold cyan]{title}[/][bold magenta] ◆[/]",
                box=box.ROUNDED,
                border_style="cyan",
                header_style="bold magenta",
                width=width,
                padding=(0, 1),
                expand=False
            )
            table.add_column("Sel", justify="center", width=6)
            table.add_column("Category", width=34)
            table.add_column("Packages", justify="right", width=14)
            table.add_column("Status", justify="center", width=14)

            for idx, it in enumerate(items):
                cat_id = it.get("id", "")
                cat_color = CAT_ICON_COLORS.get(cat_id, "bold cyan")
                is_selected = it.get("enabled", True)
                check_icon = "󰄲" if is_selected else "󰄱"
                count_str = f"{len(it.get('packages', []))} pkgs"
                icon_str = it.get("icon", "󰏖")
                styled_icon = f"[{cat_color}]{icon_str}[/]"
                name_str = it.get("name", "Category")

                if idx == selected_idx:
                    table.add_row(
                        f"[bold green]{check_icon}[/]" if is_selected else f"[dim red]{check_icon}[/]",
                        f"[bold cyan]▸[/] {styled_icon}  [bold bright_white]{name_str}[/]",
                        f"[bold cyan]{count_str}[/]",
                        f"[bold green]Included[/]" if is_selected else f"[dim yellow]Excluded[/]",
                        style="on #2d3340"
                    )
                else:
                    table.add_row(
                        f"[bold green]{check_icon}[/]" if is_selected else f"[dim red]{check_icon}[/]",
                        f"  {styled_icon}  [white]{name_str}[/]",
                        f"[cyan]{count_str}[/]",
                        f"[bold green]Included[/]" if is_selected else f"[dim yellow]Excluded[/]"
                    )

            console.print(table)

            # Dynamic Category Preview Box
            sel = items[selected_idx]
            cat_id = sel.get("id", "")
            cat_col = CAT_ICON_COLORS.get(cat_id, "bold cyan")
            pkgs = sel.get("packages", [])
            pkgs_preview = ", ".join(pkgs[:10]) + ("..." if len(pkgs) > 10 else "")
            state_text = "[bold green]Selected for installation[/]" if sel.get("enabled", True) else "[bold yellow]Skipped (will not be installed)[/]"

            cat_lines = [
                f"[bold bright_white]{sel.get('description', '')}[/]\n",
                f"[bold magenta]Packages ({len(pkgs)}):[/] [cyan]{pkgs_preview}[/]\n",
                f"[bold magenta]Status:[/] {state_text}   [dim]•[/]   [dim]Toggle with [bold yellow]Space[/dim]"
            ]

            cat_panel = Panel(
                "\n".join(cat_lines),
                title=f"[bold magenta]◆[/] [bold cyan]Category Details[/] [dim]•[/] [{cat_col}]{sel.get('icon', '󰏖')}[/] [bold white]{sel.get('name', '')}[/] [bold magenta]◆[/]",
                box=box.ROUNDED,
                border_style="magenta",
                width=width,
                padding=(0, 2)
            )
            console.print(cat_panel)
            console.print("  [bold yellow]Navigation:[/] [bold cyan]↑/↓[/] [dim]or[/] [bold cyan]j/k[/] [dim]•[/] [bold yellow]Space[/] [dim]Toggle •[/] [bold cyan]a[/] [dim]Toggle All •[/] [bold green]Enter[/] [dim]Confirm •[/] [bold red]q[/] [dim]Cancel[/]\n")

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
                return None
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def pause_for_return(prompt: str = "Press any key to return to the main menu..."):
    """Pauses until user presses Enter or any key to return cleanly."""
    console.print(f"\n  [bold cyan]›[/] [dim]{prompt}[/]", end="")
    sys.stdout.flush()
    try:
        read_key()
    except (KeyboardInterrupt, EOFError):
        pass
