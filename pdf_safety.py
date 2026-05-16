"""
PDF Güvenlik Taraması
=====================

Üç seviyeli kontrol:
  1. Yapısal şüphe: PDF içinde JavaScript, embedded file, launch action,
     OpenAction, additional action, dış URI vb. tespiti (PyMuPDF tabanlı,
     ek bağımlılık yok). Compressed stream'leri kaçırabilir — bu yüzden
     ek katmanlar var.
  2. pdfid.py (opsiyonel): Didier Stevens'ın pdfid'i deflate edilmiş
     objeleri açıp inceliyor — compressed stream blind spot'unu kapatır.
  3. ClamAV (opsiyonel): sistemde clamscan varsa imza tabanlı virüs
     taraması.
  4. Windows Defender (opsiyonel, Win): MpCmdRun.exe ile second opinion.

assert_safe() conversion entry-point'lerinde gate görevi görür:
verdict 'danger' ise UnsafePDFError fırlatır.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


class UnsafePDFError(Exception):
    """Raised when assert_safe() refuses a PDF based on the active policy."""

    def __init__(self, scan: dict[str, Any]) -> None:
        super().__init__("Güvensiz PDF reddedildi.")
        self.scan = scan


# ----------------------------------------------------------------------------
# Yapısal şüphe — PDF byte içinde anahtar kelimeler arar (Didier Stevens'ın
# pdfid yöntemine benzer; bizim için yeterli, hızlı, kütüphane yok).
# ----------------------------------------------------------------------------

# Etiket → (anahtar regex, açıklama, ağırlık)
# Ağırlık: low (bilgi), med (dikkat), high (tehlikeli)
_SUSPICIOUS_PATTERNS: list[tuple[str, str, str, str]] = [
    ("/JavaScript", r"/JavaScript", "JavaScript çalıştırılabilir kodu", "high"),
    ("/JS", r"/JS\b", "JavaScript referansı", "high"),
    ("/OpenAction", r"/OpenAction", "Dosya açılınca otomatik tetiklenen aksiyon", "med"),
    ("/AA", r"/AA\b", "Additional Actions (sayfa olayları)", "med"),
    ("/Launch", r"/Launch", "Komut/uygulama başlatma", "high"),
    ("/EmbeddedFile", r"/EmbeddedFile", "Gömülü dosya (gizli ek)", "med"),
    ("/RichMedia", r"/RichMedia", "Flash/multimedya gömme", "med"),
    ("/SubmitForm", r"/SubmitForm", "Form gönderme aksiyonu", "med"),
    ("/GoToR", r"/GoToR", "Dış dosyaya bağlantı", "low"),
    ("/URI", r"/URI\b", "Dış URL bağlantısı", "low"),
    ("/XFA", r"/XFA\b", "XFA form (eski/karmaşık)", "low"),
]


def check_structure(pdf_path: Path, *, doc: Any | None = None) -> dict[str, Any]:
    """PDF yapısını şüpheli içerik için tarar.

    ``doc`` opsiyonel — eğer çağıran zaten ``fitz.open`` etmişse buraya verip
    bir tane daha açma maliyetinden kaçınabilir; aksi halde kendimiz açıp
    kapatırız (geri uyumlu davranış).
    """
    findings: list[dict[str, Any]] = []
    encrypted = False
    page_count = 0
    file_size_mb = 0.0

    with contextlib.suppress(OSError):
        file_size_mb = pdf_path.stat().st_size / (1024 * 1024)

    # PyMuPDF ile temel bilgiler — pre-opened doc varsa onu kullan
    if doc is not None:
        try:
            page_count = len(doc)
            encrypted = bool(doc.is_encrypted)
        except Exception:
            pass
    else:
        try:
            _doc = fitz.open(str(pdf_path))
            try:
                page_count = len(_doc)
                encrypted = bool(_doc.is_encrypted)
            finally:
                _doc.close()
        except Exception:
            pass

    # Ham PDF içinde anahtar kelime arama (compress edilmiş kısımları kaçırır
    # ama çoğu vakada işimizi görür — saldırgan paketler genelde uncompressed
    # bırakır ki AV'lardan kaçsın, biz tam tersini istiyoruz).
    #
    # Önceki sürümde 8 MB üstü dosyalarda yalnızca ilk + son 4 MB taranıyordu;
    # ortaya gizlenmiş /JavaScript / /Launch payload'ı bu pencerede kaçabiliyordu.
    # Bellek MAX_UPLOAD_MB ile sınırlı (default 200 MB), o yüzden tüm dosyayı
    # okumak güvenli — ekstra CPU maliyeti (~ saniye altı) defense-in-depth
    # için kabul edilebilir.
    try:
        raw = pdf_path.read_bytes()
        text = raw.decode("latin-1", errors="ignore")

        for label, pattern, desc, weight in _SUSPICIOUS_PATTERNS:
            count = len(re.findall(pattern, text))
            if count > 0:
                findings.append(
                    {
                        "label": label,
                        "count": count,
                        "description": desc,
                        "severity": weight,
                    }
                )
    except Exception:
        pass

    high = sum(1 for f in findings if f["severity"] == "high")
    med = sum(1 for f in findings if f["severity"] == "med")
    low = sum(1 for f in findings if f["severity"] == "low")

    if high > 0:
        verdict = "danger"
    elif med > 0:
        verdict = "warning"
    elif low > 0:
        verdict = "notice"
    else:
        verdict = "clean"

    return {
        "verdict": verdict,  # clean / notice / warning / danger
        "page_count": page_count,
        "encrypted": encrypted,
        "file_size_mb": round(file_size_mb, 2),
        "findings": findings,
        "counts": {"high": high, "medium": med, "low": low},
    }


# ----------------------------------------------------------------------------
# ClamAV opsiyonel — sistem PATH veya yan klasörde varsa kullanılır
# ----------------------------------------------------------------------------

_clamav_path: str | None = None
_clamav_checked = False


def _find_clamscan() -> str | None:
    """Sistemde clamscan yolu — yan klasör 'clamav/' önce, sonra PATH."""
    global _clamav_path, _clamav_checked
    if _clamav_checked:
        return _clamav_path

    here = Path(__file__).resolve().parent
    # 1. Portable yan klasör
    for cand in [
        here / "clamav" / "clamscan.exe",
        here / "clamav" / "clamscan",
    ]:
        if cand.exists():
            _clamav_path = str(cand)
            _clamav_checked = True
            return _clamav_path
    # 2. PATH
    found = shutil.which("clamscan")
    if found:
        _clamav_path = found
    _clamav_checked = True
    return _clamav_path


def clamav_available() -> bool:
    # Either daemon mode (clamdscan + bundled clamd) or standalone clamscan works
    try:
        from core.clamav_daemon import find_clamdscan

        if find_clamdscan() is not None:
            return True
    except Exception:
        pass
    return _find_clamscan() is not None


def clamav_scan(pdf_path: Path, timeout: int = 60) -> dict[str, Any] | None:
    """ClamAV ile dosya tara. None döndürürse ClamAV yok demek.
    Aksi halde {"clean": bool, "threat": str|None, "raw": str}.

    Strategy:
      1. If clamd daemon is running, use ``clamdscan`` (talks to daemon over
         TCP) — signatures stay hot in RAM, scan is ~ms.
      2. If clamd is bundled but not yet running, try to start it.
      3. Fall back to standalone ``clamscan`` (slow: 5-15 s per scan as it
         reloads signature DB every invocation).
    """
    # --- Daemon path (fast: ~100ms per scan via INSTREAM socket) -----------
    # Talks to clamd directly over TCP — bypasses clamdscan.exe (which has
    # Windows ANSI/UTF-8 path encoding problems with Turkish filenames) and
    # avoids subprocess overhead entirely.
    try:
        from core.clamav_daemon import ensure_clamd_running, instream_scan, is_ready

        if is_ready() or ensure_clamd_running(boot_timeout=2.0):
            result = instream_scan(pdf_path, timeout=float(timeout))
            if result is not None:
                return result
            # instream_scan returned None → daemon returned an unrecognized
            # response (rare). Fall through to standalone scanner.
    except Exception:
        pass

    # --- Standalone fallback (slow: signatures reloaded each invocation) ----
    exe = _find_clamscan()
    if not exe:
        return None
    try:
        proc_result = subprocess.run(
            [exe, "--no-summary", "--infected", "--stdout", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc_result.stdout or "") + (proc_result.stderr or "")
        threat: str | None = None
        for line in out.splitlines():
            line = line.strip()
            if line.endswith(" FOUND"):
                parts = line.rsplit(":", 1)
                if len(parts) == 2:
                    name = parts[1].strip()
                    if name.endswith(" FOUND"):
                        name = name[:-6].strip()
                    threat = name
                break
        return {
            "clean": proc_result.returncode == 0,
            "threat": threat,
            "exit_code": proc_result.returncode,
            "engine": "clamscan",
            "raw": out[:1000],
        }
    except subprocess.TimeoutExpired:
        return {
            "clean": False,
            "threat": None,
            "exit_code": -1,
            "engine": "clamscan",
            "raw": "timeout",
        }
    except Exception as e:
        return {
            "clean": True,
            "threat": None,
            "exit_code": -2,
            "engine": "clamscan",
            "raw": f"error: {e}",
        }


# ----------------------------------------------------------------------------
# pdfid.py — opsiyonel deflate-aware second opinion
# ----------------------------------------------------------------------------

_pdfid_path: str | None = None
_pdfid_checked = False

# Anahtar kelimeler içinde gerçekten tehlikeli sayılanlar
_PDFID_DANGEROUS = {"/JavaScript", "/JS", "/Launch", "/OpenAction", "/AA"}


def _find_pdfid() -> str | None:
    global _pdfid_path, _pdfid_checked
    if _pdfid_checked:
        return _pdfid_path
    here = Path(__file__).resolve().parent
    for cand in [here / "pdfid" / "pdfid.py", here / "pdfid.py"]:
        if cand.exists():
            _pdfid_path = str(cand)
            _pdfid_checked = True
            return _pdfid_path
    found = shutil.which("pdfid.py") or shutil.which("pdfid")
    if found:
        _pdfid_path = found
    _pdfid_checked = True
    return _pdfid_path


def pdfid_scan(pdf_path: Path, timeout: int = 15) -> dict[str, Any] | None:
    """Run pdfid.py if available; returns dangerous-keyword counts.

    pdfid.py açar deflate edilmiş objeleri ve içlerinde /JavaScript /Launch
    benzeri anahtar kelime aratır. Bu, ham byte taramanın kaçırdığı
    compressed stream blind spot'unu kapatır.
    """
    exe = _find_pdfid()
    if not exe:
        return None
    try:
        # pdfid.py [-f] file — count keywords; -f forces extra patterns.
        # Using ``sys.executable`` (not "python") so a poisoned PATH on the
        # operator's host can't substitute a hostile interpreter for the
        # safety scanner.
        cmd = (
            [sys.executable, exe, str(pdf_path)]
            if exe.endswith(".py")
            else [exe, str(pdf_path)]
        )
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout or ""
        counts: dict[str, int] = {}
        # Output rows: "  /JavaScript     2"
        for line in out.splitlines():
            line = line.strip()
            for kw in _PDFID_DANGEROUS:
                if line.startswith(kw):
                    rest = line[len(kw) :].strip()
                    with contextlib.suppress(ValueError, IndexError):
                        counts[kw] = int(rest.split()[0])
        dangerous_total = sum(counts.values())
        return {
            "available": True,
            "counts": counts,
            "dangerous_total": dangerous_total,
            "verdict": "danger" if dangerous_total > 0 else "clean",
        }
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "counts": {},
            "dangerous_total": 0,
            "verdict": "unknown",
            "error": "timeout",
        }
    except Exception as e:
        return {
            "available": True,
            "counts": {},
            "dangerous_total": 0,
            "verdict": "unknown",
            "error": f"error: {e}",
        }


# ----------------------------------------------------------------------------
# Windows Defender CLI (opsiyonel) — only on Windows
# ----------------------------------------------------------------------------

_mpcmd_path: str | None = None
_mpcmd_checked = False


def _find_mpcmdrun() -> str | None:
    global _mpcmd_path, _mpcmd_checked
    if _mpcmd_checked:
        return _mpcmd_path
    if os.name != "nt":
        _mpcmd_checked = True
        return None
    candidates = [
        Path(r"C:\Program Files\Windows Defender\MpCmdRun.exe"),
        Path(r"C:\ProgramData\Microsoft\Windows Defender\Platform"),
    ]
    fixed = candidates[0]
    if fixed.exists():
        _mpcmd_path = str(fixed)
        _mpcmd_checked = True
        return _mpcmd_path
    # Search the platform versioned dirs
    platform_root = candidates[1]
    if platform_root.exists():
        for sub in sorted(platform_root.iterdir(), reverse=True):
            exe = sub / "MpCmdRun.exe"
            if exe.exists():
                _mpcmd_path = str(exe)
                break
    found = shutil.which("MpCmdRun.exe")
    if not _mpcmd_path and found:
        _mpcmd_path = found
    _mpcmd_checked = True
    return _mpcmd_path


def mpcmdrun_scan(pdf_path: Path, timeout: int = 60) -> dict[str, Any] | None:
    """Windows Defender CLI scan; available on every Win10/11 box at no cost.

    Defender's exit codes are noisy: 2 means "threat detected" *or* "scanner
    failed to start" depending on context. We disambiguate by inspecting
    stdout — only treat exit==2 as a real detection when the output contains
    a known threat marker. Engine/permission failures are reported as
    ``status='error'`` and do NOT trigger a 'danger' overall verdict.
    """
    exe = _find_mpcmdrun()
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "-Scan", "-ScanType", "3", "-File", str(pdf_path), "-DisableRemediation"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (result.stdout or "") + (result.stderr or "")
        out_lower = out.lower()
        error_markers = (
            "failed with hr",
            "command line error",
            "no engine could be loaded",
            "scan starting failed",
        )
        detection_markers = ("found ", "threat detected", "infected", "list of detected")
        if any(m in out_lower for m in error_markers):
            status = "error"
        elif result.returncode == 2 and any(m in out_lower for m in detection_markers):
            status = "infected"
        elif result.returncode == 0:
            status = "clean"
        else:
            status = "error"  # unknown non-zero — be conservative, don't block
        return {
            "clean": status == "clean",
            "status": status,  # clean | infected | error
            "exit_code": result.returncode,
            "raw": out[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"clean": False, "status": "error", "exit_code": -1, "raw": "timeout"}
    except Exception as e:
        return {"clean": True, "status": "error", "exit_code": -2, "raw": f"error: {e}"}


# ----------------------------------------------------------------------------
# Birleşik tarama
# ----------------------------------------------------------------------------


def full_scan(pdf_path: Path, *, doc: Any | None = None) -> dict[str, Any]:
    """Run every available scanner. ``doc`` is forwarded to ``check_structure``
    so callers that already opened the PDF for other work don't pay a second
    ``fitz.open``.

    Scanners run in parallel via ``ThreadPoolExecutor`` — total wall time is
    bounded by the slowest scanner (typically pdfid or Defender) instead of
    the sum. Each scanner is independent and side-effect free, so parallelism
    is safe. ``mpcmdrun`` only runs when clamav is unavailable; that decision
    is made eagerly here based on ``clamav_available()`` to keep the parallel
    fan-out simple.
    """
    from concurrent.futures import ThreadPoolExecutor

    run_defender = not clamav_available()

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_struct = pool.submit(check_structure, pdf_path, doc=doc)
        fut_av = pool.submit(clamav_scan, pdf_path)
        fut_pdfid = pool.submit(pdfid_scan, pdf_path)
        fut_mpcmd = pool.submit(mpcmdrun_scan, pdf_path) if run_defender else None

        structure = fut_struct.result()
        av = fut_av.result()
        pdfid = fut_pdfid.result()
        mpcmd = fut_mpcmd.result() if fut_mpcmd is not None else None
    overall: str
    if av is not None and not av["clean"]:
        overall = "danger"  # ClamAV imza tabanlı tehdit
    elif mpcmd is not None and mpcmd.get("status") == "infected":
        overall = "danger"  # Defender'ın gerçek bulgusu (sadece status==infected)
    elif pdfid is not None and pdfid.get("verdict") == "danger":
        overall = "danger"  # compressed stream'de tehlikeli keyword
    elif structure["verdict"] in ("danger",):
        overall = "danger"
    elif structure["verdict"] == "warning":
        overall = "warning"
    elif structure["verdict"] == "notice":
        overall = "notice"
    else:
        overall = "clean"

    return {
        "overall": overall,
        "structure": structure,
        "antivirus": av,  # None ise ClamAV yok
        "av_available": clamav_available(),
        "pdfid": pdfid,  # None ise pdfid.py yok
        "defender": mpcmd,  # None ise Defender yok / atlanmış
    }


def assert_safe(pdf_path: Path, *, policy: str | None = None) -> dict[str, Any]:
    """Conversion gate: scan ``pdf_path`` and refuse it if policy demands.

    The policy argument overrides ``settings.safety_policy`` when supplied;
    otherwise the live setting is consulted on every call so an operator can
    flip ``HT_SAFETY_POLICY`` at runtime without restarting.

    Returns the scan dict on success. Raises UnsafePDFError when the active
    policy is ``block_danger`` and overall verdict is ``danger``.
    """
    if policy is None:
        # Lazy import — allows pdf_safety.py to be used standalone in tests
        from settings import settings as _settings

        policy = _settings.safety_policy

    if policy == "off":
        return {
            "overall": "clean",
            "structure": None,
            "antivirus": None,
            "av_available": False,
            "pdfid": None,
            "defender": None,
            "policy": "off",
        }

    scan = full_scan(pdf_path)
    scan["policy"] = policy
    if policy == "block_danger" and scan["overall"] == "danger":
        raise UnsafePDFError(scan)
    return scan
