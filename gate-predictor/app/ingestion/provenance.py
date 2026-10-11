"""Provenance tracking for ingested questions.

Every question is traceable to its source: year, set, question number,
original file path, page number, and extraction method.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_provenance(
    raw_file: str,
    answer_key_file: str | None,
    page: int,
    extraction_method: str,
    confidence: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a provenance JSONB dict for a question record.

    Args:
        raw_file: Filename of the source question paper PDF.
        answer_key_file: Filename of the matching answer key PDF, if any.
        page: Page number where the question was found (1-indexed).
        extraction_method: "pymupdf", "pdfplumber", or "claude_vision".
        confidence: Parser confidence score (0.0–1.0).
        extra: Additional metadata to include.

    Returns:
        A dict suitable for storing in the ``provenance`` JSONB column.
    """
    prov: dict[str, Any] = {
        "raw_file": raw_file,
        "page": page,
        "extraction_method": extraction_method,
        "confidence": round(confidence, 4),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    if answer_key_file:
        prov["answer_key_file"] = answer_key_file
    if extra:
        prov.update(extra)
    return prov
