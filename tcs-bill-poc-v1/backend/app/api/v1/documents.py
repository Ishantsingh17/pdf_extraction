"""Document endpoints (TRD section 4)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import ClaimExtraction, Document, ExtractionField, ManualEdit, ProcessingRun
from app.rules import resolve_claim_head
from app.schemas.schemas import (
    ResultOut,
    ResultPatch,
    SaveOut,
    UploadOut,
)
from app.services import file_service, pipeline, result_service
from app.services.file_service import FileValidationError
from app.db.session import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


def _next_claim_reference(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    count = db.scalar(select(func.count(ClaimExtraction.id))) or 0
    return f"CLM-{year}-{841 + count:04d}"


@router.post("", response_model=UploadOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    claim_head: str = Form(...),
    db: Session = Depends(get_db),
) -> UploadOut:
    # Deliberately sync: `pipeline.process` blocks for as long as OCR and layout
    # analysis take (seconds with the default engines, over a minute with the
    # Paddle stack). A sync endpoint runs in FastAPI's threadpool, so the event
    # loop stays free to serve the preview, health and any other request; as
    # `async def` it would freeze the whole server for the duration.
    schema = resolve_claim_head(claim_head)
    if schema is None:
        raise HTTPException(status_code=422, detail={"code": "invalid_claim_head", "message": "Select a valid claim head."})

    content = file.file.read()
    try:
        file_type, mime_type = file_service.validate_upload(file.filename or "", content)
    except FileValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc

    document = Document(
        original_filename=file.filename or f"upload.{file_type}",
        stored_filename="",
        file_type=file_type,
        mime_type=mime_type,
        file_size_bytes=len(content),
        sha256=file_service.sha256_of(content),
        preview_path="",
    )
    db.add(document)
    db.flush()

    stored = file_service.store_original(document.id, document.original_filename, content)
    document.stored_filename = stored.name
    document.preview_path = str(stored)

    try:
        analysis = file_service.analyze(stored, file_type)
    except FileValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("analysis failed for upload")
        raise HTTPException(
            status_code=422,
            detail={"code": "unreadable_file", "message": "This document could not be read."},
        ) from exc

    document.page_count = analysis.page_count
    document.has_text_layer = analysis.has_text_layer
    document.requires_ocr = analysis.requires_ocr

    run = ProcessingRun(document_id=document.id, claim_head=schema.key, status="queued")
    db.add(run)
    db.commit()

    claim_reference = _next_claim_reference(db)
    pipeline.process(db, document, run, schema, claim_reference)

    return UploadOut(
        document_id=document.id,
        status=run.status,
        claim_head=schema.key,
        claim_reference=claim_reference,
        page_count=document.page_count,
        ocr_used=bool(run.ocr_used),
    )


def _load(db: Session, document_id: str) -> tuple[Document, ClaimExtraction, ProcessingRun | None, list[ExtractionField]]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Document not found."})

    extraction = db.scalar(
        select(ClaimExtraction)
        .where(ClaimExtraction.document_id == document_id)
        .order_by(ClaimExtraction.created_at.desc())
    )
    if extraction is None:
        raise HTTPException(status_code=404, detail={"code": "not_processed", "message": "This document has not been processed."})

    run = db.get(ProcessingRun, extraction.processing_run_id)
    fields = list(
        db.scalars(
            select(ExtractionField)
            .where(ExtractionField.claim_extraction_id == extraction.id)
            .order_by(ExtractionField.display_order)
        )
    )
    return document, extraction, run, fields


@router.get("/{document_id}", response_model=ResultOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> ResultOut:
    document, extraction, run, fields = _load(db, document_id)
    return result_service.build_result(document, extraction, run, fields)


@router.get("/{document_id}/preview")
def preview_document(document_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Serves the original uploaded file - the review screen renders exactly this."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Document not found."})
    try:
        path = file_service.resolve_stored_path(document.id, document.stored_filename)
    except FileValidationError as exc:
        raise HTTPException(status_code=404, detail={"code": exc.code, "message": exc.message}) from exc

    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(document.file_type, "application/octet-stream"),
        filename=document.original_filename,
        content_disposition_type="inline",
    )


@router.get("/{document_id}/result", response_model=ResultOut)
def get_result(document_id: str, db: Session = Depends(get_db)) -> ResultOut:
    document, extraction, run, fields = _load(db, document_id)
    return result_service.build_result(document, extraction, run, fields)


@router.patch("/{document_id}/result", response_model=ResultOut)
def patch_result(document_id: str, patch: ResultPatch, db: Session = Depends(get_db)) -> ResultOut:
    """Accept user corrections, keeping the original extraction intact."""
    document, extraction, run, fields = _load(db, document_id)
    by_name = {f.field_name: f for f in fields}

    for update in patch.fields:
        row = by_name.get(update.name)
        if row is None:
            continue
        new_value = (update.value or "").strip() or None
        if new_value == row.current_value:
            continue

        db.add(
            ManualEdit(
                extraction_field_id=row.id,
                old_value=row.current_value,
                new_value=new_value,
                edited_by=patch.edited_by,
            )
        )
        row.current_value = new_value
        row.was_manually_edited = True
        # A value the user typed is theirs: it is no longer scored by the
        # heuristic, and it is never re-labelled "not found".
        row.validation_status = "valid" if new_value else "not_found"
        row.confidence_status = "high" if new_value else "not_found"
        row.validation_message = None if new_value else "Not found in document"

    extraction.status = "reviewed"
    db.commit()

    fields = list(
        db.scalars(
            select(ExtractionField)
            .where(ExtractionField.claim_extraction_id == extraction.id)
            .order_by(ExtractionField.display_order)
        )
    )
    return result_service.build_result(document, extraction, run, fields)


@router.post("/{document_id}/save", response_model=SaveOut)
def save_claim(document_id: str, db: Session = Depends(get_db)) -> SaveOut:
    document, extraction, run, fields = _load(db, document_id)

    extraction.status = "saved"
    db.commit()
    db.refresh(extraction)

    by_name = {f.field_name: f for f in fields}
    amount = by_name.get("bill_amount")
    currency = by_name.get("currency")
    amount_display = (
        result_service.display_amount(amount, currency.current_value if currency else None)
        if amount
        else None
    )

    schema = resolve_claim_head(extraction.claim_head)
    assert schema is not None

    return SaveOut(
        claim_id=extraction.id,
        claim_reference=extraction.claim_reference,
        status=extraction.status,
        saved_at=extraction.updated_at,
        claim_head_label=schema.label,
        bill_date=result_service.display_date(by_name.get("bill_date")),
        bill_amount_display=amount_display,
        manually_edited_count=sum(1 for f in fields if f.was_manually_edited),
        json_payload=result_service.build_claim_json(extraction, fields),
    )
