"""Cross-platform subprocess termination for dev orchestration."""

from __future__ import annotations

import contextlib
import signal
import subprocess
import sys
from typing import Any


def terminate_process(
    proc: subprocess.Popen[Any] | None,
    *,
    timeout: float = 2.0,
    use_sigint: bool = True,
) -> None:
    """Stop a child process gracefully, then force-kill if needed."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            proc.terminate()
        elif use_sigint:
            proc.send_signal(signal.SIGINT)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            pass
        proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=timeout)
    except Exception:
        with contextlib.suppress(Exception):
            proc.kill()


__all__ = ["terminate_process"]