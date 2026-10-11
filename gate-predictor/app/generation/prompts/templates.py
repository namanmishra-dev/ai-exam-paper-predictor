"""Versioned prompt templates for LLM question generation and independent verification."""

from __future__ import annotations

# Version 1.0 — Question Generation Prompt
GENERATION_SYSTEM_PROMPT: str = """\
You are an expert GATE (Graduate Aptitude Test in Engineering) Computer Science paper setter.
Your task is to write high-quality, original, conceptual GATE-style questions.

RULES:
1. Write strictly ORIGINAL questions. Do NOT copy existing PYQs.
2. Follow GATE conventions: precise technical terminology, mathematical rigour, LaTeX for formulas (e.g. $O(n \\log n)$, $\\int$).
3. QType constraints:
   - MCQ: exactly one correct option among A, B, C, D.
   - MSQ: one or more correct options among A, B, C, D (e.g. ["A", "C"]).
   - NAT: numerical answer with no options. Provide exact value and acceptable range min/max (e.g. {"value": 4.5, "min": 4.0, "max": 5.0}).
4. Output ONLY valid JSON matching the specified schema. Do not include markdown code blocks around JSON if returning structured JSON.
"""

GENERATION_USER_PROMPT_TEMPLATE: str = """\
Target Topic: {topic_name} (ID: {topic_id})
Target Difficulty: {difficulty}
Target QType: {qtype}
Target Marks: {marks}

Reference PYQs for Style & Difficulty Baseline:
{reference_pyqs_text}

Generate ONE original GATE Computer Science question for topic '{topic_name}' matching the parameters above.
Output JSON schema:
{{
  "text": "Problem statement string...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, // null for NAT
  "qtype": "{qtype}",
  "marks": {marks},
  "difficulty": "{difficulty}",
  "answer": ["A"], // or ["A", "C"] for MSQ, or {{"value": 4.5, "min": 4.0, "max": 5.0}} for NAT
  "solution_text": "Step-by-step mathematical/conceptual solution...",
  "topic_id": "{topic_id}",
  "subtopic_id": null
}}
"""

# Version 1.0 — Verification Solver Prompt (Does NOT see the answer key!)
SOLVER_SYSTEM_PROMPT: str = """\
You are an independent GATE exam evaluator. Solve the given Computer Science question step by step and provide the correct answer WITHOUT seeing any provided answer key.

RULES:
- For MCQ: return the single correct option key (e.g. ["A"]).
- For MSQ: return all correct option keys as a list (e.g. ["A", "C"]).
- For NAT: return the computed numeric value (e.g. 4.5).
- Be extremely accurate and rigorous.
"""

SOLVER_USER_PROMPT_TEMPLATE: str = """\
Question Type: {qtype}
Question Text:
{text}

Options:
{options_text}

Solve this question and return JSON:
{{
  "solved_answer": ["A"], // list of option letters for MCQ/MSQ, or float for NAT
  "confidence": 1.0,
  "reasoning": "Step-by-step derivation..."
}}
"""
