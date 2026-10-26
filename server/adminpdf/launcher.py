"""``python -m adminpdf.launcher`` — desktop launcher for Linux and macOS.

The same window as the Windows ``AdminPDFToolkit.exe``, in Tk (part of
Python): every component is checked and ticked off one by one
(``adminpdf.selfcheck``), the server starts in the background without a
terminal, and the window shows the addresses and the certificate
fingerprint. Network sharing can be switched on and off, the window can be
minimised while the server keeps running, and new releases are announced
(installed by downloading the new package — macOS and Linux apps are not
replaced in place).

Data lives in the user's own folder, never inside the app: an app started
from a download folder on macOS runs from a read-only, randomised location.
"""

from __future__ import annotations

import contextlib
import json
import locale
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

APP = "AdminPDFToolkit"


# -- pieces without a display (tested) -------------------------------------------
def user_data_dir() -> Path:
    """Where uploads, certificates and settings live for this user."""
    if os.environ.get("APT_DATA_DIR"):
        return Path(os.environ["APT_DATA_DIR"])
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(home))) / APP
    return Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / APP


def is_turkish() -> bool:
    lang = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if not lang:
        try:
            lang = locale.getlocale()[0] or ""
        except ValueError:
            lang = ""
    return lang.lower().startswith("tr")


TR = is_turkish()


def t(tr: str, en: str) -> str:
    return tr if TR else en


def child_python() -> str:
    """The interpreter for the server and checks (overridable for development)."""
    return os.environ.get("APT_LAUNCHER_PYTHON") or sys.executable


def child_env(data_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["APT_DATA_DIR"] = str(data_dir)
    env["PYTHONUTF8"] = "1"
    if sys.platform == "darwin":
        # Apps started from Finder get a bare PATH; Homebrew tools live here.
        extra = ["/opt/homebrew/bin", "/usr/local/bin"]
        env["PATH"] = os.pathsep.join([*extra, env.get("PATH", "/usr/bin:/bin")])
    return env


def parse_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def text_of(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("tr" if TR else "en", ""))
    return str(obj or "")


MARKS = {"ok": "✔", "warn": "⚠", "missing": "–", "error": "✖"}


class Settings:
    """``key=value`` lines in ``launcher.ini`` (the same file the Windows launcher uses)."""

    def __init__(self, folder: Path) -> None:
        self.path = folder / "launcher.ini"
        self.values: dict[str, str] = {}
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.partition("=")
                if sep:
                    self.values[key.strip()] = value.strip()
        except OSError:
            pass

    def get(self, key: str, default: bool) -> bool:
        return self.values.get(key, "1" if default else "0") == "1"

    def set(self, key: str, value: bool) -> None:
        self.values[key] = "1" if value else "0"
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("".join(f"{k}={v}\n" for k, v in self.values.items()), encoding="utf-8")
        except OSError:
            pass


def port() -> int:
    try:
        return int(os.environ.get("APT_PORT", "8000"))
    except ValueError:
        return 8000


def app_url() -> str:
    return f"https://localhost:{port()}/"


def stream_json(args: list[str], env: dict[str, str], emit: Callable[[dict[str, Any]], None]) -> int:
    """Run ``python -m …`` without a terminal and pass each JSON line on."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with subprocess.Popen(
        [child_python(), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    ) as p:
        assert p.stdout is not None
        for line in p.stdout:
            obj = parse_line(line)
            if obj is not None:
                emit(obj)
        return p.wait()


class Server:
    """The ``python -m adminpdf`` child process, in its own process group."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.proc: subprocess.Popen[bytes] | None = None

    def start(self, lan: bool, open_browser: bool) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        log = (self.data_dir / "server.log").open("ab")
        args = [child_python(), "-m", "adminpdf"]
        if lan:
            args.append("--lan")
        if open_browser:
            args.append("--open")
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            args,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=child_env(self.data_dir),
            **kwargs,
        )
        log.close()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def wait_ready(self, timeout: float = 60) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.alive():
                return False
            try:
                with socket.create_connection(("127.0.0.1", port()), timeout=1):
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    def stop(self) -> None:
        p, self.proc = self.proc, None
        if p is None or p.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                p.terminate()
            else:
                os.killpg(p.pid, signal.SIGTERM)
            p.wait(8)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if sys.platform == "win32":
                    p.kill()
                else:
                    os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass


