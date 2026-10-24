"""
ArchSetup TUI Engine
Powered by Rich for 100% pixel-perfect borders, tables, panels, and live progress bars.
"""

import sys
import shutil
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# Initialize main console
console = Console(highlight=False)

def get_terminal_width() -> int:
    cols = shutil.get_terminal_size((80, 24)).columns
    return max(60, min(cols, 90))

def show_banner(user: str, host: str, kernel: str):
    """Renders the main logo and system metadata card."""
    banner_lines = [
        "╭─╮┬─╮╭─╮┬ ┬   ╭─╮┌─┐┌┬┐┬ ┬┌─┐",
        "├─┤├┬╯│  ├─┤   ╰─╮├┤  │ │ │├─┘",
        "┴ ┴┴└─╰─╯┴ ┴   ╰─╯└─┘ ┴ └─┘┴  ",
    ]
    banner_art = "[bold cyan]" + "\n".join(banner_lines) + "[/]"
    
    meta_line = (
        f"[bold magenta]Arch Linux + Hyprland Post-Install Suite[/]\n"
        f"[dim]User:[/] [green]{user}[/]  •  "
        f"[dim]Host:[/] [green]{host}[/]  •  "
        f"[dim]Kernel:[/] [green]{kernel}[/]"
    )
    
    content = f"{banner_art}\n\n{meta_line}"
    width = get_terminal_width()
    panel = Panel(
        content,
        box=box.ROUNDED,
        border_style="cyan",
        width=width,
        padding=(0, 2)
    )
    console.print()
    console.print(panel)
    console.print()

def show_manifest_table(categories: List[Dict[str, Any]]):
    """Renders the categorized packages table with rounded borders."""
    width = get_terminal_width()
    table = Table(
        title="[bold cyan]Configured Package Manifest[/]",
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold cyan",
        width=width,
        padding=(0, 1),
        expand=True
    )
    
    table.add_column("Icon", justify="center", style="yellow", width=6)
    table.add_column("Category", style="bold white", width=28)
    table.add_column("Packages", justify="right", style="green", width=10)
    table.add_column("Description", style="dim")

    for cat in categories:
        if cat.get("enabled", True):
            count_str = f"{len(cat.get('packages', []))} pkgs"
            table.add_row(
                cat.get("icon", "󰏖"),
                cat.get("name", "Unknown"),
                count_str,
                cat.get("description", "")
            )
            
    console.print(table)
    console.print()

def show_package_audit_table(audit_results: List[Dict[str, Any]]):
    """Renders package comparison table showing installed vs missing packages per category."""
    width = get_terminal_width()
    table = Table(
        title="[bold cyan]Package Synchronization Audit[/]",
        box=box.ROUNDED,
        border_style="magenta",
        header_style="bold cyan",
        width=width,
        padding=(0, 1),
        expand=True
    )
    
    table.add_column("Icon", justify="center", style="yellow", width=5)
    table.add_column("Category", style="bold white", width=26)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Counts", justify="center", width=12)
    table.add_column("Missing Packages", style="yellow")

    for res in audit_results:
        is_complete = len(res["missing"]) == 0
        status_text = "[bold green]✔ Complete[/]" if is_complete else f"[bold yellow]⚠ Pending ({len(res['missing'])})[/]"
        missing_text = "[dim green]None[/]" if is_complete else ", ".join(res["missing"])
        count_text = f"{res['installed']} / {res['total']}"

        table.add_row(
            res.get("icon", "󰏖"),
            res.get("name", "Unknown"),
            status_text,
            count_text,
            missing_text
        )

    console.print(table)
    console.print()

def show_step_header(step_num: int, total_steps: int, title: str):
    """Prints a styled step title panel."""
    width = get_terminal_width()
    title_text = f"[bold cyan]Step {step_num}/{total_steps}:[/] [bold white]{title}[/]"
    console.print()
    console.rule(title_text, style="magenta", align="left")

def log_info(msg: str):
    console.print(f"  [bold blue]ℹ[/]  {msg}")

def log_success(msg: str):
    console.print(f"  [bold green]✔[/]  [green]{msg}[/]")

def log_warning(msg: str):
    console.print(f"  [bold yellow]⚠[/]  [yellow]{msg}[/]")

def log_error(msg: str):
    console.print(f"  [bold red]✖[/]  [red]{msg}[/]")

def log_running(msg: str):
    console.print(f"  [bold cyan]➜[/]  {msg}")

def log_dim(msg: str):
    console.print(f"      [dim]{msg}[/]")

def show_summary_panel(
    installed: List[str],
    skipped: List[str],
    failed: List[str],
    log_file: str
):
    """Renders the final completion summary card."""
    width = get_terminal_width()
    lines = [
        "[bold green]🎉 Post-Installation Tasks Completed Successfully![/]\n",
        f"  [bold]Newly Installed:[/]      [green]{len(installed)} packages[/]",
        f"  [bold]Previously Installed:[/] [cyan]{len(skipped)} packages[/]",
    ]
    
    if failed:
        lines.append(f"  [bold]Failed / Unresolved:[/]  [red]{len(failed)} packages ({', '.join(failed)})[/]")
    else:
        lines.append("  [bold]Failed / Unresolved:[/]  [dim green]0 packages[/]")
        
    lines.append(f"\n  [dim]Install Log File:[/]     [white]{log_file}[/]")

    panel = Panel(
        "\n".join(lines),
        title="[bold green]Execution Summary[/]",
        box=box.ROUNDED,
        border_style="green",
        width=width,
        padding=(1, 2)
    )
    console.print()
    console.print(panel)
    console.print()

def prompt_yes_no(question: str, default: bool = True, timeout: int = 30, auto_confirm: bool = False) -> bool:
    """Prompts the user with timed fallback."""
    if auto_confirm:
        log_info(f"{question} [dim][Auto-confirmed: Y][/]")
        return True

    def_str = "[green]Y[/]/n" if default else "y/[yellow]N[/]"
    time_hint = f"[dim](auto '{'y' if default else 'n'}' in {timeout}s)[/]"
    prompt_text = f"\n  [bold yellow]?[/] [bold white]{question}[/] [{def_str}] {time_hint}: "
    
    console.print(prompt_text, end="")
    sys.stdout.flush()

    import select
    # Non-blocking input on Unix
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        user_input = sys.stdin.readline().strip().lower()
        if not user_input:
            return default
        return user_input in ("y", "yes")
    else:
        console.print()
        return default

