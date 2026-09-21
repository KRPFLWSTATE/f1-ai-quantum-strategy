"""A3 classical/quantum candidate portfolios and inspectable runtime dispatcher."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from f1q.a3.problem import (
    FEATURE_KEYS,
    A3Instance,
    binary_to_policy,
    build_a3_qubo,
    feature_vector,
    policy_to_simulator_plan,
    proxy_direct_cost,
    qubo_structural_features,
    repair_to_legal_plan,
    variable_index_map,
)
from collections import Counter

from f1q.hashing import sha256_json
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage6.metrics_pilot import distribution_hash

ARMS = (
    "classical_only",
    "classical_plus_c0",
    "classical_plus_c1",
    "always_hybrid_c0",
    "always_hybrid_c1",
    "fixed_c0",
    "nn_transfer",
    "random_donor",
    "threshold_rule",
)


def enumerate_legal_policies(instance: A3Instance) -> list[dict[str, Any]]:
    from itertools import product

    vmap = variable_index_map(instance)
    n = vmap["n"]
    choices = [list(range(b["start"], b["end"])) for b in vmap["blocks"]]
    rows = []
    for chosen in product(*choices):
        x = np.zeros(n, dtype=int)
        for i in chosen:
            x[int(i)] = 1
        pol = binary_to_policy(instance, x)
        if pol is None:
            continue
        cost = proxy_direct_cost(instance, pol)
        wrapped = policy_to_simulator_plan(instance, pol)
        rows.append({"x": x, "policy": pol, "proxy_cost": cost, "plan": wrapped["plan"], "wrapped": wrapped})
    rows.sort(key=lambda r: (r["proxy_cost"], int(np.dot(r["x"], 1 << np.arange(n)))))
    return rows


def greedy_plan(instance: A3Instance) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return {"plan": {c: {"kind": "continuation"} for c in instance.car_ids}, "method": "empty_fallback"}
    return {**rows[0], "method": "greedy_min_proxy"}


def local_improve(instance: A3Instance, seed: int = 0) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return greedy_plan(instance)
    rng = np.random.default_rng(seed)
    cur = rows[0]
    # One-hot block flips among legal enum (small menu).
    for _ in range(min(8, len(rows))):
        cand = rows[int(rng.integers(0, len(rows)))]
        if cand["proxy_cost"] < cur["proxy_cost"]:
            cur = cand
    return {**cur, "method": "greedy_plus_local"}


def simulated_annealing(instance: A3Instance, seed: int, steps: int = 20) -> dict[str, Any]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return greedy_plan(instance)
    rng = np.random.default_rng(seed)
    idx = int(rng.integers(0, len(rows)))
    cur = rows[idx]
    best = cur
    for t in range(steps):
        nxt = rows[int(rng.integers(0, len(rows)))]
        d = nxt["proxy_cost"] - cur["proxy_cost"]
        T = max(0.01, 0.3 * (1.0 - t / steps))
        if d <= 0 or rng.random() < np.exp(-d / T):
            cur = nxt
            if cur["proxy_cost"] < best["proxy_cost"]:
                best = cur
    return {**best, "method": "sa"}


def uniform_legal(instance: A3Instance, k: int, seed: int) -> list[dict[str, Any]]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return []
    rng = np.random.default_rng(seed)
    take = min(k, len(rows))
    idxs = rng.choice(len(rows), size=take, replace=False)
    return [{**rows[int(i)], "method": "uniform_legal"} for i in idxs]


def diversity_topk(instance: A3Instance, k: int) -> list[dict[str, Any]]:
    rows = enumerate_legal_policies(instance)
    if not rows:
        return []
    selected = [rows[0]]
    for _ in range(min(k, len(rows)) - 1):
        best = None
        best_d = -1.0
        for r in rows:
            if any(np.array_equal(r["x"], s["x"]) for s in selected):
                continue
            d = min(float(np.sum(np.abs(r["x"] - s["x"]))) for s in selected)
            if d > best_d:
                best_d = d
                best = r
        if best is None:
            break
        selected.append(best)
    for s in selected:
        s["method"] = s.get("method") or "diversity_topk"
    return selected


def classical_portfolio(instance: A3Instance, *, k: int = 4, seed: int = 0) -> list[dict[str, Any]]:
    """Deadline-feasible classical generators. Offline exhaustive is labelled separately."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(row: dict[str, Any]) -> None:
        key = sha256_json(row["plan"])
        if key in seen:
            return
        seen.add(key)
        out.append(row)

    _add(greedy_plan(instance))
    _add(local_improve(instance, seed=seed))
    _add(simulated_annealing(instance, seed=seed + 17))
    for r in uniform_legal(instance, k=2, seed=seed + 3):
        _add(r)
    for r in diversity_topk(instance, k=k):
        _add(r)
    # Always retain classical fallback.
    fallback = {"plan": {c: {"kind": "continuation"} for c in instance.car_ids}, "method": "mandatory_fallback", "proxy_cost": None, "x": None}
    _add(fallback)
    return out