def open_path(path: Path) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined,unused-ignore]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


# -- the window -----------------------------------------------------------------
class LauncherApp:  # pragma: no cover - needs a display; exercised by hand and in CI screenshots
    GREEN, AMBER, RED, GREY = "#18794e", "#9a5b00", "#c4262e", "#6b7280"

    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.data_dir = user_data_dir()
        self.settings = Settings(self.data_dir)
        self.server = Server(self.data_dir)
        self.events: queue.Queue[Callable[[], None]] = queue.Queue()
        self.first_start = True
        self.update_info: dict[str, Any] | None = None

        root = self.root = tk.Tk()
        root.title("Admin PDF Toolkit")
        root.geometry("760x620")
        root.minsize(600, 500)
        self._icon()
        frame = ttk.Frame(root, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Admin PDF Toolkit", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        self.subtitle = ttk.Label(frame, text=t("Bileşenler denetleniyor…", "Checking components…"))
        self.subtitle.pack(anchor="w", pady=(0, 8))

        columns = ("mark", "name", "version", "detail")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col, title, width in (
            ("mark", "", 34),
            ("name", t("Bileşen", "Component"), 200),
            ("version", t("Sürüm", "Version"), 150),
            ("detail", t("Ayrıntı", "Details"), 330),
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, stretch=col == "detail", anchor="center" if col == "mark" else "w")
        for status, color in (("ok", self.GREEN), ("warn", self.AMBER), ("missing", self.GREY), ("error", self.RED)):
            self.tree.tag_configure(status, foreground=color)
        self.tree.pack(fill="both", expand=True)

        self.status = ttk.Label(frame, text=t("Denetleniyor…", "Checking…"), font=("TkDefaultFont", 11, "bold"))
        self.status.pack(anchor="w", pady=(10, 4))
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x")
        self.progress.start(12)

        self.info = tk.Text(frame, height=5, wrap="word", relief="flat", borderwidth=0)
        self.info.pack(fill="x", pady=(8, 6))
        self.info.configure(state="disabled")

        self.lan = tk.BooleanVar(value=self.settings.get("lan", False))
        self.check_updates = tk.BooleanVar(value=self.settings.get("check_updates", True))
        ttk.Checkbutton(
            frame,
            text=t("Ağ paylaşımı (aynı ağdaki telefon / tablet)", "Network sharing (phones / tablets on this network)"),
            variable=self.lan,
            command=self._lan_changed,
        ).pack(anchor="w")
        ttk.Checkbutton(
            frame,
            text=t("Açılışta güncellemeleri denetle", "Check for updates at start"),
            variable=self.check_updates,
            command=lambda: self.settings.set("check_updates", self.check_updates.get()),
        ).pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        self.open_button = ttk.Button(buttons, text=t("Tarayıcıda aç", "Open in browser"), command=self._open)
        self.open_button.pack(side="left")
        self.open_button.state(["disabled"])
        self.update_button = ttk.Button(
            buttons, text=t("Güncellemeleri denetle", "Check for updates"), command=self._update_clicked
        )
        self.update_button.pack(side="left", padx=6)
        more = ttk.Menubutton(buttons, text=t("Diğer", "More"))
        menu = tk.Menu(more, tearoff=False)
        menu.add_command(
            label=t("Sertifikaya bu bilgisayarda güven", "Trust the certificate here"), command=self._trust
        )
        menu.add_command(
            label=t("Sunucu günlüğü", "Server log"), command=lambda: open_path(self.data_dir / "server.log")
        )
        menu.add_command(label=t("Veri klasörü", "Data folder"), command=lambda: open_path(self.data_dir))
        more["menu"] = menu
        more.pack(side="left")
        ttk.Button(buttons, text=t("Çıkış", "Quit"), command=self._quit).pack(side="right")
        ttk.Button(buttons, text=t("Simge durumuna küçült", "Minimise"), command=root.iconify).pack(
            side="right", padx=6
        )

        root.protocol("WM_DELETE_WINDOW", self._close_window)
        if sys.platform == "darwin":
            root.createcommand("::tk::mac::Quit", self._quit)
        root.after(100, self._pump)
        root.after(200, lambda: self._background(self._run_checks))

    # -- plumbing ------------------------------------------------------------
    def _icon(self) -> None:
        icon = Path(__file__).parent / "assets" / "icon.png"
        try:
            if icon.is_file():
                self.root.iconphoto(True, self.tk.PhotoImage(file=str(icon)))
        except Exception:
            pass

    def _background(self, work: Callable[[], None]) -> None:
        threading.Thread(target=work, daemon=True).start()

    def _ui(self, action: Callable[[], None]) -> None:
        self.events.put(action)

    def _pump(self) -> None:
        while True:
            try:
                self.events.get_nowait()()
            except queue.Empty:
                break
        self.root.after(100, self._pump)

    def _set_status(self, text: str, color: str | None = None, busy: bool = False) -> None:
        self.status.configure(text=text, foreground=color or "")
        if busy:
            self.progress.pack(fill="x", after=self.status)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    # -- 1. checks ---------------------------------------------------------------
    def _run_checks(self) -> None:
        done: dict[str, Any] = {}

        def on_line(obj: dict[str, Any]) -> None:
            if obj.get("type") == "check":
                self._ui(lambda: self._add_row(obj))
            elif obj.get("type") == "done":
                done.update(obj)

        try:
            stream_json(["-m", "adminpdf.selfcheck"], child_env(self.data_dir), on_line)
        except OSError as e:
            message = t("Python başlatılamadı: ", "Could not start Python: ") + str(e)
            self._ui(lambda: self._set_status(message, self.RED))
            return
        self._ui(lambda: self._checks_done(done))

    def _add_row(self, obj: dict[str, Any]) -> None:
        status = str(obj.get("status", "error"))
        detail = text_of(obj.get("detail"))
        self.tree.insert(
            "",
            "end",
            values=(MARKS.get(status, "?"), text_of(obj.get("title")), obj.get("version", ""), detail),
            tags=(status,),
        )

    def _checks_done(self, done: dict[str, Any]) -> None:
        self.subtitle.configure(
            text=t(
                f"{len(self.tree.get_children())} bileşen denetlendi",
                f"{len(self.tree.get_children())} components checked",
            )
        )
        if not done.get("ready"):
            self._set_status(
                t("✖ Sistem hazır değil — kırmızı satırlara bakın.", "✖ Not ready — see the red rows."), self.RED
            )
            return
        self._show_info(done.get("info") or {})
        self._start_server()

    def _show_info(self, info: dict[str, Any]) -> None:
        lines = [t("Adres: ", "Address: ") + app_url()]
        if info.get("lan_urls"):
            lines.append(t("Yerel ağ: ", "Local network: ") + ", ".join(info["lan_urls"]))
        lines.append(t("Sertifika parmak izi: ", "Certificate fingerprint: ") + str(info.get("fingerprint", "")) + "…")
        lines.append(t("Veri klasörü: ", "Data folder: ") + str(info.get("data_dir", self.data_dir)))
        lines.append(t("Sürüm: ", "Version: ") + str(info.get("version", "")))
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(lines))
        self.info.configure(state="disabled")

    # -- 2. server ---------------------------------------------------------------
    def _start_server(self) -> None:
        self._set_status(t("Sunucu başlatılıyor…", "Starting the server…"), busy=True)
        self.open_button.state(["disabled"])
        try:
            self.server.start(self.lan.get(), self.first_start and self.settings.get("open_browser", True))
        except OSError as e:
            self._set_status(t("Sunucu başlatılamadı: ", "Could not start the server: ") + str(e), self.RED)
            return
        self.first_start = False
        self._background(self._wait_server)

    def _wait_server(self) -> None:
        if self.server.wait_ready():
            self._ui(self._server_ready)
        else:
            self._ui(
                lambda: self._set_status(
                    t(
                        "✖ Sunucu başlamadı — Diğer ▸ Sunucu günlüğü.",
                        "✖ The server did not start — More ▸ Server log.",
                    ),
                    self.RED,
                )
            )

    def _server_ready(self) -> None:
        sharing = t(" · ağ paylaşımı açık", " · network sharing on") if self.lan.get() else ""
        self._set_status("✔ " + t("Sistem hazır", "System ready") + sharing, self.GREEN)
        self.open_button.state(["!disabled"])
        if self.check_updates.get() and self.update_info is None:
            self._background(self._check_updates)

    def _lan_changed(self) -> None:
        self.settings.set("lan", self.lan.get())
        if self.server.alive():
            self.server.stop()
            self._start_server()

    # -- 3. updates ----------------------------------------------------------------
    def _check_updates(self) -> None:
        result: dict[str, Any] = {}
        with contextlib.suppress(OSError):
            stream_json(["-m", "adminpdf.updater", "check"], child_env(self.data_dir), result.update)
        self._ui(lambda: self._updates_checked(result))

    def _updates_checked(self, r: dict[str, Any]) -> None:
        from tkinter import messagebox

        if not r.get("ok"):
            self.update_button.configure(text=t("Güncelleme denetlenemedi", "Update check failed"))
            return
        if not r.get("available"):
            self.update_button.configure(text=t("Güncel ✔", "Up to date ✔"))
            return
        self.update_info = r
        self.update_button.configure(text=t("Yeni sürüm: v", "New version: v") + str(r.get("latest")))
        comps = r.get("components") or {}
        lines = [
            t(
                f"Yeni sürüm var: v{r.get('latest')} (şu an v{r.get('current')}).",
                f"New version v{r.get('latest')} (now v{r.get('current')}).",
            )
        ]
        if comps:
            lines += ["", t("İçerdiği bileşenler:", "Bundled components:")] + [f"  • {k} {v}" for k, v in comps.items()]
        lines += [
            "",
            t(
                "İndirme sayfası açılsın mı? (Verileriniz ayrı klasörde, korunur.)",
                "Open the download page? (Your data is kept in its own folder.)",
            ),
        ]
        if messagebox.askyesno("Admin PDF Toolkit", "\n".join(lines), parent=self.root):
            webbrowser.open(str(r.get("page")))

    def _update_clicked(self) -> None:
        if self.update_info:
            webbrowser.open(str(self.update_info.get("page")))
        else:
            self.update_button.configure(text=t("Denetleniyor…", "Checking…"))
            self._background(self._check_updates)

    # -- extras ------------------------------------------------------------------------
    def _open(self) -> None:
        webbrowser.open(app_url())

    def _trust(self) -> None:
        from tkinter import messagebox

        if sys.platform.startswith("linux"):
            messagebox.showinfo(
                "Admin PDF Toolkit",
                t(
                    "Linux'ta sertifikayı tarayıcıya güvenilir kök olarak ekleyin:\n",
                    "On Linux, add this certificate to your browser as a trusted root:\n",
                )
                + str(self.data_dir / "tls" / "ca.crt"),
                parent=self.root,
            )
            return

        def trust() -> None:
            subprocess.run([child_python(), "-m", "adminpdf", "--trust-ca"], env=child_env(self.data_dir), check=False)

        self._background(trust)

    def _close_window(self) -> None:
        from tkinter import messagebox

        if not self.server.alive():
            self._quit()
            return
        answer = messagebox.askyesnocancel(
            "Admin PDF Toolkit",
            t(
                "Sunucu kapatılsın mı?\n\nEvet: kapat · Hayır: arka planda çalışmaya devam etsin (simge durumunda)",
                "Stop the server?\n\nYes: quit · No: keep it running (minimised)",
            ),
            parent=self.root,
        )
        if answer is True:
            self._quit()
        elif answer is False:
            self.root.iconify()

    def _quit(self) -> None:
        self.server.stop()
        self.root.destroy()

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self.server.stop()


def main() -> None:  # pragma: no cover
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("Tk is not available; start with: python -m adminpdf --open")
    LauncherApp().run()


if __name__ == "__main__":  # pragma: no cover
    main()
