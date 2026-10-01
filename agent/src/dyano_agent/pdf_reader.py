"""Tool 1 — PDF reader.

Detect whether a PDF carries native text/forms or is a scanned image, then
extract accordingly:

- native PDF  -> PyMuPDF (`pymupdf4llm`) for text extraction; PyMuPDF's
  AcroForm inspection + Docling for locating existing forms.
- scanned PDF -> PaddleOCR over rendered page images.

The extracted Markdown is written under the configured work directory.
"""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Below this many non-whitespace characters we treat a PDF as a scanned image.
NATIVE_TEXT_THRESHOLD = 50


def _text_char_count(path: Path) -> int:
    doc = fitz.open(path)
    try:
        return sum(len(page.get_text().strip()) for page in doc)
    finally:
        doc.close()


def detect_pdf_type(path: Path) -> str:
    """Return ``"native"`` or ``"scanned"`` for the given PDF path."""
    try:
        count = _text_char_count(path)
    except Exception as exc:  # noqa: BLE001 - report any open/parse failure
        logger.warning("Could not inspect %s: %s", path, exc)
        return "scanned"
    return "native" if count >= NATIVE_TEXT_THRESHOLD else "scanned"


def _extract_native(path: Path) -> tuple[str, list[str]]:
    """Extract native text/forms. Returns ``(markdown, form_notes)``."""
    import pymupdf4llm

    markdown = pymupdf4llm.to_markdown(path)

    form_notes: list[str] = []
    doc = fitz.open(path)
    try:
        if doc.is_form:
            for page in doc:
                for widget in page.widgets():
                    if widget.field_name:
                        form_notes.append(
                            f"form field '{widget.field_name}' on page {page.number + 1}"
                        )
        if not form_notes:
            form_notes.append("no AcroForm fields detected")
    finally:
        doc.close()

    form_notes.extend(_docling_form_notes(path))
    return markdown, form_notes


def _docling_form_notes(path: Path) -> list[str]:
    """Best-effort Docling pass to surface existing form structure."""
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document
        if doc is None:
            return ["docling: no document produced"]
        tables = getattr(doc, "tables", None)
        forms = getattr(doc, "forms", None)
        notes: list[str] = []
        if tables:
            notes.append(f"docling: {len(tables)} table(s) detected")
        if forms:
            notes.append(f"docling: {len(forms)} form(s) detected")
        return notes or ["docling: no tables/forms detected"]
    except Exception as exc:  # noqa: BLE001 - Docling is optional/heavy
        logger.warning("Docling pass failed for %s: %s", path, exc)
        return [f"docling: unavailable ({exc})"]


def _extract_scanned(path: Path) -> str:
    """OCR a scanned PDF page-by-page with PaddleOCR."""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    doc = fitz.open(path)
    parts: list[str] = []
    try:
        for page_number, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=200)
            image = pix.tobytes("png")
            result = ocr.ocr(image)
            parts.append(f"## Page {page_number}\n\n{_ocr_to_text(result)}")
    finally:
        doc.close()
    return "\n\n".join(parts)


def _ocr_to_text(result) -> str:
    """Normalise PaddleOCR output (differs across versions) to plain text."""
    lines: list[str] = []
    if result is None:
        return ""
    # PaddleOCR 3.x returns a list of dicts: {"rec_texts": [...], ...}
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "rec_texts" in item:
                lines.extend(item["rec_texts"])
            elif isinstance(item, (list, tuple)):
                # Legacy format: [[box], (text, score)]
                for entry in item:
                    if (
                        isinstance(entry, (list, tuple))
                        and len(entry) >= 2
                        and isinstance(entry[1], (list, tuple))
                        and entry[1]
                    ):
                        lines.append(str(entry[1][0]))
    return "\n".join(line for line in lines if line)


def extract_pdf(path: Path, out_md_path: Path) -> dict:
    """Extract a PDF to Markdown and persist it. Returns a summary dict."""
    pdf_type = detect_pdf_type(path)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)

    if pdf_type == "native":
        markdown, form_notes = _extract_native(path)
        out_md_path.write_text(markdown, encoding="utf-8")
        return {
            "pdf_type": "native",
            "forms": form_notes,
            "char_count": len(markdown),
        }

    markdown = _extract_scanned(path)
    out_md_path.write_text(markdown, encoding="utf-8")
    return {
        "pdf_type": "scanned",
        "forms": ["OCR extracted (no AcroForm)"],
        "char_count": len(markdown),
    }
