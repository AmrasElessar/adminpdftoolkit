"""Taranmış / görsel PDF sınıflandırıcı.

Bu parser yalnızca classify (is_match) sağlar — taranmış PDF'lerin Word/Excel
gibi metin-bazlı dönüşümlere uygun olmadığını işaret eder ve OCR akışına
yönlendirilmesini ister. Asıl OCR ``pdf_converter.ocr_pdf_pages`` üzerinden
yapılır.
"""
from __future__ import annotations

from typing import Any

from .base import BaseParser


class ScannedParser(BaseParser):
    name = "scanned"

    def is_match(self, doc: Any) -> bool:
        if len(doc) == 0:
            return False
        total_chars = 0
        has_images = False
        for page in doc:
            total_chars += len(page.get_text().strip())
            if not has_images and page.get_images():
                has_images = True
        avg = total_chars / len(doc)
        # < 40 char/page average + at least one image → büyük ihtimal taranmış
        return avg < 40 and has_images
