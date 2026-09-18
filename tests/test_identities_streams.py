from __future__ import annotations

import hashlib

from f1q.generator.config import load_generator_config, sorted_families
from f1q.generator.spec import generate_block
from f1q.generator.streams import evaluation_key, stream_hex, stream_seed


def test_python_hash_is_not_used_for_identities():
    a = stream_hex("block_params", {"x": 1})
    b = stream_hex("block_params", {"x": 1})
    assert a == b
    assert a != hashlib.sha256(b"x").hexdigest()


def test_fitting_seed_does_not_change_episode_or_evaluation_keys(project_root):
    config, _, _ = load_generator_config(project_root)
    family = sorted_families(config)[0]
    block = generate_block(
        config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
    )
    episode = block["episodes"][0]
    fit_a = stream_hex("fitting", {"seed_id": 1})
    fit_b = stream_hex("fitting", {"seed_id": 2})
    assert fit_a != fit_b
    block2 = generate_block(
        config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
    )
    assert [ep["substantive_fingerprint"] for ep in block["episodes"]] == [
        ep["substantive_fingerprint"] for ep in block2["episodes"]
    ]
    key_a = evaluation_key(
        generator_version=config.generator_version,
        episode_id=episode["episode_id"],
        driver_id=episode["selected_car_ids"][0],
        lap=episode["checkpoint_request"]["completed_laps"],
        event_type="evaluator_bank",
        replication=0,
    )
    key_b = evaluation_key(
        generator_version=config.generator_version,
        episode_id=episode["episode_id"],
        driver_id=episode["selected_car_ids"][0],
        lap=episode["checkpoint_request"]["completed_laps"],
        event_type="evaluator_bank",
        replication=0,
    )
    assert key_a == key_b
    assert key_a != fit_a
    assert episode["stream_key_ids"]["fitting"] != stream_hex("fitting", {"seed_id": 99})


def test_event_keyed_draws_change_with_lap_or_replication(project_root):
    config, _, _ = load_generator_config(project_root)
    family = sorted_families(config)[0]
    block = generate_block(
        config, family, namespace="development", block_index=0, declared_unit_seed=7
    )
    ep = block["episodes"][0]
    base = dict(
        generator_version=config.generator_version,
        episode_id=ep["episode_id"],
        driver_id=ep["selected_car_ids"][0],
        lap=10,
        event_type="tyre_wear",
        replication=0,
    )
    a = evaluation_key(**base)
    b = evaluation_key(**{**base, "lap": 11})
    c = evaluation_key(**{**base, "replication": 1})
    assert a != b
    assert a != c
    assert stream_seed("evaluation", {**base, "driver_id": ep["selected_car_ids"][1]}) != stream_seed(
        "evaluation", base
    )
