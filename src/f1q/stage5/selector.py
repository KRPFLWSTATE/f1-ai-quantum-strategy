"""Inspectable NumPy ridge learned donor selector (training-only fit)."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from f1q.hashing import sha256_json
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage5.encode import binary_to_policy
from f1q.stage5.evaluate import check_policy_legal, evaluate_policy_cost
from f1q.stage5.model import A2Instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.splits import assert_features_clean


def compute_features(instance: A2Instance, qubo: dict[str, Any], family: str, p: int) -> dict[str, float]:
    t0 = time.perf_counter()
    blocks = instance.variable_blocks()
    Q = np.asarray(qubo["Q_dense"], dtype=float)
    nnz = int(np.count_nonzero(Q))
    feats = {
        "n_logical_vars": float(qubo["n"]),
        "n_info_sets": float(len(instance.info_sets)),
        "n_scenarios": float(len(instance.scenarios)),
        "n_epochs": float(instance.n_epochs),
        "n_blocks": float(len(blocks)),
        "mean_block_size": float(np.mean([b["size"] for b in blocks])),
        "qubo_n_terms": float(qubo["n_terms"]),
        "qubo_density": float(qubo["density"]),
        "coeff_abs_mean": float(np.mean(np.abs(Q))) if Q.size else 0.0,
        "coeff_abs_max": float(np.max(np.abs(Q))) if Q.size else 0.0,
        "penalty_M": float(qubo["penalty_M"]),
        "crew_overlap_cost": float(instance.crew_overlap_cost),
        "family_is_c1": 1.0 if family == "C1" else 0.0,
        "depth_p": float(p),
        "nnz_Q": float(nnz),
    }
    assert_features_clean(feats)
    feats["feature_compute_s"] = time.perf_counter() - t0
    return feats


FEATURE_KEYS = [
    "n_logical_vars",
    "n_info_sets",
    "n_scenarios",
    "n_epochs",
    "n_blocks",
    "mean_block_size",
    "qubo_n_terms",
    "qubo_density",
    "coeff_abs_mean",
    "coeff_abs_max",
    "penalty_M",
    "crew_overlap_cost",
    "family_is_c1",
    "depth_p",
    "nnz_Q",
]


def _vec(feats: dict[str, float]) -> np.ndarray:
    return np.array([feats[k] for k in FEATURE_KEYS], dtype=float)


class RidgeDonorSelector:
    """Ranks donors by predicted regret; does not average angle vectors."""

    def __init__(self, ridge_lambda: float = 1.0):
        self.ridge_lambda = ridge_lambda
        self.W: np.ndarray | None = None  # (n_features, n_donors) score weights per donor slot shared
        self.donor_ids: list[str] = []
        self.mean_x = None
        self.std_x = None

    def fit(self, X: np.ndarray, y: np.ndarray, donor_ids: list[str]) -> dict[str, Any]:
        """X: (n_samples, n_features), y: (n_samples, n_donors) observed regrets (lower better)."""
        self.donor_ids = list(donor_ids)
        self.mean_x = X.mean(axis=0)
        self.std_x = X.std(axis=0)
        self.std_x[self.std_x < 1e-12] = 1.0
        Xs = (X - self.mean_x) / self.std_x
        # For each donor, ridge regress predicted regret
        n_f = Xs.shape[1]
        W = []
        for d in range(y.shape[1]):
            A = Xs.T @ Xs + self.ridge_lambda * np.eye(n_f)
            b = Xs.T @ y[:, d]
            w = np.linalg.solve(A, b)
            W.append(w)
        self.W = np.stack(W, axis=1)
        return {
            "model": "numpy_ridge_ranking",
            "ridge_lambda": self.ridge_lambda,
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_donors": len(donor_ids),
            "weights_hash": sha256_json(self.W.tolist()),
        }

    def predict_scores(self, feats: dict[str, float]) -> np.ndarray:
        assert self.W is not None
        x = _vec(feats)
        xs = (x - self.mean_x) / self.std_x
        return xs @ self.W  # predicted regret per donor

    def select(self, feats: dict[str, float], donors: list[dict[str, Any]]) -> dict[str, Any]:
        scores = self.predict_scores(feats)
        # Map to available donors by index order used in training
        order = list(np.argsort(scores))  # lower predicted regret first
        best_i = int(order[0])
        if best_i >= len(donors):
            best_i = 0
        return {
            "selected_index": best_i,
            "selected_donor": donors[best_i],
            "predicted_regrets": scores.tolist(),
            "rule": "argmin_predicted_regret_no_angle_average",
        }


def evaluate_donor_on_instance(
    instance: A2Instance,
    qubo: dict[str, Any],
    donor: dict[str, Any],
    *,
    exact_cost: float | None,
    pool_size: int = 32,
    seed: int = 0,
) -> dict[str, Any]:
    family = donor["family"]
    p = int(donor["p"])
    params = np.asarray(donor["params"], dtype=float)
    gammas = params[:p].tolist()
    betas = params[p:].tolist()
    if family == "C0":
        sim = simulate_c0(qubo, gammas, betas, scaled=True)
    else:
        sim = simulate_c1(instance, qubo, gammas, betas, scaled=True)
    probs = sim["probs"]
    n = int(qubo["n"])
    rng = np.random.default_rng(seed)
    raw_feas = 0.0
    opt_prob = 0.0
    costs = []
    for b in range(1 << n):
        pr = float(probs[b])
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        raw_feas += pr
        if not check_policy_legal(instance, pol)["legal"]:
            continue
        c = float(evaluate_policy_cost(instance, pol)["expected_cost"])
        costs.append((pr, c))
        if exact_cost is not None and abs(c - exact_cost) <= 1e-8:
            opt_prob += pr
    # best-of-pool
    idx = rng.choice(1 << n, size=min(pool_size, 1 << n), replace=True, p=probs / max(probs.sum(), 1e-30))
    best = float("inf")
    for b in idx:
        x = np.array([(int(b) >> k) & 1 for k in range(n)], dtype=int)
        pol = binary_to_policy(instance, x)
        if pol is None or not check_policy_legal(instance, pol)["legal"]:
            continue
        best = min(best, float(evaluate_policy_cost(instance, pol)["expected_cost"]))
    regret = None if exact_cost is None or best == float("inf") else best - exact_cost
    return {
        "raw_feasibility": raw_feas,
        "optimal_sample_prob": opt_prob,
        "best_of_pool_regret": regret,
        "mean_energy_scaled": float(sim["expectation_scaled"]),
    }


def paired_interval(diffs: list[float], alpha: float = 0.05) -> dict[str, Any]:
    """One-sided 95% paired interval for mean(learned - reference) regret (upper bound)."""
    arr = np.asarray(diffs, dtype=float)
    n = arr.size
    if n == 0:
        return {"n": 0, "mean": None, "upper_95": None}
    mean = float(arr.mean())
    se = float(arr.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    # normal approx one-sided z_0.95 ≈ 1.645
    z = 1.6448536269514722
    upper = mean + z * se
    return {"n": int(n), "mean": mean, "se": se, "upper_95_one_sided": upper, "alpha": alpha}


def nn_transfer_donor(feats: dict[str, float], train_feats: list[dict[str, float]], donors_per_row: list[list[dict]]) -> dict:
    x = _vec(feats)
    best_d = None
    best_dist = float("inf")
    for i, tf in enumerate(train_feats):
        d = float(np.linalg.norm(x - _vec(tf)))
        if d < best_dist and donors_per_row[i]:
            best_dist = d
            best_d = donors_per_row[i][0]
    return best_d
