"""Deterministic field-level validation (Phase 7 / TRD section 10).

Validation never invents a value. A field that could not be found stays
`not_found` with a null value so the user is never shown a fabricated one
(FR-08, UI/UX section 12).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.rules.common import (
    KNOWN_CURRENCY_CODES,
    FieldSpec,
    is_plausible_bill_date,
    looks_like_identifier,
    looks_like_merchant,
    looks_like_place,
)
from app.services.extraction_service import ExtractionResult, FieldExtraction

# Status vocabulary from 06_backend_schema.md section 11.
VALID = "valid"
INVALID = "invalid"
NOT_FOUND = "not_found"
REVIEW = "review"


@dataclass
class FieldValidation:
    field_name: str
    status: str
    message: str | None = None
    checks: dict[str, bool] = field(default_factory=dict)


@dataclass
class ValidationResult:
    fields: dict[str, FieldValidation] = field(default_factory=dict)

    def status_for(self, name: str) -> str:
        entry = self.fields.get(name)
        return entry.status if entry else NOT_FOUND


class ValidationService:
    def validate(self, extraction_result: ExtractionResult) -> ValidationResult:
        result = ValidationResult()
        for name, extraction in extraction_result.fields.items():
            result.fields[name] = self._validate_field(name, extraction)
        return result

    def _validate_field(self, name: str, extraction: FieldExtraction) -> FieldValidation:
        spec = extraction.spec

        if spec.system_value is not None:
            return FieldValidation(name, VALID, checks={"system_filled": True})

        best = extraction.best
        if best is None:
            message = (
                f"{spec.label} was not found in the document."
                if spec.required
                else f"{spec.label} was not printed on this bill."
            )
            return FieldValidation(name, NOT_FOUND, message, {"candidate_found": False})

        checks: dict[str, bool] = {"candidate_found": True}
        message: str | None = None
        status = VALID

        if spec.value_type == "date":
            checks.update(self._check_date(best.normalized_value))
        elif spec.value_type == "money":
            checks.update(self._check_amount(best.normalized_value))
        elif spec.value_type == "currency":
            checks["currency_recognised"] = best.normalized_value in KNOWN_CURRENCY_CODES
        elif name == "bill_no":
            checks["plausible_identifier"] = looks_like_identifier(best.normalized_value)
        elif name == "hotel_name":
            checks["merchant_like"] = looks_like_merchant(best.normalized_value)
        else:
            checks["place_like"] = looks_like_place(best.normalized_value)

        if not all(checks.values()):
            failed = [key for key, ok in checks.items() if not ok]
            return FieldValidation(
                name, INVALID, self._message_for(spec, failed), checks
            )

        # Conflicting candidates are surfaced, never silently resolved
        # (03_app_flow.md section 13).
        if extraction.is_ambiguous:
            others = ", ".join(
                f'"{c.value}"' for c in extraction.candidates[1:3]
            )
            status = REVIEW
            message = f"Multiple possible values found ({others}). Review suggested."
            checks["unique_candidate"] = False
        else:
            checks["unique_candidate"] = True

        return FieldValidation(name, status, message, checks)

    # -- individual checks --------------------------------------------------

    @staticmethod
    def _check_date(normalized: str) -> dict[str, bool]:
        try:
            parsed = datetime.strptime(normalized, "%Y-%m-%d").date()
        except ValueError:
            return {"parseable": False, "plausible": False}
        return {"parseable": True, "plausible": is_plausible_bill_date(parsed)}

    @staticmethod
    def _check_amount(normalized: str) -> dict[str, bool]:
        try:
            value = Decimal(normalized)
        except (InvalidOperation, ValueError):
            return {"numeric": False, "positive": False}
        exponent = value.as_tuple().exponent
        decimals = -exponent if isinstance(exponent, int) else 0
        return {
            "numeric": True,
            "positive": value > 0,
            "decimal_sane": decimals <= 2,
        }

    @staticmethod
    def _message_for(spec: FieldSpec, failed: list[str]) -> str:
        reasons = {
            "parseable": "the date could not be read",
            "plausible": "the date is outside the expected range",
            "numeric": "the amount is not a number",
            "positive": "the amount is not a positive value",
            "decimal_sane": "the amount has an unexpected number of decimals",
            "currency_recognised": "the currency code is not recognised",
            "plausible_identifier": "the value does not look like a bill number",
            "merchant_like": "the value does not look like a merchant name",
            "place_like": "the value does not look like a location",
        }
        detail = next((reasons[key] for key in failed if key in reasons), "the value failed validation")
        return f"{spec.label}: {detail}. Please check it against the bill."


validation_service = ValidationService()
