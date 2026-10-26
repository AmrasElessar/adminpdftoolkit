"""Desktop launcher (Linux / macOS): the parts that need no display."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from adminpdf import launcher


def test_user_data_dir_is_outside_the_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("APT_DATA_DIR", raising=False)
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    assert launcher.user_data_dir() == tmp_path / "Library" / "Application Support" / "AdminPDFToolkit"
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert launcher.user_data_dir() == tmp_path / "xdg" / "AdminPDFToolkit"
    monkeypatch.setenv("APT_DATA_DIR", str(tmp_path / "custom"))
    assert launcher.user_data_dir() == tmp_path / "custom"


def test_settings_roundtrip(tmp_path: Path) -> None:
    s = launcher.Settings(tmp_path)
    assert s.get("lan", False) is False
    s.set("lan", True)
    assert launcher.Settings(tmp_path).get("lan", False) is True
    assert (tmp_path / "launcher.ini").read_text() == "lan=1\n"


def test_parse_line_ignores_noise() -> None:
    assert launcher.parse_line('{"type": "check", "id": "x"}') == {"type": "check", "id": "x"}
    assert launcher.parse_line("warning: the fitz API is deprecated") is None
    assert launcher.parse_line("{broken") is None
    assert launcher.parse_line("[1, 2]") is None


def test_macos_path_finds_homebrew_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin"]))
    env = launcher.child_env(tmp_path)
    assert env["PATH"].split(os.pathsep)[:2] == ["/opt/homebrew/bin", "/usr/local/bin"]
    assert env["APT_DATA_DIR"] == str(tmp_path)


def test_stream_json_runs_the_selfcheck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APT_PORT", "8768")
    lines: list[dict[str, object]] = []
    code = launcher.stream_json(["-m", "adminpdf.selfcheck"], launcher.child_env(tmp_path / "d"), lines.append)
    # Not every component exists on a test machine (e.g. no web build in CI):
    # what matters is the streamed result and an exit code that matches it.
    assert lines[0]["id"] == "python" and lines[-1]["type"] == "done"
    assert code == (0 if lines[-1]["ready"] else 1)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_server_starts_and_stops_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APT_PORT", "8769")
    server = launcher.Server(tmp_path / "d")
    server.start(lan=False, open_browser=False)
    try:
        assert server.wait_ready(60), (tmp_path / "d" / "server.log").read_text()[-800:]
    finally:
        server.stop()
    assert not server.alive()
    time.sleep(0.5)
    with pytest.raises(OSError):
        import socket

        socket.create_connection(("127.0.0.1", 8769), timeout=1).close()
