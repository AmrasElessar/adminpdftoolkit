"""Shared plumbing for the OCRmyPDF-based tools (OCR, PDF/A).

Not an operation module (the leading underscore keeps it out of the
registry's auto-discovery). It is also loaded by OCRmyPDF itself as a plugin
(``plugins=[__name__]``) so its ``get_progressbar_class`` hook can forward
OCRmyPDF's progress bars to the job's ``ctx.progress``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import signal
import sys
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from types import FrameType, TracebackType
from typing import Any

from ocrmypdf import hookimpl

from ..core.errors import UserError
from ..core.tools import find_tool
from .base import InputFile, ProgressFn

PLUGIN = __name__

# Overall progress range covered by each OCRmyPDF stage (by its bar label).
_STAGES: dict[str, tuple[float, float]] = {
    "Scanning contents": (0.02, 0.10),
    "OCR": (0.10, 0.80),
    "Image processing": (0.10, 0.80),
    "hOCR": (0.10, 0.80),
    "Grafting hOCR to PDF": (0.80, 0.85),
    "PDF/A conversion": (0.85, 0.93),
    "Recompressing JPEGs": (0.88, 0.94),
    "Deflating JPEGs": (0.88, 0.94),
    "JBIG2": (0.88, 0.94),
    "Linearizing": (0.94, 0.98),
    "Checking output": (0.97, 0.99),
}
_DEFAULT_STAGE = (0.85, 0.97)

_callback: ProgressFn | None = None


class _ProgressBar:
    """Implements OCRmyPDF's ``ProgressBar`` protocol."""

    def __init__(self, total: float | None = None, desc: str | None = None, **_kw: Any) -> None:
        self.total = float(total) if total else 0.0
        self.desc = str(desc or "")
        self.done = 0.0
        self.lo, self.hi = _STAGES.get(self.desc, _DEFAULT_STAGE)

    def __enter__(self) -> _ProgressBar:
        self._emit()
        return self

    def __exit__(self, _t: type[BaseException] | None, _e: BaseException | None, _tb: TracebackType | None) -> None:
        self.done = self.total
        self._emit()

    def update(self, n: float = 1, *, completed: float | None = None) -> None:
        self.done = float(completed) if completed is not None else self.done + float(n)
        self._emit()

    def _emit(self) -> None:
        if _callback is None:
            return
        frac = min(1.0, self.done / self.total) if self.total else 0.0
        with contextlib.suppress(Exception):
            _callback(self.lo + (self.hi - self.lo) * frac, self.desc)


@hookimpl
def get_progressbar_class() -> type[_ProgressBar]:
    return _ProgressBar


@contextlib.contextmanager
def forward_progress(fn: ProgressFn) -> Iterator[None]:
    global _callback
    _callback = fn
    try:
        yield
    finally:
        _callback = None


# -- child processes -------------------------------------------------------------
def _descendants(root: int) -> list[int]:
    """PIDs of every descendant of ``root`` (Linux ``/proc``)."""
    children: dict[int, list[int]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(entry))
    out: list[int] = []
    stack = [root]
    while stack:
        for c in children.get(stack.pop(), []):
            out.append(c)
            stack.append(c)
    return out


