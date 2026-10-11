"""API v1 router bundle."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import ai_study, health, jobs, mock_papers, subjects

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health.router)
api_v1_router.include_router(subjects.router)
api_v1_router.include_router(mock_papers.router)
api_v1_router.include_router(jobs.router)
api_v1_router.include_router(ai_study.router)
