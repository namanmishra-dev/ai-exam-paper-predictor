"""LLM client abstraction layer.

Defines an abstract ``LLMClient`` interface that is injected into all modules
that need LLM capabilities. Concrete implementations wrap the Anthropic SDK.
A ``MockLLMClient`` is provided for deterministic testing without SDK patching.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.core.config import settings
from app.core.exceptions import LLMClientError
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Response DTOs ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SubjectClassification:
    """Result of classifying a question into a GATE CS subject area."""

    classified_subject: str  # e.g. "operating_systems", "general_aptitude"
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class TopicTagResult:
    """Result of tagging a question with topic/subtopic/difficulty."""

    topic_id: str
    subtopic_id: str | None
    difficulty: str  # "easy" | "medium" | "hard"
    confidence: float
    reasoning: str


@dataclass(frozen=True)
class VisionExtractionResult:
    """Result of extracting text from an image via Claude vision."""

    extracted_text: str
    questions_json: list[dict[str, Any]]
    confidence: float


# ── Abstract Interface ───────────────────────────────────────────────────────


class LLMClient(ABC):
    """Abstract LLM client interface.

    All modules that need LLM capabilities accept an ``LLMClient`` instance
    via dependency injection. This avoids tight coupling to the Anthropic SDK
    and makes testing trivial via ``MockLLMClient``.
    """

    @abstractmethod
    def classify_subject(
        self,
        question_text: str,
        options: dict[str, str] | None,
        available_subjects: list[str],
    ) -> SubjectClassification:
        """Classify a question into one of the available GATE CS subjects.

        Args:
            question_text: The full question text.
            options: Option dict (A/B/C/D) if MCQ/MSQ, None for NAT.
            available_subjects: List of valid subject IDs.

        Returns:
            A SubjectClassification with the classified subject and confidence.
        """

    @abstractmethod
    def tag_question(
        self,
        question_text: str,
        options: dict[str, str] | None,
        taxonomy: dict[str, Any],
        subject_id: str,
    ) -> TopicTagResult:
        """Tag a question with topic, subtopic, and difficulty.

        Args:
            question_text: The full question text.
            options: Option dict if applicable.
            taxonomy: The taxonomy tree dict for the target subject.
            subject_id: The subject this question belongs to.

        Returns:
            A TopicTagResult with topic_id, subtopic_id, difficulty, confidence.
        """

    @abstractmethod
    def extract_with_vision(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> VisionExtractionResult:
        """Extract structured question data from a page image using Claude vision."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Execute a text completion prompt.

        Args:
            prompt: User prompt text.
            system: System prompt text.

        Returns:
            The raw text response from the model.
        """


# ── Anthropic Implementation ────────────────────────────────────────────────


class AnthropicLLMClient(LLMClient):
    """Production LLM client wrapping the Anthropic Claude SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self._api_key = api_key or settings.llm.anthropic_api_key
        self._model_id = model_id or settings.llm.anthropic_model_id
        self._max_tokens = max_tokens or settings.llm.anthropic_max_tokens
        self._temperature = temperature if temperature is not None else settings.llm.anthropic_temperature
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def _call(self, system: str, user: str) -> str:
        """Make a single Claude API call and return the text response."""
        try:
            response = self._client.messages.create(
                model=self._model_id,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text  # type: ignore[union-attr]
        except anthropic.APIError as e:
            logger.error("anthropic_api_error", error=str(e))
            raise LLMClientError(f"Anthropic API error: {e}") from e

    def _call_vision(self, system: str, image_bytes: bytes, media_type: str, prompt: str) -> str:
        """Make a Claude API call with an image input."""
        import base64

        b64_image = base64.standard_b64encode(image_bytes).decode("utf-8")
        try:
            response = self._client.messages.create(
                model=self._model_id,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_image,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.content[0].text  # type: ignore[union-attr]
        except anthropic.APIError as e:
            logger.error("anthropic_vision_error", error=str(e))
            raise LLMClientError(f"Anthropic vision API error: {e}") from e

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Extract and parse JSON from an LLM response.

        Handles responses that wrap JSON in markdown code fences.
        """
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json) and last line (```)
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```") and not inside:
                    inside = True
                    continue
                if line.strip() == "```" and inside:
                    break
                if inside:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        return json.loads(cleaned)  # type: ignore[no-any-return]

    def classify_subject(
        self,
        question_text: str,
        options: dict[str, str] | None,
        available_subjects: list[str],
    ) -> SubjectClassification:
        """Classify a question into a GATE CS subject area."""
        subjects_str = ", ".join(available_subjects)
        options_str = ""
        if options:
            options_str = "\n".join(f"  ({k}) {v}" for k, v in options.items())
            options_str = f"\nOptions:\n{options_str}"

        system = (
            "You are an expert GATE Computer Science question classifier. "
            "Classify the given question into exactly ONE of the provided subjects. "
            "Respond ONLY with valid JSON matching this schema: "
            '{"classified_subject": "<subject_id>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}'
        )
        user = (
            f"Available subjects: {subjects_str}\n\n"
            f"Question:\n{question_text}{options_str}\n\n"
            "Classify this question. Return ONLY the JSON."
        )

        raw = self._call(system, user)
        data = self._parse_json(raw)
        return SubjectClassification(
            classified_subject=data["classified_subject"],
            confidence=float(data["confidence"]),
            reasoning=data.get("reasoning", ""),
        )

    def tag_question(
        self,
        question_text: str,
        options: dict[str, str] | None,
        taxonomy: dict[str, Any],
        subject_id: str,
    ) -> TopicTagResult:
        """Tag a question with topic, subtopic, and difficulty."""
        taxonomy_str = json.dumps(taxonomy, indent=2)
        options_str = ""
        if options:
            options_str = "\n".join(f"  ({k}) {v}" for k, v in options.items())
            options_str = f"\nOptions:\n{options_str}"

        system = (
            "You are an expert GATE CS question tagger. Given a question and a taxonomy, "
            "identify the most specific topic and subtopic. If the question does not belong "
            "to any topic in the taxonomy, use topic_id='out_of_scope' and subtopic_id=null. "
            "Rate difficulty as 'easy', 'medium', or 'hard'. "
            "Respond ONLY with valid JSON: "
            '{"topic_id": "<id>", "subtopic_id": "<id_or_null>", '
            '"difficulty": "<easy|medium|hard>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}'
        )
        user = (
            f"Subject: {subject_id}\n\n"
            f"Taxonomy:\n{taxonomy_str}\n\n"
            f"Question:\n{question_text}{options_str}\n\n"
            "Tag this question. Return ONLY the JSON."
        )

        raw = self._call(system, user)
        data = self._parse_json(raw)
        subtopic = data.get("subtopic_id")
        if subtopic == "null" or subtopic is None:
            subtopic = None
        return TopicTagResult(
            topic_id=data["topic_id"],
            subtopic_id=subtopic,
            difficulty=data["difficulty"],
            confidence=float(data["confidence"]),
            reasoning=data.get("reasoning", ""),
        )

    def extract_with_vision(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> VisionExtractionResult:
        """Extract structured question data from a scanned page image."""
        system = (
            "You are an expert at extracting GATE exam questions from scanned pages. "
            "Extract all questions visible on the page and return structured JSON. "
            "Preserve all mathematical notation using LaTeX. "
            "Output ONLY valid JSON."
        )
        raw = self._call_vision(system, image_bytes, media_type, prompt)
        data = self._parse_json(raw)
        return VisionExtractionResult(
            extracted_text=data.get("raw_text", ""),
            questions_json=data.get("questions", []),
            confidence=float(data.get("confidence", 0.5)),
        )

    def complete(self, prompt: str, system: str = "") -> str:
        """Execute a text completion prompt."""
        return self._call(system, prompt)


# ── Mock Implementation (for tests) ─────────────────────────────────────────


@dataclass
class MockLLMClient(LLMClient):
    """Deterministic mock LLM client for testing.

    Pre-load responses via the ``subject_responses``, ``tag_responses``,
    ``vision_responses``, and ``completion_responses`` lists. Each call pops the first item.
    """

    subject_responses: list[SubjectClassification] = field(default_factory=list)
    tag_responses: list[TopicTagResult] = field(default_factory=list)
    vision_responses: list[VisionExtractionResult] = field(default_factory=list)
    completion_responses: list[str] = field(default_factory=list)
    call_log: list[dict[str, Any]] = field(default_factory=list)

    def classify_subject(
        self,
        question_text: str,
        options: dict[str, str] | None,
        available_subjects: list[str],
    ) -> SubjectClassification:
        """Return the next pre-loaded classification response."""
        self.call_log.append({
            "method": "classify_subject",
            "question_text": question_text,
            "options": options,
        })
        if not self.subject_responses:
            return SubjectClassification(
                classified_subject="operating_systems",
                confidence=0.95,
                reasoning="mock default",
            )
        return self.subject_responses.pop(0)

    def tag_question(
        self,
        question_text: str,
        options: dict[str, str] | None,
        taxonomy: dict[str, Any],
        subject_id: str,
    ) -> TopicTagResult:
        """Return the next pre-loaded tag response."""
        self.call_log.append({
            "method": "tag_question",
            "question_text": question_text,
            "subject_id": subject_id,
        })
        if not self.tag_responses:
            return TopicTagResult(
                topic_id="os_cpu_scheduling",
                subtopic_id="os_sched_algos",
                difficulty="medium",
                confidence=0.90,
                reasoning="mock default",
            )
        return self.tag_responses.pop(0)

    def extract_with_vision(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> VisionExtractionResult:
        """Return the next pre-loaded vision response."""
        self.call_log.append({
            "method": "extract_with_vision",
            "image_size": len(image_bytes),
        })
        if not self.vision_responses:
            return VisionExtractionResult(
                extracted_text="Mock extracted text",
                questions_json=[],
                confidence=0.5,
            )
        return self.vision_responses.pop(0)

    def complete(self, prompt: str, system: str = "") -> str:
        """Return the next pre-loaded raw completion response."""
        self.call_log.append({
            "method": "complete",
            "prompt": prompt,
            "system": system,
        })
        if self.completion_responses:
            return self.completion_responses.pop(0)

        # Deterministic default mock JSON for question generation/solving
        if "Solve this question" in prompt:
            if "Question Type: NAT" in prompt:
                return json.dumps({
                    "solved_answer": 4.5,
                    "confidence": 1.0,
                    "reasoning": "Mock NAT solver verification pass",
                })
            elif "Question Type: MSQ" in prompt:
                return json.dumps({
                    "solved_answer": ["A", "C"],
                    "confidence": 1.0,
                    "reasoning": "Mock MSQ solver verification pass",
                })
            else:
                return json.dumps({
                    "solved_answer": ["A"],
                    "confidence": 1.0,
                    "reasoning": "Mock MCQ solver verification pass",
                })
        elif "Target QType: NAT" in prompt:
            return json.dumps({
                "text": "Calculate the average throughput for 3 processes running for 12 seconds total.",
                "options": None,
                "qtype": "NAT",
                "marks": 2,
                "difficulty": "medium",
                "answer": {"value": 4.5, "min": 4.0, "max": 5.0},
                "solution_text": "Answer = 4.5",
                "topic_id": "os_process_mgmt",
                "subtopic_id": None,
            })
        elif "Target QType: MSQ" in prompt:
            return json.dumps({
                "text": "Which of the following process states are valid in a standard operating system kernel?",
                "options": {
                    "A": "Running",
                    "B": "Ready",
                    "C": "Blocked / Waiting",
                    "D": "Terminated",
                },
                "qtype": "MSQ",
                "marks": 2,
                "difficulty": "medium",
                "answer": ["A", "C"],
                "solution_text": "Running and Blocked are valid states.",
                "topic_id": "os_process_mgmt",
                "subtopic_id": None,
            })
        else:
            return json.dumps({
                "text": "What is the average waiting time for 3 processes with burst times 10, 5, and 8 under FCFS scheduling?",
                "options": {
                    "A": "8.33 ms",
                    "B": "10.0 ms",
                    "C": "5.0 ms",
                    "D": "12.5 ms",
                },
                "qtype": "MCQ",
                "marks": 1,
                "difficulty": "medium",
                "answer": ["A"],
                "solution_text": "Process 1 waits 0 ms, P2 waits 10 ms, P3 waits 15 ms. Total = 25 ms. Avg = 25 / 3 = 8.33 ms.",
                "topic_id": "os_process_mgmt",
                "subtopic_id": None,
            })


# ── Gemini Implementation ──────────────────────────────────────────────────


class GeminiLLMClient(LLMClient):
    """Production LLM client using Google Gemini REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.llm.gemini_api_key
        self._model_id = model_id or settings.llm.gemini_model_id or "gemini-3.5-flash-lite"

    def _call(self, system: str, user: str) -> str:
        import urllib.request
        import urllib.error

        candidate_models = [self._model_id, "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]
        # Remove duplicates while preserving order
        models_to_try = list(dict.fromkeys(candidate_models))

        last_exception = None
        for m in models_to_try:
            model_path = m if m.startswith("models/") else f"models/{m}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self._api_key}"
            payload: dict[str, Any] = {
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 4096,
                },
            }
            if system:
                payload["system_instruction"] = {"parts": [{"text": system}]}

            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    return text
            except Exception as e:
                logger.warning("gemini_api_attempt_failed", model=m, error=str(e))
                last_exception = e

        logger.error("gemini_api_error_all_models_failed", error=str(last_exception))
        raise LLMClientError(f"Gemini API error across all models: {last_exception}") from last_exception

    def _call_vision(self, system: str, image_bytes: bytes, media_type: str, prompt: str) -> str:
        import base64
        import urllib.request
        import urllib.error

        candidate_models = [self._model_id, "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]
        models_to_try = list(dict.fromkeys(candidate_models))

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        last_exception = None
        for m in models_to_try:
            model_path = m if m.startswith("models/") else f"models/{m}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self._api_key}"
            payload: dict[str, Any] = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": media_type,
                                    "data": b64_image,
                                }
                            },
                            {"text": prompt},
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 4096,
                },
            }
            if system:
                payload["system_instruction"] = {"parts": [{"text": system}]}

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    text = result["candidates"][0]["content"]["parts"][0]["text"]
                    return text
            except Exception as e:
                logger.warning("gemini_vision_attempt_failed", model=m, error=str(e))
                last_exception = e

        logger.error("gemini_vision_error_all_models_failed", error=str(last_exception))
        raise LLMClientError(f"Gemini Vision API error: {last_exception}") from last_exception

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```") and not inside:
                    inside = True
                    continue
                if line.strip() == "```" and inside:
                    break
                if inside:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        return json.loads(cleaned)  # type: ignore[no-any-return]

    def classify_subject(
        self,
        question_text: str,
        options: dict[str, str] | None,
        available_subjects: list[str],
    ) -> SubjectClassification:
        subjects_str = ", ".join(available_subjects)
        options_str = ""
        if options:
            options_str = "\n".join(f"  ({k}) {v}" for k, v in options.items())
            options_str = f"\nOptions:\n{options_str}"

        system = (
            "You are an expert GATE Computer Science question classifier. "
            "Classify the given question into exactly ONE of the provided subjects. "
            "Respond ONLY with valid JSON matching this schema: "
            '{"classified_subject": "<subject_id>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}'
        )
        user = (
            f"Available subjects: {subjects_str}\n\n"
            f"Question:\n{question_text}{options_str}\n\n"
            "Classify this question. Return ONLY the JSON."
        )

        raw = self._call(system, user)
        data = self._parse_json(raw)
        return SubjectClassification(
            classified_subject=data["classified_subject"],
            confidence=float(data["confidence"]),
            reasoning=data.get("reasoning", ""),
        )

    def tag_question(
        self,
        question_text: str,
        options: dict[str, str] | None,
        taxonomy: dict[str, Any],
        subject_id: str,
    ) -> TopicTagResult:
        taxonomy_str = json.dumps(taxonomy, indent=2)
        options_str = ""
        if options:
            options_str = "\n".join(f"  ({k}) {v}" for k, v in options.items())
            options_str = f"\nOptions:\n{options_str}"

        system = (
            "You are an expert GATE CS question tagger. Given a question and a taxonomy, "
            "identify the most specific topic and subtopic. If the question does not belong "
            "to any topic in the taxonomy, use topic_id='out_of_scope' and subtopic_id=null. "
            "Rate difficulty as 'easy', 'medium', or 'hard'. "
            "Respond ONLY with valid JSON: "
            '{"topic_id": "<id>", "subtopic_id": "<id_or_null>", '
            '"difficulty": "<easy|medium|hard>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}'
        )
        user = (
            f"Subject: {subject_id}\n\n"
            f"Taxonomy:\n{taxonomy_str}\n\n"
            f"Question:\n{question_text}{options_str}\n\n"
            "Tag this question. Return ONLY the JSON."
        )

        raw = self._call(system, user)
        data = self._parse_json(raw)
        subtopic = data.get("subtopic_id")
        if subtopic == "null" or subtopic is None:
            subtopic = None
        return TopicTagResult(
            topic_id=data["topic_id"],
            subtopic_id=subtopic,
            difficulty=data["difficulty"],
            confidence=float(data["confidence"]),
            reasoning=data.get("reasoning", ""),
        )

    def extract_with_vision(
        self,
        image_bytes: bytes,
        media_type: str,
        prompt: str,
    ) -> VisionExtractionResult:
        system = (
            "You are an expert at extracting GATE exam questions from scanned pages. "
            "Extract all questions visible on the page and return structured JSON. "
            "Preserve all mathematical notation using LaTeX. "
            "Output ONLY valid JSON."
        )
        raw = self._call_vision(system, image_bytes, media_type, prompt)
        data = self._parse_json(raw)
        return VisionExtractionResult(
            extracted_text=data.get("raw_text", ""),
            questions_json=data.get("questions", []),
            confidence=float(data.get("confidence", 0.5)),
        )

    def complete(self, prompt: str, system: str = "") -> str:
        return self._call(system, prompt)


def get_llm_client() -> LLMClient:
    """Factory function to resolve the active LLM client based on configuration."""
    provider = settings.llm.llm_provider.lower()
    if (provider == "gemini" or settings.llm.gemini_api_key) and settings.llm.gemini_api_key:
        return GeminiLLMClient()
    elif settings.llm.anthropic_api_key and settings.llm.anthropic_api_key != "sk-ant-REPLACE_ME":
        return AnthropicLLMClient()
    return MockLLMClient()

