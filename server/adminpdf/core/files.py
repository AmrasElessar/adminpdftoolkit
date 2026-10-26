"""Upload store: opaque id → file on disk, with size cap, type sniffing and TTL.

Uploads arrive as a raw request body (not multipart), so the size cap is
enforced while streaming to disk and the write aborts the moment it is
exceeded — nothing is spooled beforehand.
"""

from __future__ import annotations

import contextlib
import json
import re
import secrets
import shutil
import time
import unicodedata
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from pathlib import Path

FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class UploadTooLargeError(Exception):
    pass


class StorageFullError(Exception):
    pass


class MissingFileError(Exception):
    pass


@dataclass
class StoredFile:
    id: str
    name: str
    size: int
    kind: str  # pdf | image | docx | xlsx | pptx | font | cert | other
    mime: str
    created: float
    pages: int | None = None
    encrypted: bool = False
    # "local" or a paired device's id; nobody else can read or use the file.
    owner: str = "local"

    def public(self) -> dict[str, object]:
        d = asdict(self)
        d.pop("created")
        d.pop("owner")
        return d


def safe_filename(name: str, default: str = "file") -> str:
    """Reduce an untrusted filename to a safe, non-empty basename."""
    name = unicodedata.normalize("NFC", name or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f<>:\"|?*]", "_", name).strip().rstrip(". ")
    stem, _, ext = name.rpartition(".") if "." in name else (name, "", "")
    if not stem.strip(" ._") or stem.lower() in _WINDOWS_RESERVED:
        name = f"{default}.{ext}" if ext else default
    return name[:180]


def sniff(head: bytes, name: str) -> tuple[str, str]:
    """Return ``(kind, mime)`` from magic bytes; the extension only
    disambiguates OOXML containers, which all start with a ZIP header."""
    lower = name.lower()
    if head.startswith(b"%PDF-") or b"%PDF-" in head[:1024]:
        return "pdf", "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image", "image/tiff"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image", "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image", "image/webp"
    if head.startswith(b"BM"):
        return "image", "image/bmp"
    if head[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return "font", "font/ttf" if head[:4] != b"OTTO" else "font/otf"
    if lower.endswith((".p12", ".pfx")) and head[:1] == b"\x30":
        return "cert", "application/x-pkcs12"
    if head.startswith(b"PK\x03\x04"):
        for ext, kind, mime in (
            (".docx", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (".xlsx", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (".pptx", "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ):
            if lower.endswith(ext):
                return kind, mime
    return "other", "application/octet-stream"


class FileStore:
    def __init__(self, root: Path, *, max_bytes: int, ttl_seconds: int, max_total_bytes: int = 0) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.ttl_seconds = ttl_seconds
        # 0 = unlimited. Uploads that would push the store past it are refused,
        # so one client cannot fill the disk for everyone.
        self.max_total_bytes = max_total_bytes
        root.mkdir(parents=True, exist_ok=True)

    def usage(self) -> int:
        """Bytes currently stored (blobs only)."""
        total = 0
        for d in self.root.iterdir():
            with contextlib.suppress(OSError):
                total += (d / "blob").stat().st_size
        return total

    def room(self) -> int:
        """How many bytes the next upload may use."""
        if not self.max_total_bytes:
            return self.max_bytes
        return max(0, min(self.max_bytes, self.max_total_bytes - self.usage()))

    def _dir(self, file_id: str) -> Path:
        if not FILE_ID_RE.match(file_id):
            raise MissingFileError(file_id)
        return self.root / file_id

    async def save_stream(self, name: str, chunks: AsyncIterator[bytes], *, owner: str) -> StoredFile:
        room = self.room()
        if room <= 0:
            raise StorageFullError
        file_id = secrets.token_urlsafe(16)
        d = self.root / file_id
        d.mkdir()
        blob = d / "blob"
        size = 0
        head = b""
        try:
            with blob.open("wb") as fh:
                async for chunk in chunks:
                    size += len(chunk)
                    if size > room:
                        raise UploadTooLargeError if size > self.max_bytes else StorageFullError
                    if len(head) < 2048:
                        head += chunk[: 2048 - len(head)]
                    fh.write(chunk)
        except BaseException:
            shutil.rmtree(d, ignore_errors=True)
            raise
        safe = safe_filename(name)
        kind, mime = sniff(head, safe)
        meta = StoredFile(id=file_id, name=safe, size=size, kind=kind, mime=mime, created=time.time(), owner=owner)
        self._write_meta(meta)
        return meta

    def register_output(self, path: Path, name: str, *, owner: str) -> StoredFile:
        """Adopt a job result as a stored file so it can feed the next tool."""
        file_id = secrets.token_urlsafe(16)
        d = self.root / file_id
        d.mkdir()
        shutil.copyfile(path, d / "blob")
        with (d / "blob").open("rb") as fh:
            head = fh.read(2048)
        safe = safe_filename(name)
        kind, mime = sniff(head, safe)
        meta = StoredFile(
            id=file_id,
            name=safe,
            size=(d / "blob").stat().st_size,
            kind=kind,
            mime=mime,
            created=time.time(),
            owner=owner,
        )
        self._write_meta(meta)
        return self.probe(meta)

    def probe(self, meta: StoredFile) -> StoredFile:
        """Fill in PDF page count / encryption. Blocking: call off the loop."""
        if meta.kind != "pdf":
            return meta
        import pymupdf

        try:
            with pymupdf.open(self.path(meta.id)) as doc:
                meta.encrypted = bool(doc.needs_pass)
                meta.pages = None if doc.needs_pass else doc.page_count
        except Exception:
            meta.kind, meta.mime = "other", "application/octet-stream"
        self._write_meta(meta)
        return meta

    def update(self, meta: StoredFile) -> None:
        self._write_meta(meta)

    def _write_meta(self, meta: StoredFile) -> None:
        (self.root / meta.id / "meta.json").write_text(json.dumps(asdict(meta)), encoding="utf-8")

    def get(self, file_id: str, *, owner: str) -> StoredFile:
        """Metadata of a file owned by ``owner``; anyone else's reads as missing."""
        meta_path = self._dir(file_id) / "meta.json"
        try:
            meta = StoredFile(**json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as e:
            raise MissingFileError(file_id) from e
        if not secrets.compare_digest(meta.owner, owner):
            raise MissingFileError(file_id)
        return meta

    def path(self, file_id: str) -> Path:
        p = self._dir(file_id) / "blob"
        if not p.is_file():
            raise MissingFileError(file_id)
        return p

    def delete(self, file_id: str) -> None:
        shutil.rmtree(self._dir(file_id), ignore_errors=True)

    def sweep(self, now: float | None = None, *, keep: frozenset[str] = frozenset()) -> int:
        """Delete files older than the TTL, except ``keep`` (inputs of running
        jobs). Returns how many were removed."""
        now = now or time.time()
        removed = 0
        for d in self.root.iterdir():
            if d.name in keep:
                continue
            meta = d / "meta.json"
            try:
                created = json.loads(meta.read_text(encoding="utf-8"))["created"]
            except (OSError, ValueError, KeyError):
                # Half-written upload: fall back to the directory mtime.
                try:
                    created = d.stat().st_mtime
                except OSError:
                    continue
            if now - created > self.ttl_seconds:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        return removed
