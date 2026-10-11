"""Golden tests using real GATE page structures.

These tests validate the parser against realistic GATE question formats.
They use synthetic text that mirrors the actual layout of GATE CS papers.

To add tests with REAL GATE PDF pages:
1. Place 1-2 real pages as PDF files in tests/fixtures/golden/
2. Add the expected question count, marks, and qtypes as assertions

The synthetic fixtures below cover the most common GATE page layouts.
"""

from __future__ import annotations

import pytest

from app.ingestion.cleaner import AnswerKeyParser, QuestionCleaner
from app.ingestion.pdf_parser import parse_section_headers


@pytest.mark.golden
class TestGoldenGatePages:
    """Golden tests with realistic GATE page structures."""

    # ── Synthetic GATE page: 1-mark MCQ section ────────────────────────
    GATE_PAGE_1_MARK = """
GATE 2023 Computer Science and Information Technology (CS)

Q.1 – Q.25 carry 1 mark each

Q.1 Consider three processes P1, P2, and P3 with burst times 24, 3, and 3
milliseconds respectively. If the processes arrive in the order P1, P2, P3 and
FCFS scheduling is used, the average waiting time is _____ milliseconds.
(A) 17
(B) 3
(C) 0
(D) 10

Q.2 Which of the following page replacement algorithms suffers from Belady's
anomaly?
(A) Optimal
(B) LRU
(C) FIFO
(D) LFU

Q.3 The maximum number of processes that can be in the ready state for a system
with n CPUs is:
(A) n
(B) n - 1
(C) n + 1
(D) unlimited
"""

    # ── Synthetic GATE page: 2-mark MCQ/NAT section ────────────────────
    GATE_PAGE_2_MARK = """
Q.26 – Q.55 carry 2 marks each

Q.26 Consider a system with 5 processes P0–P4 and 3 resource types A, B, C.
Allocation is: P0(0,1,0), P1(2,0,0), P2(3,0,2), P3(2,1,1), P4(0,0,2).
Maximum need is: P0(7,5,3), P1(3,2,2), P2(9,0,2), P3(2,2,2), P4(4,3,3).
Available resources are (3,3,2). Using the Banker's Algorithm, is the system
in a safe state?
(A) Yes, with safe sequence <P1, P3, P4, P0, P2>
(B) Yes, with safe sequence <P1, P3, P4, P2, P0>
(C) No, the system is in an unsafe state
(D) Cannot be determined

Q.27 In a demand paging system with page size 4 KB and 3 frames, the page
reference string is: 7, 0, 1, 2, 0, 3, 0, 4, 2, 3. Using the LRU page
replacement policy, the total number of page faults is __________.
"""

    # ── Synthetic answer key ───────────────────────────────────────────
    ANSWER_KEY_TEXT = """
Question Answer
1       A
2       C
3       D
26      A
27      8
"""

    def test_section_header_extraction(self) -> None:
        """Section headers should correctly map question ranges to marks."""
        combined = self.GATE_PAGE_1_MARK + "\n" + self.GATE_PAGE_2_MARK
        marks_map = parse_section_headers(combined)

        assert marks_map.get(1) == 1
        assert marks_map.get(25) == 1
        assert marks_map.get(26) == 2
        assert marks_map.get(55) == 2

    def test_answer_key_qtype_detection(self) -> None:
        """Answer key format determines qtype: letter=MCQ, number=NAT."""
        parser = AnswerKeyParser()

        # Manually test the single-answer parser
        mcq_entry = parser._parse_single_answer(1, "A")
        assert mcq_entry is not None
        assert mcq_entry.qtype == "MCQ"
        assert mcq_entry.answer == {"correct": ["A"]}

        nat_entry = parser._parse_single_answer(27, "8")
        assert nat_entry is not None
        assert nat_entry.qtype == "NAT"
        assert nat_entry.answer["exact"] == 8.0

    def test_full_gate_paper_marks_assertion(self) -> None:
        """A full GATE paper should have 65 questions totalling 100 marks.

        This validates the section header parsing produces the correct total.
        """
        full_paper_headers = (
            "Q.1 – Q.25 carry 1 mark each\n"
            "Q.26 – Q.55 carry 2 marks each\n"
            "Q.56 – Q.60 carry 1 mark each\n"
            "Q.61 – Q.65 carry 2 marks each\n"
        )
        marks_map = parse_section_headers(full_paper_headers)

        assert len(marks_map) == 65, f"Expected 65 questions, got {len(marks_map)}"
        total_marks = sum(marks_map.values())
        assert total_marks == 100, f"Expected 100 marks, got {total_marks}"

    def test_text_hash_consistency_across_formats(self) -> None:
        """Same question with different whitespace → same hash."""
        q1 = "Consider three processes P1, P2, and P3 with burst times 24, 3, and 3"
        q2 = "Consider  three  processes P1, P2, and P3  with burst times 24, 3, and  3"

        h1 = QuestionCleaner.compute_text_hash(q1)
        h2 = QuestionCleaner.compute_text_hash(q2)
        assert h1 == h2

    def test_nat_range_answer(self) -> None:
        """NAT answers with ranges should be parsed correctly."""
        parser = AnswerKeyParser()
        entry = parser._parse_single_answer(30, "2.5 to 2.7")
        assert entry is not None
        assert entry.qtype == "NAT"
        assert entry.answer["range_low"] == 2.5
        assert entry.answer["range_high"] == 2.7
