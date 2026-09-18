from __future__ import annotations

import pytest

from f1q.authorization import authorize_plan
from f1q.errors import AuthorizationError
from f1q.schemas import parse_project_config

from conftest import load_yaml


@pytest.mark.parametrize(
    "plan_id",
    [
        "training",
        "materialize-training",
        "materialize_test",
        "shift",
        "campaign",
    ],
)
def test_reserved_partitions_cannot_be_materialized(project_root, plan_id):
    data = load_yaml(project_root / "configs" / "project.draft.yaml")
    config = parse_project_config(data)
    with pytest.raises(AuthorizationError):
        authorize_plan(config, plan_id)
