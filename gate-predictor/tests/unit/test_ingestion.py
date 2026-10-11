"""Tests for the PDF parser and ingestion pipeline."""

from __future__ import annotations

from app.core.llm_client import MockLLMClient
from app.ingestion.pdf_parser import PDFParser, parse_section_headers
from app.ingestion.provenance import build_provenance


class TestPDFParser:
    """Tests for PDF text extraction and question splitting."""

    def test_confidence_low_for_short_text(self) -> None:
        """Very short text should have low confidence."""
        parser = PDFParser()
        confidence = parser._compute_confidence("Hi", None, False)
        assert confidence < 0.8

    def test_confidence_penalty_for_figure(self) -> None:
        """Figure presence should reduce confidence."""
        parser = PDFParser()
        c_no_fig = parser._compute_confidence("Normal question text here", None, False)
        c_fig = parser._compute_confidence("Normal question text here", None, True)
        assert c_fig < c_no_fig

    def test_option_extraction(self) -> None:
        """Should extract options A-D from formatted text."""
        parser = PDFParser()
        text = """What is the output?
        (A) 10
        (B) 20
        (C) 30
        (D) 40"""
        options = parser._extract_options(text)
        assert options is not None
        assert len(options) == 4
        assert options["A"].strip() == "10"

    def test_option_extraction_returns_none_for_nat(self) -> None:
        """NAT questions without options should return None."""
        parser = PDFParser()
        text = "Calculate the value of x + y."
        options = parser._extract_options(text)
        assert options is None


class TestProvenance:
    """Tests for provenance tracking."""

    def test_build_provenance_complete(self) -> None:
        """Provenance should include all required fields."""
        prov = build_provenance(
            raw_file="GATE_CS_2023.pdf",
            answer_key_file="GATE_CS_2023_AK.pdf",
            page=5,
            extraction_method="pymupdf",
            confidence=0.92,
        )

        assert prov["raw_file"] == "GATE_CS_2023.pdf"
        assert prov["answer_key_file"] == "GATE_CS_2023_AK.pdf"
        assert prov["page"] == 5
        assert prov["extraction_method"] == "pymupdf"
        assert prov["confidence"] == 0.92
        assert "ingested_at" in prov

    def test_build_provenance_no_answer_key(self) -> None:
        """Provenance without answer key should omit that field."""
        prov = build_provenance(
            raw_file="test.pdf",
            answer_key_file=None,
            page=1,
            extraction_method="pdfplumber",
            confidence=0.8,
        )
        assert "answer_key_file" not in prov

    def test_build_provenance_extra_metadata(self) -> None:
        """Extra metadata should be merged into provenance."""
        prov = build_provenance(
            raw_file="test.pdf",
            answer_key_file=None,
            page=1,
            extraction_method="claude_vision",
            confidence=0.6,
            extra={"vision_model": "claude-3-5-sonnet"},
        )
        assert prov["vision_model"] == "claude-3-5-sonnet"
