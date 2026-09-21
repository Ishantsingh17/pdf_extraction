"""End-to-end processing pipeline.

    file -> text/OCR -> structure -> extraction -> validation -> confidence -> DB

Reliability rule (PRD section 8): one failed field must not prevent the
successful ones from being returned, and a total failure still leaves the
uploaded document viewable with every field open for manual entry.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import ClaimExtraction, Document, ExtractionField, ProcessingRun
from app.rules.common import ClaimHeadSchema
from app.services.confidence_service import confidence_service
from app.services.document_model import DocumentContent, Page
from app.services.extraction_service import claim_extractor
from app.services.ocr_service import OCRUnavailableError, ocr_service
from app.services.pdf_service import TextReader
from app.services.structure_service import structure_analyzer
from app.services.validation_service import NOT_FOUND, validation_service

logger = get_logger(__name__)

text_reader = TextReader()


class ProcessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def read_document(document: Document, path: Path) -> DocumentContent:
    """Acquire text + coordinates, using OCR only where it is actually needed."""
    content = _read_pdf(document, path) if document.file_type == "pdf" else _read_image(document, path)
    content.source_path = str(path)
    return content


def _read_pdf(document: Document, path: Path) -> DocumentContent:
    content = (
        text_reader.read(path, document_id=document.id)
        if document.has_text_layer
        else DocumentContent(document_id=document.id, pages=[], source="ocr")
    )

    # Mixed documents are common: a text page plus a scanned page. OCR only the
    # pages that have no usable text layer.
    pages_needing_ocr = [
        page_number
        for page_number in range(1, document.page_count + 1)
        if not _page_has_blocks(content, page_number)
    ]

    if pages_needing_ocr:
        ocr_pages: list[Page] = []
        for page_number in pages_needing_ocr:
            image_bytes = text_reader.render_page(path, page_number)
            target_size = text_reader.page_size(path, page_number)
            ocr_pages.append(
                ocr_service.extract(image_bytes, page_number=page_number, target_size=target_size)
            )
        by_number = {p.page_number: p for p in content.pages}
        for page in ocr_pages:
            by_number[page.page_number] = page
        content.pages = [by_number[n] for n in sorted(by_number)]
        content.ocr_used = True
        content.source = "ocr" if not document.has_text_layer else "pdf_text"

    return content


def _read_image(document: Document, path: Path) -> DocumentContent:
    page = ocr_service.extract(path, page_number=1)
    return DocumentContent(
        document_id=document.id, pages=[page], source="ocr", ocr_used=True
    )


def _page_has_blocks(content: DocumentContent, page_number: int) -> bool:
    return any(p.page_number == page_number and p.blocks for p in content.pages)


def process(
    db: Session,
    document: Document,
    run: ProcessingRun,
    schema: ClaimHeadSchema,
    claim_reference: str,
) -> ClaimExtraction:
    """Run the pipeline and persist the extraction, whatever the outcome."""
    run.status = "processing"
    run.started_at = _now()
    db.commit()

    path = Path(document.preview_path)
    content: DocumentContent | None = None
    failure: ProcessingError | None = None

    try:
        content = read_document(document, path)
        if content.total_characters == 0:
            raise ProcessingError(
                "extraction_failed",
                "We couldn't reliably extract the required information from this bill.",
            )
    except OCRUnavailableError as exc:
        failure = ProcessingError("ocr_unavailable", str(exc))
    except ProcessingError as exc:
        failure = exc
    except Exception as exc:  # pragma: no cover - unexpected reader failure
        logger.exception("document read failed for %s", document.id)
        failure = ProcessingError("read_failed", "This document could not be read.")

    extraction = ClaimExtraction(
        document_id=document.id,
        processing_run_id=run.id,
        claim_reference=claim_reference,
        claim_head=schema.key,
        status="extracted",
    )
    db.add(extraction)
    db.flush()

    analysis = None
    if content is not None and failure is None:
        try:
            structured = structure_analyzer.analyze(content)
            extraction_result = claim_extractor.extract(structured, schema)
            validation_result = validation_service.validate(extraction_result)
            confidence_result = confidence_service.score(extraction_result, validation_result)
            analysis = (structured, extraction_result, validation_result, confidence_result)
        except Exception:
            # The reliability rule above applies to the analysis half too: a
            # layout or extraction failure must still leave the bill on screen
            # with every field open for manual entry, not return a 500.
            logger.exception("analysis failed for %s", document.id)
            failure = ProcessingError(
                "extraction_failed",
                "We couldn't reliably extract the required information from this bill.",
            )

    if analysis is not None:
        structured, extraction_result, validation_result, confidence_result = analysis

        for spec in schema.fields:
            field_extraction = extraction_result.fields[spec.name]
            best = field_extraction.best
            validation = validation_result.fields[spec.name]
            confidence = confidence_result.fields[spec.name]

            if spec.system_value is not None:
                value = spec.system_value
                normalized = spec.system_value
            else:
                value = best.value if best else None
                normalized = best.normalized_value if best else None

            db.add(
                ExtractionField(
                    claim_extraction_id=extraction.id,
                    field_name=spec.name,
                    display_order=spec.order,
                    extracted_value=value,
                    normalized_value=normalized,
                    current_value=value,
                    value_type=spec.value_type,
                    confidence=confidence.confidence,
                    confidence_status=confidence.status,
                    validation_status=validation.status,
                    validation_message=validation.message,
                    source_page=best.page_number if best else None,
                    source_bbox=list(best.bbox) if best else None,
                    source_text=best.source_text if best else None,
                    anchor_text=best.anchor_text if best else None,
                    candidate_count=len(field_extraction.candidates),
                    candidates=[c.as_evidence() for c in field_extraction.candidates[:4]],
                    signals={
                        "weights": confidence.signals,
                        "reasons": confidence.reasons,
                        "strategy": best.strategy if best else None,
                    },
                )
            )

        extraction.overall_confidence = confidence_result.overall
        run.status = "completed"
        run.text_source = content.source
        run.ocr_used = content.ocr_used
        run.structure_model = structured.model
    else:
        # Extraction failure: keep the document visible, offer manual entry.
        for spec in schema.fields:
            is_system = spec.system_value is not None
            db.add(
                ExtractionField(
                    claim_extraction_id=extraction.id,
                    field_name=spec.name,
                    display_order=spec.order,
                    extracted_value=spec.system_value,
                    normalized_value=spec.system_value,
                    current_value=spec.system_value,
                    value_type=spec.value_type,
                    confidence=1.0 if is_system else None,
                    confidence_status="high" if is_system else NOT_FOUND,
                    validation_status="valid" if is_system else NOT_FOUND,
                    validation_message=None if is_system else "Not found in document",
                    candidate_count=0,
                )
            )
        extraction.overall_confidence = None
        extraction.status = "extracted"
        run.status = "failed"
        run.error_code = failure.code if failure else "unknown"
        run.error_message = failure.message if failure else None

    run.completed_at = _now()
    db.commit()
    db.refresh(extraction)
    logger.info(
        "processed document=%s run_status=%s overall=%s",
        document.id,
        run.status,
        extraction.overall_confidence,
    )
    return extraction
