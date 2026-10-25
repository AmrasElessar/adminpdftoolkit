"""Security: structural risk scan (with optional ClamAV) and sanitising.

The scan walks the object graph with pikepdf from the trailer, keyed by
object number so reference cycles are visited once, and stops after a node
budget so hostile files cannot explode it. Only dictionaries are inspected;
stream data is never decoded (no decompression bombs).
"""

from __future__ import annotations

import contextlib
import mmap
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pikepdf
from pikepdf import Array, Dictionary, Name, Stream

from ..core import proc
from ..core.errors import UserError
from .base import Context, Field, InputFile, Operation, Params, register

NODE_BUDGET = 1_000_000
AV_TIMEOUT = 180
MAX_LISTED = 100

TRACKED_ACTIONS = (
    "JavaScript",
    "Launch",
    "GoToR",
    "GoToE",
    "ImportData",
    "SubmitForm",
    "URI",
    "RichMediaExecute",
    "Rendition",
    "Movie",
    "Sound",
)
# Removed by `sanitize` unconditionally / only with remove_links.
ACTIVE_ACTIONS = frozenset({"JavaScript", "Launch", "GoToR", "GoToE", "ImportData", "RichMediaExecute"})
MEDIA_ACTIONS = frozenset({"Rendition", "Movie", "Sound"})
NETWORK_ACTIONS = frozenset({"URI", "SubmitForm"})
MEDIA_ANNOTS = frozenset({"RichMedia", "3D", "Screen", "Movie", "Sound"})

EXECUTABLE_EXTS = frozenset(
    {
        "exe", "dll", "scr", "com", "bat", "cmd", "pif", "msi", "msp", "vbs", "vbe", "js", "jse", "wsf",
        "wsh", "ps1", "psm1", "hta", "jar", "lnk", "reg", "cpl", "sh", "app", "dmg", "docm", "xlsm",
        "pptm", "iso", "swf",
    }
)  # fmt: skip

# Walking these keys only revisits known objects or big, inert trees.
_SKIP_KEYS = frozenset({"/Parent", "/P", "/Encrypt", "/StructTreeRoot", "/ParentTree"})
# Keys through which the "where was this action attached" label flows.
_INHERIT_KEYS = frozenset({"/Next", "/Names", "/Kids", "/JavaScript"})

LEVELS = ("none", "low", "medium", "high")


def _name(obj: Any) -> str:
    """``/JavaScript`` → ``JavaScript``; anything else → ``""``."""
    return str(obj)[1:] if isinstance(obj, Name) else ""


def _text(obj: Any, limit: int = 300) -> str:
    try:
        s = str(obj) if isinstance(obj, pikepdf.String) else ""
    except Exception:
        s = ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", s).strip()[:limit]


def _kind(d: Any) -> str:
    """Rough role of a dictionary that carries an action."""
    t = _name(d.get("/Type"))
    if t == "Catalog":
        return "document"
    if t == "Page":
        return "page"
    if "/FT" in d:
        return "field"
    if "/Subtype" in d and "/Rect" in d:
        return "annotation"
    if "/Title" in d:
        return "outline"
    return "other"


@dataclass
class Findings:
    actions: Counter[str] = field(default_factory=Counter)
    javascript: int = 0
    js_locations: Counter[str] = field(default_factory=Counter)
    js_previews: list[str] = field(default_factory=list)
    additional_actions: Counter[str] = field(default_factory=Counter)
    open_action: str = ""
    uri_hosts: Counter[str] = field(default_factory=Counter)
    submit_hosts: Counter[str] = field(default_factory=Counter)
    launch_targets: list[str] = field(default_factory=list)
    embedded: list[dict[str, Any]] = field(default_factory=list)
    media: Counter[str] = field(default_factory=Counter)
    flash: int = 0
    xfa: bool = False
    signatures: int = 0
    nodes: int = 0
    truncated: bool = False


def _host(uri: str) -> str:
    try:
        parts = urlsplit(uri.strip())
    except ValueError:
        return "?"
    return (parts.hostname or parts.scheme or "?").lower()[:200]


def _file_name(spec: Any) -> str:
    if isinstance(spec, pikepdf.String):
        return _text(spec, 200)
    if isinstance(spec, Dictionary):
        for key in ("/UF", "/F", "/DOS", "/Unix", "/Mac"):
            if key in spec:
                return _text(spec.get(key), 200)
    return ""


