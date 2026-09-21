"""A4 donor-bank v2 construction, loading, and genuine donor ranking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from f1q.a4.contracts import (
    DONOR_BANK_SCHEMA_V2,
    FAMILY_DEPTH_KEYS,
    StructuralError,
    require_finite,
    require_mapping,
    require_nonempty_list,
)
from f1q.generator.config import cartesian_family_ids
from f1q.hashing import sha256_file, sha256_json

DONOR_FEATURE_KEYS = [
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
    "family_is_c1",
    "depth_p",
]


def _family_depth_key(family: str, p: int) -> str:
    return f"{family}_p{int(p)}"


def _vec(feats: dict[str, float]) -> np.ndarray:
    return np.array([float(feats.get(k, 0.0)) for k in DONOR_FEATURE_KEYS], dtype=float)


def _parse_anchor_row(row: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    if not row.get("success"):
        return None
    family = str(row.get("family") or "")
    p = int(row.get("p") or 0)
    if family not in {"C0", "C1"} or p not in {1, 2}:
        return None
    gammas = list(row.get("gammas") or [])
    betas = list(row.get("betas") or [])
    if len(gammas) != p or len(betas) != p:
        raise StructuralError(
            "SCHEMA",
            "wrong p parameter length on reused anchor row",
            path=f"ANCHOR_FITS.jsonl[{index}].gammas/betas",
            value={"p": p, "n_gammas": len(gammas), "n_betas": len(betas)},
        )
    for i, g in enumerate(gammas):
        require_finite(g, path=f"ANCHOR_FITS.jsonl[{index}].gammas[{i}]")
    for i, b in enumerate(betas):
        require_finite(b, path=f"ANCHOR_FITS.jsonl[{index}].betas[{i}]")
    best = require_finite(row.get("best_value_scaled"), path=f"ANCHOR_FITS.jsonl[{index}].best_value_scaled")
    donor_id = str(row.get("params_hash") or "")
    if not donor_id:
        raise StructuralError("SCHEMA", "missing params_hash", path=f"ANCHOR_FITS.jsonl[{index}]")
    return {
        "donor_id": donor_id,
        "params_hash": donor_id,
        "family": family,
        "p": p,
        "gammas": gammas,
        "betas": betas,
        "best_params": list(row.get("best_params") or (gammas + betas)),
        "best_value_scaled": best,
        "block_id": row.get("block_id"),
        "family_id": row.get("family_id"),
        "source_seed": int(row.get("seed") or 0),
        "source_qubo_hash": row.get("qubo_hash"),
        "features": row.get("features") or {},
        "evals": row.get("evals"),
        "n_qubits": row.get("n_qubits"),
    }


def build_donor_bank_v2(
    fits: list[dict[str, Any]],
    *,
    source_run_id: str,
    source_anchor_path: str,
    source_anchor_sha256: str,
) -> dict[str, Any]:
    families = cartesian_family_ids()
    if len(families) != 8:
        raise StructuralError("SCHEMA", "expected eight instance families", path="cartesian_family_ids", value=len(families))
    parsed: list[dict[str, Any]] = []
    for i, row in enumerate(fits):
        rec = _parse_anchor_row(row, index=i)
        if rec is not None:
            parsed.append(rec)
    family_depths: dict[str, Any] = {}
    for family, p in (("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)):
        key = _family_depth_key(family, p)
        pool = [d for d in parsed if d["family"] == family and d["p"] == p]
        selected: list[dict[str, Any]] = []
        represented: list[str] = []
        for fam in families:
            cand = [d for d in pool if d.get("family_id") == fam]
            if not cand:
                raise StructuralError(
                    "COVERAGE",
                    "no successful donor for instance family",
                    path=f"family_depths.{key}.{fam}",
                    value=None,
                )
            cand.sort(key=lambda d: (float(d["best_value_scaled"]), str(d["params_hash"])))
            best = dict(cand[0])
            represented.append(fam)
            selected.append(best)
        ids = [d["donor_id"] for d in selected]
        if len(set(ids)) != 8:
            # Same params_hash may theoretically win two families; keep both rows but tag.
            pass
        family_depths[key] = {
            "family": family,
            "p": p,
            "donors": selected,
            "represented_instance_families": represented,
            "n_successful_source_starts": len(pool),
            "n_selected": len(selected),
        }
        if represented != families:
            raise StructuralError("COVERAGE", "family coverage incomplete", path=f"family_depths.{key}")
        if len(selected) != 8:
            raise StructuralError("COVERAGE", "expected eight donors", path=f"family_depths.{key}", value=len(selected))
    bank = {
        "schema_version": DONOR_BANK_SCHEMA_V2,
        "source_run_id": source_run_id,
        "source_anchor_path": source_anchor_path,
        "source_anchor_sha256": source_anchor_sha256,
        "construction_rule": "one_best_successful_donor_per_instance_family_tiebreak_best_value_scaled_then_params_hash",
        "family_depths": family_depths,
    }
    bank["bank_hash"] = sha256_json({k: bank[k] for k in bank if k != "bank_hash"})
    validate_donor_bank_v2(bank)
    return bank


def validate_donor_bank_v2(bank: Any, *, path: str = "$") -> dict[str, Any]:
    obj = require_mapping(bank, path=path)
    if obj.get("schema_version") != DONOR_BANK_SCHEMA_V2:
        raise StructuralError("SCHEMA", "wrong donor-bank schema", path=f"{path}.schema_version", value=obj.get("schema_version"))
    depths = require_mapping(obj.get("family_depths"), path=f"{path}.family_depths")
    missing = [k for k in FAMILY_DEPTH_KEYS if k not in depths]
    if missing:
        raise StructuralError("SCHEMA", "missing family/depth key", path=f"{path}.family_depths", value=missing)
    families = cartesian_family_ids()
    for key in FAMILY_DEPTH_KEYS:
        rec = require_mapping(depths[key], path=f"{path}.family_depths.{key}")
        donors = require_nonempty_list(rec.get("donors"), path=f"{path}.family_depths.{key}.donors")
        if len(donors) != 8:
            raise StructuralError("COVERAGE", "expected eight donors", path=f"{path}.family_depths.{key}.donors", value=len(donors))
        family = rec.get("family")
        p = int(rec.get("p") or 0)
        seen_ids: set[str] = set()
        seen_fams: list[str] = []
        for i, d in enumerate(donors):
            dm = require_mapping(d, path=f"{path}.family_depths.{key}.donors[{i}]")
            did = str(dm.get("donor_id") or dm.get("params_hash") or "")
            if not did:
                raise StructuralError("SCHEMA", "missing donor_id", path=f"{path}.family_depths.{key}.donors[{i}]")
            seen_ids.add(did)
            gp = list(dm.get("gammas") or [])
            bp = list(dm.get("betas") or [])
            if len(gp) != p or len(bp) != p:
                raise StructuralError(
                    "SCHEMA",
                    "wrong p parameter length",
                    path=f"{path}.family_depths.{key}.donors[{i}]",
                    value={"p": p, "n_gammas": len(gp), "n_betas": len(bp)},
                )
            for j, g in enumerate(gp):
                require_finite(g, path=f"{path}.family_depths.{key}.donors[{i}].gammas[{j}]")
            for j, b in enumerate(bp):
                require_finite(b, path=f"{path}.family_depths.{key}.donors[{i}].betas[{j}]")
            seen_fams.append(str(dm.get("family_id") or ""))
        if sorted(seen_fams) != sorted(families):
            raise StructuralError(
                "COVERAGE",
                "donors do not cover eight instance families",
                path=f"{path}.family_depths.{key}.represented_instance_families",
                value=seen_fams,
            )
        if rec.get("family") != key.split("_")[0] or int(rec.get("p") or 0) != int(key.split("p")[-1]):
            raise StructuralError("SCHEMA", "family/p mismatch vs key", path=f"{path}.family_depths.{key}")
    return dict(obj)


def load_donor_bank_v2(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise StructuralError("MISSING_ARTIFACT", "donor bank v2 file missing", path=str(p))
    import json

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructuralError("SCHEMA", "donor bank is not JSON", path=str(p), value=str(exc)) from exc
    return validate_donor_bank_v2(obj, path=str(p))


def selected_donors(bank: Any, family_depth: str, *, path: str = "donor_bank") -> list[dict[str, Any]]:
    """Return the validated selected list for a family/depth. Rejects the v1 {selected: ...} record."""
    if isinstance(bank, list):
        if not bank:
            raise StructuralError("SCHEMA", "empty donor list", path=path)
        return list(bank)
    obj = require_mapping(bank, path=path)
    if obj.get("schema_version") == DONOR_BANK_SCHEMA_V2 or "family_depths" in obj:
        depths = require_mapping(obj.get("family_depths"), path=f"{path}.family_depths")
        if family_depth not in depths:
            raise StructuralError("SCHEMA", "missing family/depth key", path=f"{path}.family_depths.{family_depth}")
        rec = depths[family_depth]
        return list(require_nonempty_list(rec.get("donors"), path=f"{path}.family_depths.{family_depth}.donors"))
    # v1 crash shape: {"selected": [...], "n_selected": n}
    if "selected" in obj and not any(k in obj for k in FAMILY_DEPTH_KEYS):
        raise StructuralError(
            "SCHEMA",
            "v1 donor-bank record passed to select_donor; use load_donor_bank_v2 and family_depths[key].donors",
            path=path,
            value=sorted(obj.keys()),
        )
    if family_depth in obj:
        rec = obj[family_depth]
        if isinstance(rec, list):
            return require_nonempty_list(rec, path=f"{path}.{family_depth}")
        if isinstance(rec, dict) and "selected" in rec:
            raise StructuralError(
                "SCHEMA",
                "v1 {selected: ...} record is not a donor list",
                path=f"{path}.{family_depth}",
                value=sorted(rec.keys()),
            )
    raise StructuralError("SCHEMA", "cannot resolve donor list", path=f"{path}.{family_depth}", value=sorted(obj.keys())[:20])


class DonorRanker:
    """Inspectable NumPy ridge donor ranker. Distinct from the option allocator."""

    def __init__(self, ridge_lambda: float = 1.0):
        self.ridge_lambda = float(ridge_lambda)
        self.W: np.ndarray | None = None
        self.donor_ids: list[str] = []
        self.mean_x: np.ndarray | None = None
        self.std_x: np.ndarray | None = None
        self.feature_keys = list(DONOR_FEATURE_KEYS)
        self.family_depth: str | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, donor_ids: list[str], *, family_depth: str) -> dict[str, Any]:
        if X.shape[0] != y.shape[0] or y.shape[1] != len(donor_ids):
            raise StructuralError("SCHEMA", "donor ranker X/y/donor_ids shape mismatch", path="DonorRanker.fit")
        self.family_depth = family_depth
        self.donor_ids = list(donor_ids)
        self.mean_x = X.mean(axis=0)
        self.std_x = X.std(axis=0)
        self.std_x[self.std_x < 1e-12] = 1.0
        xs = (X - self.mean_x) / self.std_x
        n_f = xs.shape[1]
        cols = []
        for d in range(y.shape[1]):
            a = xs.T @ xs + self.ridge_lambda * np.eye(n_f)
            b = xs.T @ y[:, d]
            cols.append(np.linalg.solve(a, b))
        self.W = np.stack(cols, axis=1)
        return self.to_artifact()

    def to_artifact(self) -> dict[str, Any]:
        assert self.W is not None and self.mean_x is not None and self.std_x is not None
        weights = self.W.tolist()
        return {
            "model": "a4_numpy_ridge_donor_ranker",
            "not_allocator": True,
            "ridge_lambda": self.ridge_lambda,
            "family_depth": self.family_depth,
            "feature_keys": list(self.feature_keys),
            "feature_means": self.mean_x.tolist(),
            "feature_stds": self.std_x.tolist(),
            "weights": weights,
            "donor_ids": list(self.donor_ids),
            "weights_hash": sha256_json(weights),
            "model_hash": sha256_json(
                {
                    "W": weights,
                    "mean": self.mean_x.tolist(),
                    "std": self.std_x.tolist(),
                    "lambda": self.ridge_lambda,
                    "keys": self.feature_keys,
                    "donors": self.donor_ids,
                    "family_depth": self.family_depth,
                }
            ),
        }

    @classmethod
    def from_artifact(cls, art: dict[str, Any]) -> "DonorRanker":
        sel = cls(ridge_lambda=float(art["ridge_lambda"]))
        sel.W = np.asarray(art["weights"], dtype=float)
        sel.mean_x = np.asarray(art["feature_means"], dtype=float)
        sel.std_x = np.asarray(art["feature_stds"], dtype=float)
        sel.donor_ids = list(art["donor_ids"])
        sel.family_depth = art.get("family_depth")
        sel.feature_keys = list(art.get("feature_keys") or DONOR_FEATURE_KEYS)
        if sel.feature_keys != DONOR_FEATURE_KEYS:
            raise StructuralError("SCHEMA", "donor feature order mismatch", path="DonorRanker.from_artifact.feature_keys")
        return sel

    def predict_scores(self, feats: dict[str, float]) -> np.ndarray:
        if self.W is None or self.mean_x is None or self.std_x is None:
            raise StructuralError("SCHEMA", "unfitted donor ranker", path="DonorRanker.predict_scores")
        xs = (_vec(feats) - self.mean_x) / self.std_x
        return xs @ self.W

    def select(self, feats: dict[str, float], donors: list[dict[str, Any]]) -> dict[str, Any]:
        ids = [str(d.get("donor_id") or d.get("params_hash")) for d in donors]
        if ids != list(self.donor_ids):
            raise StructuralError(
                "SCHEMA",
                "donor-order mismatch vs fitted bank",
                path="DonorRanker.select",
                value={"expected": self.donor_ids, "got": ids},
            )
        scores = self.predict_scores(feats)
        best_i = int(np.argmin(scores))
        return {
            "selected": donors[best_i],
            "selected_index": best_i,
            "policy": "learned",
            "predicted_regrets": scores.tolist(),
            "rule": "argmin_predicted_regret_no_angle_average",
        }


def select_donor_policy(
    *,
    policy: str,
    donors: list[dict[str, Any]],
    feats: dict[str, float],
    ranker: DonorRanker | None,
    rng: np.random.Generator,
    identity_seed: int | None = None,
) -> dict[str, Any]:
    if not donors:
        raise StructuralError("SCHEMA", "empty donor list", path="select_donor_policy.donors")
    if policy == "fixed":
        return {"selected": donors[0], "policy": "fixed", "reason": "training_mean_order_first"}
    if policy == "random":
        seed = int(identity_seed if identity_seed is not None else rng.integers(0, 2**31 - 1))
        local = np.random.default_rng(seed)
        i = int(local.integers(0, len(donors)))
        return {"selected": donors[i], "policy": "random", "identity_seed": seed, "selected_index": i}
    if policy in {"nn", "nearest_neighbour"}:
        def _key(d: dict[str, Any]) -> tuple[float, str]:
            df = d.get("features") or {}
            return (
                abs(float(df.get("n_logical_vars", 0.0) - feats.get("n_logical_vars", 0.0)))
                + 0.01 * abs(float(df.get("remaining_laps", 0.0) - feats.get("remaining_laps", 0.0))),
                str(d.get("donor_id") or d.get("params_hash") or ""),
            )

        best = min(donors, key=_key)
        return {"selected": best, "policy": "nn"}
    if policy == "best_found":
        # Fixed-budget variational reference among the registered donor bank.
        # Not a certified quantum optimum; no extra optimisation until favourable.
        best = min(
            donors,
            key=lambda d: (float(d.get("best_value_scaled") if d.get("best_value_scaled") is not None else 1e9), str(d.get("donor_id") or "")),
        )
        return {"selected": best, "policy": "best_found", "certified_quantum_optimum": False, "fixed_budget_reference": True}
    if policy == "learned":
        if ranker is None:
            raise StructuralError("SCHEMA", "learned donor policy requires DonorRanker", path="select_donor_policy")
        return ranker.select(feats, donors)
    raise StructuralError("SCHEMA", "unknown donor policy", path="select_donor_policy.policy", value=policy)


def donor_features_from_case(feats: dict[str, float], *, family: str, p: int) -> dict[str, float]:
    out = {k: float(feats.get(k, 0.0)) for k in DONOR_FEATURE_KEYS}
    out["family_is_c1"] = 1.0 if family == "C1" else 0.0
    out["depth_p"] = float(p)
    if "effective_remaining_s" not in feats:
        out["effective_remaining_s"] = float(feats.get("deadline_s") or 0.0)
    return out


def verify_bank_file_hash(path: Path, expected: str) -> str:
    got = sha256_file(path)
    if got != expected:
        raise StructuralError("INTEGRITY", "donor bank hash mismatch", path=str(path), value={"expected": expected, "got": got})
    return got
