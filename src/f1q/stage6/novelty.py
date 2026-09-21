"""Gate E novelty comparison scaffolding (bounded primary-source survey)."""

from __future__ import annotations

from typing import Any

from f1q.hashing import sha256_json


def build_novelty_comparison(*, pilot_headroom: str, causal_operational_ready: bool) -> dict[str, Any]:
    """Structured comparisons. No absolute novelty / 'first' claims."""
    comparisons = [
        {
            "id": "f1_dp_classical",
            "theme": "F1 DP / classical race optimisation",
            "sources": [
                {
                    "title": "On the optimization of pit stop strategies via dynamic programming",
                    "authors": "Carrasco Heine, O.F.; Thraves, C.",
                    "venue": "Central European Journal of Operations Research, 2023",
                    "url": "https://doi.org/10.1007/s10100-022-00806-4",
                    "access": "abstract_metadata_and_secondary_summaries",
                    "verified_bib": True,
                },
                {
                    "title": "Optimizing pit stop strategies in Formula 1 with dynamic programming and game theory",
                    "authors": "Aguad, F.; Thraves, C.",
                    "venue": "European Journal of Operational Research, 2024, 319(3), 908–919",
                    "url": "https://doi.org/10.1016/j.ejor.2024.06.020",
                    "access": "abstract_metadata",
                    "verified_bib": True,
                },
            ],
            "their_contribution": (
                "Classical DP/SDP and Stackelberg-game pit-stop/compound strategies with yellow-flag "
                "uncertainty and competitor interaction; race-time / win-probability objectives."
            ),
            "our_proposed_difference": (
                "Deadline-aware AI/quantum allocation over QUBO encodings with learned donor selection "
                "and auditable causal checkpoint interfaces — not a claim to replace DP race optimisation."
            ),
            "evidence_needed": (
                "Operational evaluator under live causal simulator + nonzero headroom OR a clearly "
                "scoped mechanism result that changes team practice (latency/yield/fallback)."
            ),
            "unresolved_overlap": "Both address SC/VSC-aware strategy; classical DP remains the stronger F1-ops baseline.",
        },
        {
            "id": "f1_qubo_annealing",
            "theme": "F1 QUBO / annealing",
            "sources": [
                {
                    "title": "Kolstee, S. (2026). Optimizing Formula 1 Pit Stop Strategies Using QUBO and Quantum Annealing — dossier [3]",
                    "access": "dossier_bibliographic_entry",
                    "url": "docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf",
                    "verified_bib": True,
                    "note": "Cited in dossier; full text not independently re-fetched in Phase 6 (unavailable sources remain unavailable).",
                },
                {
                    "title": "A simulation framework for Formula 1 race strategy based on pit-stop optimization",
                    "authors": "Borruso, M.; Avella, P.; Marino, M.",
                    "venue": "Optimization Online preprint, 2026",
                    "url": "https://optimization-online.org/2026/02/a-simulation-framework-for-formula-1-race-strategy-based-on-pit-stop-optimization/",
                    "access": "full_text_pdf_fetched",
                    "verified_bib": True,
                    "note": "MILP/simulation framework with ERS — not a quantum QUBO paper.",
                },
                {
                    "title": "D-Wave Ocean docs: QUBO / BQM models",
                    "url": "https://docs.dwavequantum.com/en/latest/concepts/models.html",
                    "access": "full_text_docs",
                    "verified_bib": True,
                },
            ],
            "their_contribution": (
                "Discrete F1 strategy as MILP/simulation; dossier cites Kolstee (2026) QUBO/annealing F1 work; "
                "generic QUBO tooling for annealers."
            ),
            "our_proposed_difference": (
                "Explicit C0/C1 circuit families + learned parameter-bank donor selection under split discipline, "
                "with headroom gate before superiority claims. Dossier already disclaims 'first F1 QUBO'."
            ),
            "evidence_needed": "Held-out mechanism usefulness vs classical discrete solvers under matched budgets.",
            "unresolved_overlap": "QUBO/Ising encoding of combinatorial race decisions is not novel by itself.",
        },
        {
            "id": "learned_race_strategy",
            "theme": "Learned race strategy / AI",
            "sources": [
                {
                    "title": "Dossier §11/§16 runtime AI comparisons; dossier [4][5] RL race-strategy citations",
                    "access": "full_text_dossier_v3_1",
                    "url": "docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf",
                    "verified_bib": True,
                }
            ],
            "their_contribution": "Broad RL/ML race-strategy literature exists; dossier requires fixed/NN/random comparators.",
            "our_proposed_difference": "Inspectable ridge donor ranking over a frozen parameter bank (not angle averaging).",
            "evidence_needed": "Held-out H2 intervals on eligible operational or mechanism endpoints.",
            "unresolved_overlap": "Learned policy selection over classical features is standard ML practice.",
        },
        {
            "id": "quantum_param_transfer",
            "theme": "Quantum parameter transfer / learned donor selection",
            "sources": [
                {
                    "title": "Farhi et al. QAOA (arXiv:1411.4028) — dossier [7]",
                    "url": "https://arxiv.org/abs/1411.4028",
                    "access": "abstract_metadata",
                    "verified_bib": True,
                },
                {
                    "title": "Egger et al. Warm-starting quantum optimization — dossier [9]",
                    "url": "https://quantum-journal.org/papers/q-2021-06-17-479/",
                    "access": "abstract_metadata",
                    "verified_bib": True,
                },
                {
                    "title": "Nguyen et al. Cross-Problem Parameter Transfer in QAOA — dossier [11]",
                    "url": "https://arxiv.org/abs/2504.10733",
                    "access": "abstract_metadata",
                    "verified_bib": True,
                },
            ],
            "their_contribution": "QAOA and parameter reuse / warm-start / cross-problem transfer methods are established.",
            "our_proposed_difference": "Application framing: audited bank + selector under motorsport split/causal constraints.",
            "evidence_needed": "Improvement over fixed/NN/random on held-out eligible endpoints.",
            "unresolved_overlap": "Parameter transfer itself is not a new quantum algorithm.",
        },
        {
            "id": "constraint_mixers",
            "theme": "Constraint-preserving mixers",
            "sources": [
                {
                    "title": "Hadfield et al. Quantum approximate optimization with hard and soft constraints — dossier [8]",
                    "url": "https://arxiv.org/abs/1709.03489",
                    "access": "abstract_metadata",
                    "verified_bib": True,
                    "note": "Dossier §13 attributes XY/guarded exchanges to prior art; no mixer invention claimed here.",
                }
            ],
            "their_contribution": "XY and related mixers preserve one-hot / feasible subspaces.",
            "our_proposed_difference": "None claimed as algorithmic novelty; C1 uses standard ring XY exchanges.",
            "evidence_needed": "N/A for novelty; legality/yield is engineering evidence only.",
            "unresolved_overlap": "C1 is a standard constraint-preserving construction.",
        },
        {
            "id": "algorithm_selection_deadline",
            "theme": "Algorithm selection / deadline-aware computation",
            "sources": [
                {
                    "title": "Dossier §14–§15 runtime allocator / deadlines; metareasoning and algorithm-selection citations",
                    "access": "full_text_dossier_v3_1",
                    "url": "docs/protocol/F1_AI_Quantum_Research_Dossier_v3_1.pdf",
                    "verified_bib": True,
                }
            ],
            "their_contribution": "Algorithm-selection and anytime/deadline literature is mature outside F1.",
            "our_proposed_difference": "Proposed contribution is integration with F1 causal checkpoint + quantum package under spend constraints.",
            "evidence_needed": "Implemented runtime allocator + measured end-to-end latency on operational evaluator.",
            "unresolved_overlap": "Without allocator evidence, deadline-aware claim remains unimplemented.",
        },
    ]

    if pilot_headroom == "ZERO" and not causal_operational_ready:
        gate = "PASS_FOR_DEFINED_SCOPE"
        survives = True
        surviving_question = (
            "Within a restricted synthetic A2 circuit-mechanism scope: what are the legality yields, "
            "sample regrets, and resource envelopes of frozen C0/C1 + donor policies versus exact/uniform "
            "classical baselines under matched shot budgets — and which integration blockers prevent an "
            "operational F1 race-decision claim?"
        )
        practical_relevance = (
            "Practical relevance today is engineering: an auditable negative headroom result, repaired "
            "circuit provenance, and a blocked operational path until causal integration. This does not "
            "establish F1 performance value or quantum advantage."
        )
    else:
        gate = "UNRESOLVED"
        survives = False
        surviving_question = None
        practical_relevance = "Insufficient Phase 6 evidence to close Gate E."

    redesign = None
    if pilot_headroom == "ZERO":
        redesign = (
            "Before any superiority campaign: enlarge model until exact classical is not timely, or "
            "abandon H1 for a mechanism/boundary protocol amendment. Do not permanently replace the "
            "project's F1 objective with an unrelated toy benchmark."
        )

    contribution_assessment = {
        "zero_demonstrated_proxy_headroom": pilot_headroom == "ZERO",
        "standard_C0_C1": True,
        "restricted_synthetic_observability": True,
        "classical_comparators_strong": True,
        "renamed_standard_method_insufficient": True,
        "circuit_legality_alone_insufficient": True,
        "negative_result_alone_insufficient_for_advantage": True,
        "surviving_scoped_contribution": survives,
        "surviving_research_question": surviving_question,
        "practical_relevance": practical_relevance,
        "redesign_required_before_full_campaign": redesign,
    }

    out = {
        "schema_version": "stage6.novelty.v1",
        "GATE_E_SCIENTIFIC_VALUE": gate,
        "no_absolute_novelty_claims": True,
        "no_first_claims": True,
        "comparisons": comparisons,
        "contribution_assessment": contribution_assessment,
        "search_method": "dossier_references_plus_targeted_WebSearch_2026-09-21",
        "unavailable_sources_remain_unavailable": True,
    }
    out["novelty_sha256"] = sha256_json({k: v for k, v in out.items() if k != "novelty_sha256"})
    return out
