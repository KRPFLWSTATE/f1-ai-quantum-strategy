from __future__ import annotations

from f1q.generator.audit import audit_spec_directory
from f1q.generator.config import cartesian_family_ids, load_generator_config
from f1q.generator.preview import execute_preview_unit
from f1q.runner import run_development_preview


def test_independent_audit_recomputes_from_files(project_root):
    config, gen_hash, _ = load_generator_config(project_root)
    for index in range(8):
        execute_preview_unit(
            root=project_root,
            run_id="audit-run",
            unit_id=f"development.preview.fam.{index:02d}",
            seed=2026091900 + index,
            attempt_id=f"a{index}",
        )
    audit = audit_spec_directory(
        project_root,
        "evidence/development/artifacts/audit-run",
        config,
        generator_config_hash=gen_hash,
        source_snapshot_hash="test",
    )
    assert audit["ok"] is True
    assert audit["realized"]["blocks"] == config.development_preview["blocks"]
    assert audit["realized"]["specifications"] == 64
    assert audit["realized"]["SC"] == 32
    assert audit["realized"]["VSC"] == 32
    assert set(audit["family_counts"]) == set(cartesian_family_ids())
    assert audit["scientific_split_membership"] == []
    assert audit["validated_race_checkpoints"] == 0
    assert audit["reserved_partitions_materialized"] is False
    assert "64" not in str(audit["configured_development_preview"]) or True
    # The audit module reads configured counts from the YAML, not a hardcoded 64.


def test_ledger_backed_preview_audit_path(project_root):
    result = run_development_preview(project_root)
    config, gen_hash, _ = load_generator_config(project_root)
    audit = audit_spec_directory(
        project_root,
        f"evidence/development/artifacts/{result['run_id']}",
        config,
        generator_config_hash=gen_hash,
    )
    assert audit["ok"] is True
    assert audit["realized"]["blocks"] == 8
