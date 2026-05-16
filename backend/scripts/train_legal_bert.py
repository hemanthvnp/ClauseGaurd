#!/usr/bin/env python3
"""
Legal-BERT Fine-tuning on CUAD
================================
Fine-tunes nlpaueb/legal-bert-base-uncased on the CUAD (Contract Understanding
Atticus Dataset) for 41-category clause classification.

Usage:
    # Basic training
    python scripts/train_legal_bert.py

    # With custom args
    python scripts/train_legal_bert.py \
        --model nlpaueb/legal-bert-base-uncased \
        --epochs 5 \
        --batch-size 16 \
        --output ./checkpoints/legal-bert-cuad

MLflow:
    Set MLFLOW_TRACKING_URI to log metrics, parameters, and artifacts.
    All runs are grouped under the "clauseguard-legal-bert" experiment.

Requirements:
    pip install transformers datasets scikit-learn mlflow accelerate
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ── CLI args ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fine-tune Legal-BERT on CUAD")
    p.add_argument("--model", default="nlpaueb/legal-bert-base-uncased",
                   help="Base HuggingFace model identifier")
    p.add_argument("--epochs", type=int, default=3, help="Training epochs")
    p.add_argument("--batch-size", type=int, default=8, help="Per-device batch size")
    p.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    p.add_argument("--max-length", type=int, default=512, help="Max token length")
    p.add_argument("--output", default="./checkpoints/legal-bert-cuad",
                   help="Output directory for the fine-tuned model")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    p.add_argument("--eval-steps", type=int, default=200, help="Eval frequency (steps)")
    p.add_argument("--warmup-ratio", type=float, default=0.06, help="Warmup ratio")
    return p.parse_args()


# ── Label map ─────────────────────────────────────────────────────────────────

CLAUSE_LABELS = [
    "Governing Law", "Jurisdiction", "Arbitration", "Class Action Waiver",
    "IP Ownership", "Non-Compete", "Non-Solicitation", "Indemnification",
    "Limitation of Liability", "Auto-Renewal", "Termination for Convenience",
    "Unilateral Amendment", "Data Usage Rights", "Force Majeure",
    "Confidentiality", "Payment Terms", "Warranty Disclaimer",
    "Liquidated Damages", "Change of Control", "Assignment Rights",
    "Audit Rights", "Most Favored Nation", "Price Restrictions",
    "Volume Restrictions", "Minimum Commitment", "Revenue Share",
    "Source Code Escrow", "Uncapped Liability", "Cap on Liability",
    "Anti-Assignment", "No-Solicit of Customers", "No-Solicit of Employees",
    "Non-Disparagement", "Exclusivity", "Right of First Refusal",
    "Cooperation", "Insurance", "Renewal Term", "Effective Date",
    "Expiration Date", "Notice", "Termination",
]
LABEL2ID = {l: i for i, l in enumerate(CLAUSE_LABELS)}
ID2LABEL = {i: l for i, l in enumerate(CLAUSE_LABELS)}


# ── Dataset helpers ───────────────────────────────────────────────────────────

def _load_cuad_dataset(tokenizer, max_length: int):
    """
    Load and tokenize the CUAD dataset from HuggingFace Hub.

    CUAD is a QA dataset; we convert it to clause classification by:
    1. Treating each context paragraph as a potential clause
    2. Labelling each paragraph by which question categories have answers in it
    3. Using the most specific matched category as the label
    """
    try:
        from datasets import load_dataset  # type: ignore[import]
        dataset = load_dataset("theatticusproject/cuad", split="train+test")
        print(f"[train] CUAD loaded: {len(dataset)} examples")
    except Exception as exc:
        print(f"[train] CUAD load failed: {exc}", file=sys.stderr)
        print("[train] Generating synthetic training data as fallback...")
        return _synthetic_dataset(tokenizer, max_length)

    return _cuad_to_classification(dataset, tokenizer, max_length)


def _cuad_to_classification(dataset, tokenizer, max_length: int):
    """Convert CUAD QA pairs to single-label clause classification."""
    from collections import defaultdict
    import re

    texts, labels_list = [], []

    # Map CUAD question categories to our labels
    cuad_to_label = {
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
        "Unilateral Termination": "Termination for Convenience",
        "License": "IP Ownership",
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
        "Notice Period To Terminate Renewal": "Notice",
    }

    for example in dataset:
        question = example.get("question", "")
        answers  = example.get("answers", {})
        context  = example.get("context", "")
        if not context or not answers.get("text"):
            continue
        answer_text = answers["text"][0] if answers["text"] else ""
        if not answer_text:
            continue
        # Find best matching label
        label = None
        for q_key, l in cuad_to_label.items():
            if q_key.lower() in question.lower():
                label = l
                break
        if label is None:
            label = "Cooperation"
        texts.append(answer_text[:max_length])
        labels_list.append(LABEL2ID[label])

    if not texts:
        return _synthetic_dataset(tokenizer, max_length)

    return _tokenize_dataset(texts, labels_list, tokenizer, max_length)


def _synthetic_dataset(tokenizer, max_length: int):
    """
    Generate synthetic training data based on keyword patterns.
    Used as fallback when CUAD is not available.
    """
    synthetic = [
        ("Disputes shall be resolved by binding arbitration under AAA rules.", "Arbitration"),
        ("This Agreement shall be governed by the laws of the State of New York.", "Governing Law"),
        ("Company may terminate this Agreement at any time without cause.", "Termination for Convenience"),
        ("Employee shall not compete with Company for 2 years after termination.", "Non-Compete"),
        ("All intellectual property created shall be owned exclusively by Company.", "IP Ownership"),
        ("Either party may not assign this Agreement without prior written consent.", "Anti-Assignment"),
        ("This Agreement renews automatically for successive one-year terms.", "Auto-Renewal"),
        ("Liability shall not exceed the total fees paid in the prior 12 months.", "Cap on Liability"),
        ("Each party shall maintain in confidence all Confidential Information.", "Confidentiality"),
        ("Customer shall pay all invoices within Net 30 days of receipt.", "Payment Terms"),
        ("Services are provided AS IS without any warranty whatsoever.", "Warranty Disclaimer"),
        ("Upon 30 days written notice, either party may terminate this Agreement.", "Notice"),
        ("Any class action waiver provision is included in this arbitration clause.", "Class Action Waiver"),
        ("Company may amend these Terms at any time in its sole discretion.", "Unilateral Amendment"),
        ("User data may be used for analytics and service improvement purposes.", "Data Usage Rights"),
    ] * 20  # Repeat for minimal training set

    texts  = [s[0] for s in synthetic]
    labels = [LABEL2ID.get(s[1], LABEL2ID["Cooperation"]) for s in synthetic]
    return _tokenize_dataset(texts, labels, tokenizer, max_length)


def _tokenize_dataset(texts: list[str], labels: list[int], tokenizer, max_length: int):
    from torch.utils.data import Dataset  # type: ignore[import]

    encodings = tokenizer(
        texts,
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )

    class _ClauseDataset(Dataset):
        def __len__(self): return len(labels)
        def __getitem__(self, idx):
            return {
                "input_ids":      encodings["input_ids"][idx],
                "attention_mask": encodings["attention_mask"][idx],
                "labels":         labels[idx],
            }

    return _ClauseDataset()


# ── Training ──────────────────────────────────────────────────────────────────

def train(args: argparse.Namespace) -> None:
    try:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            EarlyStoppingCallback,
        )
        from sklearn.metrics import classification_report  # type: ignore[import]
        import numpy as np
    except ImportError as exc:
        print(f"[train] Missing dependency: {exc}")
        print("Install: pip install transformers torch scikit-learn datasets accelerate")
        sys.exit(1)

    # Optional MLflow
    try:
        import mlflow  # type: ignore[import]
        mlflow.set_experiment("clauseguard-legal-bert")
        mlflow.start_run()
        mlflow.log_params({
            "model": args.model, "epochs": args.epochs,
            "batch_size": args.batch_size, "lr": args.lr,
            "max_length": args.max_length,
        })
        mlflow_active = True
    except Exception:
        mlflow_active = False

    print(f"[train] Loading tokenizer: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model)

    print("[train] Building dataset...")
    dataset = _load_cuad_dataset(tokenizer, args.max_length)

    # Train/val split (90/10)
    split_idx = int(len(dataset) * 0.9)
    train_ds  = torch.utils.data.Subset(dataset, range(split_idx))
    val_ds    = torch.utils.data.Subset(dataset, range(split_idx, len(dataset)))
    print(f"[train] Train: {len(train_ds)}, Val: {len(val_ds)}")

    print(f"[train] Loading model: {args.model}")
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(CLAUSE_LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        report = classification_report(labels, preds, output_dict=True, zero_division=0)
        metrics = {
            "accuracy": report["accuracy"],
            "macro_f1": report["macro avg"]["f1-score"],
            "macro_precision": report["macro avg"]["precision"],
            "macro_recall": report["macro avg"]["recall"],
        }
        if mlflow_active:
            try:
                mlflow.log_metrics(metrics)
            except Exception:
                pass
        return metrics

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        warmup_ratio=args.warmup_ratio,
        weight_decay=0.01,
        evaluation_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.eval_steps,
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_steps=50,
        seed=args.seed,
        report_to=["mlflow"] if mlflow_active else [],
        dataloader_num_workers=0,  # safe default for Windows
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    print("[train] Starting fine-tuning...")
    trainer.train()

    # Save final model
    trainer.save_model(str(output_dir / "best"))
    tokenizer.save_pretrained(str(output_dir / "best"))
    print(f"[train] Model saved to {output_dir / 'best'}")

    # Save label map
    with open(output_dir / "label_map.json", "w") as f:
        json.dump({"id2label": ID2LABEL, "label2id": LABEL2ID}, f, indent=2)

    if mlflow_active:
        try:
            mlflow.log_artifact(str(output_dir / "label_map.json"))
            mlflow.log_artifact(str(output_dir / "best"), artifact_path="model")
            mlflow.end_run()
        except Exception:
            pass

    print("[train] Done! Set CUAD_MODEL_PATH to use the fine-tuned model.")
    print(f"        export CUAD_MODEL_PATH={output_dir / 'best'}")


if __name__ == "__main__":
    train(parse_args())
