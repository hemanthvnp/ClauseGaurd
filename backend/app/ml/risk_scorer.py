from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RiskAssessment:
    risk_level: str
    risk_score: float
    is_standard: bool
    percentile: float


CATEGORY_BASE_SCORES: dict[str, int] = {
    'Arbitration': 92,
    'Class Action Waiver': 95,
    'Uncapped Liability': 98,
    'Data Usage Rights': 88,
    'Termination for Convenience': 86,
    'Auto-Renewal': 78,
    'Jurisdiction': 74,
    'IP Ownership': 84,
    'Non-Compete': 83,
    'Indemnification': 80,
    'Unilateral Amendment': 68,
    'Force Majeure': 48,
    'Cap on Liability': 42,
    'Limitation of Liability': 44,
    'Payment Terms': 18,
    'Governing Law': 14,
    'Notice': 12,
    'Confidentiality': 24,
}


STANDARD_FREQ_HINTS: dict[str, float] = {
    'Governing Law': 0.88,
    'Payment Terms': 0.8,
    'Notice': 0.82,
    'Confidentiality': 0.75,
    'Limitation of Liability': 0.65,
}


def _risk_level_from_score(score: float) -> str:
    if score >= 90:
        return 'critical'
    if score >= 65:
        return 'high'
    if score >= 35:
        return 'medium'
    return 'low'


class RiskScorer:
    """Convert clause categories into risk scores.

    Input: a clause category and optional text clues.
    Output: risk level, score, standardness, and percentile estimate.
    """

    def score(self, category: str, clause_text: str, confidence: float = 1.0) -> RiskAssessment:
        base_score = CATEGORY_BASE_SCORES.get(category, 40)
        text_lower = clause_text.lower()
        score = float(base_score)

        if category in {'Arbitration', 'Class Action Waiver', 'Uncapped Liability', 'Non-Compete'}:
            score += 4.0
        if 'irrevocable' in text_lower or 'perpetual' in text_lower:
            score += 6.0
        if 'without cause' in text_lower or 'at any time' in text_lower:
            score += 5.0
        if 'consent' in text_lower and 'assign' in text_lower:
            score -= 5.0
        score = max(0.0, min(100.0, score * (0.85 + (confidence * 0.15))))

        risk_level = _risk_level_from_score(score)
        is_standard = STANDARD_FREQ_HINTS.get(category, 0.55) >= 0.7 and risk_level == 'low'
        percentile = max(0.0, min(100.0, score))
        return RiskAssessment(risk_level=risk_level, risk_score=round(score, 2), is_standard=is_standard, percentile=round(percentile, 2))


risk_scorer = RiskScorer()
