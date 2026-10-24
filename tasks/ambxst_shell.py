"""
Task: Ambxst Shell Setup
"""

import shutil
from core.tui import log_info, log_success, log_error, log_running, prompt_yes_no
from core.logger import logger

def run(auto_confirm: bool = False) -> bool:
    if not prompt_yes_no("Install ambxst shell?", default=True, auto_confirm=auto_confirm):
        log_info("Skipping ambxst installation")
        return True

    if shutil.which("ambxst"):
        log_success("ambxst shell is already installed")
        return True

    log_running("Downloading and installing ambxst...")
    code, _ = logger.run_cmd(["bash", "-c", "curl -fsSL https://get.axeni.de/ambxst | sh"], check=False)
    if code == 0:
        log_success("ambxst shell installed successfully")
        return True
    else:
        log_error("Failed to install ambxst shell.")
        return False

