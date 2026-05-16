"""Admin PDF Toolkit — System Tray Launcher.

Runs in the Windows notification area (system tray) instead of opening a
console window. Spawns the bundled Python + ``app.py`` as a hidden
subprocess; the user interacts via a tray icon menu:

    ● Durum: Çalışıyor / ○ Durum: Durduruldu  (dynamic status line)
    Tarayıcıda Aç         (open browser; disabled when stopped)
    Sunucuyu Başlat        (start uvicorn; disabled when running)
    Sunucuyu Durdur        (stop uvicorn; disabled when stopped)
    Yeniden Başlat         (stop + start)
    Logları Aç             (open the log directory)
    Çıkış                  (terminate uvicorn and quit the tray)

Left-clicking the icon opens the browser. The launcher itself has no
visible window; errors are shown via a native Windows MessageBox.

The compiled .exe is built by ``build_exe.py`` with PyInstaller in
``--noconsole`` mode. Dependencies bundled into the .exe: pystray, Pillow.
"""

from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

HOST = "127.0.0.1"
PORT = 8000
APP_TITLE = "Admin PDF Toolkit"

MB_ICONERROR = 0x10
MB_ICONINFO = 0x40

# Subprocess creation flags for a hidden child process on Windows.
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def _here() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _messagebox(title: str, text: str, icon: int = MB_ICONERROR) -> None:
    ctypes.windll.user32.MessageBoxW(0, text, title, icon)


def _make_icon_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded red square (matches the "PDF" admin tool brand vibe)
    d.rounded_rectangle([4, 4, size - 4, size - 4], radius=12, fill=(204, 51, 51, 255))
    # Try a real font for "PDF" text; fall back to default if Arial isn't around.
    text = "PDF"
    font: ImageFont.ImageFont
    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except OSError:
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
    d.text((size // 2, size // 2 + 2), text, anchor="mm", fill=(255, 255, 255), font=font)
    return img


def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


class TrayApp:
    def __init__(self) -> None:
        self.here = _here()
        self.py_exe = self.here / "python" / "python.exe"
        self.app_py = self.here / "app.py"
        self.proc: subprocess.Popen | None = None
        self.icon: pystray.Icon | None = None
        self._lock = threading.Lock()

    # -- subprocess lifecycle --------------------------------------------------

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(self.here), str(self.here / "python" / "Lib" / "site-packages")]
        )
        env["PATH"] = os.pathsep.join(
            [
                str(self.here / "python"),
                str(self.here / "python" / "Scripts"),
                env.get("PATH", ""),
            ]
        )
        return env

    def _start_server(self) -> bool:
        if not self.py_exe.exists():
            _messagebox(
                APP_TITLE,
                f"Gömülü Python bulunamadı:\n{self.py_exe}\n\n"
                "Bu .exe portable klasörün İÇİNDE olmalı (python/ ile yan yana).",
            )
            return False
        if not self.app_py.exists():
            _messagebox(APP_TITLE, f"app.py bulunamadı:\n{self.app_py}")
            return False

        # Hidden console for the uvicorn subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        log_dir = self.here / "logs"
        log_dir.mkdir(exist_ok=True)
        log_path = log_dir / "server.log"
        try:
            log_fp = log_path.open("ab", buffering=0)
        except OSError:
            log_fp = None

        try:
            self.proc = subprocess.Popen(
                [str(self.py_exe), str(self.app_py)],
                env=self._env(),
                cwd=str(self.here),
                stdout=log_fp,
                stderr=log_fp,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=CREATE_NO_WINDOW,
            )
            return True
        except OSError as e:
            _messagebox(APP_TITLE, f"Sunucu başlatılamadı:\n{e}")
            return False

    def _stop_server(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self.proc is None:
                return
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None

    # -- state helpers ---------------------------------------------------------

    def _is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _status_label(self, item: object = None) -> str:
        if self._is_running():
            return "● Durum: Çalışıyor"
        return "○ Durum: Durduruldu"

    def _refresh_tooltip(self) -> None:
        if self.icon is None:
            return
        if self._is_running():
            self.icon.title = f"{APP_TITLE} — http://{HOST}:{PORT}"
        else:
            self.icon.title = f"{APP_TITLE} — durduruldu"

    # -- menu actions ----------------------------------------------------------

    def _open_browser(self, *_: object) -> None:
        if not self._is_running():
            return
        scheme = "https" if os.environ.get("HTTPS", "0") in ("1", "true", "yes") else "http"
        webbrowser.open(f"{scheme}://{HOST}:{PORT}")

    def _start_action(self, icon: pystray.Icon, *_: object) -> None:
        if self._is_running():
            return
        if self._start_server():
            threading.Thread(target=self._open_when_ready, daemon=True).start()
        self._refresh_tooltip()
        icon.update_menu()

    def _stop_action(self, icon: pystray.Icon, *_: object) -> None:
        if not self._is_running():
            return
        self._stop_server()
        self._refresh_tooltip()
        icon.update_menu()

    def _restart(self, icon: pystray.Icon, *_: object) -> None:
        self._stop_server()
        if self._start_server():
            threading.Thread(target=self._open_when_ready, daemon=True).start()
        self._refresh_tooltip()
        icon.update_menu()

    def _open_logs(self, *_: object) -> None:
        log_dir = self.here / "logs"
        log_dir.mkdir(exist_ok=True)
        os.startfile(str(log_dir))

    def _quit(self, icon: pystray.Icon, *_: object) -> None:
        self._stop_server()
        icon.stop()

    # -- main loop -------------------------------------------------------------

    def _open_when_ready(self) -> None:
        if _wait_for_port(HOST, PORT, timeout=45.0):
            self._open_browser()
            if self.icon is not None:
                self._refresh_tooltip()
                self.icon.update_menu()

    def run(self) -> int:
        if not self._start_server():
            return 1

        threading.Thread(target=self._open_when_ready, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(self._status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Tarayıcıda Aç",
                self._open_browser,
                default=True,
                enabled=lambda item: self._is_running(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Sunucuyu Başlat",
                self._start_action,
                enabled=lambda item: not self._is_running(),
            ),
            pystray.MenuItem(
                "Sunucuyu Durdur",
                self._stop_action,
                enabled=lambda item: self._is_running(),
            ),
            pystray.MenuItem("Yeniden Başlat", self._restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Logları Aç", self._open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", self._quit),
        )

        self.icon = pystray.Icon(
            "AdminPDFToolkit",
            _make_icon_image(),
            f"{APP_TITLE} — http://{HOST}:{PORT}",
            menu,
        )
        self.icon.run()
        return 0


def main() -> int:
    try:
        return TrayApp().run()
    except Exception as e:
        _messagebox(APP_TITLE, f"Beklenmedik hata:\n{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
