"""Health check endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Application health check")
def health_check() -> dict[str, Any]:
    """Return API health status."""
    return {
        "status": "healthy",
        "service": "GATE PYQ Analyzer & Mock Paper Generator",
        "version": "1.0.0",
    }
