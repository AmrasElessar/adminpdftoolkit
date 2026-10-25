"""AcroForm fields: list, fill, flatten, create.

Values are written through PyMuPDF so field dictionaries stay standard, but
text appearances for characters outside WinAnsi (ş, ğ, ı, İ…) are drawn here:
MuPDF lays such text out below the widget box, where every viewer clips it
away. Our streams use an embedded, subset Unicode font instead.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from typing import Any, Literal

import pymupdf
from pydantic import BaseModel, ConfigDict, field_validator

from ..core.errors import UserError
from ..core.pdf import open_pdf, save_pdf, unicode_font_path
from .base import Context, Field, Operation, Params, register

TYPE_NAMES = {
    pymupdf.PDF_WIDGET_TYPE_BUTTON: "button",
    pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    pymupdf.PDF_WIDGET_TYPE_COMBOBOX: "combo",
    pymupdf.PDF_WIDGET_TYPE_LISTBOX: "list",
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
    pymupdf.PDF_WIDGET_TYPE_SIGNATURE: "signature",
    pymupdf.PDF_WIDGET_TYPE_TEXT: "text",
}
TYPE_CODES = {v: k for k, v in TYPE_NAMES.items()}

FF_READONLY = 1
FF_REQUIRED = 1 << 1
FF_MULTILINE = 1 << 12
FF_NO_TOGGLE_OFF = 1 << 14
FF_RADIO = 1 << 15
FF_EDIT = 1 << 18
FF_MULTISELECT = 1 << 21

MAX_WIDGETS = 20_000
_TRUE = {"true", "yes", "on", "1", "evet", "x"}
_FALSE = {"false", "no", "off", "0", "hayır", "hayir", ""}

Widget = Any  # pymupdf.Widget — PyMuPDF ships no types


# -- reading -------------------------------------------------------------------
class FormIndex:
    """Widgets grouped by fully-qualified field name, in document order.

    Pages are held here because a PyMuPDF widget becomes unusable once its
    page object is garbage-collected.
    """

    def __init__(self, doc: pymupdf.Document) -> None:
        self.doc = doc
        self.pages: list[Any] = []
        self.fields: dict[str, list[tuple[Any, Widget]]] = {}
        count = 0
        for page in doc:
            self.pages.append(page)
            for w in page.widgets():
                count += 1
                if count > MAX_WIDGETS:
                    raise UserError("PDF'te çok fazla form alanı var.", "The PDF has too many form fields.")
                self.fields.setdefault(w.field_name or "", []).append((page, w))


def has_xfa(doc: pymupdf.Document) -> bool:
    cat = doc.pdf_catalog()
    return bool(cat) and doc.xref_get_key(cat, "AcroForm/XFA")[0] != "null"


def pdf_rect(page: Any, rect: Any) -> list[float]:
    """PyMuPDF's top-left, cropbox-relative space → PDF user space."""
    r = (pymupdf.Rect(rect) * ~page.transformation_matrix).normalize()
    return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]


def within(area: Any, rect: Any, tolerance: float = 0.5) -> bool:
    """``rect`` lies inside ``area``, forgiving rounding from coordinate maps."""
    a = pymupdf.Rect(area)
    return bool(pymupdf.Rect(a.x0 - tolerance, a.y0 - tolerance, a.x1 + tolerance, a.y1 + tolerance).contains(rect))


def options_of(w: Widget) -> list[str]:
    """Export values of a choice field (``/Opt`` entries may be pairs)."""
    out: list[str] = []
    for o in w.choice_values or []:
        out.append(str(o[0]) if isinstance(o, list | tuple) else str(o))
    return out


def _key(doc: pymupdf.Document, xref: int, key: str) -> tuple[str, str]:
    t, v = doc.xref_get_key(xref, key)
    return str(t), str(v)


def _field_xref(doc: pymupdf.Document, w: Widget) -> int:
    """The object holding /V: the widget itself, or its parent for kids."""
    if _key(doc, w.xref, "T")[0] == "null":
        t, v = _key(doc, w.xref, "Parent")
        if t == "xref":
            return int(v.split()[0])
    return int(w.xref)


def on_state(w: Widget) -> str:
    """The widget's on-state name, ``#xx`` escapes decoded (UTF-8 names)."""
    raw = re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), str(w.on_state() or "Yes"))
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def _is_on(doc: pymupdf.Document, w: Widget) -> bool:
    t, v = _key(doc, w.xref, "AS")
    return t == "name" and v not in ("/Off", "/")


