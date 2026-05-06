"""Evaluation harness — score a classifier against the labeled dataset."""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .classifier import BaseClassifier, CATEGORIES

LABELED_PATH = Path(__file__).resolve().parent / "labeled.jsonl"


def _load_labeled() -> list[dict]:
    """Load labeled headlines from the JSONL file."""
    if not LABELED_PATH.exists():
        raise FileNotFoundError(f"Labeled dataset not found: {LABELED_PATH}")
    items = []
    with LABELED_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return items


def evaluate(classifier: BaseClassifier) -> dict:
    """Score a classifier against labeled data and return a metrics dict.

    Returns
    -------
    dict with keys:
        accuracy, weighted_f1, total, correct, errors,
        per_category (precision, recall, f1, support per category),
        confusion (list of misclassified examples),
        metadata
    """
    labeled = _load_labeled()
    if not labeled:
        raise ValueError("Labeled dataset is empty")

    correct = 0
    total = len(labeled)
    confusion: list[dict] = []

    # Per-category tracking for precision/recall
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    support: Counter = Counter()

    for item in labeled:
        headline = item["headline"]
        true_cat = item["category"]
        pred_cat, confidence = classifier.classify(headline)

        support[true_cat] += 1

        if pred_cat == true_cat:
            correct += 1
            tp[true_cat] += 1
        else:
            fp[pred_cat] += 1
            fn[true_cat] += 1
            confusion.append({
                "headline": headline,
                "true": true_cat,
                "predicted": pred_cat,
                "confidence": confidence,
            })

    accuracy = correct / total if total > 0 else 0.0

    # Per-category precision, recall, F1
    per_category: dict[str, dict] = {}
    for cat in CATEGORIES:
        p = tp[cat] / (tp[cat] + fp[cat]) if (tp[cat] + fp[cat]) > 0 else 0.0
        r = tp[cat] / (tp[cat] + fn[cat]) if (tp[cat] + fn[cat]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        per_category[cat] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "support": support[cat],
        }

    # Weighted F1 (weighted by support)
    weighted_f1 = sum(
        per_category[cat]["f1"] * support[cat] for cat in CATEGORIES
    ) / total if total > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "weighted_f1": round(weighted_f1, 4),
        "total": total,
        "correct": correct,
        "errors": total - correct,
        "per_category": per_category,
        "confusion": confusion[:20],  # cap to avoid huge logs
        "metadata": classifier.metadata(),
    }
