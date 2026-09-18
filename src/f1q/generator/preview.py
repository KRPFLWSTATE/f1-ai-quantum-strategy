from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from f1q.causal import PrivateSimState, SimulatorState
from f1q.generator.config import GeneratorConfigFile, load_generator_config, sorted_families
from f1q.generator.observation import pending_envelope
from f1q.generator.spec import generate_block, substantive_fingerprint
from f1q.generator.streams import stream_hex, stream_seed
from f1q.hashing import atomic_write_bytes, canonical_json, sha256_json
from f1q.paths import resolve_within
from f1q.schemas import utc_now


def family_for_unit(config: GeneratorConfigFile, unit_id: str):
    families = sorted_families(config)
    index = int(unit_id.rsplit(".", 1)[-1])
    return families[index], index


def execute_preview_unit(
    *,
    root: Path,
    run_id: str,
    unit_id: str,
    seed: int,
    attempt_id: str,
) -> dict[str, Any]:
    config, generator_hash, _ = load_generator_config(root)
    family, block_index = family_for_unit(config, unit_id)
    block = generate_block(
        config,
        family,
        namespace="development",
        block_index=block_index,
        declared_unit_seed=seed,
        family_iteration_tag=unit_id,
    )
    rel_dir = f"evidence/development/artifacts/{run_id}/{unit_id}"
    art_dir = resolve_within(root, rel_dir)
    art_dir.mkdir(parents=True, exist_ok=True)
    private_dir = resolve_within(root, f"evidence/development/private/{run_id}/{unit_id}")
    private_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for episode in block["episodes"]:
        spec_name = episode["episode_id"].replace("/", "__") + ".spec.json"
        spec_rel = f"{rel_dir}/{spec_name}"
        spec_path = resolve_within(root, spec_rel)
        digest = atomic_write_bytes(spec_path, canonical_json(episode) + b"\n")
        written.append({"relative_path": spec_rel, "sha256": digest, "kind": "scenario_spec"})
        from f1q.generator.streams import stream_hex

        private_state = SimulatorState(
            episode_id=episode["episode_id"],
            spec_id=episode["spec_id"],
            public={
                "cars": [
                    {
                        "car_id": car["car_id"],
                        "classified_position": car["classified_position"],
                        "gap_ahead_s": car["gap_ahead_s"],
                        "lap_deficit": car["lap_deficit"],
                        "pit_entry_commitment_cutoff_race_s": None,
                    }
                    for car in episode["field"]
                ],
                "completed_laps": episode["checkpoint_request"]["completed_laps"],
                "remaining_laps": episode["checkpoint_request"]["remaining_laps"],
                "selected_team_id": episode["selected_team_id"],
            },
            private=PrivateSimState(
                block_stream_seed=stream_seed(
                    "block_params",
                    {
                        "generator_version": config.generator_version,
                        "namespace": "development",
                        "family_id": family.id,
                        "block_index": block_index,
                        "declared_unit_seed": seed,
                    },
                ),
                episode_stream_seed=stream_seed(
                    "episode",
                    {
                        "generator_version": config.generator_version,
                        "block_id": block["block_id"],
                        "episode_index": int(episode["episode_id"].split("/episode/")[1].split("/")[0]),
                        "attempt": episode["provenance"]["attempt"],
                        "declared_unit_seed": seed,
                    },
                ),
                sampled_future_regime_duration_s=None,
                rival_eventual_pit_laps=None,
                evaluator_bank_key=stream_hex(
                    "evaluation",
                    {
                        "generator_version": config.generator_version,
                        "episode_id": episode["episode_id"],
                        "driver_id": episode["selected_car_ids"][0],
                        "lap": episode["checkpoint_request"]["completed_laps"],
                        "event_type": "evaluator_bank",
                        "replication": 0,
                    },
                ),
            ),
            stream_key_ids=episode["stream_key_ids"],
        )
        priv_rel = f"evidence/development/private/{run_id}/{unit_id}/{spec_name.replace('.spec.json', '.state.json')}"
        priv_path = resolve_within(root, priv_rel)
        atomic_write_bytes(priv_path, canonical_json(private_state.model_dump(mode="python")) + b"\n")
        envelope = pending_envelope(spec=episode, private_ref=priv_rel)
        env_rel = f"{rel_dir}/{spec_name.replace('.spec.json', '.envelope.json')}"
        env_digest = atomic_write_bytes(
            resolve_within(root, env_rel), canonical_json(envelope.model_dump(mode="python")) + b"\n"
        )
        written.append({"relative_path": env_rel, "sha256": env_digest, "kind": "checkpoint_envelope"})
    block_rel = f"{rel_dir}/block.json"
    public_block = {
        "block_id": block["block_id"],
        "family_id": block["family_id"],
        "partition": block["partition"],
        "namespace": block["namespace"],
        "block_index": block["block_index"],
        "block_parameters": block["block_parameters"],
        "episode_ids": [ep["episode_id"] for ep in block["episodes"]],
        "spec_ids": [ep["spec_id"] for ep in block["episodes"]],
        "regimes": [ep["checkpoint_request"]["requested_regime"] for ep in block["episodes"]],
        "rejections": block["rejections"],
        "substantive_fingerprint": block["substantive_fingerprint"],
        "awaiting_simulator_validation": True,
        "not_a_scientific_split_member": True,
        "validated_race_checkpoints": 0,
        "generator_config_hash": generator_hash,
        "generator_version": config.generator_version,
    }
    block_digest = atomic_write_bytes(resolve_within(root, block_rel), canonical_json(public_block) + b"\n")
    written.append({"relative_path": block_rel, "sha256": block_digest, "kind": "development_block"})
    payload = {
        "unit_id": unit_id,
        "seed": seed,
        "block_id": block["block_id"],
        "family_id": family.id,
        "spec_fingerprints": [ep["substantive_fingerprint"] for ep in block["episodes"]],
        "block_fingerprint": block["substantive_fingerprint"],
        "not_a_scientific_observation": True,
        "awaiting_simulator_validation": True,
        "validated_race_checkpoints": 0,
    }
    substantive = sha256_json(payload)
    envelope = {
        "payload": payload,
        "substantive_sha256": substantive,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "written_at_utc": utc_now(),
        "files": written,
    }
    unit_rel = f"{rel_dir}/unit.json"
    digest = atomic_write_bytes(resolve_within(root, unit_rel), canonical_json(envelope) + b"\n")
    return {
        "substantive_payload_sha256": substantive,
        "artifact": {
            "artifact_id": str(uuid4()),
            "run_id": run_id,
            "unit_id": unit_id,
            "relative_path": unit_rel,
            "sha256": digest,
            "kind": "development_preview_unit",
            "created_at_utc": utc_now(),
        },
        "extra_artifacts": [
            {
                "artifact_id": str(uuid4()),
                "run_id": run_id,
                "unit_id": unit_id,
                "relative_path": item["relative_path"],
                "sha256": item["sha256"],
                "kind": item["kind"],
                "created_at_utc": utc_now(),
            }
            for item in written
        ],
        "block": public_block,
        "fingerprint": substantive_fingerprint(payload),
    }
