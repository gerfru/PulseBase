from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from sklearn.cluster import KMeans  # type: ignore[import-untyped]

_MIN_DAYS = 14
_N_CLUSTERS = 3
_MIN_POINTS_PER_DAY = 6


def extract_features(records: list[dict[str, Any]]) -> dict[str, float] | None:
    """Extract 5 scalar features from a single day's body battery time series."""
    if len(records) < _MIN_POINTS_PER_DAY:
        return None

    # Parse hour of each record
    def hour(r: dict[str, Any]) -> float:
        t = r["time"]
        if hasattr(t, "hour"):
            return t.hour + t.minute / 60.0
        return 0.0

    vals = np.array([float(r["value"]) for r in records])
    hours = np.array([hour(r) for r in records])

    morning = vals[(hours >= 6) & (hours < 9)]
    evening = vals[(hours >= 20) & (hours < 23)]
    morning_avg = float(np.mean(morning)) if len(morning) > 0 else float(vals[0])
    evening_avg = float(np.mean(evening)) if len(evening) > 0 else float(vals[-1])
    daily_range = float(vals.max() - vals.min())
    auc = float(np.mean(vals))

    # Count dips: consecutive drop > 10 points
    diffs = np.diff(vals)
    n_dips = int(np.sum(diffs < -10))

    return {
        "morning_avg": morning_avg,
        "evening_avg": evening_avg,
        "daily_range": daily_range,
        "auc": auc,
        "n_dips": n_dips,
    }


def _fill_missing_labels(labels: dict[int, str], n: int) -> None:
    """Assign fallback labels to any cluster not yet covered by the primary heuristic."""
    used = set(labels.values())
    fallbacks = ["erholung", "erschoepft", "stabil_hoch"]
    for cid in range(n):
        if cid in labels:
            continue
        for fb in fallbacks:
            if fb not in used:
                labels[cid] = fb
                used.add(fb)
                break
        else:
            labels[cid] = "erholung"


def _assign_pattern_labels(kmeans: KMeans) -> dict[int, str]:
    """Map cluster IDs to semantic labels based on cluster centers.

    Labels are German because they are stored in ml_predictions.meta and surfaced
    directly in the dashboard UI — renaming requires a DB migration.
      stabil_hoch  — high, stable energy throughout the day
      erholung     — low start, rising curve (recovery day)
      erschoepft   — overall low or rapidly draining battery (overreached/fatigued)

    Assignment heuristic: highest AUC + below-median daily_range → stabil_hoch;
    highest evening-minus-morning delta → erholung; remainder → erschoepft.
    """
    centers = kmeans.cluster_centers_
    # Features order: morning_avg, evening_avg, daily_range, auc, n_dips
    aucs = centers[:, 3]
    ranges = centers[:, 2]
    morning = centers[:, 0]
    evening = centers[:, 1]

    labels: dict[int, str] = {}
    sorted_by_auc = np.argsort(aucs)[::-1]

    # Highest auc + smallest range → stable_high
    # Lowest morning but highest (evening - morning) → recovering
    # Remaining → drained
    deltas = evening - morning
    for rank, cluster_id in enumerate(sorted_by_auc):
        cid = int(cluster_id)
        if rank == 0 and ranges[cid] < np.median(ranges):
            labels[cid] = "stabil_hoch"
        elif deltas[cid] == deltas.max() and "stabil_hoch" not in labels.values():
            labels[cid] = "stabil_hoch"
        elif deltas[cid] >= 0 and cid not in labels:
            labels[cid] = "erholung"
        else:
            labels[cid] = "erschoepft"

    _fill_missing_labels(labels, _N_CLUSTERS)
    return labels


def fit_and_save(
    history: dict[str, list[dict[str, Any]]], model_dir: str, user_id: int
) -> bool:
    """Train k-means on feature vectors from history days. Returns True on success."""
    feature_rows = []
    for day_records in history.values():
        feat = extract_features(day_records)
        if feat is not None:
            feature_rows.append(list(feat.values()))

    if len(feature_rows) < _MIN_DAYS:
        return False

    X = np.array(feature_rows)
    kmeans = KMeans(n_clusters=_N_CLUSTERS, random_state=42, n_init=10)
    kmeans.fit(X)

    labels = _assign_pattern_labels(kmeans)
    path = Path(model_dir) / f"battery_pattern_{user_id}.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"kmeans": kmeans, "labels": labels}, path)
    return True


def predict_today(
    records: list[dict[str, Any]], model_dir: str, user_id: int
) -> dict[str, Any] | None:
    """Classify today's body battery curve. Returns None if model not trained yet."""
    path = Path(model_dir) / f"battery_pattern_{user_id}.joblib"
    if not path.exists():
        return None

    feat = extract_features(records)
    if feat is None:
        return None

    saved = joblib.load(path)
    kmeans: KMeans = saved["kmeans"]
    labels: dict[int, str] = saved["labels"]

    X = np.array([list(feat.values())])
    cluster = int(kmeans.predict(X)[0])
    return {"cluster": cluster, "pattern": labels[cluster], "features": feat}
