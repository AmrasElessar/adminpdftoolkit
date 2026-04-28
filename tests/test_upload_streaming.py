"""Upload streaming tests (S4 gap closure).

Cover ``core.save_upload`` and the size-limit enforcement that the public
endpoints replicate inline (app.py:1097-1103). We don't go through HTTP for
the size check — that path is covered by individual endpoint tests — but we
do verify the helper itself handles the chunked write + close correctly.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import UploadFile

import core


def _upload(name: str, data: bytes) -> UploadFile:
    """Build an UploadFile-compatible stream from raw bytes."""
    return UploadFile(filename=name, file=io.BytesIO(data))


@pytest.mark.anyio("asyncio")
async def test_save_upload_writes_full_payload(tmp_path: Path) -> None:
    payload = b"hello world\n" * 1024
    dest = tmp_path / "u.bin"
    written = await core.save_upload(_upload("u.bin", payload), dest)
    assert written == len(payload)
    assert dest.read_bytes() == payload


@pytest.mark.anyio("asyncio")
async def test_save_upload_handles_empty_file(tmp_path: Path) -> None:
    dest = tmp_path / "empty.bin"
    written = await core.save_upload(_upload("empty.bin", b""), dest)
    assert written == 0
    assert dest.exists()
    assert dest.stat().st_size == 0


@pytest.mark.anyio("asyncio")
async def test_save_upload_handles_chunked_payload(tmp_path: Path) -> None:
    """Stream a payload larger than one read chunk to exercise the loop.

    The loop reads in 1 MiB blocks; we force at least 3 iterations to make
    sure the cumulative written count and file size stay in sync.
    """
    payload = b"x" * (3 * 1024 * 1024 + 17)  # 3 MiB + odd tail
    dest = tmp_path / "big.bin"
    written = await core.save_upload(_upload("big.bin", payload), dest)
    assert written == len(payload)
    assert dest.stat().st_size == len(payload)


def test_make_job_dir_is_unique() -> None:
    """Two consecutive calls with no parts must produce distinct directories."""
    a = core.make_job_dir()
    b = core.make_job_dir()
    try:
        assert a != b
        assert a.exists() and b.exists()
    finally:
        a.rmdir()
        b.rmdir()
