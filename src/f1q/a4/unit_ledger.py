"""Exact unit ledgers enumerated from concrete specifications.

Projection and execution consume the same enumerated plan. Closed-form
guesses that omit policy seeds are forbidden.
"""

from __future__ import annotations

from typing import Any

from f1q.a4.contracts import (
    DONOR_POLICIES,
    FAMILY_DEPTH_KEYS,
    N_MECHANISM_RESAMPLE_SEEDS,
    N_POLICY_SEEDS,
    NOMINAL_BUDGETS_S,
    POOL_DRAWS,
    PORTFOLIO_K,
    PRIMARY_BUDGET_S,
    StructuralError,
)
from f1q.hashing import sha256_json
from f1q.generator.config import cartesian_family_ids

DESIGN_F = "F"
DESIGN_R = "R"

CHECKPOINT_BALANCE = ("SC", "VSC")


def _one_checkpoint_regime(block: dict[str, Any], family_index: int, within: int) -> str:
    """Balance eight families and SC/VSC without dropping parent blocks."""
    return CHECKPOINT_BALANCE[(family_index + within) % 2]


def checkpoints_for_parent(block: dict[str, Any], *, design: str, family_index: int) -> list[str]:
    if design == DESIGN_F:
        return ["SC", "VSC"]
    return [_one_checkpoint_regime(block, family_index, int(block.get("index") or 0))]


def option_specs_all() -> list[tuple[str, str, tuple[str, int] | None]]:
    return [
        ("classical_only", "always_classical", None),
        ("C0_p1", "always_c0", ("C0", 1)),
        ("C0_p2", "always_c0", ("C0", 2)),
        ("C1_p1", "always_c1", ("C1", 1)),
        ("C1_p2", "always_c1", ("C1", 2)),
    ]


def freeze_option_specs(freeze: dict[str, Any]) -> list[tuple[str, str, tuple[str, int] | None]]:
    allowed = list(freeze.get("allowed_options") or [])
    specs: list[tuple[str, str, tuple[str, int] | None]] = []
    for opt in allowed:
        if opt == "stop_fallback":
            specs.append((opt, "stop_fallback", None))
        elif opt == "classical_only":
            specs.append((opt, "always_classical", None))
        elif opt.startswith("C0_p"):
            specs.append((opt, "always_c0", ("C0", int(opt[-1]))))
        elif opt.startswith("C1_p"):
            specs.append((opt, "always_c1", ("C1", int(opt[-1]))))
        else:
            raise StructuralError("FREEZE", "unknown frozen option", path="allowed_options", value=opt)
    if not specs:
        raise StructuralError("FREEZE", "empty frozen option set", path="allowed_options")
    return specs


def ablation_specs() -> list[dict[str, Any]]:
    return [
        {"ablation_id": "always_classical", "mode": "always_classical", "family_depth": None},
        {"ablation_id": "fixed_threshold", "mode": "frozen_allocator", "threshold_override": 0.05},
        {"ablation_id": "always_quantum", "mode": "always_c1", "family_depth": ("C1", 2)},
        {"ablation_id": "no_learned_donor", "mode": "frozen_allocator", "donor_policy": "fixed"},
        {"ablation_id": "c0_for_c1", "mode": "always_c0", "family_depth": ("C0", 2)},
        {"ablation_id": "no_margin", "mode": "frozen_allocator", "margin_override": 0.0},
        {"ablation_id": "positive_lambda", "mode": "frozen_allocator", "lambda_override": 1.0},
    ]


