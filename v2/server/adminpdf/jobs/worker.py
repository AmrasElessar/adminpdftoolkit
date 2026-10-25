"""Entry point executed inside a freshly spawned worker process.

Talks to the parent over a ``multiprocessing`` pipe:
``("progress", fraction, message)`` any number of times, then exactly one of
``("done", [(path, name), ...])`` or ``("error", payload)``.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import traceback
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any

from ..core.errors import UserError


def _limit_memory(megabytes: int) -> None:
    if megabytes <= 0 or sys.platform == "win32":
        return
    import resource

    limit = megabytes * 1024 * 1024
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run(
    conn: Connection,
    op_name: str,
    params: dict[str, Any],
    inputs: list[tuple[str, str, str]],
    output_dir: str,
    memory_mb: int,
    files: dict[str, tuple[str, str]] | None = None,
) -> None:
    _limit_memory(memory_mb)
    from ..core.proc import install_sigterm_handler

    install_sigterm_handler()
    try:
        from ..ops.base import Context, InputFile, load_all

        op_cls = load_all()[op_name]
        parsed = op_cls.Params.model_validate(params)
        ctx = Context(
            inputs=[InputFile(Path(p), name, pw) for p, name, pw in inputs],
            output_dir=Path(output_dir),
            progress=lambda f, m: conn.send(("progress", max(0.0, min(1.0, float(f))), str(m)[:200])),
            files={k: InputFile(Path(p), name) for k, (p, name) in (files or {}).items()},
        )
        op_cls().run(ctx, parsed)
        if not ctx.outputs and ctx.data is None:
            raise UserError("İşlem çıktı üretmedi.", "The operation produced no output.")
        conn.send(("done", {"outputs": [(str(o.path), o.name) for o in ctx.outputs], "data": ctx.data}))
    except UserError as e:
        conn.send(("error", e.payload()))
    except MemoryError:
        conn.send(("error", {"tr": "İşlem bellek sınırını aştı.", "en": "The operation exceeded the memory limit."}))
    except Exception:
        logging.getLogger("adminpdf.worker").error("job %s failed\n%s", op_name, traceback.format_exc())
        conn.send(("error", {"tr": "İşlem başarısız oldu.", "en": "The operation failed."}))
    finally:
        conn.close()
