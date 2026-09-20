"""Inspectable NumPy ridge learned donor selector (corrected: full coverage + genuine comparators)."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from f1q.hashing import sha256_json
from f1q.stage5.bank import fit_one_start
from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.heuristic import greedy_safe_fallback
from f1q.stage5.metrics import evaluate_distribution_metrics
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
        self.W: np.ndarray | None = None
        self.donor_ids: list[str] = []
        self.mean_x = None
        self.std_x = None
        self.feature_keys = list(FEATURE_KEYS)

    def fit(self, X: np.ndarray, y: np.ndarray, donor_ids: list[str]) -> dict[str, Any]:
        self.donor_ids = list(donor_ids)
        self.mean_x = X.mean(axis=0)
        self.std_x = X.std(axis=0)
        self.std_x[self.std_x < 1e-12] = 1.0
        Xs = (X - self.mean_x) / self.std_x
        n_f = Xs.shape[1]
        W = []
        for d in range(y.shape[1]):
            A = Xs.T @ Xs + self.ridge_lambda * np.eye(n_f)
            b = Xs.T @ y[:, d]
            w = np.linalg.solve(A, b)
            W.append(w)
        self.W = np.stack(W, axis=1)
        weights_list = self.W.tolist()
        return {
            "model": "numpy_ridge_ranking",
            "ridge_lambda": self.ridge_lambda,
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_donors": len(donor_ids),
            "feature_keys": list(FEATURE_KEYS),
            "feature_means": self.mean_x.tolist(),
            "feature_stds": self.std_x.tolist(),
            "weights": weights_list,
            "weights_hash": sha256_json(weights_list),
            "donor_ids": list(donor_ids),
            "model_hash": sha256_json(
                {
                    "W": weights_list,
                    "mean": self.mean_x.tolist(),
                    "std": self.std_x.tolist(),
                    "lambda": self.ridge_lambda,
                    "keys": FEATURE_KEYS,
                    "donors": donor_ids,
                }
            ),
        }

    def to_artifact(self) -> dict[str, Any]:
        assert self.W is not None
        return {
            "model": "numpy_ridge_ranking",
            "ridge_lambda": self.ridge_lambda,
            "feature_keys": list(FEATURE_KEYS),
            "feature_means": self.mean_x.tolist(),
            "feature_stds": self.std_x.tolist(),
            "weights": self.W.tolist(),
            "weights_hash": sha256_json(self.W.tolist()),
            "donor_ids": list(self.donor_ids),
            "model_hash": sha256_json(
                {
                    "W": self.W.tolist(),
                    "mean": self.mean_x.tolist(),
                    "std": self.std_x.tolist(),
                    "lambda": self.ridge_lambda,
                    "keys": FEATURE_KEYS,
                    "donors": self.donor_ids,
                }
            ),
        }

    @classmethod
    def from_artifact(cls, art: dict[str, Any]) -> "RidgeDonorSelector":
        sel = cls(ridge_lambda=float(art["ridge_lambda"]))
        sel.W = np.asarray(art["weights"], dtype=float)
        sel.mean_x = np.asarray(art["feature_means"], dtype=float)
        sel.std_x = np.asarray(art["feature_stds"], dtype=float)
        sel.donor_ids = list(art["donor_ids"])
        return sel

    def predict_scores(self, feats: dict[str, float]) -> np.ndarray:
        assert self.W is not None
        x = _vec(feats)
        xs = (x - self.mean_x) / self.std_x
        return xs @ self.W

    def select(self, feats: dict[str, float], donors: list[dict[str, Any]]) -> dict[str, Any]:
        scores = self.predict_scores(feats)
        order = list(np.argsort(scores))
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
    f_max: float | None,
    pool_size: int = 32,
    seed: int = 0,
) -> dict[str, Any]:
    family = donor["family"]
    p = int(donor["p"])
    params = np.asarray(donor["params"], dtype=float)
    gammas = params[:p].tolist()
    betas = params[p:].tolist()
    t0 = time.perf_counter()
    if family == "C0":
        sim = simulate_c0(qubo, gammas, betas, scaled=True)
    else:
        sim = simulate_c1(instance, qubo, gammas, betas, scaled=True)
    infer_s = time.perf_counter() - t0
    fb = greedy_safe_fallback(instance)
    weak = float(fb["cost"]) if fb.get("feasible") else None
    metrics = evaluate_distribution_metrics(
        instance,
        sim["probs"],
        exact_cost=exact_cost,
        f_max=f_max,
        weak_incumbent_cost=weak,
        pool_size=pool_size,
        seed=seed,
    )
    metrics["mean_energy_scaled"] = float(sim["expectation_scaled"])
    metrics["inference_s"] = infer_s
    metrics["donor_params_hash"] = donor.get("params_hash")
    metrics["donor_seed"] = donor.get("seed")
    metrics["family"] = family
    metrics["p"] = p
    return metrics


def paired_interval(diffs: list[float], alpha: float = 0.05) -> dict[str, Any]:
    arr = np.asarray(diffs, dtype=float)
    n = arr.size
    if n == 0:
        return {"n": 0, "mean": None, "upper_95_one_sided": None, "alpha": alpha}
    mean = float(arr.mean())
    se = float(arr.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
    z = 1.6448536269514722
    upper = mean + z * se
    return {"n": int(n), "mean": mean, "se": se, "upper_95_one_sided": upper, "alpha": alpha}


def nn_transfer_donor(
    feats: dict[str, float],
    train_feats: list[dict[str, float]],
    fitted_donor_per_row: list[dict[str, Any]],
) -> dict[str, Any]:
    """Genuine NN: fitted donor of the nearest valid training instance (not a constant first donor)."""
    x = _vec(feats)
    best_d = None
    best_dist = float("inf")
    best_i = -1
    for i, tf in enumerate(train_feats):
        if not fitted_donor_per_row[i]:
            continue
        d = float(np.linalg.norm(x - _vec(tf)))
        if d < best_dist:
            best_dist = d
            best_d = fitted_donor_per_row[i]
            best_i = i
    return {
        "donor": best_d,
        "nearest_train_index": best_i,
        "distance": None if best_i < 0 else best_dist,
    }


def seeded_random_donor(donors: list[dict[str, Any]], block_id: str, seed: int) -> dict[str, Any]:
    import hashlib

    h = int(hashlib.sha256(f"{block_id}:{seed}:random_donor".encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(h % (2**31 - 1))
    idx = int(rng.integers(0, len(donors)))
    return {"donor": donors[idx], "index": idx, "identity_seed": h}


# Frozen variational reference budget (declared before corrected run)
VARIATIONAL_REF_STARTS = 1
VARIATIONAL_REF_MAX_EVALS = 40


def per_instance_variational_fit(
    instance: A2Instance,
    qubo: dict[str, Any],
    family: str,
    p: int,
    *,
    seed: int,
    max_evals: int = VARIATIONAL_REF_MAX_EVALS,
) -> dict[str, Any]:
    """Fresh parameter fitting per instance — NOT searching an existing donor list."""
    fit = fit_one_start(instance, qubo, family, p, seed=seed, max_evals=max_evals)
    if not fit.get("success"):
        return {"success": False, "fit": fit, "donor": None}
    donor = {
        "seed": fit["seed"],
        "family": family,
        "p": p,
        "params": fit["best_params"],
        "params_hash": fit["params_hash"],
        "best_value_scaled": fit["best_value_scaled"],
        "source": "per_instance_variational_fit",
        "max_evals": max_evals,
        "starts": VARIATIONAL_REF_STARTS,
    }
    return {"success": True, "fit": fit, "donor": donor}


def run_selector_all_family_depths(
    *,
    train_pairs: list[tuple[dict[str, Any], A2Instance]],
    tuning_pairs: list[tuple[dict[str, Any], A2Instance]],
    bank: dict[str, Any],
    ridge_lambda: float,
    pool_size: int,
    noninferiority_margin: float,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Train+evaluate on ALL training and ALL tuning for each of C0/C1 × p=1,2."""
    family_depths = [("C0", 1), ("C0", 2), ("C1", 1), ("C1", 2)]
    per_fd: dict[str, Any] = {}
    training_block_ids = [b["block_id"] for b, _ in train_pairs]
    tuning_block_ids = [b["block_id"] for b, _ in tuning_pairs]
    family_train_counts: dict[str, int] = {}
    for b, _ in train_pairs:
        family_train_counts[b["family_id"]] = family_train_counts.get(b["family_id"], 0) + 1
    family_tune_counts: dict[str, int] = {}
    for b, _ in tuning_pairs:
        family_tune_counts[b["family_id"]] = family_tune_counts.get(b["family_id"], 0) + 1

    all_per_block: list[dict[str, Any]] = []
    model_artifacts: dict[str, Any] = {}

    for family, p in family_depths:
        key = f"{family}_p{p}"
        if progress:
            progress(f"selector family_depth={key} train_n={len(train_pairs)}")
        donors = bank["donor_inventory"][key]["selected"]
        if not donors:
            per_fd[key] = {"error": "no_donors", "skipped": True}
            continue

        X_rows = []
        y_rows = []
        train_feat_list = []
        fitted_donor_per_row: list[dict[str, Any]] = []
        train_usage = []

        for block, inst in train_pairs:
            if progress:
                progress(f"selector train {key} {block['block_id']}")
            qubo = build_a2_qubo(inst)
            feats = compute_features(inst, qubo, family, p)
            train_feat_list.append(feats)
            en = enumerate_legal_policies(inst)
            exact = en.get("f_star")
            f_max = en.get("f_max")
            regrets = []
            best_d = None
            best_r = float("inf")
            for d in donors:
                ev = evaluate_donor_on_instance(
                    inst, qubo, d, exact_cost=exact, f_max=f_max, pool_size=pool_size, seed=block["seed"]
                )
                r = float(ev["best_of_pool_normalised_regret"])
                regrets.append(r)
                if r < best_r:
                    best_r = r
                    best_d = d
            fitted_donor_per_row.append(best_d)
            X_rows.append(_vec(feats))
            y_rows.append(regrets)
            train_usage.append(
                {
                    "block_id": block["block_id"],
                    "family_id": block["family_id"],
                    "entered_feature_compute": True,
                    "entered_donor_eval": True,
                    "n_donors_evaluated": len(donors),
                    "best_donor_params_hash": None if best_d is None else best_d.get("params_hash"),
                }
            )

        X = np.asarray(X_rows, dtype=float)
        y = np.asarray(y_rows, dtype=float)
        selector = RidgeDonorSelector(ridge_lambda=ridge_lambda)
        train_receipt = selector.fit(X, y, donor_ids=[d["params_hash"] for d in donors])
        model_artifacts[key] = selector.to_artifact()

        # Frozen fixed donor from training only: donor with best mean training regret
        mean_reg = y.mean(axis=0)
        fixed_idx = int(np.argmin(mean_reg))
        fixed_donor = donors[fixed_idx]

        # Reload check
        reloaded = RidgeDonorSelector.from_artifact(model_artifacts[key])
        reload_ok = bool(np.allclose(reloaded.W, selector.W))

        tuning_rows = []
        learned_regs, fixed_regs, nn_regs, rand_regs, var_regs = [], [], [], [], []
        paired_vs = {k: [] for k in ("fixed", "nn", "random", "variational")}

        for block, inst in tuning_pairs:
            if progress:
                progress(f"selector tune {key} {block['block_id']}")
            t_feat0 = time.perf_counter()
            qubo = build_a2_qubo(inst)
            feats = compute_features(inst, qubo, family, p)
            feat_s = time.perf_counter() - t_feat0
            en = enumerate_legal_policies(inst)
            exact = en.get("f_star")
            f_max = en.get("f_max")

            sel = selector.select(feats, donors)
            learned = evaluate_donor_on_instance(
                inst, qubo, sel["selected_donor"], exact_cost=exact, f_max=f_max, pool_size=pool_size, seed=block["seed"]
            )
            fixed = evaluate_donor_on_instance(
                inst, qubo, fixed_donor, exact_cost=exact, f_max=f_max, pool_size=pool_size, seed=block["seed"] + 1
            )
            nn_info = nn_transfer_donor(feats, train_feat_list, fitted_donor_per_row)
            nn_d = nn_info["donor"] or fixed_donor
            nn = evaluate_donor_on_instance(
                inst, qubo, nn_d, exact_cost=exact, f_max=f_max, pool_size=pool_size, seed=block["seed"] + 2
            )
            rnd_info = seeded_random_donor(donors, block["block_id"], block["seed"])
            rnd = evaluate_donor_on_instance(
                inst,
                qubo,
                rnd_info["donor"],
                exact_cost=exact,
                f_max=f_max,
                pool_size=pool_size,
                seed=block["seed"] + 3,
            )

            # Genuine per-instance variational fit (fresh params, frozen budget)
            var_fit = per_instance_variational_fit(
                inst,
                qubo,
                family,
                p,
                seed=int(block["seed"]) + 7777 * p + (0 if family == "C0" else 99),
                max_evals=VARIATIONAL_REF_MAX_EVALS,
            )
            if var_fit["success"] and var_fit["donor"] is not None:
                var = evaluate_donor_on_instance(
                    inst,
                    qubo,
                    var_fit["donor"],
                    exact_cost=exact,
                    f_max=f_max,
                    pool_size=pool_size,
                    seed=block["seed"] + 4,
                )
            else:
                var = {
                    "best_of_pool_normalised_regret": 1.0,
                    "best_of_pool_unnormalised_gap": None,
                    "all_infeasible_pool": True,
                    "failure": "variational_fit_failed",
                }

            def _nr(ev: dict) -> float:
                return float(ev["best_of_pool_normalised_regret"])

            lr, fr, nr, rr, vr = _nr(learned), _nr(fixed), _nr(nn), _nr(rnd), _nr(var)
            learned_regs.append(lr)
            fixed_regs.append(fr)
            nn_regs.append(nr)
            rand_regs.append(rr)
            var_regs.append(vr)
            paired_vs["fixed"].append(lr - fr)
            paired_vs["nn"].append(lr - nr)
            paired_vs["random"].append(lr - rr)
            paired_vs["variational"].append(lr - vr)

            row = {
                "block_id": block["block_id"],
                "family_id": block["family_id"],
                "family_depth": key,
                "entered_tuning_eval": True,
                "feature_compute_s": feat_s,
                "learned": {
                    "normalised_regret": lr,
                    "unnormalised_gap": learned.get("best_of_pool_unnormalised_gap"),
                    "donor_params_hash": sel["selected_donor"].get("params_hash"),
                    "metrics": {k: learned[k] for k in learned if k != "probs"},
                },
                "fixed": {
                    "normalised_regret": fr,
                    "donor_params_hash": fixed_donor.get("params_hash"),
                    "unnormalised_gap": fixed.get("best_of_pool_unnormalised_gap"),
                },
                "nn": {
                    "normalised_regret": nr,
                    "donor_params_hash": nn_d.get("params_hash") if nn_d else None,
                    "nearest_train_index": nn_info["nearest_train_index"],
                    "distance": nn_info["distance"],
                    "unnormalised_gap": nn.get("best_of_pool_unnormalised_gap"),
                },
                "random": {
                    "normalised_regret": rr,
                    "donor_params_hash": rnd_info["donor"].get("params_hash"),
                    "identity_seed": rnd_info["identity_seed"],
                    "unnormalised_gap": rnd.get("best_of_pool_unnormalised_gap"),
                },
                "variational": {
                    "normalised_regret": vr,
                    "donor_params_hash": None if not var_fit.get("donor") else var_fit["donor"].get("params_hash"),
                    "fit_success": var_fit.get("success"),
                    "fit_evals": None if not var_fit.get("fit") else var_fit["fit"].get("evals"),
                    "unnormalised_gap": var.get("best_of_pool_unnormalised_gap"),
                    "budget": {"starts": VARIATIONAL_REF_STARTS, "max_evals": VARIATIONAL_REF_MAX_EVALS},
                },
                "paired_diffs_learned_minus": {
                    "fixed": lr - fr,
                    "nn": lr - nr,
                    "random": lr - rr,
                    "variational": lr - vr,
                },
            }
            tuning_rows.append(row)
            all_per_block.append(row)

        # Non-inferiority vs each comparator separately (NOT vs retrospective best-of-comparators)
        intervals = {name: paired_interval(diffs) for name, diffs in paired_vs.items()}
        noninf = {
            name: (
                None
                if intervals[name].get("upper_95_one_sided") is None
                else bool(intervals[name]["upper_95_one_sided"] <= noninferiority_margin)
            )
            for name in intervals
        }

        per_fd[key] = {
            "selector_model": "numpy_ridge_ranking",
            "family_depth_key": key,
            "training_receipt": train_receipt,
            "n_training_blocks_used": len(train_usage),
            "n_tuning_blocks_used": len(tuning_rows),
            "train_usage": train_usage,
            "reload_ok": reload_ok,
            "fixed_donor_params_hash": fixed_donor.get("params_hash"),
            "fixed_donor_selection": "argmin_mean_training_normalised_regret",
            "learned_mean_normalised_regret": float(np.mean(learned_regs)) if learned_regs else None,
            "fixed_mean_normalised_regret": float(np.mean(fixed_regs)) if fixed_regs else None,
            "nn_mean_normalised_regret": float(np.mean(nn_regs)) if nn_regs else None,
            "random_mean_normalised_regret": float(np.mean(rand_regs)) if rand_regs else None,
            "variational_mean_normalised_regret": float(np.mean(var_regs)) if var_regs else None,
            "paired_intervals_learned_minus_comparator": intervals,
            "noninferiority_0_02_vs_comparator": noninf,
            "noninferiority_margin": noninferiority_margin,
            "previous_noninferiority_superseded": True,
            "previous_noninferiority_label": "SUPERSEDED_INVALID_prior_unnormalised_or_incomplete_metric",
            "note": "development/tuning only — NOT held-out scientific claims",
            "no_retrospective_best_of_comparators_as_primary": True,
        }

    return {
        "training_block_ids": training_block_ids,
        "tuning_block_ids": tuning_block_ids,
        "n_training_used": len(training_block_ids),
        "n_tuning_used": len(tuning_block_ids),
        "family_train_counts": family_train_counts,
        "family_tune_counts": family_tune_counts,
        "eight_family_balance_train": all(v == family_train_counts[list(family_train_counts)[0]] for v in family_train_counts.values()),
        "eight_family_balance_tune": all(v == family_tune_counts[list(family_tune_counts)[0]] for v in family_tune_counts.values()),
        "family_depth_coverage": sorted(per_fd.keys()),
        "per_family_depth": per_fd,
        "model_artifacts": model_artifacts,
        "per_block_records": all_per_block,
        "variational_budget_frozen": {
            "starts": VARIATIONAL_REF_STARTS,
            "max_evals": VARIATIONAL_REF_MAX_EVALS,
            "optimiser": "seeded_random_local_search_fit_one_start",
            "failure_treatment": "regret_1_if_fit_fails",
        },
    }