def field_value(doc: pymupdf.Document, kind: str, widgets: list[tuple[Any, Widget]]) -> Any:
    w = widgets[0][1]
    if kind == "checkbox":
        return any(_is_on(doc, x) for _, x in widgets)
    if kind == "radio":
        return next((on_state(x) for _, x in widgets if _is_on(doc, x)), None)
    if kind == "signature":
        return None
    if kind == "list":
        if _key(doc, _field_xref(doc, w), "V")[0] == "array":
            return [str(s) for s in _parse_string_array(doc, _field_xref(doc, w))]
        return [w.field_value] if w.field_value else []
    return w.field_value if w.field_value is not None else ""


_PDF_STRING = re.compile(rb"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>", re.S)
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}


def _unescape(m: re.Match[bytes]) -> bytes:
    tok = m.group(1)
    if tok[:1].isdigit():
        return bytes([int(tok, 8) & 0xFF])
    return _ESCAPES.get(tok, b"" if tok in b"\r\n" else tok)


def _decode_pdf_string(raw: bytes) -> str:
    if raw.startswith(b"<"):
        data = bytes.fromhex(re.sub(rb"\s", b"", raw[1:-1]).decode())
    else:
        data = re.sub(rb"\\([0-7]{1,3}|.)", _unescape, raw[1:-1], flags=re.S)
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be", "replace")
    return data.decode("latin-1")


def _parse_string_array(doc: pymupdf.Document, xref: int) -> list[str]:
    """Decode a ``/V`` array of strings (multi-select list boxes)."""
    src = _key(doc, xref, "V")[1].encode("latin-1", "replace")
    return [_decode_pdf_string(m.group(0)) for m in _PDF_STRING.finditer(src)][:1000]


def describe_fields(doc: pymupdf.Document) -> list[dict[str, Any]]:
    index = FormIndex(doc)
    out: list[dict[str, Any]] = []
    for name, widgets in index.fields.items():
        page, w = widgets[0]
        kind = TYPE_NAMES.get(w.field_type, "unknown")
        flags = int(w.field_flags or 0)
        entry: dict[str, Any] = {
            "name": name,
            "type": kind,
            "value": field_value(doc, kind, widgets),
            "options": [],
            "page": page.number + 1,
            "rect": pdf_rect(page, w.rect),
            "required": bool(flags & FF_REQUIRED),
            "readonly": bool(flags & FF_READONLY),
            "multiline": kind == "text" and bool(flags & FF_MULTILINE),
            "max_length": (w.text_maxlen or None) if kind == "text" else None,
            "tooltip": w.field_label or "",
        }
        if kind in ("combo", "list"):
            entry["options"] = options_of(w)
            entry["multiselect"] = kind == "list" and bool(flags & FF_MULTISELECT)
        elif kind in ("checkbox", "radio"):
            entry["options"] = list(dict.fromkeys(on_state(x) for _, x in widgets))
        elif kind == "signature":
            entry["signed"] = _key(doc, _field_xref(doc, w), "V")[0] != "null"
        if len(widgets) > 1:
            entry["widgets"] = [
                {
                    "page": p.number + 1,
                    "rect": pdf_rect(p, x.rect),
                    "on_state": on_state(x) if kind in ("checkbox", "radio") else None,
                }
                for p, x in widgets
            ]
        out.append(entry)
    return out


# -- appearances ---------------------------------------------------------------
def needs_unicode(text: str) -> bool:
    try:
        text.encode("cp1252")
    except UnicodeEncodeError:
        return True
    return False