class Walker:
    """Visit every reachable container once, within a node budget."""

    def __init__(self, pdf: pikepdf.Pdf, budget: int = NODE_BUDGET) -> None:
        self.pdf = pdf
        self.budget = budget
        self.nodes = 0
        self.truncated = False

    def dicts(self) -> Any:
        """Yield ``(dictionary, context_label)`` pairs."""
        seen: set[tuple[int, int]] = set()
        stack: list[tuple[Any, str]] = [(self.pdf.trailer, "")]
        while stack:
            obj, ctx = stack.pop()
            self.nodes += 1
            if self.nodes > self.budget:
                self.truncated = True
                return
            if obj.is_indirect:
                key = obj.objgen
                if key in seen:
                    continue
                seen.add(key)
            if isinstance(obj, Array):
                self.nodes += len(obj)
                stack.extend((v, ctx) for v in obj if isinstance(v, (Dictionary, Array, Stream)))
                continue
            yield obj, ctx
            keys = list(obj.keys())
            self.nodes += len(keys)
            is_aa = ctx.startswith("aa_") and "/S" not in obj
            for k in keys:
                if k in _SKIP_KEYS:
                    continue
                try:
                    v = obj.get(k)
                except Exception:
                    continue
                if not isinstance(v, (Dictionary, Array, Stream)):
                    continue
                if k == "/OpenAction":
                    c = "open_action"
                elif k == "/AA":
                    c = "aa_" + _kind(obj)
                elif k == "/A":
                    c = _kind(obj)
                elif k == "/JavaScript" and ctx == "names":
                    c = "document"
                elif k == "/Names" and _name(obj.get("/Type")) == "Catalog":
                    c = "names"
                elif k in _INHERIT_KEYS or is_aa:
                    c = ctx
                else:
                    c = ""
                stack.append((v, c))


def analyze(pdf: pikepdf.Pdf) -> Findings:
    f = Findings()
    root = pdf.Root
    oa = root.get("/OpenAction")
    if isinstance(oa, Dictionary):
        f.open_action = _name(oa.get("/S")) or "action"
    elif isinstance(oa, Array):
        f.open_action = "destination"
    acro = root.get("/AcroForm")
    f.xfa = isinstance(acro, Dictionary) and "/XFA" in acro
    walker = Walker(pdf)
    seen_files: set[str] = set()
    for d, ctx in walker.dicts():
        s = _name(d.get("/S"))
        if s in TRACKED_ACTIONS:
            f.actions[s] += 1
        if s == "JavaScript" or "/JS" in d:
            f.javascript += 1
            f.js_locations[ctx or "other"] += 1
            preview = _text(d.get("/JS"), 160)
            if preview and len(f.js_previews) < 10:
                f.js_previews.append(preview)
        if s == "URI" and len(f.uri_hosts) < MAX_LISTED:
            f.uri_hosts[_host(_text(d.get("/URI"), 2000))] += 1
        if s == "SubmitForm" and len(f.submit_hosts) < MAX_LISTED:
            target = d.get("/F")
            url = _text(target.get("/F"), 2000) if isinstance(target, Dictionary) else _text(target, 2000)
            f.submit_hosts[_host(url)] += 1
        if s == "Launch" and len(f.launch_targets) < 20:
            win = d.get("/Win")
            target = _file_name(d.get("/F")) or (_file_name(win.get("/F")) if isinstance(win, Dictionary) else "")
            f.launch_targets.append(target or "?")
        if "/AA" in d:
            f.additional_actions[_kind(d)] += 1
        sub = _name(d.get("/Subtype"))
        if sub in MEDIA_ANNOTS or sub in ("U3D", "PRC"):
            f.media["3D" if sub in ("U3D", "PRC") else sub] += 1
        if sub == "Flash" or (sub == "RichMediaContent" and "swf" in str(d.get("/Assets", "")).lower()):
            f.flash += 1
        ef = d.get("/EF")
        if isinstance(ef, Dictionary):
            ident = str(d.objgen) if d.is_indirect else str(id(d))
            if ident not in seen_files and len(f.embedded) < MAX_LISTED:
                seen_files.add(ident)
                stream = ef.get("/UF") or ef.get("/F")
                size = None
                if isinstance(stream, Stream):
                    params = stream.get("/Params")
                    raw = params.get("/Size") if isinstance(params, Dictionary) else None
                    size = int(raw) if isinstance(raw, int) else None
                name = _file_name(d) or "?"
                if name.lower().endswith(".swf"):
                    f.flash += 1
                f.embedded.append({"name": name, "size": size})
        if "/ByteRange" in d and "/Contents" in d:
            f.signatures += 1
    f.nodes, f.truncated = walker.nodes, walker.truncated
    return f


