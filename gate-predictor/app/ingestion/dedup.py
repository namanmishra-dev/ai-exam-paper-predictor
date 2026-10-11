"""Duplicate detection for questions.

Two-layer dedup:
1. Normalised text hash (SHA-256) — exact or near-exact text match
2. Embedding cosine similarity — semantic similarity check
"""

from __future__ import annotations

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DuplicateChecker:
    """Checks for duplicate questions before they enter analytics.

    Args:
        session: A SQLAlchemy session for DB queries.
        cosine_threshold: Minimum cosine similarity to flag as duplicate.
    """

    def __init__(
        self,
        session: Session,
        cosine_threshold: float | None = None,
    ) -> None:
        self._session = session
        self._cosine_threshold = cosine_threshold or settings.ingestion.dedup_cosine_threshold

    def check_text_hash(self, text_hash: str, exclude_id: str | None = None) -> bool:
        """Check if a question with the same text hash already exists.

        Args:
            text_hash: SHA-256 hash of the normalised question text.
            exclude_id: Question ID to exclude from the check (for updates).

        Returns:
            True if a duplicate hash exists.
        """
        query = "SELECT COUNT(*) FROM questions WHERE text_hash = :hash"
        params: dict[str, str] = {"hash": text_hash}
        if exclude_id:
            query += " AND id != :exclude_id"
            params["exclude_id"] = exclude_id

        result = self._session.execute(sql_text(query), params)
        count = result.scalar()
        if count and count > 0:
            logger.info("duplicate_hash_found", text_hash=text_hash[:16])
            return True
        return False

    def check_embedding_similarity(
        self, embedding: list[float], exclude_id: str | None = None
    ) -> tuple[bool, float]:
        """Check if a semantically similar question already exists.

        Uses pgvector cosine distance (1 - cosine_similarity).

        Args:
            embedding: The question's embedding vector.
            exclude_id: Question ID to exclude from the check.

        Returns:
            Tuple of (is_duplicate, max_similarity).
        """
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        query = (
            "SELECT id, 1 - (embedding <=> :emb::vector) AS similarity "
            "FROM questions "
            "WHERE embedding IS NOT NULL"
        )
        params: dict[str, str] = {"emb": embedding_str}

        if exclude_id:
            query += " AND id != :exclude_id"
            params["exclude_id"] = exclude_id

        query += " ORDER BY embedding <=> :emb2::vector LIMIT 1"
        params["emb2"] = embedding_str

        result = self._session.execute(sql_text(query), params)
        row = result.fetchone()

        if row is None:
            return False, 0.0

        similarity = float(row[1])  # type: ignore[arg-type]
        is_dup = similarity >= self._cosine_threshold

        if is_dup:
            logger.info(
                "duplicate_embedding_found",
                similar_id=row[0],
                similarity=round(similarity, 4),
                threshold=self._cosine_threshold,
            )

        return is_dup, similarity
