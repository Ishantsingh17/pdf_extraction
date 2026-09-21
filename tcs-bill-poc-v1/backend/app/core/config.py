"""Application configuration for POC V1."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Settings come from backend/.env, overridden by real environment
    # variables. The path is absolute so it is found whatever the working
    # directory, and names are case-insensitive (STRUCTURE_ENGINE = structure_engine).
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TCS Claim Extractor - POC V1"
    api_prefix: str = "/api/v1"

    # Storage. The original uploaded file is always retained: the review screen
    # must render the exact document the user uploaded.
    data_dir: Path = PROJECT_ROOT / "data"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'poc.db').as_posix()}"

    # Upload validation
    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB, as shown on the upload screen
    allowed_extensions: tuple[str, ...] = ("pdf", "jpg", "jpeg", "png")
    allowed_mime_types: tuple[str, ...] = (
        "application/pdf",
        "image/jpeg",
        "image/png",
    )

    # A PDF page needs at least this many characters of selectable text before
    # we trust its text layer and skip OCR.
    min_chars_for_text_layer: int = 40

    # OCR engine: auto | tesseract | paddleocr. "auto" prefers Tesseract for
    # speed and falls back to PaddleOCR when it is the only one installed.
    ocr_engine: str = "auto"

    # Layout/structure engine: geometric | layout | ppstructure | auto.
    #   geometric   - block geometry and anchors, ~1ms/page (default)
    #   layout      - PP-DocLayout_plus-L on its own, ~7s/page
    #   ppstructure - the full PP-StructureV3 pipeline, ~84s/page, finest regions
    # POC V1 ships with the geometric analyzer active and leaves the model
    # stack opt-in (see README).
    structure_engine: str = "geometric"
    #: paddlepaddle 3.3.1 crashes in its oneDNN path on Windows CPU; the
    #: Paddle layout adapter therefore runs with oneDNN disabled.
    paddle_enable_mkldnn: bool = False
    #: Longest side, in pixels, of the image handed to PP-StructureV3's text
    #: detector. Above ~1 MP, PP-OCRv5_server_det takes paddlepaddle 3.3.1 down
    #: with an access violation on Windows CPU (measured: 1152x800 fine,
    #: 1280x896 crashes), so its input is capped well under that.
    paddle_text_det_max_side: int = 960

    # Confidence thresholds (TRD section 11) - configurable, calibrated in testing.
    confidence_high: float = 0.90
    confidence_review: float = 0.70

    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
