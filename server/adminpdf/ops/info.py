"""Read-only inspection."""

from __future__ import annotations

from typing import Any

from ..core.pdf import open_pdf
from .base import Context, Operation, register


@register
class Info(Operation):
    name = "info"
    category = "inspect"
    title_tr, title_en = "PDF Bilgisi", "PDF Properties"
    description_tr = "Sayfa sayısı, boyutlar, meta veri, fontlar, şifreleme ve PDF sürümünü gösterir."
    description_en = "Show page count, sizes, metadata, fonts, encryption and PDF version."
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            fonts: set[str] = set()
            sizes: dict[str, int] = {}
            images = 0
            for page in doc:
                for f in page.get_fonts():
                    fonts.add(str(f[3]).split("+", 1)[-1])
                images += len(page.get_images())
                key = f"{page.rect.width:.0f} × {page.rect.height:.0f} pt"
                sizes[key] = sizes.get(key, 0) + 1
            meta: dict[str, Any] = {k: v for k, v in (doc.metadata or {}).items() if v}
            ctx.data = {
                "pages": doc.page_count,
                "version": meta.pop("format", ""),
                "encryption": meta.pop("encryption", None) or "",
                "metadata": meta,
                "page_sizes": sizes,
                "fonts": sorted(fonts),
                "images": images,
                "form_fields": sum(1 for p in doc for _ in p.widgets()),
                "bookmarks": len(doc.get_toc()),
                "attachments": doc.embfile_count(),
                "tagged": bool(doc.pdf_catalog() and "StructTreeRoot" in doc.xref_object(doc.pdf_catalog())),
            }
