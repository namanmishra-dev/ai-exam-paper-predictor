"""CLI script to seed the taxonomy from YAML into the database.

Usage:
    python -m scripts.seed_taxonomy --subject operating_systems
    python -m scripts.seed_taxonomy --subject operating_systems --taxonomy-path data/taxonomy.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import get_session
from app.tagging.taxonomy import load_taxonomy, seed_all_subjects, seed_taxonomy

logger = get_logger(__name__)


def main() -> None:
    """Seed the taxonomy into the database."""
    parser = argparse.ArgumentParser(description="Seed GATE CS taxonomy into the database")
    parser.add_argument(
        "--subject",
        type=str,
        required=True,
        help="Target subject ID (e.g. operating_systems)",
    )
    parser.add_argument(
        "--taxonomy-path",
        type=str,
        default=None,
        help="Path to taxonomy.yaml (default: data/taxonomy.yaml)",
    )
    args = parser.parse_args()

    setup_logging(settings.app.log_level)

    taxonomy_path = Path(args.taxonomy_path) if args.taxonomy_path else settings.taxonomy_path

    logger.info("seeding_taxonomy", subject=args.subject, path=str(taxonomy_path))

    # Load and validate taxonomy
    taxonomy_data = load_taxonomy(taxonomy_path)

    with get_session() as session:
        # Seed all GATE CS subjects (for FK references)
        seed_all_subjects(session)

        # Seed the detailed taxonomy for the target subject
        seed_taxonomy(session, taxonomy_data)

    logger.info("taxonomy_seeded_successfully", subject=args.subject)
    print(f"✓ Taxonomy seeded for subject: {args.subject}")


if __name__ == "__main__":
    main()
