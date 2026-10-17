"""Corrected A4 workload arithmetic.

The historical design projection remains in ``completion._project_from_probes``
and ``completion_run`` so published receipts stay reproducible. This module is a
separate model. It does not rewrite those receipts.

Units
-----
plan-world evaluation
    One committed plan on one world. If a stored aggregate already multiplied
    by portfolio K, it is not multiplied again.
distribution build
    One ideal circuit distribution, identified by case, QUBO, circuit family,
    depth, parameters, noise model, numeric backend, and simulator version.
resample
    One pool draw from an already built distribution. It is not another build.
continuation request
    One full cold continuation identity. Only byte-identical identities dedupe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from f1q.a4.contracts import (
    DONOR_POLICIES,
    FAMILY_DEPTH_KEYS,
    N_MECHANISM_RESAMPLE_SEEDS,
    PORTFOLIO_K,
)

# Registered COBYLA cap in per_instance_variational_reference. A cap is not a
# measured evaluation count.
VARIATIONAL_OBJECTIVE_EVAL_CAP = 40

CAMPAIGN_CPU_CAP_S = 86_400.0
ADMISSION_WALL_CAP_S = 11_520.0
CAMPAIGN_WALL_CAP_S = 14_400.0

# Published under-prediction from the preserved 0b697910 diagnostic.
# Applied once, as a sensitivity, never as a speedup.
HISTORICAL_UNDERPREDICTION = 26010.0 / 20752.0


@dataclass(frozen=True)
class DistributionIdentity:
    """Complete identity of one ideal-distribution build."""

    case_id: str
    qubo_id: str
    circuit: str
    depth: int
    parameters: tuple[float, ...]
    noise_id: str
    numeric_backend: str
    simulator_version: str

    def key(self) -> tuple[Any, ...]:
        return (
            self.case_id,
            self.qubo_id,
            self.circuit,
            int(self.depth),
            tuple(float(x) for x in self.parameters),
            self.noise_id,
            self.numeric_backend,
            self.simulator_version,
        )


@dataclass(frozen=True)
class ResampleRequest:
    identity: DistributionIdentity
    resample_seed: int
    pool_draws: int


@dataclass(frozen=True)
class ContinuationIdentity:
    """Cold continuation key. Missing fields are not assumed cacheable."""

    simulator_version: str
    bank: str
    world_seed: int
    state_id: str
    plan_id: str
    arrival_delay_s: float
    nominal_budget_s: float
    commitment_s: float

    def key(self) -> tuple[Any, ...]:
        return (
            self.simulator_version,
            self.bank,
            int(self.world_seed),
            self.state_id,
            self.plan_id,
            float(self.arrival_delay_s),
            float(self.nominal_budget_s),
            float(self.commitment_s),
        )


def plan_world_evaluations(n_plans: int, n_worlds: int) -> int:
    """Each plan on each world once."""
    if n_plans < 0 or n_worlds < 0:
        raise ValueError("counts must be non-negative")
    return int(n_plans) * int(n_worlds)


def legacy_planning_charge_applies_k_again(stored_plan_world_evals: int, portfolio_k: int = PORTFOLIO_K) -> int:
    """Historical design projection: ``planning_worlds_upper * PORTFOLIO_K``.

    ``stored_plan_world_evals`` is the ledger field that already includes K.
    """
    return int(stored_plan_world_evals) * int(portfolio_k)


def legacy_resamples_charged_as_builds(n_resamples: int) -> int:
    """Historical design path: ``distributions = mechanism_resamples``."""
    return int(n_resamples)


def legacy_operation_ledger_distribution_count(n_mechanism_cases: int) -> int:
    """Historical ``operation_ledger`` expression ``n_mech * 4 depths * 8``.

    The trailing 8 is not a donor-policy count and is not a unique-key count.
    """
    return int(n_mechanism_cases) * len(FAMILY_DEPTH_KEYS) * 8


def count_distribution_operations(
    resamples: Sequence[ResampleRequest],
    *,
    extra_builds: Sequence[DistributionIdentity] = (),
) -> dict[str, int]:
    """Count unique builds and sampling operations from concrete requests."""
    builds: set[tuple[Any, ...]] = {spec.key() for spec in extra_builds}
    pools = 0
    for req in resamples:
        builds.add(req.identity.key())
        pools += 1
    return {
        "unique_builds": len(builds),
        "resamples": pools,
        "pool_sampling_operations": pools,
    }


def count_continuations(requests: Sequence[ContinuationIdentity]) -> dict[str, int]:
    """Deduplicate only proven identical full keys. Cold otherwise."""
    seen: set[tuple[Any, ...]] = set()
    duplicate = 0
    for req in requests:
        key = req.key()
        if key in seen:
            duplicate += 1
        else:
            seen.add(key)
    return {
        "requested": len(requests),
        "cold_unique": len(seen),
        "proven_duplicate_hits": duplicate,
    }


def plan_world_evals_from_units(units: Iterable[Mapping[str, Any]]) -> int:
    """Sum plan-world evaluations already stored on enumerated units.

    Mechanism rows contribute no plan-world evaluations. Offline rows keep
    ``portfolio_k == 0``, and the historical aggregate uses ``max(k, 1)`` so
    those worlds are counted once here. All-plan offline expansion is separate.
    """
    total = 0
    for unit in units:
        if unit.get("role") == "mechanism_resample":
            continue
        worlds = int(unit.get("n_planning_worlds") or 0)
        k = int(unit.get("portfolio_k") or 0)
        total += worlds * max(k, 1)
    return total


def mechanism_distribution_counts(units: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Unique mechanism builds from executable unit rows.

    The resample seed is not part of the build identity. Donor policy names
    stay distinct unless the caller supplies equal parameter tuples through
    :class:`DistributionIdentity`. Noise and backend are the ideal local
    statevector identity used by ``build_ideal_distribution`` (no device noise
    on this path).
    """
    builds: set[tuple[Any, ...]] = set()
    resamples = 0
    for unit in units:
        if unit.get("role") != "mechanism_resample":
            continue
        resamples += 1
        family_depth = str(unit.get("family_depth") or "")
        if family_depth not in FAMILY_DEPTH_KEYS and "family_depth" not in unit:
            raise ValueError("mechanism unit missing family_depth")
        params = unit.get("donor_parameters")
        if params is None:
            # Policy name is not proof that parameters match another policy.
            param_key: tuple[Any, ...] = ("policy_name_not_proven_equal", str(unit.get("donor_policy")))
        else:
            param_key = tuple(float(x) for x in params)
        builds.add(
            (
                str(unit.get("checkpoint_id") or unit.get("parent_id")),
                str(unit.get("qubo_id") or unit.get("checkpoint_id") or unit.get("parent_id")),
                family_depth,
                param_key,
                str(unit.get("noise_id") or "ideal_noiseless"),
                str(unit.get("numeric_backend") or "local_statevector"),
                str(unit.get("simulator_version") or "simulator_version_unspecified"),
            )
        )
    return {
        "unique_builds": len(builds),
        "resamples": resamples,
        "pool_sampling_operations": resamples,
        "donor_policies_in_contract": len(DONOR_POLICIES),
        "resample_seeds_in_contract": N_MECHANISM_RESAMPLE_SEEDS,
    }


