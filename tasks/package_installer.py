"""
Task: Categorized Package Installation
Installs software defined in packages.json with real-time progress indicators.
"""

import json
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from core.tui import console, log_info, log_success, log_running
from core.pacman import pm
from core.logger import logger

def install_package_batch(category_name: str, packages: list) -> bool:
    """Installs a specific list of packages with a live progress bar."""
    if not packages:
        return True

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.fields[category]}"),
        BarColumn(bar_width=25),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[dim]({task.completed}/{task.total})[/]"),
        TextColumn("[yellow]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        t_id = progress.add_task(packages[0], total=len(packages), category=category_name[:24])
        for pkg in packages:
            progress.update(t_id, description=pkg)
            pm.install_package(pkg)
            progress.update(t_id, advance=1)
    return True

def run(manifest_path: Path, auto_confirm: bool = False, target_category: str = None) -> bool:
    if not manifest_path.exists():
        log_info("packages.json not found; skipping package installation")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    categories = data.get("categories", [])
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.fields[category]}"),
        BarColumn(bar_width=25),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[dim]({task.completed}/{task.total})[/]"),
        TextColumn("[yellow]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        for cat in categories:
            if not cat.get("enabled", True):
                continue

            if target_category and cat.get("id") != target_category and target_category.lower() not in cat.get("name", "").lower():
                continue

            cat_name = cat.get("name", "Packages")
            pkgs = cat.get("packages", [])
            if not pkgs:
                continue

            t_id = progress.add_task(pkgs[0], total=len(pkgs), category=cat_name[:24])
            for pkg in pkgs:
                progress.update(t_id, description=pkg)
                pm.install_package(pkg)
                progress.update(t_id, advance=1)
                
    # Ensure MPV uosc fallback if not packaged
    uosc_dir = Path.home() / ".config/mpv/scripts/uosc"
    if not pm.is_installed("mpv-uosc") and not uosc_dir.exists():
        log_running("Installing MPV uosc interface script...")
        logger.run_cmd(["bash", "-c", "curl -fsSL https://raw.githubusercontent.com/tomasklaen/uosc/HEAD/installers/unix.sh | bash"], check=False)

    log_success("All selected package categories processed")
    return True

