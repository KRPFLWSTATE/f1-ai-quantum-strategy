"""Regression: A3 constructions must not reappear in A4."""

from __future__ import annotations

import inspect

from f1q.a3 import agents as a3_agents
from f1q.a3 import campaign as a3_campaign
from f1q.a3 import loop as a3_loop
from f1q.a3 import partitions as a3_parts
from f1q.a3 import problem as a3_problem
from f1q.a4 import campaign as a4_campaign
from f1q.a4 import generators as a4_gen
from f1q.a4 import loop as a4_loop
from f1q.a4 import partitions as a4_parts
from f1q.a4 import problem as a4_problem


def test_a3_selects_first_candidate_a4_does_not():
    src = inspect.getsource(a3_loop.decide_from_observation)
    assert '["downstream_candidates"][0]' in src
    src4 = inspect.getsource(a4_loop.decide_and_evaluate)
    assert '["downstream_candidates"][0]' not in src4
    assert "select_by_planning_mean" in src4


def test_a3_appends_quantum_budget_a4_replaces():
    src = inspect.getsource(a3_agents.assemble_portfolio)
    assert "equal_k * 2" in src
    src4 = inspect.getsource(a4_gen.assemble_portfolio)
    assert "equal_k * 2" not in src4
    assert "replaced_not_appended" in src4


def test_a3_offline_copied_a4_evaluates():
    src = inspect.getsource(a3_campaign.execute_campaign)
    assert 'offline_plan_loss = cl["mean_loss"]' in src
    src4 = inspect.getsource(a4_campaign.execute_campaign)
    assert 'offline_plan_loss = cl["mean_loss"]' not in src4
    assert "copied_from_arm" in src4


def test_a3_later_info_set_a4_current_only():
    src = inspect.getsource(a3_problem.policy_to_simulator_plan)
    assert "contingent_completion" in src
    src4 = inspect.getsource(a4_problem.policy_to_simulator_plan)
    assert "contingent_completion" not in src4
    srcm = inspect.getsource(a3_problem.build_menu_and_instance)
    assert "acts[:2]" in srcm
    srcm4 = inspect.getsource(a4_problem.build_menu_and_instance)
    assert "acts[:2]" not in srcm4


def test_a3_hardcoded_reduction_absent_in_a4():
    src = inspect.getsource(a3_parts.reduced_execution_subset)
    assert "45 min" in src
    src4 = inspect.getsource(a4_parts.build_a4_partitions)
    assert "45 min" not in src4
    assert "reduced_execution_subset" not in inspect.getsource(a4_campaign.execute_campaign)


def test_a3_random_default_params_not_used_as_learned_in_a4():
    src = inspect.getsource(a3_loop.default_params)
    assert "standard_normal" in src
    src4 = inspect.getsource(a4_loop.decide_and_evaluate)
    assert "default_params" not in src4
    assert "standard_normal" not in src4
    assert "unfitted_diagnostic_constant_not_learned" in src4 or "[0.3]" in src4