def variational_objective_cap(n_best_found_fits: int) -> dict[str, int]:
    """Upper bound on optimiser objective evaluations. Not a measurement."""
    n = int(n_best_found_fits)
    return {
        "fits": n,
        "objective_evaluations_cap": n * VARIATIONAL_OBJECTIVE_EVAL_CAP,
        "cap_per_fit": VARIATIONAL_OBJECTIVE_EVAL_CAP,
        "measured": 0,
    }


def decompose_cpu(
    *,
    fixed_s: float,
    accelerated_s: float,
    overhead_s: float,
) -> dict[str, float]:
    """``fixed + accelerated + overhead``. Infinite kernel speed zeros only the accelerated term."""
    fixed = float(fixed_s)
    accel = float(accelerated_s)
    overhead = float(overhead_s)
    if min(fixed, accel, overhead) < 0.0:
        raise ValueError("component seconds must be non-negative")
    point = fixed + accel + overhead
    floor = fixed + overhead
    return {
        "fixed_s": fixed,
        "accelerated_s": accel,
        "overhead_s": overhead,
        "point_cpu_s": point,
        "infinite_kernel_floor_s": floor,
        "floor_exceeds_campaign_cpu_cap": floor > CAMPAIGN_CPU_CAP_S,
    }


def project_wall_s(
    *,
    conservative_cpu_s: float,
    workers: int,
    efficiency: float,
    efficiency_measured_at_workers: int,
    wall_contingency: float = 1.20,
) -> dict[str, Any]:
    """Wall at a worker count only when efficiency was measured at that count."""
    n = int(workers)
    measured_n = int(efficiency_measured_at_workers)
    if n < 1:
        raise ValueError("workers must be positive")
    claim = measured_n == n and float(efficiency) > 0.0
    if not claim:
        return {
            "wall_claim_allowed": False,
            "reason": "efficiency was not measured at this worker count",
            "workers": n,
            "efficiency_measured_at_workers": measured_n,
            "conservative_wall_s": None,
        }
    eff = float(efficiency)
    wall = float(conservative_cpu_s) / (n * eff) * float(wall_contingency)
    return {
        "wall_claim_allowed": True,
        "workers": n,
        "efficiency": eff,
        "wall_contingency": float(wall_contingency),
        "conservative_wall_s": wall,
        "within_admission_wall": wall <= ADMISSION_WALL_CAP_S,
        "within_campaign_wall": wall <= CAMPAIGN_WALL_CAP_S,
    }


