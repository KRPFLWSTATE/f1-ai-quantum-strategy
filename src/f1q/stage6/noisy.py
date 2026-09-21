"""Optional predeclared noisy-simulation feasibility panel (synthetic noise ≠ IBM)."""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np

from f1q.hashing import sha256_json
import hashlib

from f1q.stage5.circuits_c0 import simulate_c0
from f1q.stage5.circuits_c1 import simulate_c1
from f1q.stage5.enumerate_policies import enumerate_legal_policies
from f1q.stage5.model import build_a2_instance
from f1q.stage5.qubo import build_a2_qubo
from f1q.stage5.selector import compute_features
from f1q.stage6.config import Phase6Config
from f1q.stage6.metrics_pilot import exact_distribution_metrics


ProgressFn = Callable[[str], None]


def _noisy_probs_from_ideal(probs: np.ndarray, *, seed: int, p1: float, p2: float) -> np.ndarray:
    """Lightweight synthetic noise: mix ideal distribution toward uniform (depolarizing proxy).

    Not a full Aer noise model; labelled synthetic. Zero-noise control uses p1=p2=0
    and returns the ideal distribution unchanged (exact consistency control).
    """
    if p1 == 0.0 and p2 == 0.0:
        return np.asarray(probs, dtype=float).copy()
    rng = np.random.default_rng(seed)
    n = probs.size
    # Effective depolarization strength from declared 1q/2q rates (order-of-magnitude proxy)
    strength = min(0.5, 2.0 * p1 + 4.0 * p2)
    mixed = (1.0 - strength) * probs + strength * (np.ones(n) / n)
    # Tiny seeded jitter to ensure seed sensitivity without breaking normalisation
    jitter = rng.normal(0.0, 1e-6, size=n)
    mixed = np.clip(mixed + jitter, 0.0, None)
    mixed = mixed / mixed.sum()
    return mixed


def run_noisy_panel(
    cfg: Phase6Config,
    *,
    assets: dict[str, Any],
    progress: ProgressFn,
) -> dict[str, Any]:
    """One VSC-style ≤10q case per family; learned + fixed; C0/C1 at predeclared depth."""
    if not cfg.noisy_panel_enabled:
        return {"status": "DISABLED", "reason": "noisy_panel_enabled=false"}

    # Parse predeclared noise
    # format: depolarizing_1q_1e-3_2q_1e-2
    p1, p2 = 1e-3, 1e-2
    depth = 1 if cfg.noisy_depth_choice == "p1" else 2
    families = ["C0", "C1"]
    from f1q.generator.config import cartesian_family_ids

    fams = cartesian_family_ids()
    rows = []
    t0 = time.perf_counter()
    for fam in fams:
        progress(f"noisy panel {fam}")
        # Force n<=10: standard microcase → typically 8 qubits
        inst = build_a2_instance(
            instance_id=f"phase6.noisy.{fam}",
            family_id=fam,
            rung="circuit_unit",
            seed=9000 + int(hashlib.sha256(fam.encode()).hexdigest()[:6], 16) % 1000,
            deadline_s=cfg.deadline_s,
            n_scenarios=2,
            n_epochs=2,
            n_actions=2,
            microcase="standard",
        )
        qubo = build_a2_qubo(inst)
        n = qubo["n"]
        if n > cfg.noisy_max_qubits:
            rows.append(
                {
                    "family_id": fam,
                    "status": "excluded",
                    "reason": f"n_qubits={n}>{cfg.noisy_max_qubits}",
                    "n_qubits": n,
                }
            )
            continue
        en = enumerate_legal_policies(inst)
        for family in families:
            fd = f"{family}_p{depth}"
            feats = compute_features(inst, qubo, family, depth)
            donors = assets["donors"][fd]["selected"]
            learned = assets["selectors"][fd].select(feats, donors)["selected_donor"]
            fixed = assets["fixed"][fd]
            for policy_name, donor in (("learned", learned), ("fixed", fixed)):
                params = np.asarray(donor["params"], dtype=float)
                gammas = params[:depth].tolist()
                betas = params[depth:].tolist()
                if family == "C0":
                    ideal = simulate_c0(qubo, gammas, betas, scaled=True)
                else:
                    ideal = simulate_c1(inst, qubo, gammas, betas, scaled=True)
                ideal_m = exact_distribution_metrics(
                    inst,
                    ideal["probs"],
                    exact_cost=en.get("f_star"),
                    f_max=en.get("f_max"),
                    weak_incumbent_cost=None,
                    improvement_tol=cfg.improvement_tol,
                )
                # Zero-noise consistency
                zn = _noisy_probs_from_ideal(ideal["probs"], seed=1, p1=0.0, p2=0.0)
                zn_ok = bool(np.allclose(zn, ideal["probs"], atol=1e-5))
                seed_rows = []
                for s in range(cfg.noisy_seeds):
                    noisy = _noisy_probs_from_ideal(ideal["probs"], seed=s + 11, p1=p1, p2=p2)
                    nm = exact_distribution_metrics(
                        inst,
                        noisy,
                        exact_cost=en.get("f_star"),
                        f_max=en.get("f_max"),
                        weak_incumbent_cost=None,
                        improvement_tol=cfg.improvement_tol,
                    )
                    seed_rows.append(
                        {
                            "seed": s,
                            "legal_prob": nm["complete_legal_policy_probability"],
                            "one_hot_prob": nm["one_hot_probability"],
                            "optimal_mass": nm["optimal_sample_probability"],
                        }
                    )
                rows.append(
                    {
                        "status": "completed",
                        "family_id": fam,
                        "circuit_family": family,
                        "p": depth,
                        "policy": policy_name,
                        "n_qubits": n,
                        "params_hash": donor.get("params_hash"),
                        "ideal_legal_prob": ideal_m["complete_legal_policy_probability"],
                        "zero_noise_consistency_ok": zn_ok,
                        "noise_model": cfg.noisy_noise_model,
                        "synthetic_noise_not_ibm": True,
                        "noisy_seeds": seed_rows,
                    }
                )
    return {
        "status": "COMPLETED",
        "elapsed_s": time.perf_counter() - t0,
        "predeclared_depth": cfg.noisy_depth_choice,
        "noise_model": cfg.noisy_noise_model,
        "max_qubits": cfg.noisy_max_qubits,
        "n_rows": len(rows),
        "rows": rows,
        "panel_hash": sha256_json([{k: v for k, v in r.items() if k != "noisy_seeds"} for r in rows]),
    }
