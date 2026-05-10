from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

settings = get_settings()

CLAUSE_LABELS: list[str] = [
    'Governing Law',
    'Jurisdiction',
    'Arbitration',
    'Class Action Waiver',
    'IP Ownership',
    'Non-Compete',
    'Non-Solicitation',
    'Indemnification',
    'Limitation of Liability',
    'Auto-Renewal',
    'Termination for Convenience',
    'Unilateral Amendment',
    'Data Usage Rights',
    'Force Majeure',
    'Confidentiality',
    'Payment Terms',
    'Warranty Disclaimer',
    'Liquidated Damages',
    'Change of Control',
    'Assignment Rights',
    'Audit Rights',
    'Most Favored Nation',
    'Price Restrictions',
    'Volume Restrictions',
    'Minimum Commitment',
    'Revenue Share',
    'Source Code Escrow',
    'Uncapped Liability',
    'Cap on Liability',
    'Anti-Assignment',
    'No-Solicit of Customers',
    'No-Solicit of Employees',
    'Non-Disparagement',
    'Exclusivity',
    'Right of First Refusal',
    'Cooperation',
    'Insurance',
    'Renewal Term',
    'Effective Date',
    'Expiration Date',
    'Notice',
    'Termination',
]


@dataclass(slots=True)
class ClassificationResult:
    category: str
    confidence: float


class ClauseClassifier:
    """Classify legal clauses into CUAD-style labels.

    Input: a single clause text.
    Output: the most likely clause category and a confidence estimate.
    """

    KEYWORDS: dict[str, tuple[str, ...]] = {
        'Arbitration': ('arbitration', 'arbitrator', 'binding arbitration'),
        'Class Action Waiver': ('class action', 'collective action', 'waiver of class'),
        'Non-Compete': ('non-compete', 'compete', 'competitive'),
        'Non-Solicitation': ('non-solicit', 'solicit', 'poach'),
        'Indemnification': ('indemnify', 'indemnification', 'hold harmless'),
        'Limitation of Liability': ('limitation of liability', 'liable', 'liability shall'),
        'Cap on Liability': ('cap', 'maximum liability', 'shall not exceed'),
        'Uncapped Liability': ('without limitation', 'unlimited liability', 'no cap'),
        'Auto-Renewal': ('auto-renew', 'renew automatically', 'shall renew'),
        'Termination for Convenience': ('terminate for convenience', 'at any time', 'without cause'),
        'Unilateral Amendment': ('modify this agreement', 'unilaterally', 'amend at any time'),
        'Data Usage Rights': ('data', 'usage rights', 'analytics', 'personal information'),
        'Force Majeure': ('force majeure', 'act of god', 'beyond its control'),
        'Confidentiality': ('confidential', 'non-disclosure', 'secret'),
        'Payment Terms': ('payment', 'invoice', 'fees due', 'net 30'),
        'Warranty Disclaimer': ('as is', 'warrant', 'disclaim'),
        'Governing Law': ('governing law', 'laws of the state', 'laws of'),
        'Jurisdiction': ('exclusive jurisdiction', 'courts of', 'venue'),
        'Assignment Rights': ('assign', 'assignment', 'transfer this agreement'),
        'Anti-Assignment': ('without consent', 'may not assign', 'assignment is prohibited'),
        'Renewal Term': ('renewal term', 'renewal period'),
        'Effective Date': ('effective date', 'commences on'),
        'Expiration Date': ('expiration date', 'expires on', 'term ends'),
        'Termination': ('terminate', 'termination', 'end this agreement'),
        'Notice': ('notice', 'written notice', 'email notice'),
    }

    def __init__(self) -> None:
        self._transformer_model: Any | None = self._load_transformer_model()

    def _load_transformer_model(self) -> Any | None:
        """Load a CUAD-style Transformer classifier when available."""
        if not settings.bert_model_name:
            return None
        try:
            from transformers import pipeline

            return pipeline(
                task='text-classification',
                model=settings.bert_model_name,
                tokenizer=settings.bert_model_name,
                top_k=None,
                truncation=True,
            )
        except Exception:
            return None

    def classify(self, clause_text: str) -> ClassificationResult:
        """Return the best matching clause category for the given text."""
        if self._transformer_model is not None:
            try:
                predictions = self._transformer_model(clause_text)
                top_prediction = predictions[0][0] if predictions and isinstance(predictions[0], list) else predictions[0]
                label = str(top_prediction.get('label', '')).strip()
                score = float(top_prediction.get('score', 0.5))
                normalized = label.replace('_', ' ').replace('-', ' ').title()
                if normalized in CLAUSE_LABELS:
                    return ClassificationResult(category=normalized, confidence=score)
            except Exception:
                pass

        lowered = clause_text.lower()
        for category, keywords in self.KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return ClassificationResult(category=category, confidence=0.91)
        return ClassificationResult(category='Cooperation', confidence=0.55)


@lru_cache(maxsize=1)
def get_classifier() -> ClauseClassifier:
    return ClauseClassifier()
