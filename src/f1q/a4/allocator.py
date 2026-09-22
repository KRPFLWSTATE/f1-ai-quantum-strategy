"""Option-level allocator g(z,m,b). Donor ranking lives in f1q.a4.donors."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.a4.contracts import ALLOCATOR_OPTIONS, StructuralError
from f1q.a4.donors import DonorRanker, selected_donors, select_donor_policy
from f1q.hashing import sha256_json

ALLOCATOR_FEATURE_KEYS = [
    "n_logical_vars",
    "n_legal_joint",
    "qubo_density",
    "penalty_M",
    "remaining_laps",
    "completed_laps",
    "mean_tyre_age",
    "mean_gap_ahead",
    "crew_overlap_cost",
    "effective_remaining_s",
    "n_expired",
    "regime_is_sc",
    "n_pit_now_actions",
    "n_delay_actions",
    "nominal_budget_s",
    "portfolio_k",
    "pool_draws",
    "pred_latency_s",
    "opt_stop_fallback",
    "opt_classical_only",
    "opt_C0_p1",
    "opt_C0_p2",
    "opt_C1_p1",
    "opt_C1_p2",
]


class RidgeModel:
    """Option allocator g(z,m,b). Must not be used as a donor ranker."""

    kind = "a4_option_allocator"

    def __init__(self, l2: float = 1.0):
        self.l2 = float(l2)
        self.w: np.ndarray | None = None
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.residual_std: float = 1.0
        self.feature_keys = list(ALLOCATOR_FEATURE_KEYS)
        self.fit_receipt: dict[str, Any] = {}

    def _std(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = x.mean(axis=0)
        std = x.std(axis=0)
        std = np.where(std < 1e-12, 1.0, std)
        return (x - mean) / std, mean, std

    def fit(self, x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        if x.shape[1] != len(self.feature_keys):
            raise StructuralError("SCHEMA", "allocator feature width mismatch", path="RidgeModel.fit")
        xs, mean, std = self._std(x)
        xs = np.hstack([np.ones((xs.shape[0], 1)), xs])
        d = xs.shape[1]
        a = xs.T @ xs + self.l2 * np.eye(d)
        self.w = np.linalg.solve(a, xs.T @ y)
        self.mean = mean
        self.std = std
        pred = xs @ self.w
        resid = y - pred
        self.residual_std = float(np.std(resid) + 1e-6)
        self.fit_receipt = {
            "n_train": int(x.shape[0]),
            "l2": self.l2,
            "kind": self.kind,
            "not_donor_ranker": True,
            "feature_keys": list(self.feature_keys),
            "w": self.w.tolist(),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "residual_std": self.residual_std,
            "hash": sha256_json({"w": self.w.tolist(), "keys": self.feature_keys, "l2": self.l2}),
            "no_hidden_future_features": True,
            "no_evaluator_outcome_features": True,
            "no_exact_optima_as_online_features": True,
        }
        return self.fit_receipt

    def to_artifact(self) -> dict[str, Any]:
        if self.w is None or self.mean is None or self.std is None:
            raise StructuralError("SCHEMA", "unfitted allocator", path="RidgeModel.to_artifact")
        return dict(self.fit_receipt)

    @classmethod
    def from_artifact(cls, art: dict[str, Any]) -> "RidgeModel":
        model = cls(l2=float(art.get("l2") or 1.0))
        keys = list(art.get("feature_keys") or ALLOCATOR_FEATURE_KEYS)
        if keys != ALLOCATOR_FEATURE_KEYS:
            raise StructuralError("SCHEMA", "allocator feature order mismatch", path="RidgeModel.from_artifact")
        model.w = np.asarray(art["w"], dtype=float)
        model.mean = np.asarray(art["mean"], dtype=float)
        model.std = np.asarray(art["std"], dtype=float)
        model.residual_std = float(art.get("residual_std") or 1.0)
        model.fit_receipt = dict(art)
        return model

    def predict_vector(self, vec: np.ndarray) -> dict[str, float]:
        if self.w is None or self.mean is None or self.std is None:
            return {"pred_marginal_utility": 0.0, "uncertainty": 1.0}
        z = (vec - self.mean) / self.std
        z = np.concatenate([[1.0], z])
        return {"pred_marginal_utility": float(z @ self.w), "uncertainty": float(self.residual_std)}

    def predict(self, feats: dict[str, float]) -> dict[str, float]:
        vec = allocator_feature_vector(feats)
        return self.predict_vector(vec)


def allocator_feature_vector(feats: dict[str, float]) -> np.ndarray:
    return np.array([float(feats.get(k, 0.0)) for k in ALLOCATOR_FEATURE_KEYS], dtype=float)


def option_feature_row(
    base: dict[str, float],
    *,
    option: str,
    nominal_budget_s: float,
    effective_remaining_s: float,
    k: int,
    pool_draws: int,
    pred_latency_s: float,
) -> dict[str, float]:
    if option not in ALLOCATOR_OPTIONS:
        raise StructuralError("SCHEMA", "unknown allocator option", path="option_feature_row.option", value=option)
    row = dict(base)
    row["nominal_budget_s"] = float(nominal_budget_s)
    row["effective_remaining_s"] = float(effective_remaining_s)
    row["portfolio_k"] = float(k)
    row["pool_draws"] = float(pool_draws)
    row["pred_latency_s"] = float(pred_latency_s)
    for opt in ALLOCATOR_OPTIONS:
        row[f"opt_{opt}"] = 1.0 if opt == option else 0.0
    return row


def dispatch_choice(
    pred: dict[str, float],
    *,
    deadline_s: float,
    pred_latency_s: float,
    margin: float,
    mode: str,
    conservative_residual: float,
    allowed_options: tuple[str, ...] | list[str] | None = None,
    freeze: dict[str, Any] | None = None,
) -> str:
    """Map a score to an option. Calibration uses freeze-selected depths and threshold."""
    allowed = list(allowed_options or (list(freeze["allowed_options"]) if freeze else ALLOCATOR_OPTIONS))
    if mode in {"always_classical", "classical_only"}:
        return "classical_only"
    if mode == "always_c0":
        depth = (freeze or {}).get("frozen_c0_depth") or "C0_p1"
        return depth if depth in allowed else ("C0_p1" if "C0_p1" in allowed else "classical_only")
    if mode == "always_c1":
        depth = (freeze or {}).get("frozen_c1_depth") or "C1_p1"
        return depth if depth in allowed else ("C1_p1" if "C1_p1" in allowed else "classical_only")
    if mode in {"always_c0_p2"}:
        return "C0_p2"
    if mode in {"always_c1_p2"}:
        return "C1_p2"
    if mode == "stop_fallback":
        return "stop_fallback"
    lam = float((freeze or {}).get("primary_lambda") or 0.0)
    thresh = float((freeze or {}).get("dispatch_threshold") or 0.0)
    c0 = str((freeze or {}).get("frozen_c0_depth") or "C0_p1")
    c1 = str((freeze or {}).get("frozen_c1_depth") or "C1_p1")
    adj = float(pred.get("pred_marginal_utility") or 0.0) - float(conservative_residual) - lam * float(pred.get("uncertainty") or 0.0) - thresh
    if pred_latency_s > 0.8 * max(deadline_s, 1e-6):
        return "classical_only" if "classical_only" in allowed else "stop_fallback"
    if adj <= 0.0:
        return "classical_only" if "classical_only" in allowed else "stop_fallback"
    if c1 in allowed and adj > 2 * max(margin, 1e-12):
        return c1
    if c0 in allowed:
        return c0
    return "classical_only" if "classical_only" in allowed else "stop_fallback"


def select_calibrated_option(
    scores: dict[str, float],
    *,
    infeasible: set[str] | None = None,
) -> str:
    """Highest positive score; ties toward lower-cost classical; else stop/fallback."""
    blocked = infeasible or set()
    order = ["classical_only", "C0_p1", "C0_p2", "C1_p1", "C1_p2"]
    ranked = []
    for opt in order:
        if opt in blocked:
            continue
        s = float(scores.get(opt, 0.0))
        if s > 0.0:
            ranked.append((s, -order.index(opt), opt))
    if not ranked:
        return "stop_fallback"
    ranked.sort(reverse=True)
    return ranked[0][2]


def select_donor(
    *,
    policy: str,
    donors: list[dict[str, Any]] | dict[str, Any],
    feats: dict[str, float],
    ranker: Any,
    rng: np.random.Generator,
    family_depth: str | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper. Rejects using the allocator RidgeModel as a donor ranker."""
    if isinstance(ranker, RidgeModel):
        raise StructuralError(
            "SCHEMA",
            "allocator RidgeModel cannot be used as a donor ranker",
            path="select_donor.ranker",
        )
    if isinstance(donors, dict):
        if family_depth is None:
            raise StructuralError("SCHEMA", "family_depth required when passing a bank record", path="select_donor")
        donors = selected_donors(donors, family_depth, path="select_donor.donors")
    donor_ranker = ranker if isinstance(ranker, DonorRanker) else None
    if policy == "learned" and donor_ranker is None and ranker is not None:
        raise StructuralError("SCHEMA", "learned donor policy requires DonorRanker", path="select_donor.ranker")
    return select_donor_policy(policy=policy, donors=list(donors), feats=feats, ranker=donor_ranker, rng=rng)
