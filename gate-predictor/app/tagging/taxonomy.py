"""Taxonomy loader and validator.

Loads a two-level topic taxonomy from YAML and seeds the database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.core.exceptions import TaxonomyError
from app.core.logging import get_logger
from app.db.models.subject import Subject, Topic

logger = get_logger(__name__)


def load_taxonomy(yaml_path: Path) -> dict[str, Any]:
    """Load and validate a taxonomy YAML file.

    Args:
        yaml_path: Path to the taxonomy.yaml file.

    Returns:
        The parsed taxonomy dict.

    Raises:
        TaxonomyError: If the file is missing or invalid.
    """
    if not yaml_path.exists():
        raise TaxonomyError(f"Taxonomy file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "subject" not in data:
        raise TaxonomyError("Taxonomy YAML must have a top-level 'subject' key")

    subject = data["subject"]
    required_keys = {"id", "name", "code", "topics"}
    missing = required_keys - set(subject.keys())
    if missing:
        raise TaxonomyError(f"Subject missing required keys: {missing}")

    # Validate topics
    seen_ids: set[str] = set()
    seen_codes: set[str] = set()
    for topic in subject.get("topics", []):
        _validate_topic(topic, seen_ids, seen_codes)
        for subtopic in topic.get("subtopics", []):
            _validate_topic(subtopic, seen_ids, seen_codes)

    logger.info(
        "taxonomy_loaded",
        subject=subject["id"],
        topic_count=len(subject["topics"]),
        total_entries=len(seen_ids),
    )

    return data  # type: ignore[no-any-return]


def _validate_topic(topic: dict[str, Any], seen_ids: set[str], seen_codes: set[str]) -> None:
    """Validate a single topic entry for required keys and uniqueness."""
    for key in ("id", "name", "code"):
        if key not in topic:
            raise TaxonomyError(f"Topic missing required key '{key}': {topic}")

    if topic["id"] in seen_ids:
        raise TaxonomyError(f"Duplicate topic ID: {topic['id']}")
    if topic["code"] in seen_codes:
        raise TaxonomyError(f"Duplicate topic code: {topic['code']}")

    seen_ids.add(topic["id"])
    seen_codes.add(topic["code"])


def get_taxonomy_tree(taxonomy_data: dict[str, Any]) -> dict[str, Any]:
    """Convert taxonomy data to a flat tree dict for LLM prompts.

    Returns a dict mapping topic_id → {name, code, subtopics: [{id, name, code}]}.

    Args:
        taxonomy_data: The parsed taxonomy YAML data.

    Returns:
        A dict suitable for including in LLM prompts.
    """
    tree: dict[str, Any] = {}
    subject = taxonomy_data["subject"]

    for topic in subject.get("topics", []):
        subtopics = []
        for st in topic.get("subtopics", []):
            subtopics.append({
                "id": st["id"],
                "name": st["name"],
                "code": st["code"],
            })
        tree[topic["id"]] = {
            "name": topic["name"],
            "code": topic["code"],
            "subtopics": subtopics,
        }

    return tree


def seed_taxonomy(session: Session, taxonomy_data: dict[str, Any]) -> None:
    """Idempotently seed subjects and topics from taxonomy data.

    Args:
        session: A SQLAlchemy session.
        taxonomy_data: Parsed taxonomy YAML data.
    """
    subject_data = taxonomy_data["subject"]

    # Upsert subject
    existing_subject = session.get(Subject, subject_data["id"])
    if existing_subject is None:
        subject = Subject(
            id=subject_data["id"],
            name=subject_data["name"],
            code=subject_data["code"],
            description=subject_data.get("description", ""),
        )
        session.add(subject)
        logger.info("subject_seeded", id=subject_data["id"])
    else:
        existing_subject.name = subject_data["name"]
        existing_subject.code = subject_data["code"]
        logger.info("subject_updated", id=subject_data["id"])

    session.flush()

    # Seed topics (two levels)
    order = 0
    for topic_data in subject_data.get("topics", []):
        order += 1
        _upsert_topic(
            session,
            topic_id=topic_data["id"],
            subject_id=subject_data["id"],
            parent_id=None,
            name=topic_data["name"],
            code=topic_data["code"],
            syllabus_order=order,
        )

        for subtopic_data in topic_data.get("subtopics", []):
            order += 1
            _upsert_topic(
                session,
                topic_id=subtopic_data["id"],
                subject_id=subject_data["id"],
                parent_id=topic_data["id"],
                name=subtopic_data["name"],
                code=subtopic_data["code"],
                syllabus_order=order,
            )

    logger.info("taxonomy_seeded", subject=subject_data["id"], topics_count=order)


def seed_all_subjects(session: Session) -> None:
    """Seed all GATE CS subject entries (without detailed topics).

    This ensures the subjects table has entries for all classified subjects
    so foreign key constraints are satisfied.
    """
    subjects = [
        ("operating_systems", "Operating Systems", "CS-OS"),
        ("data_structures", "Data Structures", "CS-DS"),
        ("algorithms", "Algorithms", "CS-AL"),
        ("databases", "Databases", "CS-DB"),
        ("computer_networks", "Computer Networks", "CS-CN"),
        ("compiler_design", "Compiler Design", "CS-CD"),
        ("theory_of_computation", "Theory of Computation", "CS-TOC"),
        ("digital_logic", "Digital Logic", "CS-DL"),
        ("computer_organization", "Computer Organization & Architecture", "CS-COA"),
        ("programming_languages", "Programming Languages", "CS-PL"),
        ("software_engineering", "Software Engineering", "CS-SE"),
        ("engineering_mathematics", "Engineering Mathematics", "CS-EM"),
        ("general_aptitude", "General Aptitude", "CS-GA"),
    ]

    for sid, name, code in subjects:
        existing = session.get(Subject, sid)
        if existing is None:
            session.add(Subject(id=sid, name=name, code=code))
            logger.info("subject_seeded", id=sid)

    session.flush()


def _upsert_topic(
    session: Session,
    topic_id: str,
    subject_id: str,
    parent_id: str | None,
    name: str,
    code: str,
    syllabus_order: int,
) -> None:
    """Insert or update a single topic."""
    existing = session.get(Topic, topic_id)
    if existing is None:
        session.add(Topic(
            id=topic_id,
            subject_id=subject_id,
            parent_topic_id=parent_id,
            name=name,
            code=code,
            syllabus_order=syllabus_order,
        ))
    else:
        existing.name = name
        existing.code = code
        existing.parent_topic_id = parent_id
        existing.syllabus_order = syllabus_order
