#!/usr/bin/env python3
"""
CUAD Benchmark Evaluation
===========================
Evaluates the ClauseGuard classifier pipeline against the CUAD test set.

Outputs:
  - Per-category precision, recall, F1
  - Macro and weighted averages
  - Confusion matrix (saved to eval_output/confusion_matrix.png)
  - Full report (eval_output/report.json)
  - MLflow metrics (if MLFLOW_TRACKING_URI is set)

Usage:
    python scripts/evaluate_cuad.py
    python scripts/evaluate_cuad.py --model ./checkpoints/legal-bert-cuad/best
    python scripts/evaluate_cuad.py --sample 500  # quick eval on 500 examples
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate ClauseGuard on CUAD benchmark")
    p.add_argument("--model", default=None,
                   help="CUAD model path (overrides CUAD_MODEL_PATH env var)")
    p.add_argument("--sample", type=int, default=None,
                   help="Evaluate on N random examples (default: full test set)")
    p.add_argument("--output-dir", default="./eval_output",
                   help="Directory for evaluation artifacts")
    p.add_argument("--split", default="test", choices=["train", "test", "validation"],
                   help="Dataset split to evaluate on")
    return p.parse_args()


CUAD_TO_LABEL = {
    "Governing Law": "Governing Law",
    "Arbitration": "Arbitration",
    "Class Action Waiver": "Class Action Waiver",
    "Intellectual Property": "IP Ownership",
    "Non-Compete": "Non-Compete",
    "Non-Solicitation": "Non-Solicitation",
    "Indemnification": "Indemnification",
    "Limitation On Liability": "Limitation of Liability",
    "Auto-Renewal": "Auto-Renewal",
    "Termination For Convenience": "Termination for Convenience",
    "License Grant": "IP Ownership",
    "Confidentiality": "Confidentiality",
    "Payment Frequency": "Payment Terms",
    "Warranty Duration": "Warranty Disclaimer",
    "Change Of Control": "Change of Control",
    "Assignment": "Assignment Rights",
    "Audit Rights": "Audit Rights",
    "Exclusivity": "Exclusivity",
    "Right Of First Refusal": "Right of First Refusal",
    "Insurance": "Insurance",
    "Renewal Term": "Renewal Term",
    "Effective Date": "Effective Date",
    "Expiration Date": "Expiration Date",
    "Notice Period": "Notice",
}


def load_cuad_examples(split: str, sample: int | None) -> list[tuple[str, str]]:
    """Return list of (clause_text, true_label) pairs from CUAD."""
    try:
        from datasets import load_dataset  # type: ignore[import]
        ds = load_dataset("theatticusproject/cuad", split=split)
        print(f"[eval] Loaded {len(ds)} examples from CUAD {split} split")
    except Exception as exc:
        print(f"[eval] Could not load CUAD dataset: {exc}", file=sys.stderr)
        print("[eval] Using synthetic examples for demo evaluation...")
        return _synthetic_examples()

    examples: list[tuple[str, str]] = []
    for ex in ds:
        question = ex.get("question", "")
        answers  = ex.get("answers", {})
        if not answers.get("text"):
            continue
        text = answers["text"][0]
        if not text:
            continue
        label = "Cooperation"
        for q_key, mapped_label in CUAD_TO_LABEL.items():
            if q_key.lower() in question.lower():
                label = mapped_label
                break
        examples.append((text, label))

    if sample and sample < len(examples):
        import random
        random.seed(42)
        examples = random.sample(examples, sample)

    print(f"[eval] Using {len(examples)} examples")
    return examples


def _synthetic_examples() -> list[tuple[str, str]]:
    return [
        ("Disputes shall be resolved by binding arbitration.", "Arbitration"),
        ("Governed by the laws of California.", "Governing Law"),
        ("Employee may not compete for 2 years post-termination.", "Non-Compete"),
        ("IP created is work-for-hire owned by the Company.", "IP Ownership"),
        ("This Agreement auto-renews for successive one-year terms.", "Auto-Renewal"),
        ("Liability is capped at fees paid in the last 12 months.", "Cap on Liability"),
        ("All confidential information shall remain strictly secret.", "Confidentiality"),
        ("Invoices are due Net 30 from date of issuance.", "Payment Terms"),
        ("Company may terminate for any reason with 30 days notice.", "Termination for Convenience"),
        ("Assignment is prohibited without prior written consent.", "Anti-Assignment"),
    ]


def run_evaluation(args: argparse.Namespace) -> dict:
    if args.model:
        os.environ["CUAD_MODEL_PATH"] = args.model

    # Import after env var is set
    from app.ml.legal_bert_classifier import LegalBertClassifier, evaluate_predictions

    clf = LegalBertClassifier()
    examples = load_cuad_examples(args.split, args.sample)

    print(f"[eval] Running inference on {len(examples)} examples...")
    texts      = [ex[0] for ex in examples]
    true_labels = [ex[1] for ex in examples]

    # Batch inference
    results = clf.classify_batch(texts)
    pred_labels = [r.category for r in results]
    confidences  = [r.confidence for r in results]

    # Compute metrics
    all_labels = sorted(set(true_labels) | set(pred_labels))
    metrics = evaluate_predictions(pred_labels, true_labels, all_labels)

    avg_confidence = sum(confidences) / max(len(confidences), 1)
    metrics["avg_confidence"] = round(avg_confidence, 4)

    print(f"\n[eval] Results:")
    print(f"  Accuracy:         {metrics['accuracy']:.3f}")
    print(f"  Macro F1:         {metrics['macro_f1']:.3f}")
    print(f"  Macro Precision:  {metrics['macro_precision']:.3f}")
    print(f"  Macro Recall:     {metrics['macro_recall']:.3f}")
    print(f"  Avg Confidence:   {metrics['avg_confidence']:.3f}")

    # Save artifacts
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump({
            "metrics": metrics,
            "args": vars(args),
            "num_examples": len(examples),
        }, f, indent=2)
    print(f"[eval] Report saved to {report_path}")

    # Confusion matrix plot
    _save_confusion_matrix(true_labels, pred_labels, all_labels, output_dir)

    # MLflow logging
    _log_to_mlflow(metrics, report_path)

    return metrics


def _save_confusion_matrix(
    true_labels: list[str], pred_labels: list[str],
    all_labels: list[str], output_dir: Path
) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import]
        from sklearn.metrics import confusion_matrix  # type: ignore[import]
        import numpy as np

        cm = confusion_matrix(true_labels, pred_labels, labels=all_labels)
        fig, ax = plt.subplots(figsize=(max(10, len(all_labels)), max(8, len(all_labels) * 0.7)))
        im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
        plt.colorbar(im, ax=ax)
        ax.set_xticks(range(len(all_labels)))
        ax.set_yticks(range(len(all_labels)))
        ax.set_xticklabels(all_labels, rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(all_labels, fontsize=7)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title("ClauseGuard Confusion Matrix (CUAD)")
        plt.tight_layout()
        path = output_dir / "confusion_matrix.png"
        plt.savefig(path, dpi=120)
        plt.close()
        print(f"[eval] Confusion matrix saved to {path}")
    except ImportError:
        print("[eval] matplotlib/sklearn not available, skipping confusion matrix")


def _log_to_mlflow(metrics: dict, report_path: Path) -> None:
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        return
    try:
        import mlflow  # type: ignore[import]
        mlflow.set_experiment("clauseguard-evaluation")
        with mlflow.start_run():
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
            mlflow.log_artifact(str(report_path))
        print("[eval] Metrics logged to MLflow")
    except Exception as exc:
        print(f"[eval] MLflow logging failed: {exc}")


if __name__ == "__main__":
    run_evaluation(parse_args())
