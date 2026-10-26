"""Scan release files on VirusTotal and write a Markdown report for the release page.

    VIRUSTOTAL_API_KEY=... python scripts/virustotal.py report.md dist/*.zip AdminPDFToolkit.exe

Next to report.md it writes report.json — one short result per package
("clean 0/71", "2/71 flagged", "analyzing") — published with the release,
so the README's shields.io badges always show the latest release.

Uses the free public API (a free VirusTotal account's key, stored as the
GitHub Actions secret VIRUSTOTAL_API_KEY): 4 requests a minute, so the
script paces itself. Files already known to VirusTotal (same SHA-256) are
not uploaded again. Without a key it writes nothing and exits 0, so the
release never depends on it. Detections never fail the run either: an
unsigned new program often gets a few heuristic hits, and the report links
every file so anyone can look at the results themselves.

Standard library only.
"""

# ruff: noqa: E501  (Markdown lines)
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

API = "https://www.virustotal.com/api/v3"
GUI = "https://www.virustotal.com/gui/file/{}"
DIRECT_LIMIT = 32 * 1024 * 1024  # bigger files need an upload URL
MAX_SIZE = 650 * 1024 * 1024
PACE = 16.0  # seconds between requests: 4 per minute
WAIT = 25 * 60  # give each analysis this long


class Client:
    def __init__(self, key: str) -> None:
        self.key = key
        self.last = 0.0

    def call(self, method: str, url: str, body: bytes | None = None, ctype: str | None = None) -> tuple[int, Any]:
        delay = self.last + PACE - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()
        headers = {"x-apikey": self.key, "accept": "application/json"}
        if ctype:
            headers["content-type"] = ctype
        req = urllib.request.Request(url if url.startswith("https://") else API + url, body, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read() or b"{}")
            except ValueError:
                return exc.code, {}


def multipart(path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    return head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def known(client: Client, digest: str) -> dict[str, int] | None:
    status, data = client.call("GET", f"/files/{digest}")
    if status != 200:
        return None
    stats = data["data"]["attributes"].get("last_analysis_stats")
    return stats if stats and sum(stats.values()) else None


def upload(client: Client, path: Path) -> str:
    url = "/files"
    if path.stat().st_size > DIRECT_LIMIT:
        status, data = client.call("GET", "/files/upload_url")
        if status != 200:
            raise RuntimeError(f"upload URL: HTTP {status} {data}")
        url = data["data"]
    body, ctype = multipart(path)
    status, data = client.call("POST", url, body, ctype)
    if status != 200:
        raise RuntimeError(f"upload: HTTP {status} {data}")
    return str(data["data"]["id"])


def analysis(client: Client, analysis_id: str) -> dict[str, int] | None:
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        status, data = client.call("GET", f"/analyses/{analysis_id}")
        attrs = data.get("data", {}).get("attributes", {}) if status == 200 else {}
        if attrs.get("status") == "completed":
            stats: dict[str, int] = attrs["stats"]
            return stats
        time.sleep(30)
    return None


def scan(client: Client, path: Path) -> dict[str, Any]:
    digest = sha256(path)
    row: dict[str, Any] = {"name": path.name, "sha256": digest, "stats": None, "error": ""}
    if path.stat().st_size > MAX_SIZE:
        row["error"] = "too large"
        return row
    try:
        row["stats"] = known(client, digest) or analysis(client, upload(client, path))
    except (OSError, RuntimeError, KeyError) as exc:
        row["error"] = str(exc)[:200]
    return row


def result(row: dict[str, Any]) -> tuple[str, str]:
    stats = row["stats"]
    if row["error"]:
        return "tarama yapılamadı", "not scanned"
    if not stats:
        return "tarama sürüyor", "still scanning"
    bad = stats.get("malicious", 0) + stats.get("suspicious", 0)
    engines = sum(stats.get(k, 0) for k in ("malicious", "suspicious", "undetected", "harmless"))
    if bad:
        return f"⚠️ {bad} / {engines} motor uyarı verdi", f"⚠️ {bad} / {engines} engines flagged it"
    return f"✅ temiz (0 / {engines})", f"✅ clean (0 / {engines})"


def render(rows: list[dict[str, Any]]) -> str:
    lines = [
        "## VirusTotal",
        "",
        "Bu sürümün dosyaları yayımlanırken [VirusTotal](https://www.virustotal.com) ile otomatik tarandı; "
        "bağlantılardan tüm antivirüs motorlarının güncel sonucunu görebilirsiniz. "
        "*Every file of this release was scanned on VirusTotal while publishing; the links show the current result of every engine.*",
        "",
        "| Dosya / File | Sonuç | Result | SHA-256 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        tr, en = result(row)
        lines.append(f"| [`{row['name']}`]({GUI.format(row['sha256'])}) | {tr} | {en} | `{row['sha256'][:16]}…` |")
    if any(r["stats"] and r["stats"].get("malicious", 0) + r["stats"].get("suspicious", 0) for r in rows):
        lines += [
            "",
            "> [!NOTE]",
            "> Az sayıda motorun uyarısı yeni ve ücretli sertifikayla imzalanmamış programlarda sık görülen bir yanlış alarmdır; "
            "kaynak kod ve derleme kayıtları herkese açıktır. *A few hits on a new program without a paid signing certificate "
            "are a common false positive; the source and the build logs are public.*",
        ]
    return "\n".join(lines) + "\n"


# Badge keys in report.json, by file name.
KINDS = {
    ".exe": "exe",
    "-Windows.zip": "windows",
    "-macOS-arm64.zip": "macos",
    "-Linux-x86_64.tar.gz": "linux",
    "-Linux-macOS.zip": "source",
}


def badges(rows: list[dict[str, Any]]) -> dict[str, str]:
    out = {}
    for row in rows:
        kind = next((k for suffix, k in KINDS.items() if row["name"].endswith(suffix)), None)
        if not kind:
            continue
        stats = row["stats"]
        if row["error"]:
            text = "not scanned"
        elif not stats:
            text = "analyzing"
        else:
            bad = stats.get("malicious", 0) + stats.get("suspicious", 0)
            engines = sum(stats.get(k, 0) for k in ("malicious", "suspicious", "undetected", "harmless"))
            text = f"{bad}/{engines} flagged" if bad else f"clean 0/{engines}"
        out[kind] = text
    return out


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: virustotal.py <report.md> <file>...")
    key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
    if not key:
        print("VIRUSTOTAL_API_KEY is not set: skipping the VirusTotal scan")
        return
    client = Client(key)
    rows = []
    for name in sys.argv[2:]:
        row = scan(client, Path(name))
        print(json.dumps(row), flush=True)
        if row["error"]:
            print(f"::warning::VirusTotal {row['name']}: {row['error']}")
        rows.append(row)
    report = Path(sys.argv[1])
    report.write_text(render(rows), encoding="utf-8")
    report.with_suffix(".json").write_text(json.dumps(badges(rows), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
