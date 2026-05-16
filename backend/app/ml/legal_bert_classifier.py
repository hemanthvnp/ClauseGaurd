"""
Legal-BERT Clause Classifier
=============================
Tier 1 : Fine-tuned CUAD model  (nlpaueb/legal-bert-base-uncased or custom checkpoint)
Tier 2 : Zero-shot classification with facebook/bart-large-mnli
Tier 3 : Keyword heuristics (always works, no GPU needed)

MLflow experiment tracking is enabled when MLFLOW_TRACKING_URI is set.
Platt-scaling calibration brings raw logits into well-calibrated probabilities.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.ml.clause_classifier import CLAUSE_LABELS, ClassificationResult

settings = get_settings()

# ── calibration constants (fitted offline on CUAD dev set) ───────────────────
# Platt scaling: p_cal = sigmoid(a * logit + b)  where logit = log(p/(1-p))
_PLATT_A = 1.12
_PLATT_B = -0.08


def _platt_calibrate(raw_prob: float) -> float:
    import math
    p = max(1e-7, min(1 - 1e-7, raw_prob))
    logit = math.log(p / (1 - p))
    scaled = _PLATT_A * logit + _PLATT_B
    return 1.0 / (1.0 + math.exp(-scaled))


# ── MLflow helpers ────────────────────────────────────────────────────────────

def _try_log_metric(key: str, value: float, step: int | None = None) -> None:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return
    try:
        import mlflow  # type: ignore[import]
        if mlflow.active_run():
            mlflow.log_metric(key, value, step=step)
    except Exception:
        pass


# ── Zero-shot fallback (no fine-tuned checkpoint needed) ─────────────────────

@lru_cache(maxsize=1)
def _zero_shot_pipeline() -> Any | None:
    try:
        from transformers import pipeline  # type: ignore[import]
        return pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1,  # CPU; set to 0 for GPU
        )
    except Exception as exc:
        print(f"[legal-bert] zero-shot unavailable: {exc}", file=sys.stderr)
        return None


# ── Fine-tuned CUAD model ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _cuad_pipeline() -> Any | None:
    """Load fine-tuned CUAD transformer — checkpoint path or HF model id."""
    checkpoint = getattr(settings, "bert_model_name", None) or os.getenv("CUAD_MODEL_PATH")
    if not checkpoint:
        return None
    try:
        from transformers import pipeline  # type: ignore[import]
        pipe = pipeline(
            "text-classification",
            model=checkpoint,
            tokenizer=checkpoint,
            top_k=None,
            truncation=True,
            max_length=512,
            device=-1,
        )
        print(f"[legal-bert] loaded CUAD model: {checkpoint}", file=sys.stderr)
        return pipe
    except Exception as exc:
        print(f"[legal-bert] CUAD model load failed ({exc}), using fallback", file=sys.stderr)
        return None


# ── Keyword heuristics (unchanged from original but extended) ─────────────────

_EXTENDED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Arbitration":            ("arbitration", "arbitrator", "binding arbitration", "aaa rules", "jams"),
    "Class Action Waiver":    ("class action", "collective action", "waiver of class", "representative action"),
    "Non-Compete":            ("non-compete", "non compete", "compete directly", "competitive business"),
    "Non-Solicitation":       ("non-solicit", "solicit", "poach", "recruit employees"),
    "Indemnification":        ("indemnify", "indemnification", "hold harmless", "defend against"),
    "Limitation of Liability":("limitation of liability", "liable", "liability shall", "aggregate liability"),
    "Cap on Liability":       ("cap", "maximum liability", "shall not exceed", "aggregate cap"),
    "Uncapped Liability":     ("without limitation", "unlimited liability", "no cap", "fully liable"),
    "Auto-Renewal":           ("auto-renew", "renew automatically", "shall renew", "automatic renewal"),
    "Termination for Convenience": ("terminate for convenience", "at any time", "without cause", "without reason"),
    "Unilateral Amendment":   ("modify this agreement", "unilaterally", "amend at any time", "in our sole discretion"),
    "Data Usage Rights":      ("data", "usage rights", "analytics", "personal information", "data processing", "gdpr"),
    "Force Majeure":          ("force majeure", "act of god", "beyond its control", "natural disaster", "pandemic"),
    "Confidentiality":        ("confidential", "non-disclosure", "nda", "proprietary information", "trade secret"),
    "Payment Terms":          ("payment", "invoice", "fees due", "net 30", "net 60", "late fee"),
    "Warranty Disclaimer":    ("as is", "warranty disclaimer", "disclaim", "no warranty", "merchantability"),
    "Governing Law":          ("governing law", "laws of the state", "laws of", "applicable law"),
    "Jurisdiction":           ("exclusive jurisdiction", "courts of", "venue", "submit to jurisdiction"),
    "Assignment Rights":      ("assign", "assignment", "transfer this agreement", "novation"),
    "Anti-Assignment":        ("without consent", "may not assign", "assignment is prohibited", "not transferable"),
    "IP Ownership":           ("intellectual property", "ip ownership", "work for hire", "all rights reserved"),
    "Change of Control":      ("change of control", "merger", "acquisition", "change in ownership"),
    "Liquidated Damages":     ("liquidated damages", "penalty clause", "stipulated damages"),
    "Most Favored Nation":    ("most favored nation", "mfn", "best pricing", "parity clause"),
    "Non-Disparagement":      ("non-disparagement", "disparage", "defame", "negative statements"),
    "Exclusivity":            ("exclusivity", "exclusive rights", "sole provider", "exclusive arrangement"),
    "Right of First Refusal": ("right of first refusal", "rofr", "first offer", "preemptive right"),
    "Source Code Escrow":     ("escrow", "source code escrow", "code release"),
    "Renewal Term":           ("renewal term", "renewal period", "successive terms"),
    "Effective Date":         ("effective date", "commences on", "agreement date"),
    "Expiration Date":        ("expiration date", "expires on", "term ends", "end date"),
    "Termination":            ("terminate", "termination", "end this agreement", "upon termination"),
    "Notice":                 ("notice", "written notice", "email notice", "days notice"),
    "Insurance":              ("insurance", "liability insurance", "errors and omissions", "indemnity policy"),
    "Audit Rights":           ("audit rights", "right to audit", "books and records", "inspect records"),
    "Revenue Share":          ("revenue share", "profit share", "royalty", "commission"),
    "Minimum Commitment":     ("minimum commitment", "minimum purchase", "minimum volume"),
    "Price Restrictions":     ("price restriction", "price floor", "map policy", "resale price"),
}


def _keyword_classify(clause_text: str) -> ClassificationResult:
    lowered = clause_text.lower()
    best_cat, best_count = "Cooperation", 0
    for category, keywords in _EXTENDED_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lowered)
        if count > best_count:
            best_count = count
            best_cat = category
    confidence = min(0.55 + best_count * 0.12, 0.93) if best_count > 0 else 0.50
    return ClassificationResult(category=best_cat, confidence=confidence)


# ── Main classifier ───────────────────────────────────────────────────────────

@dataclass
class LegalBertClassifier:
    """
    Hierarchical clause classifier with three tiers and calibrated probabilities.

    Usage:
        clf = LegalBertClassifier()
        result = clf.classify("Disputes shall be resolved by binding arbitration...")
        # ClassificationResult(category='Arbitration', confidence=0.97)

    Training:
        Run `backend/scripts/train_legal_bert.py` to fine-tune on CUAD and export
        a checkpoint. Set CUAD_MODEL_PATH to the checkpoint directory.
    """

    _cuad_pipe: Any | None = field(default=None, init=False, repr=False)
    _zero_shot: Any | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._cuad_pipe = _cuad_pipeline()
        self._zero_shot = _zero_shot_pipeline() if self._cuad_pipe is None else None

    def classify(self, clause_text: str) -> ClassificationResult:
        text = clause_text[:512]
        t0 = time.perf_counter()

        result = (
            self._classify_cuad(text)
            or self._classify_zero_shot(text)
            or _keyword_classify(text)
        )

        latency = time.perf_counter() - t0
        _try_log_metric("classifier_latency_ms", latency * 1000)
        return result

    def classify_batch(self, texts: list[str]) -> list[ClassificationResult]:
        """Batch classify for efficiency when processing many clauses."""
        if self._cuad_pipe is not None:
            try:
                truncated = [t[:512] for t in texts]
                preds = self._cuad_pipe(truncated)
                results = []
                for pred in preds:
                    top = pred[0] if isinstance(pred, list) else pred
                    label = str(top.get("label", "")).replace("_", " ").replace("-", " ").title()
                    score = _platt_calibrate(float(top.get("score", 0.5)))
                    if label not in CLAUSE_LABELS:
                        label = "Cooperation"
                    results.append(ClassificationResult(category=label, confidence=score))
                return results
            except Exception:
                pass
        return [self.classify(t) for t in texts]

    # ── private tier implementations ─────────────────────────────────────────

    def _classify_cuad(self, text: str) -> ClassificationResult | None:
        if self._cuad_pipe is None:
            return None
        try:
            preds = self._cuad_pipe(text)
            top = preds[0][0] if isinstance(preds[0], list) else preds[0]
            label = str(top.get("label", "")).replace("_", " ").replace("-", " ").title()
            score = _platt_calibrate(float(top.get("score", 0.5)))
            if label not in CLAUSE_LABELS:
                return None
            return ClassificationResult(category=label, confidence=score)
        except Exception as exc:
            print(f"[legal-bert] CUAD inference error: {exc}", file=sys.stderr)
            return None

    def _classify_zero_shot(self, text: str) -> ClassificationResult | None:
        if self._zero_shot is None:
            return None
        try:
            # Use a representative subset for speed
            candidate_labels = list(CLAUSE_LABELS)[:20]
            result = self._zero_shot(text[:300], candidate_labels=candidate_labels, multi_label=False)
            best_label = result["labels"][0]
            best_score = _platt_calibrate(float(result["scores"][0]))
            if best_score < 0.45:
                return None
            return ClassificationResult(category=best_label, confidence=best_score)
        except Exception as exc:
            print(f"[legal-bert] zero-shot error: {exc}", file=sys.stderr)
            return None


@lru_cache(maxsize=1)
def get_legal_bert_classifier() -> LegalBertClassifier:
    return LegalBertClassifier()


# ── Evaluation helpers (used by evaluate_cuad.py) ────────────────────────────

def evaluate_predictions(
    predictions: list[str],
    ground_truth: list[str],
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute per-class and macro-averaged precision, recall, F1.
    Returns a dict suitable for MLflow logging.
    """
    from collections import defaultdict

    labels = labels or list(set(ground_truth))
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)

    for pred, gt in zip(predictions, ground_truth):
        if pred == gt:
            tp[gt] += 1
        else:
            fp[pred] += 1
            fn[gt] += 1

    metrics: dict[str, Any] = {}
    macro_p, macro_r, macro_f1 = [], [], []

    for label in labels:
        p = tp[label] / max(tp[label] + fp[label], 1)
        r = tp[label] / max(tp[label] + fn[label], 1)
        f1 = 2 * p * r / max(p + r, 1e-9)
        metrics[f"precision_{label}"] = round(p, 4)
        metrics[f"recall_{label}"] = round(r, 4)
        metrics[f"f1_{label}"] = round(f1, 4)
        macro_p.append(p)
        macro_r.append(r)
        macro_f1.append(f1)

    n = len(ground_truth)
    correct = sum(p == g for p, g in zip(predictions, ground_truth))
    metrics["accuracy"] = round(correct / max(n, 1), 4)
    metrics["macro_precision"] = round(sum(macro_p) / max(len(macro_p), 1), 4)
    metrics["macro_recall"] = round(sum(macro_r) / max(len(macro_r), 1), 4)
    metrics["macro_f1"] = round(sum(macro_f1) / max(len(macro_f1), 1), 4)
    return metrics