# -- raw-file facts ------------------------------------------------------------------
def count_eof_markers(path: Path) -> int:
    with path.open("rb") as fh:
        try:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:  # empty file
            return 0
        with mm:
            count, pos = 0, mm.find(b"%%EOF")
            while pos != -1:
                count += 1
                pos = mm.find(b"%%EOF", pos + 5)
            return count


def _scrub(message: str, path: Path) -> str:
    return message.replace(str(path), "PDF").replace(path.name, "PDF")[:300]


# -- antivirus -------------------------------------------------------------------------
def antivirus_scan(path: Path) -> dict[str, Any]:
    exe = shutil.which("clamscan")
    base: dict[str, Any] = {"engine": "ClamAV", "available": False}
    if exe is None:
        return base | {"reason": {"tr": "ClamAV yüklü değil.", "en": "ClamAV is not installed."}}
    try:
        r = proc.run([exe, "--no-summary", "--stdout", str(path)], timeout=AV_TIMEOUT)
    except (UserError, OSError):
        return base | {"reason": {"tr": "Virüs taraması zaman aşımına uğradı.", "en": "The virus scan timed out."}}
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    if r.returncode == 0:
        return base | {"available": True, "clean": True, "threat": None}
    if r.returncode == 1:
        threat = "?"
        for line in out.splitlines():
            if line.rstrip().endswith(" FOUND"):
                threat = line.rsplit(":", 1)[-1].strip()[: -len("FOUND")].strip()[:200] or "?"
                break
        return base | {"available": True, "clean": False, "threat": threat}
    if "database" in out.lower():
        return base | {
            "reason": {
                "tr": "ClamAV imza veritabanı bulunamadı (freshclam ile güncelleyin).",
                "en": "ClamAV signature database not found (update it with freshclam).",
            }
        }
    return base | {"reason": {"tr": "Virüs taraması çalıştırılamadı.", "en": "The virus scan could not run."}}


# -- risk -------------------------------------------------------------------------------
def _reason(level: str, code: str, tr: str, en: str) -> dict[str, str]:
    return {"level": level, "code": code, "tr": tr, "en": en}


