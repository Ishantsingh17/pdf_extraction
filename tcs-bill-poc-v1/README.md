# TCS Claim Extractor — POC V1

Bill information extraction for two claim heads, **Travel Conveyance** and **Food**.

A user picks a claim head, uploads a real bill (PDF/JPG/JPEG/PNG), and the app
extracts only the fields that claim head needs, validates them, scores a
transparent heuristic confidence, and shows the result **beside the actual
uploaded document** for review and correction.

No LLM and no ML model are used for extraction or confidence in V1.

---

## Running it

Two processes: the FastAPI backend and the Vite frontend.

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux

.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Health check, which also reports which engines were found:

```bash
curl http://127.0.0.1:8000/api/v1/health
# {"status":"ok","ocr_backend":"tesseract","structure_model":"geometric-v1"}
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to port 8000)
```

### Sample bills

```bash
cd backend
.venv/Scripts/python tests/make_samples.py     # writes data/samples/
.venv/Scripts/python tests/test_pipeline.py    # end-to-end checks
```

| Sample | Exercises |
|---|---|
| `travel-receipt.pdf` | Travel, text PDF, 2 pages, AED, subtotal vs total |
| `hotel-bill.pdf` | Food, text PDF, INR, "Grand Total" |
| `hotel-bill.jpg` | Food, **OCR path** and image viewer |
| `cafe-bill.pdf` | Food, USD, **no bill number printed** (not-found state) |

---

## What the app does

```
claim head + upload
      ↓
validate file  →  PDF text layer?  ──yes──→  direct text + coordinates
      ↓                            └──no───→  OCR (images, scanned pages only)
layout / structure analysis
      ↓
claim-head-specific field extraction  (anchors → layout → candidate ranking)
      ↓
deterministic validation
      ↓
heuristic confidence  →  high / review / needs_review / not_found
      ↓
original document  +  editable fields  →  save  →  structured JSON
```

### Rules that shape the behaviour

- **The document on screen is the uploaded file.** PDFs are rendered by pdf.js
  from the original bytes; images are shown as uploaded. Nothing is recreated.
- **Currency is whatever the bill printed.** `AED 1,069.50` stays AED. No
  conversion, no INR default.
- **Missing values stay missing.** A field that could not be found is `null`
  and shows "Not found in document" with a manual-entry box — never a guess.
- **Ambiguity is surfaced, not resolved.** When two candidates compete, both
  are offered as chips with the label each was found near.
- **One bad field cannot sink the run.** Extraction failures are caught per
  field, and a total failure still shows the bill with every field editable.

---

## Layout

