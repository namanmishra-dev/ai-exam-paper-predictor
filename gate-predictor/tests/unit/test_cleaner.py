"""Tests for the answer key parser, question cleaner, and marks extraction.

Covers:
- qtype detection from answer key (MCQ, MSQ, NAT)
- marks derivation from section headers
- MTA, NAT range, multiple-correct answers
- Text normalisation and SHA-256 dedup hash
"""

from __future__ import annotations

from app.ingestion.cleaner import AnswerKeyParser, QuestionCleaner


class TestAnswerKeyParser:
    """Tests for qtype detection from answer key format."""

    def setup_method(self) -> None:
        self.parser = AnswerKeyParser()

    def test_single_letter_is_mcq(self) -> None:
        """A single letter answer should be classified as MCQ."""
        entry = self.parser._parse_single_answer(1, "A")
        assert entry is not None
        assert entry.qtype == "MCQ"
        assert entry.answer == {"correct": ["A"]}
        assert entry.is_mta is False

    def test_single_letter_lowercase_is_mcq(self) -> None:
        """Lowercase letters should be normalised to uppercase MCQ."""
        entry = self.parser._parse_single_answer(2, "c")
        assert entry is not None
        assert entry.qtype == "MCQ"
        assert entry.answer == {"correct": ["C"]}

    def test_multiple_letters_comma_separated_is_msq(self) -> None:
        """Multiple comma-separated letters → MSQ."""
        entry = self.parser._parse_single_answer(3, "A, C")
        assert entry is not None
        assert entry.qtype == "MSQ"
        assert set(entry.answer["correct"]) == {"A", "C"}

    def test_multiple_letters_semicolon_separated_is_msq(self) -> None:
        """Multiple semicolon-separated letters → MSQ."""
        entry = self.parser._parse_single_answer(4, "B;D")
        assert entry is not None
        assert entry.qtype == "MSQ"
        assert set(entry.answer["correct"]) == {"B", "D"}

    def test_numeric_single_is_nat(self) -> None:
        """A single numeric value → NAT."""
        entry = self.parser._parse_single_answer(5, "42")
        assert entry is not None
        assert entry.qtype == "NAT"
        assert entry.answer["exact"] == 42.0

    def test_numeric_float_is_nat(self) -> None:
        """A floating-point value → NAT."""
        entry = self.parser._parse_single_answer(6, "3.14")
        assert entry is not None
        assert entry.qtype == "NAT"
        assert abs(entry.answer["exact"] - 3.14) < 0.001

    def test_nat_range(self) -> None:
        """A range like '4.5 to 4.7' → NAT with range."""
        entry = self.parser._parse_single_answer(7, "4.5 to 4.7")
        assert entry is not None
        assert entry.qtype == "NAT"
        assert entry.answer["range_low"] == 4.5
        assert entry.answer["range_high"] == 4.7
        assert abs(entry.answer["exact"] - 4.6) < 0.001

    def test_mta_marks_to_all(self) -> None:
        """'Marks to All' → MCQ with mta=True."""
        entry = self.parser._parse_single_answer(8, "Marks to All")
        assert entry is not None
        assert entry.qtype == "MCQ"
        assert entry.is_mta is True
        assert entry.answer == {"mta": True}

    def test_mta_abbreviation(self) -> None:
        """'MTA' abbreviation → MCQ with mta=True."""
        entry = self.parser._parse_single_answer(9, "MTA")
        assert entry is not None
        assert entry.is_mta is True

    def test_negative_nat(self) -> None:
        """Negative numeric value → NAT."""
        entry = self.parser._parse_single_answer(10, "-7.5")
        assert entry is not None
        assert entry.qtype == "NAT"
        assert entry.answer["exact"] == -7.5


