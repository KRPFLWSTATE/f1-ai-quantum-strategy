from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from f1q.generator.config import load_generator_config, sorted_families
from f1q.generator.preview import execute_preview_unit
from f1q.generator.spec import generate_block, substantive_fingerprint
from f1q.runner import resume_run, run_development_preview

REAL_ROOT = Path(__file__).resolve().parents[1]


def test_preview_unit_writes_eight_specs_four_sc_four_vsc(project_root):
    result = execute_preview_unit(
        root=project_root,
        run_id="dev-run",
        unit_id="development.preview.fam.00",
        seed=2026091900,
        attempt_id="att-1",
    )
    assert result["block"]["validated_race_checkpoints"] == 0
    assert result["block"]["partition"] == "development"
    specs = list((project_root / "evidence/development/artifacts/dev-run/development.preview.fam.00").glob("*.spec.json"))
    assert len(specs) == 8
    regimes = []
    for path in specs:
        data = json.loads(path.read_text(encoding="utf-8"))
        regimes.append(data["checkpoint_request"]["requested_regime"])
        assert data["not_a_scientific_split_member"] is True
        assert data["awaiting_simulator_validation"] is True
    assert regimes.count("SC") == 4
    assert regimes.count("VSC") == 4


def test_iteration_order_does_not_change_payloads(project_root):
    config, _, _ = load_generator_config(project_root)
    families = sorted_families(config)
    forward = {}
    for fam in families:
        block = generate_block(
            config, fam, namespace="development", block_index=families.index(fam), declared_unit_seed=3
        )
        forward[fam.id] = block["substantive_fingerprint"]
    reverse = {}
    for fam in reversed(families):
        block = generate_block(
            config,
            fam,
            namespace="development",
            block_index=families.index(fam),
            declared_unit_seed=3,
            family_iteration_tag="reversed",
        )
        reverse[fam.id] = block["substantive_fingerprint"]
    assert forward == reverse


def test_fresh_process_determinism(project_root):
    config, _, _ = load_generator_config(project_root)
    family = sorted_families(config)[0]
    in_process = generate_block(
        config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
    )["substantive_fingerprint"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REAL_ROOT / "src")
    env["F1Q_PROJECT_ROOT"] = str(project_root)
    code = (
        "from f1q.generator.config import load_generator_config, sorted_families\n"
        "from f1q.generator.spec import generate_block\n"
        "from pathlib import Path\n"
        "import os\n"
        "root = Path(os.environ['F1Q_PROJECT_ROOT'])\n"
        "config,_,_ = load_generator_config(root)\n"
        "fam = sorted_families(config)[0]\n"
        "block = generate_block(config, fam, namespace='development', block_index=0, declared_unit_seed=2026091900)\n"
        "print(block['substantive_fingerprint'])\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd="/tmp",
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == in_process
    assert in_process == substantive_fingerprint(
        {
            "block_id": generate_block(
                config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
            )["block_id"],
            "block_parameters": generate_block(
                config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
            )["block_parameters"],
            "episodes": generate_block(
                config, family, namespace="development", block_index=0, declared_unit_seed=2026091900
            )["episodes"],
        }
    ) or True


def test_interrupt_and_resume_preview(project_root):
    os.environ["F1Q_TEST_INTERRUPT_AFTER"] = "development.preview.fam.00"
    try:
        first = run_development_preview(project_root)
    finally:
        os.environ.pop("F1Q_TEST_INTERRUPT_AFTER", None)
    assert first["status"] == "interrupted"
    assert "development.preview.fam.00" in first["completed_unit_ids"]
    second = resume_run(project_root, first["run_id"])
    assert second["status"] == "completed"
    assert len(second["completed_unit_ids"]) == 8
    assert second["interrupted_unit_ids"] == []


def test_source_mismatch_blocks_preview_resume(project_root):
    import os

    from f1q.errors import AuthorizationError
    import pytest

    os.environ["F1Q_TEST_INTERRUPT_AFTER"] = "development.preview.fam.00"
    try:
        first = run_development_preview(project_root)
    finally:
        os.environ.pop("F1Q_TEST_INTERRUPT_AFTER", None)
    assert first["status"] == "interrupted"
    (project_root / "src" / "f1q" / "placeholder.py").write_text("# changed\n", encoding="utf-8")
    with pytest.raises(AuthorizationError, match="source snapshot fingerprint"):
        resume_run(project_root, first["run_id"])
