"""Reversible policy ↔ binary ↔ decoded mapping for A2."""

from __future__ import annotations

from typing import Any

import numpy as np

from f1q.stage5.model import A2Instance


def variable_index_map(instance: A2Instance) -> dict[str, Any]:
    blocks = instance.variable_blocks()
    index_to_meta: list[dict[str, Any]] = []
    key_to_index: dict[tuple[str, str, str], int] = {}
    for block in blocks:
        for offset, aid in enumerate(block["action_ids"]):
            idx = block["start"] + offset
            meta = {
                "index": idx,
                "info_set_id": block["info_set_id"],
                "car_id": block["car_id"],
                "action_id": aid,
                "epoch": block["epoch"],
                "f1_decision": f"{block['car_id']}@{block['info_set_id']}:{aid}",
            }
            index_to_meta.append(meta)
            key_to_index[(block["info_set_id"], block["car_id"], aid)] = idx
    return {
        "n": len(index_to_meta),
        "blocks": blocks,
        "index_to_meta": index_to_meta,
        "key_to_index": key_to_index,
    }


def policy_to_binary(instance: A2Instance, policy: dict[str, dict[str, str]]) -> np.ndarray:
    vmap = variable_index_map(instance)
    x = np.zeros(vmap["n"], dtype=np.int8)
    for info in instance.info_sets:
        for car in instance.car_ids:
            aid = policy[info.info_set_id][car]
            key = (info.info_set_id, car, aid)
            if key not in vmap["key_to_index"]:
                raise KeyError(f"unknown policy choice {key}")
            x[vmap["key_to_index"][key]] = 1
    return x


def binary_to_policy(instance: A2Instance, x: np.ndarray) -> dict[str, dict[str, str]] | None:
    """Decode one-hot binary; return None if any block is not exactly one-hot."""
    vmap = variable_index_map(instance)
    x = np.asarray(x, dtype=int).reshape(-1)
    if x.size != vmap["n"]:
        return None
    policy: dict[str, dict[str, str]] = {}
    for block in vmap["blocks"]:
        sl = x[block["start"] : block["end"]]
        if int(sl.sum()) != 1:
            return None
        chosen = block["action_ids"][int(np.argmax(sl))]
        policy.setdefault(block["info_set_id"], {})[block["car_id"]] = chosen
    return policy


def is_one_hot_feasible(instance: A2Instance, x: np.ndarray) -> bool:
    return binary_to_policy(instance, x) is not None
