"""Async background job status endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/jobs", tags=["Async Jobs"])

_MOCK_JOB_STORE: dict[str, dict[str, Any]] = {}


@router.get("/{job_id}", summary="Get background job status")
def get_job_status(job_id: str) -> dict[str, Any]:
    """Retrieve status of an async custom paper generation job."""
    job = _MOCK_JOB_STORE.get(job_id)
    if not job:
        # Default mock status for testing
        return {
            "job_id": job_id,
            "status": "completed",
            "progress_pct": 100.0,
            "result_paper_id": f"paper_{job_id[-6:]}",
            "message": "Job completed successfully.",
        }
    return job
