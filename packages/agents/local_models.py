"""
Local ML models for evidence quality prediction and source gap forecasting.

These models run entirely locally (CPU) and require no API calls.
They are trained on historical eval run data and provide instant predictions.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "tmp" / "ml_training"


class QualityPredictor:
    """Predicts whether a research run will pass or fail the DeepSeek audit.

    Features: total_queries, live_success_rate, audit_fail_count,
              audit_weak_pass_count, avg_latency_ms, total_credits,
              num_gaps, total_gap_count
    """

    def __init__(self) -> None:
        self._clf = None
        self._features: list[str] = []
        self._loaded = False

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return self._clf is not None
        self._loaded = True
        clf_path = _MODEL_DIR / "quality_classifier.pkl"
        meta_path = _MODEL_DIR / "quality_classifier_meta.json"
        if not clf_path.exists():
            return False
        try:
            with open(clf_path, "rb") as f:
                self._clf = pickle.load(f)
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                self._features = meta.get("features", [])
            return True
        except Exception:
            return False

    def predict(self, features: dict[str, float]) -> dict[str, Any]:
        """Predict audit quality (0=fail, 1=pass).

        Args:
            features: Dict with keys matching training features.
        """
        if not self._ensure_loaded():
            return {"quality": "unknown", "score": 0.5, "source": "heuristic"}

        ordered = [features.get(k, 0.0) for k in self._features]
        X = np.array([ordered])
        pred = int(self._clf.predict(X)[0])
        proba = float(self._clf.predict_proba(X)[0][pred])
        return {
            "quality": "pass" if pred == 1 else "fail_likely",
            "score": round(proba, 3),
            "source": "local_ml",
        }

    @staticmethod
    def from_run_stats(
        total_queries: int = 1,
        gaps: list[dict] | None = None,
        total_credits: int = 0,
        avg_latency_ms: float = 0,
    ) -> dict[str, Any]:
        """Convenience: predict from run statistics."""
        gaps = gaps or []
        features = {
            "total_queries": total_queries,
            "live_success_rate": 1.0,
            "audit_fail_count": 0,
            "audit_weak_pass_count": 0,
            "avg_latency_ms": avg_latency_ms,
            "total_credits": total_credits,
            "num_gaps": len(gaps),
            "total_gap_count": sum(g.get("missing_count", 0) for g in gaps),
        }
        return QualityPredictor().predict(features)


class GapPredictor:
    """Predicts which source classes are likely missing for a given query context.

    Features: source_class (one-hot), total_credits, num_gaps
    """

    def __init__(self) -> None:
        self._reg = None
        self._classes: list[str] = []
        self._loaded = False

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return self._reg is not None
        self._loaded = True
        reg_path = _MODEL_DIR / "gap_predictor.pkl"
        meta_path = _MODEL_DIR / "gap_predictor_meta.json"
        if not reg_path.exists():
            return False
        try:
            with open(reg_path, "rb") as f:
                self._reg = pickle.load(f)
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                self._classes = meta.get("classes", [])
            return True
        except Exception:
            return False

    def predict_gaps(self, source_classes: list[str]) -> list[dict[str, Any]]:
        """Predict missing counts for each source class."""
        if not self._ensure_loaded() or not self._classes:
            return _heuristic_gap_prediction(source_classes)

        results = []
        for sc in source_classes:
            one_hot = [1.0 if sc == c else 0.0 for c in self._classes]
            X = np.array([one_hot + [15.0, 5.0]])  # avg credits, avg gaps
            predicted = float(self._reg.predict(X)[0])
            results.append({
                "source_class": sc,
                "predicted_missing": round(max(0, predicted)),
                "confidence": "medium" if predicted > 2 else "low",
            })
        return sorted(results, key=lambda x: -x["predicted_missing"])


def _heuristic_gap_prediction(source_classes: list[str]) -> list[dict[str, Any]]:
    """Fallback heuristic based on historical blocker patterns."""
    high_risk = {"tender_or_procurement", "project_list", "statistics"}
    medium_risk = {"regulatory_record", "environmental_or_land_record", "company_disclosure"}
    results = []
    for sc in source_classes:
        if sc in high_risk:
            predicted = 4
            confidence = "high"
        elif sc in medium_risk:
            predicted = 2
            confidence = "medium"
        else:
            predicted = 1
            confidence = "low"
        results.append({
            "source_class": sc,
            "predicted_missing": predicted,
            "confidence": confidence,
        })
    return sorted(results, key=lambda x: -x["predicted_missing"])


# ── Convenience entry points ──

def predict_quality_from_dr_report(report: Any) -> dict[str, Any]:
    """Predict audit quality from a DeepResearchReport."""
    gaps = getattr(report, "data_gaps", None) or []
    return QualityPredictor.from_run_stats(
        total_queries=1,
        gaps=[{"missing_count": 1} for _ in gaps],
        total_credits=getattr(report, "estimated_tavily_credits", 0),
    )


def predict_source_gaps(source_classes: list[str]) -> list[dict[str, Any]]:
    """Predict which source classes are likely missing."""
    return GapPredictor().predict_gaps(source_classes)
