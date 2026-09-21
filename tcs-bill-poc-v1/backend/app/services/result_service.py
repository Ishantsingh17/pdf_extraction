"""Assembles stored extraction rows into the API result shape."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.core.config import settings
from app.models import ClaimExtraction, Document, ExtractionField, ProcessingRun
from app.rules import resolve_claim_head
from app.rules.common import ClaimHeadSchema, parse_money
from app.schemas.schemas import (
    CandidateRef,
    ClaimOut,
    DocumentOut,
    FieldOut,
    ProcessingNotice,
    ResultOut,
    SourceRef,
    SummaryOut,
)

_ERROR_HINTS = {
    "ocr_unavailable": "This document needs text recognition, which isn't available on this server. Enter the values manually - your bill stays on screen.",
    "extraction_failed": "The scan is too blurry. Nothing was guessed - enter the values manually.",
    "read_failed": "The file could not be opened. Try re-uploading it.",
}


def build_result(
    document: Document,
    extraction: ClaimExtraction,
    run: ProcessingRun | None,
    fields: list[ExtractionField],
) -> ResultOut:
    schema = resolve_claim_head(extraction.claim_head)
    assert schema is not None

    ordered = sorted(fields, key=lambda f: f.display_order)
    currency_row = next((f for f in ordered if f.field_name == "currency"), None)
    currency_code = currency_row.current_value if currency_row else None
    field_outs = [_field_out(schema, row, currency_code) for row in ordered]
    summary = _summary(field_outs)

    remarks = next((f.value for f in field_outs if f.name == "remarks"), None)
    currency = next((f for f in field_outs if f.name == "currency"), None)

    notice = None
    if run and run.status == "failed" and run.error_code:
        notice = ProcessingNotice(
            code=run.error_code,
            message=run.error_message or "We couldn't reliably extract the required information from this bill.",
            hint=_ERROR_HINTS.get(run.error_code),
        )

    return ResultOut(
        document=DocumentOut(
            id=document.id,
            filename=document.original_filename,
            file_type=document.file_type,
            page_count=document.page_count,
            ocr_used=bool(run.ocr_used) if run else document.requires_ocr,
            preview_url=f"{settings.api_prefix}/documents/{document.id}/preview",
        ),
        claim=ClaimOut(
            claim_head=schema.key,
            claim_head_label=schema.label,
            claim_reference=extraction.claim_reference,
            status=extraction.status,
        ),
        summary=summary,
        fields=field_outs,
        remarks=remarks,
        currency_note=(
            f"{currency.value} detected - no conversion applied"
            if currency and currency.value and currency.value != "INR"
            else (f"{currency.value} detected" if currency and currency.value else None)
        ),
        notice=notice,
    )


def _field_out(
    schema: ClaimHeadSchema, row: ExtractionField, currency_code: str | None = None
) -> FieldOut:
    spec = schema.get(row.field_name)
    label = spec.label if spec else row.field_name.replace("_", " ").title()
    signals = row.signals or {}

    source = None
    if row.source_page and row.source_bbox:
        source = SourceRef(
            page=row.source_page,
            bbox=[float(v) for v in row.source_bbox],
            text=row.source_text,
            anchor=row.anchor_text,
        )

    candidates = [
        CandidateRef(
            value=c.get("value", ""),
            page=int(c.get("page", 1)),
            bbox=[float(v) for v in c.get("bbox", [])],
            text=c.get("text"),
            anchor=c.get("anchor"),
        )
        for c in (row.candidates or [])
    ]

    return FieldOut(
        name=row.field_name,
        label=label,
        value=display_amount(row, currency_code)
        if row.value_type == "money"
        else row.current_value,
        value_type=row.value_type,
        required=spec.required if spec else True,
        system_filled=bool(spec and spec.system_value is not None),
        confidence=row.confidence,
        status=row.confidence_status,  # type: ignore[arg-type]
        validation=row.validation_status,  # type: ignore[arg-type]
        validation_message=row.validation_message,
        manually_edited=row.was_manually_edited,
        reasons=list(signals.get("reasons", [])),
        source=source,
        candidates=candidates,
    )


def _summary(fields: list[FieldOut]) -> SummaryOut:
    """Review-summary wording from 02_ui_ux_flow.md section 14."""
    scored = [f for f in fields if not f.system_filled]
    total = len(scored)
    not_found = [f for f in scored if f.status == "not_found"]
    high = [f for f in scored if f.status == "high"]
    medium = [f for f in scored if f.status == "review"]
    low = [f for f in scored if f.status == "needs_review"]
    extracted = total - len(not_found)

    # System-filled fields still count as extracted content for the headline.
    total_with_system = len(fields)
    extracted_with_system = extracted + (total_with_system - total)

    if not_found:
        names = ", ".join(f.label for f in not_found)
        headline = f"{len(not_found)} field not found" if len(not_found) == 1 else f"{len(not_found)} fields not found"
        detail = (
            f"{extracted_with_system} of {total_with_system} fields extracted"
            f" · {len(high)} high confidence · {names} missing"
        )
        tone = "review"
    elif len(low) >= 2:
        headline = f"{len(low)} fields need review"
        detail = (
            f"{total_with_system} fields extracted · {len(high)} high confidence"
            f" · {len(low)} low · {len(medium)} medium"
        )
        tone = "issue"
    elif low:
        headline = "Review required"
        detail = (
            f"{total_with_system} fields extracted · {len(high)} high confidence"
            f" · {len(low)} needs review"
        )
        tone = "review"
    elif medium:
        headline = "Review suggested"
        detail = (
            f"{total_with_system} fields extracted · {len(high)} high confidence"
            f" · {len(medium)} to verify"
        )
        tone = "review"
    else:
        headline = "Ready for review"
        detail = (
            f"{total_with_system} fields extracted · {len(high) + (total_with_system - total)}"
            f" high confidence · 0 need review"
        )
        tone = "ready"

    return SummaryOut(
        headline=headline,
        detail=detail,
        tone=tone,  # type: ignore[arg-type]
        total_fields=total_with_system,
        extracted_fields=extracted_with_system,
        high_confidence=len(high) + (total_with_system - total),
        needs_review=len(low) + len(medium),
        not_found=len(not_found),
    )


def build_claim_json(
    extraction: ClaimExtraction, fields: list[ExtractionField]
) -> dict:
    """Structured claim JSON (06_backend_schema.md sections 8-9)."""
    schema = resolve_claim_head(extraction.claim_head)
    assert schema is not None

    by_name = {f.field_name: f for f in fields}
    payload: dict = {"claim_head": schema.label}
    confidence: dict[str, float | None] = {}

    for spec in schema.fields:
        row = by_name.get(spec.name)
        value = row.current_value if row else None
        if spec.value_type == "money" and value:
            payload[spec.name] = _to_float(value)
        elif spec.value_type == "date" and row and row.normalized_value:
            payload[spec.name] = row.normalized_value if not row.was_manually_edited else value
        else:
            payload[spec.name] = value
        if spec.system_value is None and row:
            confidence[spec.name] = row.confidence

    payload["confidence"] = confidence
    payload["claim_reference"] = extraction.claim_reference
    payload["overall_confidence"] = extraction.overall_confidence
    payload["fields_manually_edited"] = [
        name for name, row in by_name.items() if row.was_manually_edited
    ]
    return payload


def display_amount(row: ExtractionField, currency_code: str | None) -> str | None:
    """Amounts are shown with the currency printed on the bill, e.g. "AED 1,069.50".

    The currency is never converted and never replaced - it is only put back
    in front of the number the bill actually showed (FR-07).
    """
    value = row.current_value
    if not value:
        return None
    if not currency_code or any(ch.isalpha() for ch in value):
        return value
    return f"{currency_code} {value}"


def _to_float(value: str) -> float | None:
    """Numeric value of an amount, tolerating a currency prefix the user kept."""
    parsed = parse_money(value)
    if parsed is not None:
        return float(parsed)
    try:
        return float(Decimal(value.replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def display_date(row: ExtractionField | None) -> str | None:
    """'11 Feb 2026' for the save-confirmation card."""
    if not row or not row.current_value:
        return None
    raw = row.normalized_value or row.current_value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%d %b %Y")
        except ValueError:
            continue
    return row.current_value
