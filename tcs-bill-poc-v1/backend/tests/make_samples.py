"""Generate sample bills for local testing.

These are throwaway test fixtures for the extraction pipeline - the app itself
never generates or renders a bill, it only displays the file a user uploaded.

    python tests/make_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "samples"


def _page(doc, lines: list[tuple[float, float, str, float, bool]]) -> None:
    page = doc.new_page(width=420, height=595)
    for x, y, text, size, bold in lines:
        page.insert_text(
            (x, y),
            text,
            fontsize=size,
            fontname="hebo" if bold else "helv",
            color=(0.08, 0.09, 0.11),
        )


def travel_receipt() -> None:
    doc = fitz.open()
    _page(
        doc,
        [
            (40, 60, "SWIFT CABS LLC", 16, True),
            (40, 78, "Deira, Dubai - United Arab Emirates", 8, False),
            (40, 90, "TRN 100234567800003", 8, False),
            (40, 125, "TAX INVOICE", 11, True),
            (40, 150, "Invoice No:", 9, False),
            (140, 150, "INV-88412", 9, True),
            (40, 168, "Bill Date:", 9, False),
            (140, 168, "11/02/2026", 9, True),
            (40, 186, "Passenger:", 9, False),
            (140, 186, "A. Rao", 9, False),
            (40, 220, "TRIP DETAILS", 10, True),
            (40, 244, "From:", 9, False),
            (140, 244, "Dubai - Deira", 9, True),
            (40, 262, "To:", 9, False),
            (140, 262, "Dubai - Airport T3", 9, True),
            (40, 280, "Distance:", 9, False),
            (140, 280, "18.4 km", 9, False),
            (40, 340, "Base Fare", 9, False),
            (300, 340, "AED 940.00", 9, False),
            (40, 358, "Waiting Charges", 9, False),
            (300, 358, "AED 28.50", 9, False),
            (40, 376, "Subtotal", 9, False),
            (300, 376, "AED 968.50", 9, False),
            (40, 394, "VAT 5%", 9, False),
            (300, 394, "AED 101.00", 9, False),
            (40, 424, "Total", 11, True),
            (300, 424, "AED 1,069.50", 11, True),
            (40, 470, "Payment Mode: Corporate Card", 8, False),
        ],
    )
    _page(
        doc,
        [
            (40, 60, "SWIFT CABS LLC", 12, True),
            (40, 90, "Terms & Conditions", 10, True),
            (40, 115, "1. This invoice is computer generated.", 8, False),
            (40, 130, "2. Fares include all applicable taxes.", 8, False),
            (40, 145, "3. For support contact +971 4 555 0100.", 8, False),
        ],
    )
    doc.save(OUT / "travel-receipt.pdf")
    doc.close()


def hotel_bill() -> None:
    doc = fitz.open()
    _page(
        doc,
        [
            (40, 60, "Shree Annapurna Bhavan", 16, True),
            (40, 78, "Restaurant & Caterers, Bengaluru", 8, False),
            (40, 90, "GSTIN 29AABCU9603R1ZX", 8, False),
            (40, 130, "Bill No:", 9, False),
            (140, 130, "FB-22104", 9, True),
            (40, 148, "Bill Date:", 9, False),
            (140, 148, "08/02/2026", 9, True),
            (40, 166, "Table:", 9, False),
            (140, 166, "12", 9, False),
            (40, 200, "Item", 9, True),
            (300, 200, "Amount", 9, True),
            (40, 224, "South Indian Thali x 2", 9, False),
            (300, 224, "Rs. 1,100.00", 9, False),
            (40, 242, "Filter Coffee x 3", 9, False),
            (300, 242, "Rs. 240.00", 9, False),
            (40, 260, "Paneer Butter Masala", 9, False),
            (300, 260, "Rs. 560.00", 9, False),
            (40, 290, "Subtotal", 9, False),
            (300, 290, "Rs. 1,900.00", 9, False),
            (40, 308, "CGST 2.5%", 9, False),
            (300, 308, "Rs. 47.50", 9, False),
            (40, 326, "SGST 2.5%", 9, False),
            (300, 326, "Rs. 47.50", 9, False),
            (40, 356, "Grand Total", 11, True),
            (300, 356, "Rs. 2,340.00", 11, True),
            (40, 400, "Thank you, visit again!", 8, False),
        ],
    )
    doc.save(OUT / "hotel-bill.pdf")
    doc.close()


def cafe_bill_no_number() -> None:
    """Food bill with no printed bill number - exercises the not-found state."""
    doc = fitz.open()
    _page(
        doc,
        [
            (40, 60, "Cafe Nilgiri", 16, True),
            (40, 78, "Terminal 3, Changi", 8, False),
            (40, 120, "Date:", 9, False),
            (140, 120, "09/02/2026", 9, True),
            (40, 160, "Cappuccino x 2", 9, False),
            (300, 160, "USD 12.40", 9, False),
            (40, 178, "Club Sandwich", 9, False),
            (300, 178, "USD 21.00", 9, False),
            (40, 196, "Fresh Juice", 9, False),
            (300, 196, "USD 9.80", 9, False),
            (40, 226, "Subtotal", 9, False),
            (300, 226, "USD 43.20", 9, False),
            (40, 244, "Service Charge", 9, False),
            (300, 244, "USD 5.00", 9, False),
            (40, 274, "Total Amount Payable", 11, True),
            (300, 274, "USD 48.20", 11, True),
        ],
    )
    doc.save(OUT / "cafe-bill.pdf")
    doc.close()


def scanned_image() -> None:
    """A JPG of a bill - exercises the OCR path and the image viewer."""
    doc = fitz.open(OUT / "hotel-bill.pdf")
    pix = doc[0].get_pixmap(dpi=200)
    pix.save(OUT / "hotel-bill.jpg", "jpg")
    doc.close()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    travel_receipt()
    hotel_bill()
    cafe_bill_no_number()
    scanned_image()
    print(f"samples written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
