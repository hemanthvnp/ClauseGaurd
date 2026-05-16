"""
Clause Contradiction Detector
================================
Finds logically conflicting clauses within a single contract.

Detection strategy:
  1. Pair-wise semantic similarity (cosine via embeddings) — find topically
     related clause pairs that might overlap.
  2. Risk-signal contradiction — one clause says "limited liability" but another
     says "uncapped liability" → explicit conflict.
  3. Keyword antonym rules — fast regex pass for known opposing terms.
  4. Optional LLM confirmation — if Groq/Claude available, validate ambiguous
     pairs with a cheap single-shot call.

Returns a list of ContradictionPair objects suitable for display in the UI.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any

import requests

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None  # type: ignore[assignment]
    _NUMPY_OK = False

from app.core.config import get_settings

settings = get_settings()

_GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ContradictionPair:
    clause_a_id: str
    clause_b_id: str
    clause_a_category: str
    clause_b_category: str
    clause_a_text: str
    clause_b_text: str
    contradiction_type: str   # "risk_signal" | "keyword_antonym" | "semantic" | "llm_confirmed"
    severity: str             # "high" | "medium" | "low"
    explanation: str
    confidence: float         # 0-1

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__


# ── Antonym rule engine ───────────────────────────────────────────────────────

_ANTONYM_PAIRS: list[tuple[re.Pattern, re.Pattern, str]] = [
    # (pattern_in_A, pattern_in_B, contradiction_description)
    (re.compile(r"\bcap(?:ped)?\s+(?:on\s+)?liability\b", re.I),
     re.compile(r"\buncapped\b|\bwithout\s+limitation\b|\bunlimited\s+liability\b", re.I),
     "Cap on liability vs. uncapped liability"),

    (re.compile(r"\bno[\s-]?arbitration\b|\bjury\s+trial\b", re.I),
     re.compile(r"\barbitration\b|\baarbitrat(?:or|ion)\b", re.I),
     "Arbitration waiver vs. mandatory arbitration"),

    (re.compile(r"\bmay\s+assign\b|\bassignment\s+permitted\b", re.I),
     re.compile(r"\bmay\s+not\s+assign\b|\banti[\s-]?assignment\b|\bno\s+assignment\b", re.I),
     "Assignment permitted vs. anti-assignment"),

    (re.compile(r"\bno\s+non[\s-]?compete\b|\bemployee\s+may\s+work\b", re.I),
     re.compile(r"\bnon[\s-]?compete\b|\brestrictive\s+covenant\b", re.I),
     "No non-compete vs. non-compete clause"),

    (re.compile(r"\bno\s+(?:auto[\s-]?)?renewal\b|\bdoes\s+not\s+renew\b", re.I),
     re.compile(r"\bauto[\s-]?renew\b|\brenews?\s+automatically\b", re.I),
     "No auto-renewal vs. automatic renewal"),

    (re.compile(r"\bmutual\s+non[\s-]?disclosure\b|\bboth\s+parties.*?confidential\b", re.I),
     re.compile(r"\bone[\s-]?way\b|\bone\s+party\s+only\b|\bonly\s+(?:the\s+)?(?:company|employer)\b", re.I),
     "Mutual vs. one-sided confidentiality"),

    (re.compile(r"\bwarrant(?:y|ies)\b", re.I),
     re.compile(r"\bdisclaim\b|\bno\s+warrant(?:y|ies)\b|\bas[\s-]?is\b", re.I),
     "Warranty provided vs. warranty disclaimer"),
]


# ── Risk-signal contradiction rules ──────────────────────────────────────────

_RISK_SIGNAL_CONFLICTS: dict[frozenset, str] = {
    frozenset({"Cap on Liability", "Uncapped Liability"}):
        "Contract simultaneously caps and uncaps liability",
    frozenset({"Assignment Rights", "Anti-Assignment"}):
        "Contract both permits and prohibits assignment",
    frozenset({"Arbitration", "Jurisdiction"}):
        "Arbitration clause and exclusive court jurisdiction may conflict",
    frozenset({"Auto-Renewal", "Expiration Date"}):
        "Fixed expiration date may conflict with auto-renewal clause",
    frozenset({"Termination for Convenience", "Renewal Term"}):
        "Unilateral termination right may override renewal term",
}


# ── Main detector ─────────────────────────────────────────────────────────────

class ContradictionDetector:
    """
    Detect contradicting clause pairs in a legal document.

    Usage:
        detector = ContradictionDetector()
        pairs = detector.detect(clauses)
        for p in pairs:
            print(p.explanation, p.severity)
    """

    SEMANTIC_THRESHOLD = 0.82   # cosine similarity above which clauses are "topically related"
    MAX_PAIRS_TO_CHECK = 200    # limit O(n²) comparisons

    def detect(self, clauses: list[Any]) -> list[ContradictionPair]:
        contradictions: list[ContradictionPair] = []
        seen: set[frozenset] = set()

        # Pass 1: risk-signal conflicts (O(n²) category pairs)
        contradictions += self._risk_signal_pass(clauses, seen)

        # Pass 2: keyword antonym rules
        contradictions += self._antonym_pass(clauses, seen)

        # Pass 3: semantic similarity (expensive; skip if no numpy)
        if _NUMPY_OK and len(clauses) <= 300:
            contradictions += self._semantic_pass(clauses, seen)

        # Sort by severity
        sev_rank = {"high": 0, "medium": 1, "low": 2}
        contradictions.sort(key=lambda p: (sev_rank.get(p.severity, 3), -p.confidence))
        return contradictions[:20]  # cap at 20 most significant

    # ── passes ────────────────────────────────────────────────────────────────

    def _risk_signal_pass(
        self, clauses: list[Any], seen: set[frozenset]
    ) -> list[ContradictionPair]:
        results: list[ContradictionPair] = []
        cat_to_clauses: dict[str, list[Any]] = {}
        for c in clauses:
            cat = c.category or "General"
            cat_to_clauses.setdefault(cat, []).append(c)

        for cat_pair, description in _RISK_SIGNAL_CONFLICTS.items():
            cats = list(cat_pair)
            if len(cats) < 2:
                continue
            group_a = cat_to_clauses.get(cats[0], [])
            group_b = cat_to_clauses.get(cats[1], [])
            for ca in group_a:
                for cb in group_b:
                    key = frozenset([str(ca.id), str(cb.id)])
                    if key in seen:
                        continue
                    seen.add(key)
                    severity = self._severity_from_risk(ca.risk_level, cb.risk_level)
                    results.append(ContradictionPair(
                        clause_a_id=str(ca.id),
                        clause_b_id=str(cb.id),
                        clause_a_category=ca.category or "General",
                        clause_b_category=cb.category or "General",
                        clause_a_text=ca.clause_text[:300],
                        clause_b_text=cb.clause_text[:300],
                        contradiction_type="risk_signal",
                        severity=severity,
                        explanation=description,
                        confidence=0.85,
                    ))
        return results

    def _antonym_pass(
        self, clauses: list[Any], seen: set[frozenset]
    ) -> list[ContradictionPair]:
        results: list[ContradictionPair] = []
        n = min(len(clauses), 150)
        for i in range(n):
            for j in range(i + 1, n):
                ca, cb = clauses[i], clauses[j]
                key = frozenset([str(ca.id), str(cb.id)])
                if key in seen:
                    continue
                for pat_a, pat_b, desc in _ANTONYM_PAIRS:
                    a_match = pat_a.search(ca.clause_text)
                    b_match = pat_b.search(cb.clause_text)
                    if a_match and b_match:
                        seen.add(key)
                        results.append(ContradictionPair(
                            clause_a_id=str(ca.id),
                            clause_b_id=str(cb.id),
                            clause_a_category=ca.category or "General",
                            clause_b_category=cb.category or "General",
                            clause_a_text=ca.clause_text[:300],
                            clause_b_text=cb.clause_text[:300],
                            contradiction_type="keyword_antonym",
                            severity="high",
                            explanation=desc,
                            confidence=0.78,
                        ))
                        break
        return results

    def _semantic_pass(
        self, clauses: list[Any], seen: set[frozenset]
    ) -> list[ContradictionPair]:
        """Find topically similar but risk-conflicting clause pairs."""
        if np is None:
            return []
        try:
            from app.ml.vector_store import _encode_texts
            texts = [f"{c.category}: {c.clause_text[:300]}" for c in clauses]
            vecs = _encode_texts(texts)
            if vecs is None:
                return []
        except Exception:
            return []

        results: list[ContradictionPair] = []
        n = min(len(clauses), self.MAX_PAIRS_TO_CHECK)

        sim_matrix = vecs[:n] @ vecs[:n].T
        for i in range(n):
            for j in range(i + 1, n):
                if sim_matrix[i, j] < self.SEMANTIC_THRESHOLD:
                    continue
                ca, cb = clauses[i], clauses[j]
                key = frozenset([str(ca.id), str(cb.id)])
                if key in seen:
                    continue
                # Only flag as contradiction if risk levels differ significantly
                if not self._risk_levels_conflict(ca.risk_level, cb.risk_level):
                    continue
                seen.add(key)
                results.append(ContradictionPair(
                    clause_a_id=str(ca.id),
                    clause_b_id=str(cb.id),
                    clause_a_category=ca.category or "General",
                    clause_b_category=cb.category or "General",
                    clause_a_text=ca.clause_text[:300],
                    clause_b_text=cb.clause_text[:300],
                    contradiction_type="semantic",
                    severity="medium",
                    explanation=(
                        f"Semantically similar clauses ({ca.category} vs {cb.category}) "
                        f"carry conflicting risk signals "
                        f"({ca.risk_level} vs {cb.risk_level})"
                    ),
                    confidence=round(float(sim_matrix[i, j]), 3),
                ))
        return results

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _severity_from_risk(level_a: str, level_b: str) -> str:
        levels = {l: i for i, l in enumerate(["low", "medium", "high", "critical"])}
        max_level = max(levels.get(level_a or "low", 0), levels.get(level_b or "low", 0))
        return ["low", "medium", "high", "high"][max_level]

    @staticmethod
    def _risk_levels_conflict(level_a: str | None, level_b: str | None) -> bool:
        rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        a = rank.get(level_a or "low", 0)
        b = rank.get(level_b or "low", 0)
        return abs(a - b) >= 2  # e.g. low vs high


_detector_instance: ContradictionDetector | None = None


def get_contradiction_detector() -> ContradictionDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ContradictionDetector()
    return _detector_instance
