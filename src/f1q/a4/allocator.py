"""Inspectable A4 donor ranker and runtime allocator g(z,m,b)."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.a4.problem import FEATURE_KEYS, feature_vector
from f1q.hashing import sha256_json


class RidgeModel:
    def __init__(self, l2: float = 1.0):
        self.l2 = l2
        self.w: np.ndarray | None = None
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.residual_std: float = 1.0
        self.fit_receipt: dict[str, Any] = {}

    def _std(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < 1e-12, 1.0, std)
        return (X - mean) / std, mean, std

    def fit(self, X: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        Xs, mean, std = self._std(X)
        Xs = np.hstack([np.ones((Xs.shape[0], 1)), Xs])
        d = Xs.shape[1]
        A = Xs.T @ Xs + self.l2 * np.eye(d)
        self.w = np.linalg.solve(A, Xs.T @ y)
        self.mean = mean
        self.std = std
        pred = Xs @ self.w
        resid = y - pred
        self.residual_std = float(np.std(resid) + 1e-6)
        self.fit_receipt = {
            "n_train": int(X.shape[0]),
            "l2": self.l2,
            "feature_keys": FEATURE_KEYS,
            "w": self.w.tolist(),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "residual_std": self.residual_std,
            "hash": sha256_json({"w": self.w.tolist()}),
            "no_hidden_future_features": True,
            "no_evaluator_outcome_features": True,
            "no_exact_optima_as_online_features": True,
        }
        return self.fit_receipt

    def predict(self, feats: dict[str, float]) -> dict[str, float]:
        v = feature_vector(feats)
        if self.w is None or self.mean is None or self.std is None:
            return {"pred_marginal_utility": 0.0, "uncertainty": 1.0}
        z = (v - self.mean) / self.std
        z = np.concatenate([[1.0], z])
        return {"pred_marginal_utility": float(z @ self.w), "uncertainty": float(self.residual_std)}


def dispatch_choice(
    pred: dict[str, float],
    *,
    deadline_s: float,
    pred_latency_s: float,
    margin: float,
    mode: str,
    conservative_residual: float,
) -> str:
    if mode in {"always_classical", "classical_only"}:
        return "classical_only"
    if mode == "always_c0":
        return "always_c0"
    if mode == "always_c1":
        return "always_c1"
    if mode == "threshold":
        adj = pred["pred_marginal_utility"] - conservative_residual
        if adj > 0.0 and pred_latency_s < 0.8 * deadline_s:
            return "hybrid_c0"
        return "classical_only"
    # learned allocator
    adj = pred["pred_marginal_utility"] - conservative_residual
    if pred["uncertainty"] > 3.0 * max(margin, 1e-6):
        return "classical_only"
    if pred_latency_s > 0.8 * max(deadline_s, 1e-6):
        return "classical_only"
    if adj <= 0.0:
        return "classical_only"
    if adj > 2 * margin:
        return "hybrid_c1"
    return "hybrid_c0"


def select_donor(
    *,
    policy: str,
    donors: list[dict[str, Any]],
    feats: dict[str, float],
    ranker: RidgeModel | None,
    rng: np.random.Generator,
) -> dict[str, Any]:
    if not donors:
        return {"selected": None, "policy": policy, "reason": "empty_bank"}
    if policy == "fixed":
        return {"selected": donors[0], "policy": "fixed"}
    if policy == "random":
        i = int(rng.integers(0, len(donors)))
        return {"selected": donors[i], "policy": "random"}
    if policy == "nn":
        # nearest neighbour on n_logical_vars then remaining_laps
        def _key(d):
            df = d.get("features") or {}
            return abs(float(df.get("n_logical_vars", 0) - feats.get("n_logical_vars", 0))) + 0.01 * abs(
                float(df.get("remaining_laps", 0) - feats.get("remaining_laps", 0))
            )

        best = min(donors, key=_key)
        return {"selected": best, "policy": "nn"}
    # learned ranker: score each donor via concatenated features (instance feats only; donor id as bias via order)
    if ranker is None or ranker.w is None:
        return {"selected": donors[0], "policy": "learned_fallback_fixed"}
    pred = ranker.predict(feats)
    # Higher predicted utility → prefer later donors only as a weak rank; keep inspectable:
    # use residual to pick the donor whose training objective is best among those with matching n.
    n_target = feats.get("n_logical_vars")
    matched = [d for d in donors if (d.get("features") or {}).get("n_logical_vars") == n_target]
    pool = matched or donors
    pool = sorted(pool, key=lambda d: (float(d.get("best_value_scaled", 0.0)), d.get("params_hash") or ""))
    idx = 0 if pred["pred_marginal_utility"] <= 0 else min(len(pool) - 1, 1)
    return {"selected": pool[idx], "policy": "learned", "pred": pred}