def assess(report: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    reasons: list[dict[str, str]] = []
    a: dict[str, int] = report["actions"]
    js = report["javascript"]["count"]
    if js:
        reasons.append(_reason("high", "javascript", f"JavaScript içeriyor ({js}).", f"Contains JavaScript ({js})."))
    if a.get("Launch"):
        reasons.append(
            _reason(
                "high", "launch", "Program/dosya başlatma eylemi var.", "Has an action that launches programs/files."
            )
        )
    if report["flash"]:
        reasons.append(_reason("high", "flash", "Flash (SWF) içerik var.", "Contains Flash (SWF) content."))
    names = [str(e["name"]) for e in report["embedded_files"]]
    executables = [n for n in names if n.rsplit(".", 1)[-1].lower() in EXECUTABLE_EXTS]
    if executables:
        reasons.append(
            _reason(
                "high",
                "embedded_executable",
                f"Çalıştırılabilir/makrolu gömülü dosya: {', '.join(executables[:5])}.",
                f"Embedded executable/macro file: {', '.join(executables[:5])}.",
            )
        )
    av = report["antivirus"]
    if av.get("available") and av.get("clean") is False:
        reasons.append(
            _reason(
                "high", "virus", f"Virüs tarayıcı tehdit buldu: {av['threat']}.", f"Antivirus found: {av['threat']}."
            )
        )
    n_files = len(report["embedded_files"])
    if n_files and not executables:
        reasons.append(
            _reason(
                "medium", "embedded_files", f"Gömülü dosya içeriyor ({n_files}).", f"Has embedded files ({n_files})."
            )
        )
    if report["rich_media"]:
        reasons.append(_reason("medium", "rich_media", "Multimedya/3B içerik var.", "Contains multimedia/3D content."))
    if report["xfa"]:
        reasons.append(
            _reason("medium", "xfa", "XFA formu var (betik içerebilir).", "Has an XFA form (may contain scripts).")
        )
    for action, tr, en in (
        ("GoToR", "Başka bir dosyayı açan bağlantı var", "Links that open another file"),
        ("GoToE", "Gömülü belgeye geçiş eylemi var", "Actions that open embedded documents"),
        ("ImportData", "Dış veri içe aktarma eylemi var", "Actions that import external data"),
        ("SubmitForm", "Form verisini dışarı gönderen eylem var", "Actions that submit form data externally"),
    ):
        if a.get(action):
            reasons.append(_reason("medium", action.lower(), f"{tr} ({a[action]}).", f"{en} ({a[action]})."))
    aa = sum(report["additional_actions"].values())
    if aa:
        reasons.append(
            _reason(
                "medium",
                "additional_actions",
                f"Otomatik tetiklenen eylemler (AA) var ({aa}).",
                f"Has automatically triggered actions (AA) ({aa}).",
            )
        )
    if report["open_action"] not in ("", "destination", "GoTo", "JavaScript"):
        reasons.append(
            _reason(
                "medium",
                "open_action",
                f"Belge açılınca eylem çalışır ({report['open_action']}).",
                f"An action runs when the document opens ({report['open_action']}).",
            )
        )
    if report["structure"]["scan_truncated"]:
        reasons.append(
            _reason(
                "medium",
                "truncated",
                "Yapı çok büyük/karmaşık; tarama yarıda kesildi.",
                "The structure is too large/complex; the scan was cut short.",
            )
        )
    if report["structure"]["repaired"]:
        reasons.append(
            _reason(
                "medium",
                "repaired",
                "Dosya yapısı bozuk; açılırken onarıldı.",
                "The file structure is broken and was repaired on open.",
            )
        )
    elif report["structure"]["warnings"]:
        reasons.append(
            _reason("low", "warnings", "Dosya yapısında küçük hatalar var.", "The file structure has minor errors.")
        )
    if a.get("URI"):
        hosts = ", ".join(list(report["uri_hosts"])[:5])
        reasons.append(
            _reason(
                "low", "uri", f"Dış bağlantılar var ({a['URI']}): {hosts}.", f"External links ({a['URI']}): {hosts}."
            )
        )
    if report["structure"]["incremental_updates"] > 3:
        n = report["structure"]["incremental_updates"]
        reasons.append(
            _reason("low", "updates", f"Çok sayıda artımlı güncelleme ({n}).", f"Many incremental updates ({n}).")
        )
    if report["structure"]["unusual_object_count"]:
        reasons.append(_reason("low", "objects", "Olağandışı sayıda nesne var.", "Unusually high number of objects."))
    reasons.sort(key=lambda r: -LEVELS.index(r["level"]))
    return (reasons[0]["level"] if reasons else "none"), reasons


def open_pikepdf(inp: InputFile) -> pikepdf.Pdf:
    try:
        return pikepdf.open(inp.path, password=inp.password)
    except pikepdf.PasswordError as e:
        raise UserError(
            "PDF şifreli — doğru şifreyi girin.", "The PDF is password-protected — enter the correct password."
        ) from e
    except Exception as e:
        raise UserError(
            "PDF okunamadı; dosya çok bozuk olabilir. Önce 'Onar' aracını deneyin.",
            "The PDF could not be read; it may be badly damaged. Try the 'Repair' tool first.",
        ) from e


def scan_file(inp: InputFile, *, antivirus: bool) -> dict[str, Any]:
    import pymupdf

    repaired = False
    with contextlib.suppress(Exception), pymupdf.open(inp.path) as doc:
        repaired = bool(doc.is_repaired)
    with open_pikepdf(inp) as pdf:
        warnings = [_scrub(str(w), inp.path) for w in pdf.get_warnings()]
        found = analyze(pdf)
        try:
            pages = len(pdf.pages)
        except Exception:
            pages = 0
        objects = len(pdf.objects)
        enc: dict[str, Any] | None = None
        if pdf.is_encrypted:
            info = pdf.encryption
            enc = {"method": str(info.stream_method).rsplit(".", 1)[-1], "bits": int(info.bits), "revision": info.R}
        linearized = bool(pdf.is_linearized)
    eofs = count_eof_markers(inp.path)
    report: dict[str, Any] = {
        "pages": pages,
        "javascript": {
            "count": found.javascript,
            "locations": dict(found.js_locations),
            "previews": found.js_previews,
        },
        "open_action": found.open_action,
        "additional_actions": dict(found.additional_actions),
        "actions": {k: found.actions.get(k, 0) for k in TRACKED_ACTIONS if found.actions.get(k)},
        "uri_hosts": dict(found.uri_hosts.most_common(MAX_LISTED)),
        "submit_hosts": dict(found.submit_hosts),
        "launch_targets": found.launch_targets,
        "embedded_files": found.embedded,
        "rich_media": dict(found.media),
        "flash": found.flash,
        "xfa": found.xfa,
        "encryption": enc,
        "signatures": found.signatures,
        "structure": {
            "objects": objects,
            "unusual_object_count": objects > 1_000_000 or (objects > 50_000 and objects > 5_000 * max(pages, 1)),
            "incremental_updates": max(0, eofs - 1 - int(linearized)),
            "linearized": linearized,
            "repaired": repaired,
            "warnings": warnings[:20],
            "nodes_scanned": found.nodes,
            "scan_truncated": found.truncated,
        },
        "antivirus": antivirus_scan(inp.path) if antivirus else {"engine": "ClamAV", "available": False},
    }
    report["risk"], report["reasons"] = assess(report)
    return report


class ScanParams(Params):
    antivirus: bool = Field(
        True,
        tr="Virüs taraması (ClamAV)",
        en="Virus scan (ClamAV)",
        help_tr="ClamAV yüklüyse dosya ayrıca taranır.",
        help_en="When ClamAV is installed the file is also scanned with it.",
    )


@register
class SecurityScan(Operation):
    name = "security_scan"
    category = "security"
    title_tr, title_en = "Güvenlik Taraması", "Security Scan"
    description_tr = "JavaScript, otomatik eylem, gömülü dosya, dış bağlantı ve bozuk yapı için risk raporu."
    description_en = "Risk report on JavaScript, automatic actions, embedded files, external links and damage."
    returns_data = True
    Params = ScanParams

    def run(self, ctx: Context, params: ScanParams) -> None:
        ctx.progress(0.05, "scan")
        ctx.data = scan_file(ctx.inputs[0], antivirus=params.antivirus)


# -- sanitize -------------------------------------------------------------------------
class SanitizeParams(Params):
    remove_embedded: bool = Field(True, tr="Gömülü dosyaları kaldır", en="Remove embedded files")
    remove_xfa: bool = Field(True, tr="XFA formlarını kaldır", en="Remove XFA forms")
    remove_links: bool = Field(
        False,
        tr="Dış bağlantıları kaldır",
        en="Remove external links",
        help_tr="Web bağlantıları ve form gönderme eylemleri kaldırılır; belge içi bağlantılar kalır.",
        help_en="Web links and form-submit actions are removed; links within the document stay.",
    )
    remove_metadata: bool = Field(False, tr="Meta verileri kaldır", en="Remove metadata")


def _is_removable(obj: Any, kinds: frozenset[str]) -> str:
    """Action type if ``obj`` is an action to remove, else ``""``."""
    if not isinstance(obj, Dictionary):
        return ""
    s = _name(obj.get("/S"))
    if s in kinds:
        return s
    return "JavaScript" if "/JS" in obj else ""


def _count_name_tree(node: Any, budget: int = 100_000) -> int:
    count, stack = 0, [node]
    while stack and budget > 0:
        n = stack.pop()
        budget -= 1
        if not isinstance(n, Dictionary):
            continue
        names = n.get("/Names")
        if isinstance(names, Array):
            count += len(names) // 2
        kids = n.get("/Kids")
        if isinstance(kids, Array):
            stack.extend(kids)
    return count


def sanitize(pdf: pikepdf.Pdf, params: SanitizeParams) -> Counter[str]:
    removed: Counter[str] = Counter()
    kinds = ACTIVE_ACTIONS | MEDIA_ACTIONS | (NETWORK_ACTIONS if params.remove_links else frozenset())
    drop_annots = MEDIA_ANNOTS | ({"FileAttachment"} if params.remove_embedded else set())
    root = pdf.Root
    if "/OpenAction" in root:
        oa = root.get("/OpenAction")
        # A plain "open at page N" destination is harmless; keep it.
        if not isinstance(oa, Array) and not (isinstance(oa, Dictionary) and _name(oa.get("/S")) == "GoTo"):
            del root["/OpenAction"]
            removed["open_action"] += 1
    names = root.get("/Names")
    if isinstance(names, Dictionary):
        if "/JavaScript" in names:
            removed["javascript"] += _count_name_tree(names.get("/JavaScript"))
            del names["/JavaScript"]
        if params.remove_embedded and "/EmbeddedFiles" in names:
            removed["embedded_files"] += _count_name_tree(names.get("/EmbeddedFiles"))
            del names["/EmbeddedFiles"]
    if params.remove_embedded and "/AF" in root:
        del root["/AF"]
    acro = root.get("/AcroForm")
    if params.remove_xfa and isinstance(acro, Dictionary) and "/XFA" in acro:
        del acro["/XFA"]
        removed["xfa"] += 1
        if "/NeedsRendering" in root:
            del root["/NeedsRendering"]
    if params.remove_metadata:
        if "/Info" in pdf.trailer:
            del pdf.trailer["/Info"]
            removed["metadata"] += 1
        if "/Metadata" in root:
            del root["/Metadata"]
            removed["metadata"] += 1

    walker = Walker(pdf)
    for d, _ctx in walker.dicts():
        if "/AA" in d:
            del d["/AA"]
            removed["additional_actions"] += 1
        for key in ("/A", "/Next", "/OpenAction"):
            v = d.get(key)
            kind = _is_removable(v, kinds)
            if kind:
                del d[key]
                removed[kind.lower()] += 1
            elif key == "/Next" and isinstance(v, Array):
                keep = []
                for x in v:
                    kind = _is_removable(x, kinds)
                    if kind:
                        removed[kind.lower()] += 1
                    else:
                        keep.append(x)
                if len(keep) != len(v):
                    d["/Next"] = Array(keep)
        if "/JS" in d:  # a script reached some other way
            del d["/JS"]
            removed["javascript"] += 1
        if params.remove_embedded and "/EF" in d:
            del d["/EF"]
            if "/RF" in d:
                del d["/RF"]
            removed["embedded_files"] += 1
        if params.remove_metadata and "/PieceInfo" in d:
            del d["/PieceInfo"]
        annots = d.get("/Annots")
        if isinstance(annots, Array):
            keep = []
            for annot in annots:
                sub = _name(annot.get("/Subtype")) if isinstance(annot, Dictionary) else ""
                if sub in drop_annots:
                    removed["rich_media" if sub in MEDIA_ANNOTS else "attachment_annotations"] += 1
                elif sub == "Link" and params.remove_links and _is_removable(annot.get("/A"), NETWORK_ACTIONS):
                    removed["links"] += 1
                else:
                    keep.append(annot)
            if len(keep) != len(annots):
                d["/Annots"] = Array(keep)
    if walker.truncated:
        raise UserError(
            "Belge yapısı çok büyük/karmaşık; güvenli şekilde temizlenemedi.",
            "The document structure is too large/complex to sanitise safely.",
        )
    return removed


@register
class Sanitize(Operation):
    name = "sanitize"
    category = "security"
    title_tr, title_en = "Güvenli Temizle", "Sanitize"
    description_tr = "JavaScript, otomatik eylem, program başlatma, gömülü dosya ve XFA'yı kaldırıp temiz kopya üretir."
    description_en = "Make a clean copy without JavaScript, automatic or launch actions, embedded files and XFA."
    Params = SanitizeParams

    def run(self, ctx: Context, params: SanitizeParams) -> None:
        inp = ctx.inputs[0]
        out = ctx.output(f"{inp.stem}_temiz.pdf")
        with open_pikepdf(inp) as pdf:
            ctx.progress(0.1, "scan")
            signatures = analyze(pdf).signatures
            ctx.progress(0.3, "clean")
            removed = sanitize(pdf, params)
            ctx.progress(0.7, "save")
            # qpdf writes only objects still reachable from the trailer, so
            # everything unlinked above is gone from the file.
            pdf.save(
                out,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                compress_streams=True,
                encryption=bool(pdf.is_encrypted),
            )
        ctx.progress(0.85, "verify")
        after = scan_file(InputFile(out, inp.name, inp.password), antivirus=False)
        notes: list[dict[str, str]] = []
        if signatures:
            notes.append(
                {
                    "tr": "Belgedeki dijital imzalar bu işlemle geçersiz hale gelir.",
                    "en": "The document's digital signatures are invalidated by this operation.",
                }
            )
        ctx.data = {
            "removed": dict(removed),
            "total_removed": sum(removed.values()),
            "risk_after": after["risk"],
            "reasons_after": after["reasons"],
            "notes": notes,
        }