@contextlib.contextmanager
def reap_children_on_term() -> Iterator[None]:
    """OCRmyPDF starts Tesseract / Ghostscript with ``subprocess`` directly,
    so ``core.proc`` cannot track them. While it runs, chain a SIGTERM
    handler that kills every descendant before the worker's own handler
    exits, so a timed-out or cancelled job leaves nothing behind."""
    if not sys.platform.startswith("linux") or threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.getsignal(signal.SIGTERM)

    def handler(signum: int, frame: FrameType | None) -> None:
        for pid in _descendants(os.getpid()):
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
        if callable(previous):
            previous(signum, frame)
        else:
            os._exit(143)

    signal.signal(signal.SIGTERM, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


# -- input preparation ---------------------------------------------------------------
@contextlib.contextmanager
def plain_input(inp: InputFile) -> Iterator[Path]:
    """Yield a path OCRmyPDF can read: the upload itself, or a decrypted
    temporary copy when the PDF is password-protected."""
    import pikepdf

    with tempfile.TemporaryDirectory(prefix="apt-ocr-") as tmp:
        src = inp.path
        try:
            with pikepdf.open(inp.path, password=inp.password) as pdf:
                if pdf.is_encrypted:
                    src = Path(tmp) / "input.pdf"
                    pdf.save(src, encryption=False)
        except pikepdf.PasswordError as e:
            raise UserError(
                "PDF şifreli — doğru şifreyi girin.",
                "The PDF is password-protected — enter the correct password.",
            ) from e
        except pikepdf.PdfError as e:
            raise UserError("Dosya geçerli bir PDF değil.", "Not a valid PDF.") from e
        yield src


def find_ghostscript() -> str | None:
    return find_tool(
        ("gs", "gswin64c", "gswin32c"),
        windows_globs=("gs/gs*/bin/gswin64c.exe", "gs/gs*/bin/gswin32c.exe"),
        unix_paths=("/opt/homebrew/bin/gs", "/usr/local/bin/gs"),
    )


# -- running ---------------------------------------------------------------------------
_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][^\s'\"\\/]+){2,}[\\/]?")


class _WarningCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if len(self.messages) < 20:
            with contextlib.suppress(Exception):
                # Never leak server paths (temp folders, uploads) to the client.
                text = _PATH_RE.sub("…", record.getMessage())
                self.messages.append(re.sub(r"\s+", " ", text).strip()[:300])


def run_ocrmypdf(src: Path, out: Path, progress: ProgressFn, **options: Any) -> list[str]:
    """Run ``ocrmypdf.ocr`` in-process, single-threaded, with friendly errors.

    Returns the warnings OCRmyPDF logged (English, for diagnostics)."""
    import ocrmypdf
    from ocrmypdf import exceptions as ex

    collector = _WarningCollector()
    log = logging.getLogger("ocrmypdf")
    log.addHandler(collector)
    # Tesseract's own OpenMP threads would oversubscribe the worker pool.
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")
    try:
        with reap_children_on_term(), forward_progress(progress):
            code = ocrmypdf.ocr(
                src,
                out,
                jobs=1,
                use_threads=True,
                progress_bar=True,
                plugins=[PLUGIN],
                **options,
            )
    except ex.MissingDependencyError as e:
        msg = str(e).lower()
        if "ghostscript" in msg or "gs" in msg.split():
            raise UserError(
                "Ghostscript yüklü değil; bu işlem için gereklidir.", "Ghostscript is not installed; it is required."
            ) from e
        raise UserError(
            "OCR motoru (Tesseract) veya gerekli bir bileşen yüklü değil.",
            "The OCR engine (Tesseract) or a required component is not installed.",
        ) from e
    except ex.PriorOcrFoundError as e:
        raise UserError(
            "Belgede zaten metin var. 'Atla' veya 'Yeniden OCR' kipini seçin.",
            "The document already has text. Choose the 'skip' or 'redo' mode.",
        ) from e
    except ex.EncryptedPdfError as e:
        raise UserError(
            "PDF şifreli — doğru şifreyi girin.", "The PDF is password-protected — enter the correct password."
        ) from e
    except ex.DigitalSignatureError as e:
        raise UserError(
            "PDF dijital olarak imzalı; bu işlem imzayı geçersiz kılar. Önce imzasız bir kopya kullanın.",
            "The PDF is digitally signed and this would invalidate the signature. Use an unsigned copy.",
        ) from e
    except ex.TaggedPDFError as e:
        raise UserError(
            "Belge erişilebilirlik etiketli ve zaten metin içeriyor; OCR gerekmiyor olabilir.",
            "The document is tagged and already contains text; it may not need OCR.",
        ) from e
    except (ex.InputFileError, ex.UnsupportedImageFormatError, ex.DpiError) as e:
        raise UserError(
            "PDF okunamadı veya desteklenmeyen içerik barındırıyor.",
            "The PDF could not be read or contains unsupported content.",
        ) from e
    except ex.ColorConversionNeededError as e:
        raise UserError(
            "Belgedeki renk uzayı PDF/A için dönüştürülemedi.",
            "The document's colour space could not be converted for PDF/A.",
        ) from e
    except ex.PdfaConversionFailedError as e:
        raise UserError("PDF/A dönüştürme başarısız oldu.", "PDF/A conversion failed.") from e
    except ex.SubprocessOutputError as e:
        raise UserError(
            "OCR/Ghostscript bileşeni hata verdi; belge bozuk olabilir.",
            "Tesseract/Ghostscript reported an error; the document may be damaged.",
        ) from e
    except ex.ExitCodeException as e:
        raise UserError("İşlem tamamlanamadı.", "The operation could not be completed.") from e
    finally:
        log.removeHandler(collector)
    if code != ex.ExitCode.ok and not (code == ex.ExitCode.pdfa_conversion_failed and out.is_file()):
        raise UserError("İşlem tamamlanamadı.", "The operation could not be completed.")
    if not out.is_file():
        raise UserError("İşlem çıktı üretmedi.", "The operation produced no output.")
    return collector.messages
