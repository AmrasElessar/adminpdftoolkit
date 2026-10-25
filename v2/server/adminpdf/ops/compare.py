"""Compare two PDFs: page alignment, word-level text diff, visual check."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from typing import Any

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, save_pdf, unicode_font
from .base import Context, Field, Operation, Params, register

MAX_PAGES = 2000
MAX_WORDS_PER_PAGE = 20_000
MAX_SNIPPETS = 200
SNIPPET_CHARS = 200
# Pairing two pages needs at least this much word similarity.
MIN_SIMILARITY = 0.3
# Largest unmatched block aligned with the O(n·m) similarity search.
MAX_ALIGN_CELLS = 40_000

GREEN = (0.2, 0.8, 0.3)
RED = (0.9, 0.15, 0.15)


@dataclass
class PageWords:
    words: list[str]
    rects: list[pymupdf.Rect]
    digest: str


@dataclass
class Pair:
    old: int | None  # 0-based page index, None = page added
    new: int | None  # None = page removed
    inserted: list[int] = field(default_factory=list)  # word indices in new
    deleted: list[int] = field(default_factory=list)  # word indices in old
    visual: bool = False

    @property
    def changed(self) -> bool:
        return self.old is None or self.new is None or bool(self.inserted or self.deleted) or self.visual


def read_words(doc: pymupdf.Document) -> list[PageWords]:
    out: list[PageWords] = []
    for page in doc:
        items = page.get_text("words", sort=True)
        if len(items) > MAX_WORDS_PER_PAGE:
            raise UserError(
                f"Sayfa {page.number + 1} karşılaştırma için çok fazla sözcük içeriyor.",
                f"Page {page.number + 1} has too many words to compare.",
            )
        words = [str(w[4]) for w in items]
        rects = [pymupdf.Rect(w[:4]) for w in items]
        out.append(PageWords(words, rects, hashlib.sha1("\x00".join(words).encode()).hexdigest()))
    return out


def similarity(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < MIN_SIMILARITY or sm.quick_ratio() < MIN_SIMILARITY:
        return 0.0
    return sm.ratio()


def _align_block(old: list[PageWords], new: list[PageWords], i0: int, i1: int, j0: int, j1: int) -> list[Pair]:
    """Best monotone pairing of old[i0:i1] with new[j0:j1] (sum of
    similarities); unpaired pages are removals / insertions."""
    n, m = i1 - i0, j1 - j0
    if n * m > MAX_ALIGN_CELLS:
        # Too large to search: pair in order, rest added / removed.
        k = min(n, m)
        return (
            [Pair(i0 + t, j0 + t) for t in range(k)]
            + [Pair(i0 + t, None) for t in range(k, n)]
            + [Pair(None, j0 + t) for t in range(k, m)]
        )
    sim = [[similarity(old[i0 + a].words, new[j0 + b].words) for b in range(m)] for a in range(n)]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for a in range(n - 1, -1, -1):
        for b in range(m - 1, -1, -1):
            s = sim[a][b]
            take = best[a + 1][b + 1] + s if s >= MIN_SIMILARITY else -1.0
            best[a][b] = max(take, best[a + 1][b], best[a][b + 1])
    pairs: list[Pair] = []
    a = b = 0
    while a < n and b < m:
        s = sim[a][b]
        if s >= MIN_SIMILARITY and best[a][b] == best[a + 1][b + 1] + s:
            pairs.append(Pair(i0 + a, j0 + b))
            a, b = a + 1, b + 1
        elif best[a][b] == best[a + 1][b]:
            pairs.append(Pair(i0 + a, None))
            a += 1
        else:
            pairs.append(Pair(None, j0 + b))
            b += 1
    pairs += [Pair(i0 + t, None) for t in range(a, n)]
    pairs += [Pair(None, j0 + t) for t in range(b, m)]
    return pairs


def align_pages(old: list[PageWords], new: list[PageWords]) -> list[Pair]:
    """Identical pages anchor the alignment; the gaps between them are
    paired by text similarity so inserted / removed pages are detected."""
    sm = difflib.SequenceMatcher(None, [p.digest for p in old], [p.digest for p in new], autojunk=False)
    pairs: list[Pair] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs += [Pair(i1 + t, j1 + t) for t in range(i2 - i1)]
        else:
            pairs += _align_block(old, new, i1, i2, j1, j2)
    return pairs


def diff_words(pair: Pair, old: PageWords, new: PageWords, snippets: list[dict[str, Any]]) -> None:
    sm = difflib.SequenceMatcher(None, old.words, new.words, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        pair.deleted.extend(range(i1, i2))
        pair.inserted.extend(range(j1, j2))
        if len(snippets) < MAX_SNIPPETS:
            snippets.append(
                {
                    "old_page": (pair.old or 0) + 1,
                    "new_page": (pair.new or 0) + 1,
                    "type": tag,
                    "old": " ".join(old.words[i1:i2])[:SNIPPET_CHARS],
                    "new": " ".join(new.words[j1:j2])[:SNIPPET_CHARS],
                }
            )


def pixels_differ(a: pymupdf.Page, b: pymupdf.Page, dpi: int = 30) -> bool:
    from PIL import Image, ImageChops

    pa = a.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False, annots=False)
    pb = b.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False, annots=False)
    if (pa.width, pa.height) != (pb.width, pb.height):
        return True
    ia = Image.frombytes("L", (pa.width, pa.height), pa.samples)
    ib = Image.frombytes("L", (pb.width, pb.height), pb.samples)
    hist = ImageChops.difference(ia, ib).histogram()
    changed: int = sum(hist[40:])
    return changed > max(4, int(pa.width * pa.height) // 2000)


def _mark(
    doc: pymupdf.Document, pno: int, words: PageWords, idx: list[int], color: tuple[float, ...], strike: bool
) -> None:
    page = doc[pno]
    for i in idx:
        r = words.rects[i]
        if r.is_empty:
            continue
        annot = page.add_strikeout_annot(r) if strike else page.add_highlight_annot(r)
        annot.set_colors(stroke=color)
        annot.update()


SHEET_W, SHEET_H, MARGIN, HEADER = 842.0, 595.0, 24.0, 28.0


def _text(page: pymupdf.Page, rect: pymupdf.Rect, text: str, size: float, color: tuple[float, ...] = (0, 0, 0)) -> None:
    tw = pymupdf.TextWriter(page.rect, color=color)
    tw.fill_textbox(rect, text, font=unicode_font(), fontsize=size)
    tw.write_text(page)


def _summary_page(report: pymupdf.Document, lines: list[str]) -> None:
    page = report.new_page(width=595, height=842)
    _text(page, pymupdf.Rect(48, 48, 547, 90), "Karşılaştırma Raporu / Comparison Report", 18)
    _text(page, pymupdf.Rect(48, 100, 547, 800), "\n".join(lines), 11)


class CompareParams(Params):
    visual: bool = Field(
        False,
        tr="Görsel farkları da işaretle",
        en="Also flag visual differences",
        help_tr="Metni aynı olan sayfaları düşük çözünürlükte görüntü olarak karşılaştırır.",
        help_en="Compares pages with identical text as low-resolution images.",
    )
    only_changed: bool = Field(True, tr="Raporda yalnızca değişen sayfalar", en="Only changed pages in the report")


@register
class Compare(Operation):
    name = "compare"
    category = "compare"
    title_tr, title_en = "PDF Karşılaştır", "Compare PDFs"
    description_tr = "İki sürüm arasındaki eklenen, silinen ve değişen sözcükleri ve sayfaları yan yana gösterir."
    description_en = "Show words and pages added, removed or changed between two versions, side by side."
    min_inputs, max_inputs = 2, 2
    Params = CompareParams

    def run(self, ctx: Context, params: CompareParams) -> None:
        old_in, new_in = ctx.inputs
        with open_pdf(old_in.path, old_in.password) as old_doc, open_pdf(new_in.path, new_in.password) as new_doc:
            if old_doc.page_count > MAX_PAGES or new_doc.page_count > MAX_PAGES:
                raise UserError(
                    f"Karşılaştırma en fazla {MAX_PAGES} sayfalık belgeler için yapılabilir.",
                    f"Comparison supports documents of up to {MAX_PAGES} pages.",
                )
            old_words, new_words = read_words(old_doc), read_words(new_doc)
            ctx.progress(0.15, "")
            pairs = align_pages(old_words, new_words)
            snippets: list[dict[str, Any]] = []
            for k, pair in enumerate(pairs):
                if pair.old is not None and pair.new is not None:
                    o, n = old_words[pair.old], new_words[pair.new]
                    if o.digest != n.digest:
                        diff_words(pair, o, n, snippets)
                    elif params.visual:
                        pair.visual = pixels_differ(old_doc[pair.old], new_doc[pair.new])
                ctx.progress(0.15 + 0.35 * (k + 1) / len(pairs), "")

            summary = {
                "old_pages": old_doc.page_count,
                "new_pages": new_doc.page_count,
                "pages_added": sum(1 for p in pairs if p.old is None),
                "pages_removed": sum(1 for p in pairs if p.new is None),
                "pages_changed": sum(1 for p in pairs if p.old is not None and p.new is not None and p.changed),
                "pages_visual_only": sum(1 for p in pairs if p.visual),
                "words_inserted": sum(len(p.inserted) for p in pairs),
                "words_deleted": sum(len(p.deleted) for p in pairs),
            }
            pages = [
                {
                    "old_page": None if p.old is None else p.old + 1,
                    "new_page": None if p.new is None else p.new + 1,
                    "status": (
                        "added"
                        if p.old is None
                        else "removed"
                        if p.new is None
                        else "visual"
                        if p.visual
                        else "changed"
                        if p.changed
                        else "same"
                    ),
                    "inserted": len(p.inserted),
                    "deleted": len(p.deleted),
                }
                for p in pairs
            ]
            ctx.data = {
                "summary": summary,
                "pages": pages,
                "changes": snippets,
                "changes_truncated": len(snippets) >= MAX_SNIPPETS,
            }
            self._report(ctx, params, pairs, old_words, new_words, summary)

    def _report(
        self,
        ctx: Context,
        params: CompareParams,
        pairs: list[Pair],
        old_words: list[PageWords],
        new_words: list[PageWords],
        summary: dict[str, int],
    ) -> None:
        old_in, new_in = ctx.inputs
        # Mark up private copies so the inputs stay untouched, then bake the
        # annotations into content: show_pdf_page copies content only.
        with open_pdf(old_in.path, old_in.password) as old_doc, open_pdf(new_in.path, new_in.password) as new_doc:
            for p in pairs:
                if p.old is not None and p.deleted:
                    _mark(old_doc, p.old, old_words[p.old], p.deleted, RED, strike=True)
                if p.new is not None and p.inserted:
                    _mark(new_doc, p.new, new_words[p.new], p.inserted, GREEN, strike=False)
            old_doc.bake(annots=True, widgets=True)
            new_doc.bake(annots=True, widgets=True)
            report = pymupdf.open()
            try:
                _summary_page(
                    report,
                    [
                        f"Eski / Old: {old_in.name} ({summary['old_pages']} sayfa / pages)",
                        f"Yeni / New: {new_in.name} ({summary['new_pages']} sayfa / pages)",
                        "",
                        f"Eklenen sayfa / Pages added: {summary['pages_added']}",
                        f"Silinen sayfa / Pages removed: {summary['pages_removed']}",
                        f"Değişen sayfa / Pages changed: {summary['pages_changed']}",
                        *(
                            [f"Yalnızca görsel fark / Visual-only changes: {summary['pages_visual_only']}"]
                            if params.visual
                            else []
                        ),
                        f"Eklenen sözcük / Words inserted: {summary['words_inserted']}",
                        f"Silinen sözcük / Words deleted: {summary['words_deleted']}",
                        "",
                        "Yeşil vurgu: eklenen · Kırmızı üstü çizili: silinen",
                        "Green highlight: inserted · Red strike-through: deleted",
                    ],
                )
                shown = [p for p in pairs if p.changed or not params.only_changed]
                for k, p in enumerate(shown):
                    self._sheet(report, p, old_doc, new_doc)
                    ctx.progress(0.5 + 0.5 * (k + 1) / max(1, len(shown)), "")
                report.set_toc([[1, "Özet / Summary", 1]] + [[1, _sheet_title(p), i + 2] for i, p in enumerate(shown)])
                save_pdf(report, ctx.output(f"{new_in.stem}_karsilastirma.pdf"))
            finally:
                report.close()

    @staticmethod
    def _sheet(report: pymupdf.Document, p: Pair, old_doc: pymupdf.Document, new_doc: pymupdf.Document) -> None:
        sheet = report.new_page(width=SHEET_W, height=SHEET_H)
        half = (SHEET_W - 3 * MARGIN) / 2
        left = pymupdf.Rect(MARGIN, MARGIN + HEADER, MARGIN + half, SHEET_H - MARGIN)
        right = pymupdf.Rect(2 * MARGIN + half, MARGIN + HEADER, SHEET_W - MARGIN, SHEET_H - MARGIN)
        _text(sheet, pymupdf.Rect(left.x0, MARGIN, left.x1, MARGIN + HEADER), _side_label("Eski", "Old", p.old), 10)
        _text(sheet, pymupdf.Rect(right.x0, MARGIN, right.x1, MARGIN + HEADER), _side_label("Yeni", "New", p.new), 10)
        for doc, pno, box in ((old_doc, p.old, left), (new_doc, p.new, right)):
            if pno is None:
                sheet.draw_rect(box, color=(0.7, 0.7, 0.7), dashes="[4] 0", width=0.8)
                continue
            sheet.show_pdf_page(box, doc, pno)
        if p.old is None:
            sheet.draw_rect(right, color=GREEN, width=2)
        if p.new is None:
            sheet.draw_rect(left, color=RED, width=2)
        if p.visual:
            sheet.draw_rect(right, color=(0.95, 0.6, 0.1), width=2)


def _side_label(tr: str, en: str, pno: int | None) -> str:
    if pno is None:
        return f"{tr} / {en}: —"
    return f"{tr} / {en}: sayfa / page {pno + 1}"


def _sheet_title(p: Pair) -> str:
    if p.old is None:
        return f"+ Yeni sayfa / New page {(p.new or 0) + 1}"
    if p.new is None:
        return f"− Silinen sayfa / Removed page {p.old + 1}"
    return f"{p.old + 1} ↔ {p.new + 1}"