class TestSectionHeaderParsing:
    """Tests for marks derivation from section headers."""

    def test_standard_gate_sections(self) -> None:
        """Parse standard GATE section headers."""
        from app.ingestion.pdf_parser import parse_section_headers

        text = (
            "Q.1 - Q.25 carry 1 mark each\n"
            "Q.26 - Q.55 carry 2 marks each\n"
        )
        marks_map = parse_section_headers(text)

        assert marks_map[1] == 1
        assert marks_map[25] == 1
        assert marks_map[26] == 2
        assert marks_map[55] == 2

    def test_full_gate_paper_sections(self) -> None:
        """Parse all sections including GA."""
        from app.ingestion.pdf_parser import parse_section_headers

        text = (
            "Q.1 to Q.25 carry 1 mark each\n"
            "Q.26 to Q.55 carry 2 marks each\n"
            "Q.56 to Q.60 carry 1 mark each\n"
            "Q.61 to Q.65 carry 2 marks each\n"
        )
        marks_map = parse_section_headers(text)

        # Verify total: 25*1 + 30*2 + 5*1 + 5*2 = 25+60+5+10 = 100
        total_marks = sum(marks_map.values())
        assert total_marks == 100
        assert len(marks_map) == 65


class TestQuestionCleaner:
    """Tests for text normalisation and hash computation."""

    def setup_method(self) -> None:
        self.cleaner = QuestionCleaner()

    def test_text_hash_deterministic(self) -> None:
        """Same text → same hash."""
        hash1 = QuestionCleaner.compute_text_hash("What is a mutex?")
        hash2 = QuestionCleaner.compute_text_hash("What is a mutex?")
        assert hash1 == hash2

    def test_text_hash_ignores_whitespace(self) -> None:
        """Normalised hash ignores whitespace differences."""
        hash1 = QuestionCleaner.compute_text_hash("What is a mutex?")
        hash2 = QuestionCleaner.compute_text_hash("  What   is  a   mutex?  ")
        assert hash1 == hash2

    def test_text_hash_ignores_case(self) -> None:
        """Normalised hash ignores case differences."""
        hash1 = QuestionCleaner.compute_text_hash("What is a MUTEX?")
        hash2 = QuestionCleaner.compute_text_hash("what is a mutex?")
        assert hash1 == hash2

    def test_text_hash_length(self) -> None:
        """Hash is SHA-256, always 64 hex chars."""
        h = QuestionCleaner.compute_text_hash("test")
        assert len(h) == 64

    def test_different_text_different_hash(self) -> None:
        """Different texts → different hashes."""
        hash1 = QuestionCleaner.compute_text_hash("What is a mutex?")
        hash2 = QuestionCleaner.compute_text_hash("What is a semaphore?")
        assert hash1 != hash2

    def test_clean_and_merge_review_needed(self) -> None:
        """Low-confidence parse or missing answer key → review_needed."""
        from app.ingestion.cleaner import AnswerKeyEntry

        cleaned = self.cleaner.clean_and_merge(
            question_no=1,
            raw_text="Test question",
            raw_options=None,
            answer_entry=None,  # No answer key match
            marks_map={1: 1},
            has_figure=False,
            parse_confidence=0.5,
        )
        assert cleaned.parse_status == "review_needed"

    def test_clean_and_merge_parsed(self) -> None:
        """High-confidence parse with answer key → parsed."""
        from app.ingestion.cleaner import AnswerKeyEntry

        ak = AnswerKeyEntry(
            question_no=1, raw_answer="A", qtype="MCQ",
            answer={"correct": ["A"]},
        )
        cleaned = self.cleaner.clean_and_merge(
            question_no=1,
            raw_text="What is the time complexity of binary search?",
            raw_options={"A": "O(n)", "B": "O(log n)", "C": "O(n²)", "D": "O(1)"},
            answer_entry=ak,
            marks_map={1: 1},
            has_figure=False,
            parse_confidence=0.95,
        )
        assert cleaned.parse_status == "parsed"
        assert cleaned.qtype == "MCQ"
        assert cleaned.marks == 1
