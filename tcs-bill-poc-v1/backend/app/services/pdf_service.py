"""Direct text extraction from PDFs with a usable text layer (Phase 3).

Text PDFs never go through OCR - PyMuPDF already gives us text plus exact
coordinates, which is both faster and more accurate.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import get_logger
from app.services.document_model import Block, DocumentContent, Page

logger = get_logger(__name__)


class TextReader:
    """Reads the selectable text layer of a PDF."""

    def can_read(self, file_path: str | Path) -> bool:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            return False
        try:
            with fitz.open(path) as doc:
                return any(
                    len(page.get_text("text").strip()) >= settings.min_chars_for_text_layer
                    for page in doc
                )
        except Exception:  # pragma: no cover - corrupt file
            return False

    def read(self, file_path: str | Path, document_id: str = "") -> DocumentContent:
        path = Path(file_path)
        pages: list[Page] = []
        with fitz.open(path) as doc:
            for index, page in enumerate(doc, start=1):
                rect = page.rect
                blocks: list[Block] = []
                # "dict" gives us line-level boxes, which map much better onto
                # label/value relationships than raw block boxes.
                data = page.get_text("dict")
                counter = 0
                for block in data.get("blocks", []):
                    if block.get("type") != 0:  # skip images
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        text = "".join(span.get("text", "") for span in spans)
                        if not text.strip():
                            continue
                        x0, y0, x1, y1 = line["bbox"]
                        font_size = max((float(s.get("size", 0)) for s in spans), default=0.0)
                        counter += 1
                        blocks.append(
                            Block(
                                id=f"p{index}-b{counter}",
                                text=text.strip(),
                                bbox=(x0, y0, x1, y1),
                                source="pdf_text",
                                font_size=font_size or None,
                            )
                        )
                pages.append(
                    Page(
                        page_number=index,
                        width=rect.width,
                        height=rect.height,
                        blocks=blocks,
                    )
                )
        logger.info(
            "pdf text read: pages=%s blocks=%s",
            len(pages),
            sum(len(p.blocks) for p in pages),
        )
        return DocumentContent(
            document_id=document_id, pages=pages, source="pdf_text", ocr_used=False
        )

    def page_has_text(self, file_path: str | Path, page_number: int) -> bool:
        with fitz.open(Path(file_path)) as doc:
            page = doc[page_number - 1]
            return len(page.get_text("text").strip()) >= settings.min_chars_for_text_layer

    def render_page(self, file_path: str | Path, page_number: int, dpi: int = 200) -> bytes:
        """Rasterise one PDF page so it can be sent to OCR."""
        with fitz.open(Path(file_path)) as doc:
            page = doc[page_number - 1]
            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")

    def page_size(self, file_path: str | Path, page_number: int) -> tuple[float, float]:
        with fitz.open(Path(file_path)) as doc:
            rect = doc[page_number - 1].rect
            return rect.width, rect.height
