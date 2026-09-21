"""A3 novelty comparison. No 'first', no quantum advantage, no real-team claims."""

from __future__ import annotations

from typing import Any

from f1q.hashing import sha256_json


def build_a3_novelty(*, causal_ok: bool, headroom: str, gate_e: str) -> dict[str, Any]:
    comparisons = [
        {
            "id": "f1_dp",
            "theme": "F1 DP / classical race optimisation",
            "sources": [
                {
                    "title": "On the optimization of pit stop strategies via dynamic programming",
                    "authors": "Carrasco Heine, O.F.; Thraves, C.",
                    "venue": "Central European Journal of Operations Research 31(1):239–268, 2023",
                    "url": "https://doi.org/10.1007/s10100-022-00806-4",
                    "access": "abstract_metadata_and_secondary_full_record",
                    "verified_this_campaign": True,
                }
            ],
            "their_contribution": (
                "DP/SDP for pit lap and compound under tyre wear, yellow flags, and weather; "
                "SDP delays stops to exploit possible yellow flags."
            ),
            "a3_precise_difference": (
                "A3 is a causal checkpoint decision with two-car shared-crew constraints and a "
                "deadline-aware hybrid candidate portfolio, scored by an independent simulator "
                "evaluator. It does not replace DP race optimisation and does not claim better race times."
            ),
            "implemented_evidence": "A3 rolling-horizon menu + simulator continuation evaluator",
            "unresolved_overlap": "Both treat SC/VSC-aware pit timing; classical DP remains the stronger ops baseline.",
        },
        {
            "id": "f1_game",
            "theme": "F1 game-theoretic optimisation",
            "sources": [
                {
                    "title": "Optimizing pit stop strategies in Formula 1 with dynamic programming and game theory",
                    "authors": "Aguad, F.; Thraves, C.",
                    "venue": "European Journal of Operational Research 319(3):908–919, 2024",
                    "url": "https://doi.org/10.1016/j.ejor.2024.07.011",
                    "access": "abstract_metadata",
                    "verified_this_campaign": True,
                    "doi_note": "RePEc/EJOR record; earlier SSRN preprint 4470115. Abstract access, not paywalled full text.",
                }
            ],
            "their_contribution": (
                "Two-driver zero-sum feedback Stackelberg pit/compound game with overtaking and yellow flags."
            ),
            "a3_precise_difference": (
                "A3 models one team's two cars vs a frozen non-reactive rival field in a Stage 3 simulator, "
                "not an equilibrium game against a strategic opponent."
            ),
            "implemented_evidence": "hand/spec rival.policy.frozen_nonreactive.v1",
            "unresolved_overlap": "Competitive interaction is present in both; A3 does not solve a Stackelberg game.",
        },
        {
            "id": "f1_rl",
            "theme": "Multi-agent / learning F1 strategy",
            "sources": [
                {
                    "title": "Race Strategy Reinforcement Learning: Optimising Pitstop Strategy with Emergent Tactics in Formula One",
                    "venue": "Machine Learning (Springer), 2026 record",
                    "url": "https://doi.org/10.1007/s10994-026-07081-3",
                    "access": "abstract_metadata",
                    "verified_this_campaign": True,
                }
            ],
            "their_contribution": "RL race-strategy agent with post-hoc explanations vs hard-coded/MC baselines.",
            "a3_precise_difference": (
                "A3 uses small inspectable ridge models for donor/dispatch only; policies are enumerated "
                "rolling-horizon plans, not an RL policy network. No claim to outperform RSRL."
            ),
            "implemented_evidence": "RidgeRuntime fit receipts; no neural race policy",
            "unresolved_overlap": "Both learn something about when to pit; methods and estimands differ.",
        },
        {
            "id": "f1_qubo",
            "theme": "F1 QUBO / annealing",
            "sources": [
                {
                    "title": "Optimizing Formula 1 Pit Stop Strategies Using QUBO and Annealing-Based Methods",
                    "authors": "Kolstee, S.",
                    "venue": "LIACS bachelor thesis listing 2025–26",
                    "url": "https://theses.liacs.nl/bachelori",
                    "access": "repository_listing_metadata",
                    "verified_this_campaign": True,
                    "note": "Full thesis body not independently fetched; listing confirms topic.",
                }
            ],
            "their_contribution": "QUBO/annealing encoding of F1 pit-stop strategies (thesis-scale).",
            "a3_precise_difference": (
                "A3 QUBO is a candidate generator inside a causal simulator loop; value is marginal "
                "simulator loss after strong classical candidates, not annealer energy."
            ),
            "implemented_evidence": "direct-cost/QUBO agreement + continuation evaluator",
            "unresolved_overlap": "Discrete pit/compound QUBO encodings; A3 does not claim a new QUBO family.",
        },
        {
            "id": "qaoa_transfer",
            "theme": "QAOA parameter transfer",
            "sources": [
                {
                    "title": "For Fixed Control Parameters the QAOA Objective Function Value Concentrates for Typical Instances",
                    "authors": "Brandão et al.",
                    "url": "https://doi.org/10.48550/arxiv.1812.04170",
                    "access": "full_text_arxiv",
                    "verified_this_campaign": True,
                },
                {
                    "title": "Transferability of optimal QAOA parameters between random graphs",
                    "authors": "Galda et al.",
                    "venue": "IEEE QCE 2021",
                    "url": "https://doi.org/10.1109/qce52317.2021.00034",
                    "access": "abstract_and_conference_record",
                    "verified_this_campaign": True,
                },
            ],
            "their_contribution": "QAOA angle concentration/transfer on MaxCut-like graphs.",
            "a3_precise_difference": (
                "A3 donor selection is on causal F1 observables + QUBO structure for C0/C1, not graph-lightcone MaxCut transfer. No new mixer/QAOA claimed."
            ),
            "implemented_evidence": "new A3 ridge selector features; A2 donors not reused as A3 models",
            "unresolved_overlap": "Both reuse variational angles; problem class differs.",
        },
        {
            "id": "xy_mixers",
            "theme": "Constraint-preserving mixers",
            "sources": [
                {
                    "title": "From the Quantum Approximate Optimization Algorithm to a Quantum Alternating Operator Ansatz",
                    "authors": "Hadfield et al.",
                    "url": "https://arxiv.org/abs/1709.03489",
                    "access": "full_text_arxiv",
                    "verified_this_campaign": True,
                },
                {
                    "title": "Constraint Preserving Mixers for the Quantum Approximate Optimization Algorithm",
                    "url": "https://doi.org/10.3390/a15060202",
                    "access": "full_text",
                    "verified_this_campaign": True,
                },
            ],
            "their_contribution": "XY / feasibility-preserving mixers for one-hot subspaces.",
            "a3_precise_difference": "C1 reuses XY one-hot mixers as a candidate generator; not claimed as a new mixer.",
            "implemented_evidence": "existing Stage 5 C1 circuits invoked from A3",
            "unresolved_overlap": "Identical mixer class; application and causal loop are the difference, not the mixer.",
        },
        {
            "id": "algo_select",
            "theme": "Algorithm selection / metareasoning / deadline-aware hybrid opt",
            "sources": [
                {
                    "title": "The Algorithm Selection Problem",
                    "authors": "Rice, J.R.",
                    "venue": "Advances in Computers, 1976",
                    "access": "bibliographic_plus_survey_secondary",
                    "verified_this_campaign": True,
                },
                {
                    "title": "Algorithm Selection for Combinatorial Search Problems: A Survey",
                    "authors": "Kotthoff, L.",
                    "url": "http://www.cs.uwyo.edu/~larsko/papers/kotthoff_algorithm_2012-1.pdf",
                    "access": "full_text_pdf",
                    "verified_this_campaign": True,
                },
                {
                    "title": "Learning to select computations",
                    "authors": "Hay, N. et al. / related BMPS line (Lieder, Russell)",
                    "url": "https://arxiv.org/pdf/1711.06892v3.pdf",
                    "access": "full_text_arxiv",
                    "verified_this_campaign": True,
                    "note": "Metareasoning / value-of-computation; not F1-specific.",
                },
            ],
            "their_contribution": "Map instance features to algorithms; metareason about computation under limits.",
            "a3_precise_difference": (
                "A3 dispatcher predicts marginal simulator utility and latency for C0/C1 vs classical-only "
                "at a causal F1 checkpoint with mandatory fallback. Not a general SAT/CSP selector."
            ),
            "implemented_evidence": "RidgeRuntime + dispatch_choice with fallback",
            "unresolved_overlap": "Same meta-problem class (choose an algorithm under a deadline).",
        },
    ]
    return {
        "GATE_E_SCIENTIFIC_VALUE": gate_e,
        "F1_CONTRIBUTION_STATUS": (
            "BOUNDARY_STUDY_IMPLEMENTED" if causal_ok else "INSUFFICIENT"
        ),
        "no_first_claim": True,
        "no_quantum_advantage_claim": True,
        "no_real_team_performance_claim": True,
        "operational_headroom": headroom,
        "comparisons": comparisons,
        "hash": sha256_json(comparisons),
        "dossier_is_not_verification_of_cited_papers": True,
        "access_levels_disclosed": True,
    }
