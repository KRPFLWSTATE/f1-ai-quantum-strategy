from __future__ import annotations

from pathlib import Path

from f1q.simulator.checks import run_all_mechanism_checks
from f1q.simulator.config import load_simulator_config
from f1q.simulator.hand_specs import build_hand_spec
from f1q.simulator.interface import RaceSimulator, SimulatorAdapter

ROOT = Path(__file__).resolve().parents[1]


def test_all_named_mechanism_checks_pass():
    cfg, _ = load_simulator_config(ROOT)
    report = run_all_mechanism_checks(cfg)
    assert report["ok"], report.get("failed")


def test_resume_equivalence_in_fresh_process(tmp_path):
    import json
    import subprocess
    import sys

    cfg, _ = load_simulator_config(ROOT)
    spec = build_hand_spec(obligation=2, remaining_at_checkpoint=7, laps_until_checkpoint=1, regime="SC")
    sim = RaceSimulator(cfg)
    sim.initialize(spec)
    sim.apply_plan(
        {
            spec["selected_car_ids"][0]: {
                "kind": "pit_now",
                "compound": "medium",
                "set_id": f"{spec['selected_car_ids'][0]}.set.medium.0",
            }
        }
    )
    sim.advance_to_checkpoint()
    sim.advance_to_time(float(sim.engine.state["t"]) + 3.0)
    blob_path = tmp_path / "blob.json"
    spec_path = tmp_path / "spec.json"
    blob_path.write_text(json.dumps(sim.serialize()), encoding="utf-8")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    sim.continue_to_finish()
    expected = sim.engine.outcome()
    script = tmp_path / "restore.py"
    script.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "from f1q.simulator.config import load_simulator_config\n"
        "from f1q.simulator.interface import RaceSimulator\n"
        "root = Path(sys.argv[1])\n"
        "cfg, _ = load_simulator_config(root)\n"
        "spec = json.loads(Path(sys.argv[2]).read_text())\n"
        "blob = json.loads(Path(sys.argv[3]).read_text())\n"
        "sim = RaceSimulator(cfg)\n"
        "sim.restore(blob, spec)\n"
        "_, out = sim.continue_to_finish()\n"
        "print(json.dumps({'t': out['t'], 'ranks': out['ranking']['ranks']}))\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(script), str(ROOT), str(spec_path), str(blob_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert got["ranks"] == expected["ranking"]["ranks"]
    assert abs(got["t"] - expected["t"]) <= 1e-6


def test_adapter_initializes_and_excludes_private_from_observation():
    cfg, _ = load_simulator_config(ROOT)
    spec = build_hand_spec(obligation=1)
    sim = RaceSimulator(cfg)
    state = sim.initialize(spec)
    sim.advance_to_checkpoint()
    obs = sim.observe()
    blob = str(obs.model_dump(mode="python"))
    assert "fuel_actual" not in blob
    assert state.private.sampled_future_regime_duration_s is not None
    assert str(state.private.sampled_future_regime_duration_s) not in blob
    adapter = SimulatorAdapter(project_root=ROOT)
    adapter.initialize(spec)
    adapter.run_to_checkpoint(spec)
