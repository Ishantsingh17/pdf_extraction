"""End-to-end checks over the sample bills.

    python tests/test_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use a throwaway database so the test run never touches a running dev server.
_TEST_DB = ROOT.parent / "data" / "test.db"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
_TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import init_db  # noqa: E402
from app.main import app  # noqa: E402

SAMPLES = ROOT.parent / "data" / "samples"

MEDIA = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}


def upload(client: TestClient, filename: str, claim_head: str) -> dict:
    path = SAMPLES / filename
    with path.open("rb") as handle:
        response = client.post(
            "/api/v1/documents",
            files={"file": (filename, handle, MEDIA[path.suffix])},
            data={"claim_head": claim_head},
        )
    assert response.status_code == 201, response.text
    return response.json()


def show(client: TestClient, document_id: str, title: str) -> dict:
    result = client.get(f"/api/v1/documents/{document_id}/result").json()
    print(f"\n=== {title} " + "=" * (56 - len(title)))
    print(f"  {result['summary']['headline']} - {result['summary']['detail']}")
    print(f"  document: {result['document']['filename']} "
          f"pages={result['document']['page_count']} ocr={result['document']['ocr_used']}")
    for field in result["fields"]:
        confidence = f"{field['confidence']:.0%}" if field["confidence"] is not None else "  -"
        source = field.get("source")
        where = f"p{source['page']} near {source['anchor']!r}" if source and source["anchor"] else ""
        print(f"  {field['label']:<16} {str(field['value']):<26} {field['status']:<12} {confidence:>5}  {where}")
    return result


def main() -> int:
    init_db()
    client = TestClient(app)
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  PASS  {label}")
        else:
            failures.append(f"{label} {detail}")
            print(f"  FAIL  {label} {detail}")

    # -- Travel, text PDF, foreign currency, multi-page ---------------------
    upload_out = upload(client, "travel-receipt.pdf", "Travel Conveyance")
    travel = show(client, upload_out["document_id"], "Travel Conveyance - travel-receipt.pdf")
    values = {f["name"]: f["value"] for f in travel["fields"]}
    print()
    check("text PDF avoids OCR", travel["document"]["ocr_used"] is False)
    check("multi-page detected", travel["document"]["page_count"] == 2)
    check("from_location", values["from_location"] == "Dubai - Deira", f"got {values['from_location']!r}")
    check("to_location", values["to_location"] == "Dubai - Airport T3", f"got {values['to_location']!r}")
    check("bill_date", values["bill_date"] == "11/02/2026", f"got {values['bill_date']!r}")
    check("bill_no", values["bill_no"] == "INV-88412", f"got {values['bill_no']!r}")
    check("bill_amount prefers total over subtotal", values["bill_amount"] == "AED 1,069.50", f"got {values['bill_amount']!r}")
    check("currency preserved as AED", values["currency"] == "AED", f"got {values['currency']!r}")
    check("remarks auto-filled", values["remarks"] == "Travel Conveyance")
    check("source bbox present for amount",
          any(f["name"] == "bill_amount" and f["source"] for f in travel["fields"]))

    # -- Food, INR ----------------------------------------------------------
    upload_out = upload(client, "hotel-bill.pdf", "Food")
    food = show(client, upload_out["document_id"], "Food - hotel-bill.pdf")
    values = {f["name"]: f["value"] for f in food["fields"]}
    print()
    check("hotel_name", values["hotel_name"] == "Shree Annapurna Bhavan", f"got {values['hotel_name']!r}")
    check("bill_date", values["bill_date"] == "08/02/2026", f"got {values['bill_date']!r}")
    check("bill_no", values["bill_no"] == "FB-22104", f"got {values['bill_no']!r}")
    check("grand total wins", values["bill_amount"] == "INR 2,340.00", f"got {values['bill_amount']!r}")
    check("currency INR", values["currency"] == "INR", f"got {values['currency']!r}")
    check("remarks auto-filled", values["remarks"] == "Food")
    check("no travel fields present", "from_location" not in values)

    # -- Food, missing bill number -----------------------------------------
    upload_out = upload(client, "cafe-bill.pdf", "Food")
    cafe_id = upload_out["document_id"]
    cafe = show(client, cafe_id, "Food - cafe-bill.pdf (no bill number)")
    values = {f["name"]: f["value"] for f in cafe["fields"]}
    bill_no = next(f for f in cafe["fields"] if f["name"] == "bill_no")
    print()
    check("missing bill_no is null, not fabricated", bill_no["value"] is None, f"got {bill_no['value']!r}")
    check("missing bill_no marked not_found", bill_no["status"] == "not_found")
    check("summary reports the missing field", "not found" in cafe["summary"]["headline"].lower(),
          cafe["summary"]["headline"])
    check("currency USD", values["currency"] == "USD", f"got {values['currency']!r}")

    # -- Food, JPG via OCR --------------------------------------------------
    from app.services.ocr_service import ocr_service  # noqa: E402

    if ocr_service.is_available:
        upload_out = upload(client, "hotel-bill.jpg", "Food")
        scan = show(client, upload_out["document_id"], "Food - hotel-bill.jpg (OCR)")
        values = {f["name"]: f["value"] for f in scan["fields"]}
        amount = next(f for f in scan["fields"] if f["name"] == "bill_amount")
        print()
        check("image uses OCR", scan["document"]["ocr_used"] is True)
        check("OCR found the merchant", (values["hotel_name"] or "").lower().startswith("shree"),
              f"got {values['hotel_name']!r}")
        check("OCR found the grand total", "2,340" in (values["bill_amount"] or ""),
              f"got {values['bill_amount']!r}")
        check("OCR keeps source coordinates for highlighting", amount["source"] is not None)
    else:
        print()
        print("  (OCR backend unavailable - skipping the image case)")

    # -- Manual edit + save -------------------------------------------------
    patched = client.patch(
        f"/api/v1/documents/{cafe_id}/result",
        json={"fields": [{"name": "bill_no", "value": "CN-5567"}]},
    ).json()
    edited = next(f for f in patched["fields"] if f["name"] == "bill_no")
    print()
    check("manual entry accepted", edited["value"] == "CN-5567")
    check("manual entry flagged", edited["manually_edited"] is True)
    check("summary clears the missing field", patched["summary"]["not_found"] == 0)

    # Editing an amount that carries its currency prefix must still save numerically.
    client.patch(
        f"/api/v1/documents/{cafe_id}/result",
        json={"fields": [{"name": "bill_amount", "value": "USD 48.20"}]},
    )

    saved = client.post(f"/api/v1/documents/{cafe_id}/save").json()
    check("save returns claim reference", saved["claim_reference"].startswith("CLM-"))
    check("save shows amount with currency", saved["bill_amount_display"] == "USD 48.20",
          str(saved["bill_amount_display"]))
    check("save counts manual edits", saved["manually_edited_count"] == 2, str(saved["manually_edited_count"]))
    check("claim JSON keeps bill currency", saved["json_payload"]["currency"] == "USD")
    check("claim JSON amount numeric (currency stripped)", saved["json_payload"]["bill_amount"] == 48.20,
          str(saved["json_payload"]["bill_amount"]))
    print("\n  claim JSON:", json.dumps(saved["json_payload"], indent=2)[:400], "...")

    # -- Error states -------------------------------------------------------
    print()
    bad = client.post(
        "/api/v1/documents",
        files={"file": ("expenses.xlsx", b"PK\x03\x04 not a bill", "application/vnd.ms-excel")},
        data={"claim_head": "Food"},
    )
    check("unsupported file rejected", bad.status_code == 422)
    check("unsupported file has safe code", bad.json()["detail"]["code"] == "unsupported_file")

    big = client.post(
        "/api/v1/documents",
        files={"file": ("huge.pdf", b"%PDF-" + b"0" * (11 * 1024 * 1024), "application/pdf")},
        data={"claim_head": "Food"},
    )
    check("oversized file rejected", big.status_code == 422)
    check("oversized file has safe code", big.json()["detail"]["code"] == "file_too_large")

    preview = client.get(f"/api/v1/documents/{cafe_id}/preview")
    check("preview serves the original file", preview.status_code == 200)
    check("preview is a PDF", preview.headers["content-type"] == "application/pdf")

    print("\n" + "=" * 64)
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for failure in failures:
            print("  -", failure)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
