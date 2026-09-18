from __future__ import annotations

import pytest

from f1q.errors import AuthorizationError
from f1q.generator.config import load_generator_config
from f1q.generator.splits import TEST_BLOCK_CHOICES, build_split_plan, planned_counts


def test_test_blocks_accepts_every_multiple_of_eight_from_80_to_160(project_root):
    config, _, _ = load_generator_config(project_root)
    assert TEST_BLOCK_CHOICES[0] == 80
    assert TEST_BLOCK_CHOICES[-1] == 160
    assert 88 in TEST_BLOCK_CHOICES
    plan = build_split_plan(config, test_blocks=88)
    assert plan["test_blocks"] == 88
    assert plan["per_family"]["test"] == 11
    assert plan["planned_counts"]["test_checkpoints_planned"] == 704
    assert all(not rec["materialized"] for rec in plan["records"])


@pytest.mark.parametrize("bad", [72, 84, 81, 168])
def test_invalid_test_blocks_rejected(bad):
    with pytest.raises(AuthorizationError, match="multiple of eight"):
        planned_counts(test_blocks=bad, include_shift=True)