def default_params(p: int, seed: int) -> tuple[list[float], list[float]]:
    rng = np.random.default_rng(seed)
    gammas = (0.3 + 0.15 * rng.standard_normal(p)).tolist()
    betas = (0.2 + 0.15 * rng.standard_normal(p)).tolist()
    return gammas, betas


def quantum_candidates(
    instance: A3Instance,
    qubo: dict[str, Any],
    *,
    family: str,
    p: int,
    params: tuple[list[float], list[float]],
    pool_size: int,
    seed: int,
    sim_validate,
) -> dict[str, Any]:
    gammas, betas = params
    if family == "C0":
        sim = simulate_c0(qubo, gammas, betas, scaled=True)
    else:
        sim = simulate_c1(instance, qubo, gammas, betas, scaled=True)
    n = int(qubo["n"])
    p_norm = np.asarray(sim["probs"], dtype=np.float64)
    p_norm = p_norm / max(float(p_norm.sum()), 1e-30)
    rng = np.random.default_rng(seed)
    idx = rng.choice(p_norm.size, size=int(pool_size), replace=True, p=p_norm)
    counts = Counter(int(b) for b in idx)
    hist = {str(b): int(c) for b, c in sorted(counts.items())}
    n_legal = n_decode_invalid = n_repaired = 0
    decoded = []
    for b_s, cnt in sorted(hist.items(), key=lambda kv: -int(kv[1])):
        b = int(b_s)
        x = np.array([(b >> k) & 1 for k in range(n)], dtype=int)
        repaired = repair_to_legal_plan(instance, sim_validate, x)
        if binary_to_policy(instance, x) is None:
            n_decode_invalid += int(cnt)
        elif repaired["repaired"]:
            n_repaired += int(cnt)
        else:
            n_legal += int(cnt)
        decoded.append(
            {
                "bitstring": b,
                "count": int(cnt),
                "plan": repaired["plan"],
                "repaired": repaired["repaired"],
                "reason": repaired["reason"],
                "method": f"quantum_{family}_p{p}",
            }
        )
        if len(decoded) >= 8:
            break
    pool = {
        "seed": int(seed),
        "requested_shots": int(pool_size),
        "actual_draws": int(idx.size),
        "histogram_sum": int(sum(counts.values())),
        "shot_conservation_ok": int(idx.size) == int(pool_size) and int(sum(counts.values())) == int(idx.size),
        "histogram_sparse": hist,
        "distribution_hash": distribution_hash(p_norm),
        "rng_id": "numpy.random.Generator",
        "rng_bit_generator": type(rng.bit_generator).__name__,
        "numpy_version": str(np.__version__),
        "n_legal_in_pool": n_legal,
        "n_decoding_invalid": n_decode_invalid,
        "n_repaired": n_repaired,
        "circuit_id": family,
        "instance_id": instance.instance_id,
        "policy_id": f"{family}_p{p}",
        "candidate_selection_rule": "lex_first_among_tied_best_bitstrings",
    }
    return {
        "family": family,
        "p": p,
        "n": n,
        "norm": float(sim["norm"]),
        "expectation_scaled": float(sim["expectation_scaled"]),
        "amp_outside_one_hot": float(sim.get("amp_outside_one_hot", 0.0)),
        "pool": pool,
        "decoded": decoded,
        "resource_counts": {"n_qubits": n, "p": p, "param_count": 2 * p, "family": family},
        "not_claimed_novel_mixer": True,
    }


