"""Pinned defect-to-fix-to-test traceability for the Phase 6 A4 repair set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from f1q.hashing import atomic_write_text, sha256_json

START_COMMIT = "bcc740cd71ea5b6367b9332a300bf89590656ffc"

REPAIR_ITEMS: list[dict[str, Any]] = [
    {
        "id": 1,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "anchors.select_donors wrote {selected: ...}; loop passed that record to allocator.select_donor expecting a list (KeyError 0).",
        "fix": "donors.selected_donors / load_donor_bank_v2 reject v1 records; decide_and_evaluate uses selected_donors(bank, family_depth).",
        "tests": ["test_malformed_bank_fails_before_campaign", "test_v2_bank_all_policies_after_fit"],
    },
    {
        "id": 2,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "DONOR_SELECTOR.json declared policy names with no fitted A4 donor-ranking model.",
        "fix": "DonorRanker fit on training; DONOR_SELECTOR_MODELS.json + DONOR_SELECTOR_TRAINING/TUNING jsonl.",
        "tests": ["test_v2_bank_all_policies_after_fit", "test_donor_save_reload_rejects_order_change"],
    },
    {
        "id": 3,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "select_donor(..., policy='learned') used allocator RidgeModel as a donor model.",
        "fix": "allocator.RidgeModel.kind=a4_option_allocator; select_donor raises if ranker is RidgeModel; DonorRanker is separate.",
        "tests": ["test_allocator_ridge_rejected_as_donor_ranker", "test_option_budget_features_change_rows"],
    },
    {
        "id": 4,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "Training compared only classical vs always_c1 at p=1, omitted C0 and p=2, dropped identical-plan cases.",
        "fix": "Training executes classical_only and all four family/depths at every budget; zero-utility labels retained.",
        "tests": ["test_all_four_family_depths_and_three_seeds", "test_zero_utility_same_plan_label_retained"],
    },
    {
        "id": 5,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "Allocator feature vector omitted generator option, depth, budget, K, predicted latency (not g(z,m,b)).",
        "fix": "option_feature_row one-hots options and includes nominal_budget_s, remaining, k, pool, pred_latency_s.",
        "tests": ["test_option_budget_features_change_rows"],
    },
    {
        "id": 6,
        "area": "data_model",
        "confirmed_in_bcc740c": True,
        "defect": "Tuning wrote frozen values without actually selecting donor policy, depth, comparator, regularisation, or threshold.",
        "fix": "Donor policies compared on all tuning parents; allocator lambdas [0.1,1,10]; winner recorded in DONOR_POLICY_SELECTION.json.",
        "tests": ["test_v2_bank_all_policies_after_fit"],
    },
    {
        "id": 7,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "family_spec overwrote every split with partition=development and erased train/tune/calib identity.",
        "fix": "ScenarioSpec.partition remains the Stage-2 legal fixture 'development'; scientific identity is namespace a4.{train|tune|calib|anchor} and PreparedCase.split. finaltest/test/shift raise.",
        "tests": ["test_family_spec_retains_true_split", "test_qpu_and_finaltest_closed"],
    },
    {
        "id": 8,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "extract_causal_view used absolute race-clock as remaining decision time.",
        "fix": "effective_remaining_s = max(0, effective_end_race_s - decision_time_race_s); features use remaining duration.",
        "tests": ["test_remaining_duration_distinct_from_absolute_end"],
    },
    {
        "id": 9,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "deadline_s argument did not change RaceSimulator spec budget (always 30 s).",
        "fix": "spec_with_budget / decide_and_evaluate writes primary_nominal_budget_s into the spec the simulator reads.",
        "tests": ["test_budget_5_vs_30_changes_simulator_window"],
    },
    {
        "id": 10,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "pred_latency_s=0.05 hard-coded in dispatch.",
        "fix": "dispatch uses feats['pred_latency_s'] from the option/allocator row, defaulting to 0 only if missing.",
        "tests": ["test_option_budget_features_change_rows"],
    },
    {
        "id": 11,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "Arrival delay contained only generation_s.",
        "fix": "precommit_s sums menu/QUBO, generation, and planning-sim; that uncapped total is arrival_delay_s.",
        "tests": ["test_late_recommendation_stays_late"],
    },
    {
        "id": 12,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "Arrival and common-commit delays were min-capped, concealing lateness.",
        "fix": "timings.uncapped=True; no min(deadline, ...) on arrival_delay_s.",
        "tests": ["test_late_recommendation_stays_late", "test_timely_cache_not_reused_for_late"],
    },
    {
        "id": 13,
        "area": "causal_deadline_cache",
        "confirmed_in_bcc740c": True,
        "defect": "cache_key omitted budget, arrival, commitment epoch, simulator/interface version, evaluator identity.",
        "fix": "banks.cache_key hashes those fields; tests show each field changes identity.",
        "tests": ["test_cache_key_fields_change_identity", "test_timely_cache_not_reused_for_late"],
    },
    {
        "id": 14,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Every arm reinitialised the simulator and rebuilt menu/QUBO/enumeration/MILP.",
        "fix": "PreparedCase created once per (partition, block, regime); campaign passes legal_table and spec_with_budget.",
        "tests": ["test_one_prepared_case_counters"],
    },
    {
        "id": 15,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Campaign never passed family_depth; quantum arms defaulted to p=1.",
        "fix": "decide_and_evaluate family_depth argument; campaign iterates C0_p1/C0_p2/C1_p1/C1_p2.",
        "tests": ["test_all_four_family_depths_and_three_seeds"],
    },
    {
        "id": 16,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "n_stochastic_seeds=3 expanded only classical generators; quantum ran one seed.",
        "fix": "assemble_portfolio loops n_stochastic_seeds quantum pools and stores seed_receipts.",
        "tests": ["test_all_four_family_depths_and_three_seeds"],
    },
    {
        "id": 17,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Hybrid inserted quantum first, could drop the classical incumbent, and labelled shared plans origin=quantum.",
        "fix": "Matched K: fallback + strongest classical incumbent protected; quantum fills residual slots only.",
        "tests": ["test_portfolios_k_fallback_incumbent"],
    },
    {
        "id": 18,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Candidate provenance was a single string; shared plans counted as quantum-exclusive.",
        "fix": "found_by set; merge on duplicate hashes; quantum_incremental_at_k only if absent from matched classical K.",
        "tests": ["test_provenance_merge_not_quantum_incremental_duplicate"],
    },
    {
        "id": 19,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Planning and evaluation simulations were per-arm instead of once per complete cache key.",
        "fix": "_simulate_plan_world uses full cache_key; evaluation bank rejected from planning helpers.",
        "tests": ["test_evaluation_payload_rejected_from_planning", "test_cache_key_fields_change_identity"],
    },
    {
        "id": 20,
        "area": "treatment_execution",
        "confirmed_in_bcc740c": True,
        "defect": "Offline reference unrun; copied arm loss.",
        "fix": "evaluate_offline_reference evaluates every legal plan on offline planning bank; copied_from_arm=False.",
        "tests": ["test_offline_helper_covers_all_legal_not_copy", "test_a3_offline_copied_a4_evaluates"],
    },
    {
        "id": 21,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Preflight undercounted arms/depths/seeds/offline and charged new anchors.",
        "fix": "Admission measures real end-to-end witnesses, reuses 288 anchors, projects ladder against 60 min / 20% reserve.",
        "tests": ["test_real_anchor_fits_rebuild_eight_family_banks"],
    },
    {
        "id": 22,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Training loop caught structural exceptions and repeated them across the corpus.",
        "fix": "StructuralError fails on first occurrence; coordinator cancels and exits nonzero.",
        "tests": ["test_failed_rows_cannot_satisfy_counts", "test_malformed_bank_fails_before_campaign"],
    },
    {
        "id": 23,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "verify.py counted failed training as parent completion, empty paired analysis, first-80 manifest, no donor/budget/q checks.",
        "fix": "Independent verifier hashes every manifest entry, recomputes q, uses status-specific required files, includes PRESTART_QUARANTINE.",
        "tests": ["test_verifier_hashes_every_manifest_entry_not_first_80"],
    },
    {
        "id": 24,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Forced-quantum test appended a fake hash; classical/hybrid difference allowed none; offline test did not execute offline.",
        "fix": "Real quantum hashes from legal table; offline helper executed; difference not required to be favourable.",
        "tests": ["test_real_quantum_candidate_not_fake_hash", "test_offline_helper_covers_all_legal_not_copy"],
    },
    {
        "id": 25,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "START_STATE.json hard-coded obsolete be9e11 start commit.",
        "fix": "START_STATE binds bcc740cd71ea5b6367b9332a300bf89590656ffc and the reviewed source commit at admission.",
        "tests": ["test_family_spec_retains_true_split"],
    },
    {
        "id": 26,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Test receipts copied from global /tmp/a4_test_receipts.",
        "fix": "Development writes only .scratch/; admission writes evidence/stage6_a4/<run_id>/tests/.",
        "tests": ["test_one_prepared_case_counters"],
    },
    {
        "id": 27,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Gate E could pass merely because legal_plan_count > K.",
        "fix": "Gate E requires a genuine matched-K quantum-incremental-at-K candidate generated and planning-evaluated.",
        "tests": ["test_portfolios_k_fallback_incumbent", "test_planning_outcomes_can_select_or_reject_incremental"],
    },
    {
        "id": 28,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Gate F checked superficial counts and flawed preflight boolean.",
        "fix": "Gate F requires 24 calibration parents, q, MC uncertainty, Stage 7 sizing, and measured resources.",
        "tests": ["test_failed_rows_cannot_satisfy_counts"],
    },
    {
        "id": 29,
        "area": "runtime_verify_report",
        "confirmed_in_bcc740c": True,
        "defect": "Report called calibration a primary analysis and claimed five budgets while only 30 s executed.",
        "fix": "Closure report labels calibration DEVELOPMENT ONLY; campaign iterates the five-budget grid on training.",
        "tests": ["test_budget_5_vs_30_changes_simulator_window"],
    },
]


def repair_traceability_document() -> dict[str, Any]:
    return {
        "schema": "f1q.a4.repair_traceability.v1",
        "start_commit": START_COMMIT,
        "n_items": len(REPAIR_ITEMS),
        "all_confirmed": all(item["confirmed_in_bcc740c"] for item in REPAIR_ITEMS),
        "items": REPAIR_ITEMS,
        "document_hash": sha256_json({"items": REPAIR_ITEMS, "start_commit": START_COMMIT}),
    }


def write_repair_traceability(path: Path) -> str:
    doc = repair_traceability_document()
    return atomic_write_text(path, __import__("json").dumps(doc, indent=2, sort_keys=True) + "\n")
