"""Immutable circuit distributions: once per unique key; C1 legal-subspace only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from f1q import SIMULATOR_VERSION
from f1q.a4.cache import ByteBoundedCache
from f1q.a4.circuits import simulate_c0, simulate_c1
from f1q.hashing import sha256_json
from f1q.stage6.metrics_pilot import distribution_hash

_BUILD_COUNTERS: dict[str, int] = {"distribution_builds": 0, "resamples": 0}


def reset_distribution_counters() -> None:
    _BUILD_COUNTERS["distribution_builds"] = 0
    _BUILD_COUNTERS["resamples"] = 0


def distribution_counters() -> dict[str, int]:
    return dict(_BUILD_COUNTERS)


def distribution_key(
    *,
    prepared_case_hash: str,
    family: str,
    depth: int,
    donor_parameters: tuple[list[float], list[float]] | dict[str, Any],
    simulator_version: str = SIMULATOR_VERSION,
) -> str:
    if isinstance(donor_parameters, dict):
        payload = donor_parameters
    else:
        gammas, betas = donor_parameters
        payload = {"gammas": list(gammas), "betas": list(betas)}
    return sha256_json(
        {
            "prepared_case_hash": prepared_case_hash,
            "family": family,
            "depth": int(depth),
            "donor_parameters": payload,
            "simulator_version": simulator_version,
        }
    )


@dataclass(frozen=True)
class IdealDistribution:
    key: str
    family: str
    p: int
    n: int
    n_legal: int
    legal_xs: tuple[tuple[int, ...], ...]
    legal_bitstrings: tuple[int, ...]
    probs_legal: tuple[float, ...]
    expectation_scaled: float
    dense_2n_allocated: bool
    distribution_hash: str

    def probs_array(self) -> np.ndarray:
        return np.asarray(self.probs_legal, dtype=np.float64)


def build_ideal_distribution(
    *,
    instance: Any,
    qubo: dict[str, Any],
    family: str,
    depth: int,
    gammas: list[float],
    betas: list[float],
    prepared_case_hash: str,
    cache: ByteBoundedCache | dict[str, Any] | None = None,
    legal_table: list[dict[str, Any]] | None = None,
) -> IdealDistribution:
    key = distribution_key(
        prepared_case_hash=prepared_case_hash,
        family=family,
        depth=depth,
        donor_parameters=(gammas, betas),
    )
    if cache is not None:
        hit = cache.get(key) if isinstance(cache, ByteBoundedCache) else cache.get(key)
        if hit is not None and isinstance(hit, IdealDistribution):
            return hit
        if hit is not None and isinstance(hit, dict) and hit.get("key") == key:
            return _from_dict(hit)
    _BUILD_COUNTERS["distribution_builds"] += 1
    if family == "C0":
        sim = simulate_c0(qubo, list(gammas), list(betas), scaled=True)
        probs = np.asarray(sim["probs"], dtype=np.float64)
        n = int(qubo["n"])
        legal_idx = tuple(int(i) for i in range(probs.size) if probs[i] > 0.0)
        if not legal_idx:
            legal_idx = tuple(range(min(probs.size, 1)))
        legal_xs = tuple(tuple((b >> k) & 1 for k in range(n)) for b in legal_idx)
        p_legal = tuple(float(probs[i]) for i in legal_idx)
        dist = IdealDistribution(
            key=key,
            family="C0",
            p=int(depth),
            n=n,
            n_legal=len(legal_idx),
            legal_xs=legal_xs,
            legal_bitstrings=legal_idx,
            probs_legal=p_legal,
            expectation_scaled=float(sim["expectation_scaled"]),
            dense_2n_allocated=True,
            distribution_hash=distribution_hash(probs),
        )
    else:
        sim = simulate_c1(
            instance,
            qubo,
            list(gammas),
            list(betas),
            scaled=True,
            legal_table=legal_table,
            allocate_dense=False,
        )
        if sim.get("dense_2n_allocated"):
            raise RuntimeError("C1 must not allocate a dense 2^n probability vector")
        xs = tuple(tuple(int(v) for v in row) for row in sim["legal_xs"])
        bits = tuple(int(b) for b in sim["legal_bitstrings"])
        p_legal = tuple(float(p) for p in np.asarray(sim["probs_legal"], dtype=np.float64))
        dist = IdealDistribution(
            key=key,
            family="C1",
            p=int(depth),
            n=int(qubo["n"]),
            n_legal=int(sim["n_legal"]),
            legal_xs=xs,
            legal_bitstrings=bits,
            probs_legal=p_legal,
            expectation_scaled=float(sim["expectation_scaled"]),
            dense_2n_allocated=False,
            distribution_hash=str(sim.get("distribution_hash") or distribution_hash(np.asarray(p_legal))),
        )
    if cache is not None:
        if isinstance(cache, ByteBoundedCache):
            cache.put(key, dist)
        else:
            cache[key] = dist
    return dist


def resample_pool(dist: IdealDistribution, *, pool_draws: int, seed: int) -> dict[str, Any]:
    _BUILD_COUNTERS["resamples"] += 1
    p = np.asarray(dist.probs_legal, dtype=np.float64)
    s = float(p.sum())
    if s <= 0 or p.size == 0:
        p = np.ones(max(len(dist.legal_bitstrings), 1), dtype=np.float64)
        s = float(p.sum())
    p = p / s
    rng = np.random.default_rng(int(seed))
    idx = rng.choice(p.size, size=int(pool_draws), replace=True, p=p)
    from collections import Counter

    counts = Counter(int(i) for i in idx)
    hist = {str(dist.legal_bitstrings[i] if i < len(dist.legal_bitstrings) else i): int(c) for i, c in sorted(counts.items())}
    return {
        "seed": int(seed),
        "requested_shots": int(pool_draws),
        "actual_draws": int(idx.size),
        "histogram_sum": int(sum(counts.values())),
        "shot_conservation_ok": int(idx.size) == int(pool_draws) and int(sum(counts.values())) == int(idx.size),
        "histogram_sparse": hist,
        "index_counts": {str(i): int(c) for i, c in sorted(counts.items())},
        "distribution_key": dist.key,
        "distribution_hash": dist.distribution_hash,
        "dense_2n_allocated": dist.dense_2n_allocated,
        "family": dist.family,
        "p": dist.p,
    }


def _from_dict(d: dict[str, Any]) -> IdealDistribution:
    return IdealDistribution(
        key=str(d["key"]),
        family=str(d["family"]),
        p=int(d["p"]),
        n=int(d["n"]),
        n_legal=int(d["n_legal"]),
        legal_xs=tuple(tuple(int(v) for v in row) for row in d["legal_xs"]),
        legal_bitstrings=tuple(int(b) for b in d["legal_bitstrings"]),
        probs_legal=tuple(float(p) for p in d["probs_legal"]),
        expectation_scaled=float(d["expectation_scaled"]),
        dense_2n_allocated=bool(d["dense_2n_allocated"]),
        distribution_hash=str(d["distribution_hash"]),
    )