def _subset_font(path: str, chars: str) -> bytes:
    """Subset keeping glyph ids, so ``Font.has_glyph`` ids stay valid CIDs."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    opts = subset.Options()
    opts.retain_gids = True
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    opts.drop_tables = [*opts.drop_tables, "FFTM"]  # FontForge timestamp; fontTools warns otherwise
    font = TTFont(path)
    sub = subset.Subsetter(opts)
    sub.populate(text=chars + "?")
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _color(values: Iterable[float] | None, *, stroke: bool) -> str:
    c = [float(v) for v in values or []]
    ops = {1: ("g", "G"), 3: ("rg", "RG"), 4: ("k", "K")}.get(len(c))
    return " ".join(f"{x:.3f}" for x in c) + " " + ops[stroke] if ops else ""


class UnicodeAppearance:
    """Writes text appearance streams with an embedded Unicode font.

    The font is subset to the characters actually used and embedded once per
    document; every stream shares it.
    """

    NAME = "AptUni"

    def __init__(self, doc: pymupdf.Document, texts: Iterable[str]) -> None:
        self.doc = doc
        self.font: Any = None
        self.xref = 0
        chars = "".join(sorted({c for t in texts for c in t if c >= " "}))
        path = unicode_font_path()
        if not chars or not path:
            return
        data = _subset_font(path, chars)
        self.font = pymupdf.Font(fontbuffer=data)
        self.xref = doc[0].insert_font(fontname=self.NAME, fontbuffer=data)

    @property
    def available(self) -> bool:
        return self.font is not None

    def _hex(self, text: str) -> str:
        return "".join(f"{self.font.has_glyph(ord(c)) or 0:04x}" for c in text)

    def _width(self, text: str, size: float) -> float:
        return float(self.font.text_length(text, fontsize=size))

    def _wrap(self, text: str, size: float, width: float) -> list[str]:
        lines: list[str] = []
        for para in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = ""
            for word in para.split(" "):
                cand = f"{line} {word}" if line else word
                if self._width(cand, size) <= width or not line:
                    line = cand
                else:
                    lines.append(line)
                    line = word
                while self._width(line, size) > width and len(line) > 1:
                    cut = len(line) - 1
                    while cut > 1 and self._width(line[:cut], size) > width:
                        cut -= 1
                    lines.append(line[:cut])
                    line = line[cut:]
            lines.append(line)
            if len(lines) > 500:
                break
        return lines[:500]

    def _stream(self, w: Widget) -> tuple[int, float, float, float, float]:
        """The widget's normal-appearance stream xref and its BBox."""
        doc = self.doc
        t, v = _key(doc, w.xref, "AP/N")
        if t == "xref":
            apx = int(v.split()[0])
        else:
            r = w.rect
            apx = doc.get_new_xref()
            doc.update_object(apx, f"<</Type/XObject/Subtype/Form/BBox[0 0 {r.width:.2f} {r.height:.2f}]>>")
            doc.update_stream(apx, b" ", new=True)
            doc.xref_set_key(w.xref, "AP", f"<</N {apx} 0 R>>")
        t, v = _key(doc, apx, "BBox")
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", v)] if t == "array" else []
        if len(nums) != 4:
            r = w.rect
            nums = [0.0, 0.0, float(r.width), float(r.height)]
        x0, y0, x1, y1 = nums
        return apx, min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)

    def _frame(self, w: Widget, x0: float, y0: float, bw: float, bh: float) -> list[str]:
        ops: list[str] = []
        fill = _color(w.fill_color, stroke=False)
        if fill:
            ops.append(f"{fill} {x0:.2f} {y0:.2f} {bw:.2f} {bh:.2f} re f")
        border = _color(w.border_color, stroke=True)
        width = float(w.border_width or 0)
        if border and width > 0:
            ops.append(f"{border} {width:.2f} w {x0 + width / 2:.2f} {y0 + width / 2:.2f} ")
            ops[-1] += f"{bw - width:.2f} {bh - width:.2f} re S"
        return ops

    def _write(self, apx: int, ops: list[str]) -> None:
        content = "/Tx BMC\nq\n" + "\n".join(ops) + "\nQ\nEMC\n"
        self.doc.update_stream(apx, content.encode("latin-1"))
        self.doc.xref_set_key(apx, "Resources", f"<</Font<</{self.NAME} {self.xref} 0 R>>>>")

    def text(self, w: Widget, value: str, *, multiline: bool) -> None:
        apx, x0, y0, bw, bh = self._stream(w)
        pad = 2 + float(w.border_width or 0)
        avail_w, avail_h = max(bw - 2 * pad, 1), max(bh - 2 * pad, 1)
        asc, desc = float(self.font.ascender), float(self.font.descender)
        size = float(w.text_fontsize or 0)
        if multiline:
            size = size or 10.0
            lines = self._wrap(value, size, avail_w)
            while not w.text_fontsize and size > 4 and len(lines) * size * 1.15 > avail_h:
                size -= 0.5
                lines = self._wrap(value, size, avail_w)
        else:
            lines = [value.replace("\r", " ").replace("\n", " ")]
            if not size:
                size = max(4.0, min(12.0, avail_h / (asc - desc)))
                width = self._width(lines[0], size)
                if width > avail_w:
                    size = max(4.0, size * avail_w / width)
        q = _key(self.doc, w.xref, "Q")[1]
        align = int(q) if q.isdigit() else 0
        ops = self._frame(w, x0, y0, bw, bh)
        ops.append(f"{x0 + 1:.2f} {y0 + 1:.2f} {bw - 2:.2f} {bh - 2:.2f} re W n")
        ops.append(f"BT {_color(w.text_color, stroke=False) or '0 g'} /{self.NAME} {size:.2f} Tf")
        lead = size * 1.15
        # Multi-line text starts at the top; a single line is centred.
        y = y0 + bh - pad - asc * size if multiline else y0 + (bh - (asc - desc) * size) / 2 - desc * size
        for line in lines:
            lw = self._width(line, size)
            x = x0 + pad + {1: (avail_w - lw) / 2, 2: avail_w - lw}.get(align, 0)
            ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm <{self._hex(line)}> Tj")
            y -= lead
        ops.append("ET")
        self._write(apx, ops)

    def listbox(self, w: Widget, options: list[str], selected: list[str]) -> None:
        apx, x0, y0, bw, bh = self._stream(w)
        size = float(w.text_fontsize or 0) or 10.0
        asc, desc = float(self.font.ascender), float(self.font.descender)
        lead = (asc - desc) * size * 1.1
        ops = self._frame(w, x0, y0, bw, bh)
        ops.append(f"{x0 + 1:.2f} {y0 + 1:.2f} {bw - 2:.2f} {bh - 2:.2f} re W n")
        top = y0 + bh - 1
        for i, opt in enumerate(options):
            if top - (i + 1) * lead < y0 - lead:
                break
            if opt in selected:
                ops.append(f"0.600 0.757 0.855 rg {x0 + 1:.2f} {top - (i + 1) * lead:.2f} {bw - 2:.2f} {lead:.2f} re f")
        ops.append(f"BT {_color(w.text_color, stroke=False) or '0 g'} /{self.NAME} {size:.2f} Tf")
        for i, opt in enumerate(options):
            y = top - (i + 1) * lead - desc * size * 1.05
            if y < y0 - lead:
                break
            ops.append(f"1 0 0 1 {x0 + 3:.2f} {y:.2f} Tm <{self._hex(opt)}> Tj")
        ops.append("ET")
        self._write(apx, ops)


