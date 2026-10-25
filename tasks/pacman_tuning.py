"""
Task: Pacman Turbo Optimization
Enables ParallelDownloads = 5, Color, and ILoveCandy progress bar.
"""

import re
from pathlib import Path
from core.tui import log_info, log_success, log_running
from core.logger import logger

def run(auto_confirm: bool = False) -> bool:
    pacman_conf = Path("/etc/pacman.conf")
    if not pacman_conf.exists():
        log_info("/etc/pacman.conf not found; skipping pacman tuning")
        return False

    content = pacman_conf.read_text(encoding="utf-8")
    original = content
    modified = False

    # 1. Enable ParallelDownloads = 5
    if re.search(r"#\s*ParallelDownloads\s*=\s*\d+", content):
        content = re.sub(r"#\s*(ParallelDownloads\s*=\s*)\d+", r"\g<1>5", content)
        modified = True
    elif re.search(r"^ParallelDownloads\s*=\s*[1-4]\b", content, re.MULTILINE):
        content = re.sub(r"^(ParallelDownloads\s*=\s*)[1-4]\b", r"\g<1>5", content, flags=re.MULTILINE)
        modified = True
    elif "ParallelDownloads" not in content:
        content = content.replace("[options]", "[options]\nParallelDownloads = 5")
        modified = True

    # 2. Enable Color
    if "#Color" in content or "# Color" in content:
        content = re.sub(r"#\s*Color", "Color", content)
        modified = True

    # 3. Enable ILoveCandy progress styling if not present
    if "ILoveCandy" not in content and "Color" in content:
        content = content.replace("Color", "Color\nILoveCandy")
        modified = True

    if modified:
        log_running("Applying ParallelDownloads = 5 and Color enhancements...")
        # Backup original
        logger.run_cmd(["sudo", "cp", "/etc/pacman.conf", "/etc/pacman.conf.backup"], check=False)
        
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        logger.run_cmd(["sudo", "cp", temp_path, "/etc/pacman.conf"], check=False)
        Path(temp_path).unlink(missing_ok=True)
        log_success("Pacman configuration optimized (ParallelDownloads=5, Color, ILoveCandy)")
    else:
        log_info("Pacman configuration already optimized")

    return True