def enumerate_design_units(
    *,
    design: str,
    parts: dict[str, Any],
    worlds: dict[str, Any],
    freeze: dict[str, Any] | None = None,
    miniature: bool = False,
) -> dict[str, Any]:
    if design not in {DESIGN_F, DESIGN_R}:
        raise StructuralError("DESIGN", "design must be F or R", path="enumerate_design_units", value=design)
    fams = cartesian_family_ids()
    fam_index = {f: i for i, f in enumerate(fams)}
    train = list(parts["train"])
    tune = list(parts["tune"])
    calib = list(parts["calib"])
    if miniature:
        train, tune, calib = train[:2], tune[:2], calib[:2]
    n_seeds = 1 if miniature else N_POLICY_SEEDS
    train_opts = option_specs_all()[:3] if miniature else option_specs_all()
    budgets = [5, 30] if miniature else list(NOMINAL_BUDGETS_S)
    freeze_specs = freeze_option_specs(freeze) if freeze is not None else [
        ("classical_only", "always_classical", None),
        ("C0_selected", "always_c0", ("C0", 2)),
        ("C1_selected", "always_c1", ("C1", 2)),
    ]
    units: list[dict[str, Any]] = []

    def add_case(*, split: str, block: dict[str, Any], regime: str, option: str, mode: str, fd, budget: float, seed: int, n_plan: int, n_eval: int, role: str, donor_policy: str = "fixed") -> None:
        units.append(
            {
                "unit_id": f"{split}:{block['block_id']}:{regime}:{option}:{budget}:{seed}:{role}",
                "parent_id": block["block_id"],
                "checkpoint_id": f"{block['block_id']}:{regime}",
                "split": split,
                "family_id": block["family_id"],
                "regime": regime,
                "option": option,
                "mode": mode,
                "family_depth": None if fd is None else f"{fd[0]}_p{fd[1]}",
                "donor_policy": donor_policy,
                "budget_s": float(budget),
                "policy_seed": int(seed),
                "n_planning_worlds": int(n_plan),
                "n_evaluation_worlds": int(n_eval),
                "pool_draws": 64 if miniature else POOL_DRAWS,
                "portfolio_k": PORTFOLIO_K,
                "role": role,
                "index": int(block.get("index") or 0),
                "seed": int(block["seed"]),
            }
        )

    for block in train:
        fi = fam_index[block["family_id"]]
        for regime in checkpoints_for_parent(block, design=design, family_index=fi):
            for option, mode, fd in train_opts:
                for budget in budgets:
                    for seed in range(n_seeds):
                        add_case(
                            split="train",
                            block=block,
                            regime=regime,
                            option=option,
                            mode=mode,
                            fd=fd,
                            budget=budget,
                            seed=seed,
                            n_plan=int(worlds["training"]["planning"]),
                            n_eval=int(worlds["training"]["evaluation"]),
                            role="train_option",
                        )
    for block in tune:
        fi = fam_index[block["family_id"]]
        for regime in checkpoints_for_parent(block, design=design, family_index=fi):
            for option, mode, fd in train_opts:
                for budget in budgets:
                    for seed in range(n_seeds):
                        add_case(
                            split="tune",
                            block=block,
                            regime=regime,
                            option=option,
                            mode=mode,
                            fd=fd,
                            budget=budget,
                            seed=seed,
                            n_plan=int(worlds["tuning"]["planning"]),
                            n_eval=int(worlds["tuning"]["evaluation"]),
                            role="tune_option",
                        )
    for block in calib:
        fi = fam_index[block["family_id"]]
        for regime in checkpoints_for_parent(block, design=design, family_index=fi):
            for option, mode, fd in freeze_specs:
                for budget in budgets:
                    if design == DESIGN_R and float(budget) != float(PRIMARY_BUDGET_S):
                        n_eval = 128
                        role = "calib_exploratory_sensitivity"
                    else:
                        n_eval = int(worlds["calibration"]["evaluation"])
                        role = "calib_primary" if float(budget) == float(PRIMARY_BUDGET_S) else "calib_budget"
                    add_case(
                        split="calib",
                        block=block,
                        regime=regime,
                        option=option,
                        mode="frozen_allocator" if option != "stop_fallback" else "stop_fallback",
                        fd=fd,
                        budget=budget,
                        seed=0 if miniature else 0,
                        n_plan=int(worlds["calibration"]["planning"]),
                        n_eval=n_eval,
                        role=role,
                        donor_policy=str((freeze or {}).get("donor_policy_by_fd", {}).get(
                            (None if fd is None else f"{fd[0]}_p{fd[1]}") or "classical",
                            {},
                        ).get("policy") if isinstance((freeze or {}).get("donor_policy_by_fd"), dict) else "fixed")
                        or "fixed",
                    )
            if not miniature:
                for ab in ablation_specs():
                    add_case(
                        split="calib",
                        block=block,
                        regime=regime,
                        option=ab["ablation_id"],
                        mode=ab["mode"],
                        fd=ab.get("family_depth"),
                        budget=PRIMARY_BUDGET_S,
                        seed=0,
                        n_plan=int(worlds["calibration"]["planning"]),
                        n_eval=int(worlds["calibration"]["evaluation"]) if design == DESIGN_F else 128,
                        role="ablation",
                    )

    mech_n = 1 if miniature else min(120, len(train))
    for block in train[:mech_n]:
        fi = fam_index[block["family_id"]]
        regime = checkpoints_for_parent(block, design=design, family_index=fi)[0]
        for key in FAMILY_DEPTH_KEYS:
            for policy in DONOR_POLICIES:
                for rs in range(1 if miniature else N_MECHANISM_RESAMPLE_SEEDS):
                    units.append(
                        {
                            "unit_id": f"mech:{block['block_id']}:{regime}:{key}:{policy}:{rs}",
                            "parent_id": block["block_id"],
                            "checkpoint_id": f"{block['block_id']}:{regime}",
                            "split": "train",
                            "family_id": block["family_id"],
                            "regime": regime,
                            "option": key,
                            "mode": "mechanism",
                            "family_depth": key,
                            "donor_policy": policy,
                            "budget_s": None,
                            "policy_seed": None,
                            "resample_seed": rs,
                            "n_planning_worlds": 0,
                            "n_evaluation_worlds": 0,
                            "pool_draws": 64 if miniature else POOL_DRAWS,
                            "portfolio_k": PORTFOLIO_K,
                            "role": "mechanism_resample",
                            "index": int(block.get("index") or 0),
                            "seed": int(block["seed"]),
                        }
                    )

    n_off = 2 if miniature else 8
    seen_fams: set[str] = set()
    off_i = 0
    for block in calib + train:
        if block["family_id"] in seen_fams:
            continue
        seen_fams.add(block["family_id"])
        regime = "SC" if off_i % 2 == 0 else "VSC"
        units.append(
            {
                "unit_id": f"offline:{block['block_id']}:{regime}",
                "parent_id": block["block_id"],
                "checkpoint_id": f"{block['block_id']}:{regime}",
                "split": "calib",
                "family_id": block["family_id"],
                "regime": regime,
                "option": "all_legal_plans",
                "mode": "offline",
                "family_depth": None,
                "donor_policy": None,
                "budget_s": float(PRIMARY_BUDGET_S),
                "policy_seed": 0,
                "n_planning_worlds": int(worlds["offline"]["planning"]),
                "n_evaluation_worlds": int(worlds["offline"]["evaluation"]),
                "pool_draws": 0,
                "portfolio_k": 0,
                "role": "offline_all_plan",
                "index": int(block.get("index") or 0),
                "seed": int(block["seed"]),
            }
        )
        off_i += 1
        if off_i >= n_off:
            break

    n_lat = 2 if miniature else 6
    for i, block in enumerate(train[:n_lat]):
        for pkg in ("frozen_c0", "frozen_c1"):
            units.append(
                {
                    "unit_id": f"latency:{block['block_id']}:{pkg}",
                    "parent_id": block["block_id"],
                    "checkpoint_id": f"{block['block_id']}:SC",
                    "split": "train",
                    "family_id": block["family_id"],
                    "regime": "SC",
                    "option": pkg,
                    "mode": "latency",
                    "family_depth": pkg,
                    "donor_policy": "fixed",
                    "budget_s": float(PRIMARY_BUDGET_S),
                    "policy_seed": 0,
                    "n_planning_worlds": 2,
                    "n_evaluation_worlds": 2,
                    "pool_draws": 64 if miniature else POOL_DRAWS,
                    "portfolio_k": PORTFOLIO_K,
                    "role": "isolated_latency",
                    "index": int(block.get("index") or 0),
                    "seed": int(block["seed"]),
                }
            )

    plan_w = sum(int(u.get("n_planning_worlds") or 0) * max(int(u.get("portfolio_k") or 1), 1) for u in units if u["role"] not in {"mechanism_resample"})
    eval_w = sum(int(u.get("n_evaluation_worlds") or 0) for u in units)
    ids = [u["unit_id"] for u in units]
    if len(ids) != len(set(ids)):
        raise StructuralError("LEDGER", "duplicate unit ids", path="enumerate_design_units")
    return {
        "design": design,
        "miniature": miniature,
        "n_units": len(units),
        "units": units,
        "unit_ids_hash": sha256_json(sorted(ids)),
        "aggregates": {
            "train_parents": len(train),
            "tune_parents": len(tune),
            "calib_parents": len(calib),
            "train_checkpoints": sum(len(checkpoints_for_parent(b, design=design, family_index=fam_index[b["family_id"]])) for b in train),
            "tune_checkpoints": sum(len(checkpoints_for_parent(b, design=design, family_index=fam_index[b["family_id"]])) for b in tune),
            "calib_checkpoints": sum(len(checkpoints_for_parent(b, design=design, family_index=fam_index[b["family_id"]])) for b in calib),
            "n_policy_seeds": n_seeds,
            "n_budgets": len(budgets),
            "planning_world_evals_upper": plan_w,
            "evaluation_worlds": eval_w,
            "mechanism_resamples": sum(1 for u in units if u["role"] == "mechanism_resample"),
            "offline": sum(1 for u in units if u["role"] == "offline_all_plan"),
            "latency": sum(1 for u in units if u["role"] == "isolated_latency"),
            "ablations": sum(1 for u in units if u["role"] == "ablation"),
            "policy_seeds_included_in_world_counts": True,
        },
        "worlds": worlds,
        "budgets": budgets,
        "hash": sha256_json({"design": design, "ids": sorted(ids), "worlds": worlds}),
    }


def design_worlds(design: str, level: str) -> dict[str, Any]:
    from f1q.a4.contracts import WORLD_LADDERS

    base = dict(WORLD_LADDERS[level])
    if design == DESIGN_R:
        cal = dict(base["calibration"])
        cal["evaluation_primary"] = 2048
        cal["evaluation_sensitivity"] = 128
        cal["evaluation"] = 2048
        base["calibration"] = cal
    return base
