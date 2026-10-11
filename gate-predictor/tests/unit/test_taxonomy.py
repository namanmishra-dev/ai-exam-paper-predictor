"""Tests for taxonomy YAML loading, validation, and database seeding."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from app.core.exceptions import TaxonomyError
from app.tagging.taxonomy import get_taxonomy_tree, load_taxonomy, seed_all_subjects, seed_taxonomy


class TestLoadTaxonomy:
    """Tests for YAML loading and validation."""

    def test_load_valid_taxonomy(self, sample_taxonomy: dict, tmp_path: Path) -> None:
        """A valid taxonomy YAML loads without errors."""
        yaml_path = tmp_path / "taxonomy.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(sample_taxonomy, f)

        data = load_taxonomy(yaml_path)
        assert data["subject"]["id"] == "operating_systems"
        assert len(data["subject"]["topics"]) == 2

    def test_missing_file_raises(self) -> None:
        """Missing file → TaxonomyError."""
        with pytest.raises(TaxonomyError, match="not found"):
            load_taxonomy(Path("/nonexistent/taxonomy.yaml"))

    def test_missing_subject_key_raises(self, tmp_path: Path) -> None:
        """YAML without 'subject' key → TaxonomyError."""
        yaml_path = tmp_path / "bad.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump({"topics": []}, f)

        with pytest.raises(TaxonomyError, match="subject"):
            load_taxonomy(yaml_path)

    def test_duplicate_topic_id_raises(self, tmp_path: Path) -> None:
        """Duplicate topic IDs → TaxonomyError."""
        data = {
            "subject": {
                "id": "test",
                "name": "Test",
                "code": "T",
                "topics": [
                    {"id": "dup", "name": "A", "code": "A", "subtopics": []},
                    {"id": "dup", "name": "B", "code": "B", "subtopics": []},
                ],
            },
        }
        yaml_path = tmp_path / "dup.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(data, f)

        with pytest.raises(TaxonomyError, match="Duplicate topic ID"):
            load_taxonomy(yaml_path)

    def test_duplicate_topic_code_raises(self, tmp_path: Path) -> None:
        """Duplicate topic codes → TaxonomyError."""
        data = {
            "subject": {
                "id": "test",
                "name": "Test",
                "code": "T",
                "topics": [
                    {"id": "a", "name": "A", "code": "SAME", "subtopics": []},
                    {"id": "b", "name": "B", "code": "SAME", "subtopics": []},
                ],
            },
        }
        yaml_path = tmp_path / "dup_code.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(data, f)

        with pytest.raises(TaxonomyError, match="Duplicate topic code"):
            load_taxonomy(yaml_path)


class TestGetTaxonomyTree:
    """Tests for converting taxonomy data to a flat tree for LLM prompts."""

    def test_tree_structure(self, sample_taxonomy: dict) -> None:
        """Tree should map topic_id → {name, code, subtopics: [...]}."""
        tree = get_taxonomy_tree(sample_taxonomy)

        assert "os_cpu_scheduling" in tree
        assert tree["os_cpu_scheduling"]["name"] == "CPU Scheduling"
        assert len(tree["os_cpu_scheduling"]["subtopics"]) == 1
        assert tree["os_cpu_scheduling"]["subtopics"][0]["id"] == "os_sched_algos"


@pytest.mark.integration
class TestSeedTaxonomy:
    """Integration tests for database seeding (requires real Postgres)."""

    def test_seed_all_subjects(self, db_session) -> None:
        """seed_all_subjects creates all GATE CS subject entries."""
        seed_all_subjects(db_session)
        db_session.flush()

        from app.db.models.subject import Subject

        subjects = db_session.query(Subject).all()
        subject_ids = {s.id for s in subjects}

        assert "operating_systems" in subject_ids
        assert "data_structures" in subject_ids
        assert "general_aptitude" in subject_ids
        assert len(subjects) >= 13

    def test_seed_taxonomy_idempotent(self, db_session, sample_taxonomy: dict) -> None:
        """Seeding twice should not create duplicates."""
        seed_all_subjects(db_session)
        seed_taxonomy(db_session, sample_taxonomy)
        db_session.flush()

        # Seed again
        seed_taxonomy(db_session, sample_taxonomy)
        db_session.flush()

        from app.db.models.subject import Topic

        topics = db_session.query(Topic).filter(Topic.subject_id == "operating_systems").all()
        topic_ids = [t.id for t in topics]
        # Should have unique IDs
        assert len(topic_ids) == len(set(topic_ids))