class RidgeRuntime:
    """Small inspectable NumPy ridge: predicted marginal utility and latency."""

    def __init__(self, l2: float = 1.0):
        self.l2 = l2
        self.w_util: np.ndarray | None = None
        self.w_lat: np.ndarray | None = None
        self.mean = None
        self.std = None
        self.uncertainty: float = 0.05
        self.fit_receipt: dict[str, Any] = {}

    def _std(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < 1e-12, 1.0, std)
        return (X - mean) / std, mean, std

    def fit(self, X: np.ndarray, y_util: np.ndarray, y_lat: np.ndarray) -> dict[str, Any]:
        Xs, mean, std = self._std(X)
        Xs = np.hstack([np.ones((Xs.shape[0], 1)), Xs])
        d = Xs.shape[1]
        A = Xs.T @ Xs + self.l2 * np.eye(d)
        self.w_util = np.linalg.solve(A, Xs.T @ y_util)
        self.w_lat = np.linalg.solve(A, Xs.T @ y_lat)
        self.mean = mean
        self.std = std
        pred = Xs @ self.w_util
        resid = y_util - pred
        self.uncertainty = float(np.std(resid) + 1e-6)
        self.fit_receipt = {
            "n_train": int(X.shape[0]),
            "l2": self.l2,
            "feature_keys": FEATURE_KEYS,
            "w_util": self.w_util.tolist(),
            "w_lat": self.w_lat.tolist(),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "residual_std_util": self.uncertainty,
            "hash": sha256_json({"w_util": self.w_util.tolist(), "w_lat": self.w_lat.tolist()}),
            "no_hidden_future_features": True,
            "no_evaluator_outcome_features": True,
        }
        return self.fit_receipt

    def predict(self, feats: dict[str, float]) -> dict[str, float]:
        v = feature_vector(feats)
        if self.w_util is None or self.mean is None or self.std is None:
            return {"pred_marginal_utility": 0.0, "pred_latency_s": 0.05, "uncertainty": 1.0}
        z = (v - self.mean) / self.std
        z = np.concatenate([[1.0], z])
        return {
            "pred_marginal_utility": float(z @ self.w_util),
            "pred_latency_s": float(max(0.0, z @ self.w_lat)),
            "uncertainty": float(self.uncertainty),
        }


def dispatch_choice(
    pred: dict[str, float],
    *,
    deadline_s: float,
    margin: float,
    mode: str,
) -> str:
    """Safe choice among classical_only / classical+C0 / classical+C1."""
    if mode == "always_classical":
        return "classical_only"
    if mode == "always_hybrid_c0":
        return "classical_plus_c0"
    if mode == "always_hybrid_c1":
        return "classical_plus_c1"
    if mode == "fixed_c0":
        return "classical_plus_c0"
    if mode == "threshold_rule":
        if pred["pred_marginal_utility"] > 0.002 and pred["pred_latency_s"] < 0.6 * deadline_s:
            return "classical_plus_c0"
        return "classical_only"
    # learned dispatcher
    if pred["uncertainty"] > 3.0 * margin:
        return "classical_only"
    if pred["pred_latency_s"] > 0.8 * max(deadline_s, 1e-6):
        return "classical_only"
    if pred["pred_marginal_utility"] < margin:
        return "classical_only"
    if pred["pred_marginal_utility"] > 2 * margin:
        return "classical_plus_c1"
    return "classical_plus_c0"


def assemble_portfolio(
    instance: A3Instance,
    qubo: dict[str, Any],
    *,
    choice: str,
    seed: int,
    pool_size: int,
    sim_validate,
    params_c0: tuple[list[float], list[float]],
    params_c1: tuple[list[float], list[float]],
    equal_k: int = 4,
) -> dict[str, Any]:
    classical = classical_portfolio(instance, k=equal_k, seed=seed)
    quantum_rows: list[dict[str, Any]] = []
    qrec = None
    if choice in ("classical_plus_c0", "always_hybrid_c0") or choice == "classical_plus_c0":
        qrec = quantum_candidates(
            instance, qubo, family="C0", p=1, params=params_c0, pool_size=pool_size, seed=seed, sim_validate=sim_validate
        )
        quantum_rows = qrec["decoded"]
    elif choice in ("classical_plus_c1", "always_hybrid_c1"):
        qrec = quantum_candidates(
            instance, qubo, family="C1", p=1, params=params_c1, pool_size=pool_size, seed=seed, sim_validate=sim_validate
        )
        quantum_rows = qrec["decoded"]
    # Fairness view 1: equal number of downstream-evaluated candidates.
    merged = classical[:equal_k]
    for q in quantum_rows:
        if len(merged) >= equal_k * 2:
            break
        merged.append(q)
    # Unique plans
    uniq = []
    seen = set()
    for row in merged:
        key = sha256_json(row["plan"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return {
        "choice": choice,
        "classical": classical,
        "quantum": qrec,
        "downstream_candidates": uniq,
        "n_classical": len(classical),
        "n_quantum_decoded": len(quantum_rows),
        "n_downstream": len(uniq),
        "fairness_equal_k": equal_k,
        "mandatory_classical_fallback": True,
    }