def apply_historical_underprediction(point_cpu_s: float) -> dict[str, float]:
    """One conservative multiplier. Not chosen from candidate timings."""
    point = float(point_cpu_s)
    return {
        "point_cpu_s": point,
        "multiplier": HISTORICAL_UNDERPREDICTION,
        "conservative_cpu_s": point * HISTORICAL_UNDERPREDICTION,
    }


def component_cpu_s(
    *,
    n_prepare: int,
    prepare_s: float,
    n_builds: int,
    build_s: float,
    n_resamples: int,
    resample_s: float,
    n_plan_world: int,
    plan_world_s: float,
    n_eval_world: int,
    eval_world_s: float,
    n_offline: int,
    offline_s: float,
    n_optimiser_evals: int,
    optimiser_eval_s: float,
    other_fixed_s: float = 0.0,
) -> dict[str, Any]:
    """Race continuations are the accelerated term. Builds, resamples, fits, and prepare are not."""
    prepare = int(n_prepare) * float(prepare_s)
    builds = int(n_builds) * float(build_s)
    resamples = int(n_resamples) * float(resample_s)
    plan = int(n_plan_world) * float(plan_world_s)
    evaluation = int(n_eval_world) * float(eval_world_s)
    offline = int(n_offline) * float(offline_s)
    optimiser = int(n_optimiser_evals) * float(optimiser_eval_s)
    other = float(other_fixed_s)
    fixed = prepare + builds + resamples + optimiser + other
    accelerated = plan + evaluation + offline
    parts = decompose_cpu(fixed_s=fixed, accelerated_s=accelerated, overhead_s=0.0)
    parts["components_s"] = {
        "prepare": prepare,
        "distribution_builds": builds,
        "resamples": resamples,
        "planning_worlds": plan,
        "evaluation_worlds": evaluation,
        "offline": offline,
        "optimiser_objective_evals": optimiser,
        "other_fixed": other,
    }
    parts["counts"] = {
        "prepare": int(n_prepare),
        "unique_builds": int(n_builds),
        "resamples": int(n_resamples),
        "plan_world_evaluations": int(n_plan_world),
        "evaluation_worlds": int(n_eval_world),
        "offline_continuations": int(n_offline),
        "optimiser_objective_evals": int(n_optimiser_evals),
    }
    return parts
