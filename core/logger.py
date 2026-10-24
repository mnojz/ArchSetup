"""
ArchSetup Logging & Execution Engine
Streams command output to log files while keeping the terminal clean.
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

class Logger:
    def __init__(self):
        state_dir = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "archsetup"
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = state_dir / f"install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        except Exception:
            fallback = Path("/tmp/archsetup")
            fallback.mkdir(parents=True, exist_ok=True)
            self.log_file = fallback / f"install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        self.log_path_str = str(self.log_file.resolve())

    def get_latest_existing_log(self) -> Optional[Path]:
        """Finds the most recent non-empty installation log file."""
        search_dirs = [
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "archsetup",
            Path("/tmp/archsetup")
        ]
        logs = []
        for d in search_dirs:
            if d.is_dir():
                logs.extend(d.glob("install_*.log"))
        logs = [f for f in logs if f.stat().st_size > 0]
        if logs:
            logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return logs[0]
        return None

    def log(self, level: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{level.upper()}] {message}\n")
        except Exception:
            pass

    def run_cmd(self, cmd: List[str], shell: bool = False, check: bool = True, cwd: Optional[Path] = None) -> Tuple[int, str]:
        """Runs a subprocess, redirecting stdout & stderr into the log file."""
        cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
        cwd_str = f" [cwd={cwd}]" if cwd else ""
        self.log("CMD", f"Running: {cmd_str}{cwd_str}")
        
        with open(self.log_file, "a", encoding="utf-8") as log_fd:
            proc = subprocess.run(
                cmd,
                shell=shell,
                cwd=str(cwd) if cwd else None,
                stdout=log_fd,
                stderr=log_fd,
                text=True
            )

        self.log("CMD_EXIT", f"Return code: {proc.returncode}")
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
            
        return proc.returncode, ""

# Global singleton
logger = Logger()

