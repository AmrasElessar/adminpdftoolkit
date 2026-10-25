from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from adminpdf.core import tools


def test_finds_on_path() -> None:
    assert tools.find_tool((Path(sys.executable).name,)) is not None


def test_missing_tool() -> None:
    assert tools.find_tool(("apt-no-such-tool",), windows_globs=("Nope/nope.exe",)) is None


def test_windows_install_folder_is_found_and_added_to_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "gs" / "gs10.05.1" / "bin" / "gswin64c.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    older = tmp_path / "gs" / "gs9.50" / "bin" / "gswin64c.exe"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"")
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setattr(tools, "_windows_roots", lambda: [str(tmp_path)])
    monkeypatch.setenv("PATH", "")
    found = tools.find_tool(("apt-no-such-gs",), windows_globs=("gs/gs*/bin/gswin64c.exe",))
    assert found == str(exe)
    assert os.environ["PATH"].split(os.pathsep)[0] == str(exe.parent)