# -- writing -------------------------------------------------------------------
Value = str | bool | list[str]


def _as_bool(value: Value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().casefold()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
    return None


def _need_str(name: str, value: Value) -> str:
    if not isinstance(value, str):
        raise UserError(f"'{name}' alanı metin bekliyor.", f"Field '{name}' expects text.")
    return value


def _set_v_array(doc: pymupdf.Document, xref: int, values: list[str], options: list[str]) -> None:
    doc.xref_set_key(xref, "V", "[" + "".join(pymupdf.get_pdf_str(v) for v in values) + "]")
    idx = sorted(options.index(v) for v in values if v in options)
    doc.xref_set_key(xref, "I", "[" + " ".join(map(str, idx)) + "]")


def unicode_texts(doc: pymupdf.Document, index: FormIndex, values: dict[str, Value]) -> list[str]:
    """Every string that will need a Unicode appearance (to size the font subset)."""
    out: list[str] = []
    for name, value in values.items():
        widgets = index.fields.get(name)
        if not widgets:
            continue
        w = widgets[0][1]
        kind = TYPE_NAMES.get(w.field_type, "")
        if kind in ("text", "combo") and isinstance(value, str) and needs_unicode(value):
            out.append(value)
        elif kind == "list":
            opts = options_of(w)
            if any(needs_unicode(o) for o in opts) or (isinstance(value, list) and len(value) > 1):
                out.extend(opts)
    return out


def set_field(
    doc: pymupdf.Document, name: str, widgets: list[tuple[Any, Widget]], value: Value, uni: UnicodeAppearance
) -> None:
    """Set one field's value on every widget and regenerate appearances."""
    first = widgets[0][1]
    kind = TYPE_NAMES.get(first.field_type, "unknown")
    flags = int(first.field_flags or 0)
    if kind in ("signature", "button", "unknown"):
        raise UserError(
            f"'{name}' alanı doldurulamaz (imza veya düğme).",
            f"Field '{name}' cannot be filled (signature or button).",
        )
    if kind == "text":
        text = _need_str(name, value)
        if first.text_maxlen and len(text) > first.text_maxlen:
            raise UserError(
                f"'{name}' alanı en fazla {first.text_maxlen} karakter alır.",
                f"Field '{name}' accepts at most {first.text_maxlen} characters.",
            )
        for _, w in widgets:
            w.field_value = text
            w.update()
            if uni.available and needs_unicode(text):
                uni.text(w, text, multiline=bool(flags & FF_MULTILINE))
    elif kind in ("checkbox", "radio"):
        _set_toggle(doc, name, widgets, value)
    elif kind == "combo":
        text = _need_str(name, value)
        opts = options_of(first)
        if text and text not in opts and not flags & FF_EDIT:
            raise _bad_option(name, text, opts)
        display = text
        for o in first.choice_values or []:
            if isinstance(o, list | tuple) and len(o) > 1 and str(o[0]) == text:
                display = str(o[1])
        for _, w in widgets:
            w.field_value = text
            w.update()
            if uni.available and needs_unicode(display):
                uni.text(w, display, multiline=False)
    elif kind == "list":
        chosen = [value] if isinstance(value, str) else value if isinstance(value, list) else None
        if chosen is None:
            raise UserError(f"'{name}' alanı seçenek listesi bekliyor.", f"Field '{name}' expects option(s).")
        chosen = [c for c in chosen if c]
        opts = options_of(first)
        for c in chosen:
            if c not in opts:
                raise _bad_option(name, c, opts)
        if len(chosen) > 1 and not flags & FF_MULTISELECT:
            raise UserError(
                f"'{name}' listesinde yalnızca bir seçim yapılabilir.",
                f"List '{name}' allows only one selection.",
            )
        for _, w in widgets:
            w.field_value = chosen[0] if chosen else ""
            w.update()
        if len(chosen) > 1:
            _set_v_array(doc, _field_xref(doc, first), chosen, opts)
        if uni.available and (len(chosen) > 1 or any(needs_unicode(o) for o in opts)):
            for _, w in widgets:
                uni.listbox(w, opts, chosen)


def _bad_option(name: str, value: str, opts: list[str]) -> UserError:
    shown = ", ".join(opts[:10]) + (" …" if len(opts) > 10 else "")
    return UserError(
        f"'{name}' alanı için geçersiz seçenek: {value!r}. Seçenekler: {shown}",
        f"Invalid option for field '{name}': {value!r}. Options: {shown}",
    )


def _set_toggle(doc: pymupdf.Document, name: str, widgets: list[tuple[Any, Widget]], value: Value) -> None:
    """Checkbox / radio: accept true/false or an on-state name."""
    states = [on_state(w) for _, w in widgets]
    target: str | None
    if isinstance(value, str) and value in states:
        target = value
    elif isinstance(value, str) and value.casefold() in {s.casefold() for s in states}:
        target = next(s for s in states if s.casefold() == value.casefold())
    else:
        on = _as_bool(value)
        if on is None or (on and len(set(states)) > 1):
            shown = ", ".join(dict.fromkeys(states))
            raise UserError(
                f"'{name}' alanı için şunlardan birini girin: {shown} (veya false).",
                f"For field '{name}' enter one of: {shown} (or false).",
            )
        target = states[0] if on else None
    for _, w in widgets:
        w.field_value = False
        w.update()
    for (_, w), state in zip(widgets, states, strict=True):
        if state == target:
            w.field_value = True
            w.update()
    parent = _field_xref(doc, widgets[0][1])
    if parent != widgets[0][1].xref:
        on_name = next((_key(doc, w.xref, "AS")[1] for _, w in widgets if _is_on(doc, w)), "/Off")
        doc.xref_set_key(parent, "V", on_name)


def fill(doc: pymupdf.Document, values: dict[str, Value]) -> FormIndex:
    index = FormIndex(doc)
    unknown = [n for n in values if n not in index.fields]
    if unknown:
        shown = ", ".join(unknown[:10]) + (f" (+{len(unknown) - 10})" if len(unknown) > 10 else "")
        raise UserError(f"Bilinmeyen alan adları: {shown}", f"Unknown field names: {shown}")
    uni = UnicodeAppearance(doc, unicode_texts(doc, index, values))
    for name, value in values.items():
        set_field(doc, name, index.fields[name], value, uni)
    return index


def flatten(doc: pymupdf.Document, *, annotations: bool) -> None:
    """Burn widgets (and optionally other annotations) into page content.

    Fields without an appearance stream (``NeedAppearances`` files) get one
    first, or their values would vanish.
    """
    index = FormIndex(doc)
    missing: dict[str, Value] = {}
    for name, widgets in index.fields.items():
        w = widgets[0][1]
        kind = TYPE_NAMES.get(w.field_type, "")
        if kind in ("text", "combo") and any(_key(doc, x.xref, "AP/N")[0] == "null" for _, x in widgets):
            missing[name] = str(w.field_value or "")
    if missing:
        uni = UnicodeAppearance(doc, unicode_texts(doc, index, missing))
        for name, value in missing.items():
            set_field(doc, name, index.fields[name], value, uni)
    doc.bake(annots=annotations, widgets=True)


# -- operations ----------------------------------------------------------------
@register
class FormFields(Operation):
    name = "form_fields"
    category = "forms"
    title_tr, title_en = "Form Alanlarını Listele", "List Form Fields"
    description_tr = "Formdaki alanları türü, değeri, seçenekleri ve konumuyla listeler."
    description_en = "List form fields with their type, value, options and position."
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            ctx.data = {"fields": describe_fields(doc), "has_xfa": has_xfa(doc)}


class FillParams(Params):
    values: dict[str, Value] = Field(
        ...,
        tr="Değerler (JSON)",
        en="Values (JSON)",
        help_tr='Alan adı → değer. Örn: {"ad": "Ayşe", "onay": true, "il": "İzmir"}',
        help_en='Field name → value. E.g. {"name": "Ayşe", "agree": true, "city": "İzmir"}',
        ui={"widget": "json"},
    )
    flatten: bool = Field(
        False,
        tr="Doldurduktan sonra düzleştir",
        en="Flatten after filling",
        help_tr="Alanlar sayfaya gömülür, artık düzenlenemez.",
        help_en="Fields are burned into the page and can no longer be edited.",
    )

    @field_validator("values")
    @classmethod
    def _bounded(cls, v: dict[str, Value]) -> dict[str, Value]:
        if not v:
            raise ValueError("at least one value is required")
        if len(v) > 5000:
            raise ValueError("at most 5000 fields")
        for k, val in v.items():
            if len(k) > 1000:
                raise ValueError("field name too long")
            items = val if isinstance(val, list) else [val]
            if len(items) > 1000:
                raise ValueError(f"{k}: too many items")
            if any(isinstance(s, str) and len(s) > 10_000 for s in items):
                raise ValueError(f"{k}: value longer than 10000 characters")
        return v


@register
class FormFill(Operation):
    name = "form_fill"
    category = "forms"
    title_tr, title_en = "Form Doldur", "Fill Form"
    description_tr = "Form alanlarına değer yazar; isterseniz sonra düzleştirir."
    description_en = "Write values into form fields, optionally flattening afterwards."
    Params = FillParams

    def run(self, ctx: Context, params: FillParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            if has_xfa(doc):
                # Viewers that understand XFA would show the stale XFA data
                # and ignore the AcroForm values just written.
                doc.xref_set_key(doc.pdf_catalog(), "AcroForm/XFA", "null")
            fill(doc, params.values)
            ctx.progress(0.8, "")
            if params.flatten:
                doc.bake(annots=False, widgets=True)
            save_pdf(doc, ctx.output(f"{inp.stem}_doldurulmus.pdf"))


class FlattenParams(Params):
    annotations: bool = Field(
        False,
        tr="Yorum ve işaretlemeleri de düzleştir",
        en="Also flatten comments and markup",
    )


@register
class FormFlatten(Operation):
    name = "form_flatten"
    category = "forms"
    title_tr, title_en = "Formu Düzleştir", "Flatten Form"
    description_tr = "Form alanlarını sayfa içeriğine gömer; değerler görünür kalır ama düzenlenemez."
    description_en = "Burn form fields into the page; values stay visible but can no longer be edited."
    Params = FlattenParams

    def run(self, ctx: Context, params: FlattenParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            has_widgets = any(True for p in doc for _ in p.widgets())
            has_annots = params.annotations and any(True for p in doc for _ in p.annots())
            if not has_widgets and not has_annots:
                raise UserError("Bu PDF'te düzleştirilecek form alanı yok.", "This PDF has no form fields to flatten.")
            flatten(doc, annotations=params.annotations)
            save_pdf(doc, ctx.output(f"{inp.stem}_duzlestirilmis.pdf"))


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., tr="Sayfa", en="Page", ge=1, le=100_000)
    type: Literal["text", "checkbox", "radio", "combo", "list", "signature"] = Field(..., tr="Tür", en="Type")
    name: str = Field(..., tr="Ad", en="Name", min_length=1, max_length=128, pattern=r"^[^.\x00-\x1f]+$")
    rect: list[float] = Field(
        ...,
        tr="Konum [x0, y0, x1, y1]",
        en="Position [x0, y0, x1, y1]",
        help_tr="PDF kullanıcı biriminde, sol alt köşe başlangıç.",
        help_en="PDF user space, origin bottom-left.",
        min_length=4,
        max_length=4,
    )
    options: list[str] = Field([], tr="Seçenekler", en="Options", max_length=500)
    default: Value = Field("", tr="Varsayılan değer", en="Default value")
    required: bool = Field(False, tr="Zorunlu", en="Required")
    readonly: bool = Field(False, tr="Salt okunur", en="Read-only")
    multiline: bool = Field(False, tr="Çok satırlı", en="Multi-line")
    font_size: float = Field(0, tr="Yazı boyutu (0 = otomatik)", en="Font size (0 = auto)", ge=0, le=144)
    tooltip: str = Field("", tr="İpucu", en="Tooltip", max_length=500)

    @field_validator("options")
    @classmethod
    def _opts(cls, v: list[str]) -> list[str]:
        if any(not o or len(o) > 1000 for o in v):
            raise ValueError("options must be 1–1000 characters")
        if len(set(v)) != len(v):
            raise ValueError("options must be unique")
        return v

    @field_validator("default")
    @classmethod
    def _default(cls, v: Value) -> Value:
        items = v if isinstance(v, list) else [v]
        if len(items) > 500 or any(isinstance(s, str) and len(s) > 10_000 for s in items):
            raise ValueError("default value too long")
        return v


class CreateParams(Params):
    fields: list[FieldSpec] = Field(..., tr="Alanlar", en="Fields", min_length=1, max_length=2000)


_BORDER = (0.55, 0.55, 0.55)  # created fields get a visible frame; PyMuPDF's default has none


def _pdf_name(value: str) -> str:
    """Encode text as a PDF name (``#xx`` for delimiters and non-ASCII)."""
    out = []
    for b in value.encode("utf-8"):
        out.append(chr(b) if 0x21 <= b <= 0x7E and chr(b) not in "()<>[]{}/%#" else f"#{b:02X}")
    return "/" + "".join(out)


def _group_radios(doc: pymupdf.Document, name: str, kids: list[int], options: list[str], spec: FieldSpec) -> None:
    """Turn same-named radio widgets into one field with /Kids.

    PyMuPDF creates each radio button as its own field, which viewers do not
    treat as a group; the standard shape is a parent holding /V and the
    flags, and kids carrying only the widget and their on-state appearance.
    """
    flags = FF_RADIO | FF_NO_TOGGLE_OFF
    flags |= FF_REQUIRED if spec.required else 0
    flags |= FF_READONLY if spec.readonly else 0
    tip = f"/TU{pymupdf.get_pdf_str(spec.tooltip)}" if spec.tooltip else ""
    parent = doc.get_new_xref()
    refs = " ".join(f"{k} 0 R" for k in kids)
    doc.update_object(parent, f"<</FT/Btn/Ff {flags}/T{pymupdf.get_pdf_str(name)}{tip}/V/Off/Kids[{refs}]>>")
    for k, opt in zip(kids, options, strict=True):
        for key in ("T", "FT", "Ff", "V", "TU"):
            doc.xref_set_key(k, key, "null")
        doc.xref_set_key(k, "Parent", f"{parent} 0 R")
        doc.xref_set_key(k, "AS", "/Off")
        for ap in ("AP/N", "AP/D"):
            t, v = _key(doc, k, ap)
            if t == "dict":
                doc.xref_set_key(k, ap, v.replace("/Yes", _pdf_name(opt)))
    cat = doc.pdf_catalog()
    t, v = _key(doc, cat, "AcroForm/Fields")
    if t == "array":
        kept = [r for r in re.findall(r"(\d+) 0 R", v) if int(r) not in kids]
        doc.xref_set_key(cat, "AcroForm/Fields", "[" + " ".join(f"{r} 0 R" for r in [*kept, str(parent)]) + "]")


@register
class FormCreate(Operation):
    name = "form_create"
    category = "forms"
    title_tr, title_en = "Form Alanı Oluştur", "Create Form Fields"
    description_tr = "Sayfalara metin, onay kutusu, seçenek, liste ve imza alanları ekler."
    description_en = "Add text, checkbox, radio, choice, list and signature fields to pages."
    Params = CreateParams
    hidden = True

    def run(self, ctx: Context, params: CreateParams) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            existing = set(FormIndex(doc).fields)
            seen: set[str] = set()
            for spec in params.fields:
                if spec.name in seen or spec.name in existing:
                    raise UserError(
                        f"Alan adı zaten kullanılıyor: {spec.name}", f"Field name already in use: {spec.name}"
                    )
                seen.add(spec.name)
                if spec.page > doc.page_count:
                    raise UserError(
                        f"'{spec.name}': sayfa {spec.page} yok (1–{doc.page_count}).",
                        f"'{spec.name}': page {spec.page} does not exist (1–{doc.page_count}).",
                    )
                if spec.type in ("combo", "list", "radio") and not spec.options:
                    raise UserError(f"'{spec.name}' için seçenek girin.", f"Enter options for '{spec.name}'.")
            defaults: dict[str, Value] = {}
            for k, spec in enumerate(params.fields):
                self._create(doc, spec)
                if spec.default not in ("", [], False):
                    defaults[spec.name] = spec.default
                ctx.progress((k + 1) / len(params.fields) * 0.8, "")
            if defaults:
                fill(doc, defaults)
            save_pdf(doc, ctx.output(f"{inp.stem}_formlu.pdf"))

    @staticmethod
    def _create(doc: pymupdf.Document, spec: FieldSpec) -> None:
        page = doc[spec.page - 1]
        rect = (pymupdf.Rect(spec.rect) * page.transformation_matrix).normalize()
        area = pymupdf.Rect(0, 0, page.cropbox.width, page.cropbox.height)
        if rect.width < 4 or rect.height < 4 or not within(area, rect):
            raise UserError(
                f"'{spec.name}' alanının konumu sayfanın dışında veya çok küçük.",
                f"Field '{spec.name}' is outside the page or too small.",
            )
        flags = (FF_REQUIRED if spec.required else 0) | (FF_READONLY if spec.readonly else 0)
        if spec.type == "radio":
            kids: list[int] = []
            n = len(spec.options)
            horizontal = rect.width >= rect.height
            cell = (rect.width if horizontal else rect.height) / n
            side = min(cell, rect.height if horizontal else rect.width)
            for i in range(n):
                if horizontal:
                    x, y = rect.x0 + i * cell + (cell - side) / 2, rect.y0 + (rect.height - side) / 2
                else:
                    x, y = rect.x0 + (rect.width - side) / 2, rect.y0 + i * cell + (cell - side) / 2
                w = pymupdf.Widget()
                w.field_type = pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON
                w.field_name = spec.name
                w.rect = pymupdf.Rect(x, y, x + side, y + side)
                w.field_value = False
                w.border_color, w.border_width = _BORDER, 1
                kids.append(page.add_widget(w).xref)
            _group_radios(doc, spec.name, kids, spec.options, spec)
            return
        w = pymupdf.Widget()
        w.field_type = TYPE_CODES[spec.type]
        w.field_name = spec.name
        w.rect = rect
        if spec.tooltip:
            w.field_label = spec.tooltip
        if spec.type == "text":
            flags |= FF_MULTILINE if spec.multiline else 0
            w.text_fontsize = spec.font_size
            w.field_value = ""
        elif spec.type in ("combo", "list"):
            w.choice_values = spec.options
            w.text_fontsize = spec.font_size
            if spec.type == "list" and isinstance(spec.default, list):
                flags |= FF_MULTISELECT
            w.field_value = ""
        elif spec.type == "checkbox":
            w.field_value = False
        w.field_flags = flags
        if spec.type != "signature":
            w.border_color, w.border_width = _BORDER, 1
        page.add_widget(w)