```
tcs-bill-poc-v1/
├── backend/
│   ├── app/
│   │   ├── api/v1/           documents.py, claims.py
│   │   ├── core/             config, logging
│   │   ├── db/               SQLAlchemy session
│   │   ├── models/           documents, runs, extractions, fields, edits
│   │   ├── rules/            claim-head schemas (travel.py, food.py, common.py)
│   │   ├── schemas/          API request/response models
│   │   └── services/         file, pdf, ocr, structure, extraction,
│   │                         validation, confidence, pipeline, result
│   └── tests/                make_samples.py, test_pipeline.py
├── frontend/src/
│   ├── components/           AppHeader, DocumentViewer, ExtractedDetailsPanel,
│   │                         ExtractedFieldRow, ConfidenceBadge, icons
│   ├── pages/                Upload, Processing, Review, Success
│   ├── services/api.ts       typed API client
│   └── types/                shared API types
└── data/
    ├── uploads/{document_id}/original.ext    originals, retained for preview
    └── samples/                              test fixtures
```

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/documents` | Upload (`file`, `claim_head`), runs the pipeline |
| GET | `/api/v1/documents/{id}` | Document + extraction result |
| GET | `/api/v1/documents/{id}/preview` | **The original file**, for the viewer |
| GET | `/api/v1/documents/{id}/result` | Fields, confidence, validation, evidence |
| PATCH | `/api/v1/documents/{id}/result` | User corrections (audited) |
| POST | `/api/v1/documents/{id}/save` | Finalise; returns the claim JSON |
| GET | `/api/v1/claims/{id}` | Saved claim |

Saved Travel claim:

```json
{
  "claim_head": "Travel Conveyance",
  "from_location": "Dubai - Deira",
  "to_location": "Dubai - Airport T3",
  "bill_date": "2026-02-11",
  "bill_no": "INV-88412",
  "currency": "AED",
  "bill_amount": 1069.5,
  "remarks": "Travel Conveyance",
  "confidence": { "bill_amount": 0.84, "bill_date": 0.98, "...": 0.0 }
}
```

---

## Confidence

The score is a weighted sum of signals that can be observed and explained:

| Signal | Weight | Meaning |
|---|---|---|
| `candidate_found` | 0.20 | A value was located at all |
| `anchor_match` | 0.22 | A clear field label (or decisive structure) was found |
| `format_valid` | 0.18 | The value parses as its type |
| `spatial_proximity` | 0.15 | The value sits near its label |
| `unique_candidate` | 0.15 | Only one strong candidate |
| `source_quality` | 0.10 | Document text (1.0) vs OCR (engine score) |

Thresholds (`app/core/config.py`): ≥ 0.90 high · ≥ 0.70 review · below needs review.
Validation caps the score, so a value that failed its checks can never read as
high confidence. Every field stores its signals, source page, bbox, anchor and
candidates — the evidence set POC V2 would train a model on.

---

## Swapping engines

Both model-facing pieces sit behind interfaces, chosen by environment variable
and reported by `/api/v1/health`:

| Variable | Values | Default |
|---|---|---|
| `STRUCTURE_ENGINE` | `geometric` / `ppstructure` / `auto` | `geometric` |
| `OCR_ENGINE` | `auto` / `tesseract` / `paddleocr` | `auto` |

- `StructureAnalyzer` - `GeometricStructureAnalyzer` (header / key-value /
  summary regions from block geometry and anchors) or `PPStructureV3Analyzer`
  (PaddleOCR 3.x `PPStructureV3`).
- `OCRService` - Tesseract or PaddleOCR (PP-OCRv5), both normalized to the same
  `Page`/`Block` model. With neither installed the pipeline degrades to manual
  entry rather than failing the upload.

### PP-StructureV3 findings (measured)

PP-StructureV3 **does install and run on this project's Python 3.13** - the
"no 3.13 wheels" limitation applied to PaddlePaddle 2.x and is gone in 3.x.
Verified end to end in a throwaway venv on Windows 11 / CPU:

```
python 3.13.5  ·  paddlepaddle 3.3.1  (cp313-win_amd64 wheel published)
paddleocr 3.7.0 + paddlex[ocr] 3.7.2  (pure-Python wheels, requires-python >=3.8)
```

Three caveats, all handled in code rather than by pinning a different Python:

1. **oneDNN must be off.** On the default oneDNN path, paddlepaddle 3.3.1
   raises `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not
   support [pir::ArrayAttribute<pir::DoubleAttribute>]` on Windows CPU. The
   adapter runs with `enable_mkldnn=False` (`PADDLE_ENABLE_MKLDNN`).
2. **PP-StructureV3's text detector must have its input capped.** The pipeline
   runs a general-OCR sub-pipeline (PP-OCRv5_server_det/rec) on every page
   unconditionally - paddlex 3.7.2 exposes no switch for it (`pipeline_v2.py`
   calls `self.general_ocr_pipeline(...)` outside any `model_settings` check) -
   and ships it with `limit_type: min`, i.e. *never downscale*. Above roughly
   1 MP, PP-OCRv5_server_det then aborts the interpreter with a native access
   violation in `paddlex/inference/models/text_detection/predictor.py`, killing
   the API worker with no Python traceback.

   Measured on `hotel-bill.jpg` (1653x1167), one process per row:

   | resize | input tensor | result |
   |---|---|---|
   | `max` / 1024 | 1024x736 | 26 boxes |
   | `max` / 1152 | 1152x800 | 26 boxes |
   | `max` / 1280 | 1280x896 | **access violation** |
   | `min` / 736 (PP-StructureV3's own default) | 1664x1152 | **access violation** |

   So the adapter passes `text_det_limit_type="max"` with a long side of
   `PADDLE_TEXT_DET_MAX_SIDE` (960, comfortably under the ceiling). Those
   detections only refine the layout boxes - the text this app extracts comes
   from the OCR service at full resolution - so the cap costs nothing here.
3. **Cost.** Per page on this hardware:

   | Stage | Default | `layout` | `ppstructure` |
   |---|---|---|---|
   | Layout analysis | 1.1 ms (geometric) | ~7 s | ~84 s |
   | OCR of a scan | 0.8 s (Tesseract) | ~50-90 s (PP-OCRv5) | ~50-90 s (PP-OCRv5) |

**What the full pipeline buys.** On the four original sample bills, extraction
output was identical for all three engines. On a photographed till receipt it is
not: PP-StructureV3 resolves 19 regions where the layout module alone finds 11,
and only it covers the merchant's name line (`paragraph_title`, y=131..182 on
`20260124_171938.jpg`) - the layout module leaves that line outside every
region, so it reaches the extractor as ordinary body text.

**Conclusion:** the geometric analyzer stays the active adapter for POC V1; the
extractor no longer depends on a layout model finding the masthead (it also
ranks the top band of the page by type size and reading order). The model stack
is one variable away for harder layouts:

```bash
pip install paddlepaddle==3.3.1 paddleocr==3.7.0 "paddlex[ocr]==3.7.2"
STRUCTURE_ENGINE=ppstructure OCR_ENGINE=paddleocr uvicorn app.main:app
```

Python 3.12 is **not** required: 3.3.1 ships cp39-cp313 wheels, all three
caveats above live in Paddle's native code rather than in the Python version,
and a second interpreter would fragment the project for no gain. The full stack
adds ~2.2 GB (1.1 GB packages + 1.1 GB downloaded models under `~/.paddlex`).


## Adding a claim head

Add a `ClaimHeadSchema` in `app/rules/` and register it in `CLAIM_HEADS`.
Fields declare their anchors, type, validation and whether they are required.
The pipeline, viewer, APIs and UI are schema-driven and need no changes.
