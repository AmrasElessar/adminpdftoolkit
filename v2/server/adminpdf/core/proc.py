"""External helper processes (LibreOffice) run from inside a job worker.

The job engine stops a worker with SIGTERM on timeout or cancel. A plain
``subprocess.run`` child would outlive it, so children are started in their
own process group and the worker's SIGTERM handler kills those groups first.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from .errors import UserError

_children: set[subprocess.Popen[bytes]] = set()


def kill_children() -> None:
    for p in list(_children):
        try:
            if sys.platform == "win32":
                p.kill()
            else:
                os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def install_sigterm_handler() -> None:
    if sys.platform == "win32":
        return

    def handler(_signum: int, _frame: object) -> None:
        kill_children()
        os._exit(143)

    signal.signal(signal.SIGTERM, handler)


def run(cmd: Sequence[str], *, timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    kwargs: dict[str, object] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    p = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,  # type: ignore[call-overload]
    )
    _children.add(p)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_children()
        p.communicate()
        raise UserError("Dönüştürme zaman aşımına uğradı.", "The conversion timed out.") from None
    finally:
        _children.discard(p)
    return subprocess.CompletedProcess(list(cmd), p.returncode, out, err)
