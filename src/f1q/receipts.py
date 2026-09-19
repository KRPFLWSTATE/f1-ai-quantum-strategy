from __future__ import annotations

from collections import Counter

from f1q.hashing import atomic_write_text, canonical_json
from f1q.ledger import Ledger
from f1q.paths import resolve_within
from f1q.schemas import Receipt, RunManifest


def build_receipt(ledger: Ledger, manifest: RunManifest) -> Receipt:
    units = ledger.units_for(manifest.run_id)
    by_id = {u["unit_id"]: u for u in units}
    attempts = ledger.attempts_for(manifest.run_id)
    events = ledger.events_for(manifest.run_id)
    artifacts = ledger.artifacts_for(manifest.run_id)
    by_id = {u["unit_id"]: u for u in units}
    by_status = Counter(u["status"] for u in units)
    completed = [u for u in manifest.planned_unit_ids if by_id[u]["status"] == "completed"]
    failed = [u for u in manifest.planned_unit_ids if by_id[u]["status"] == "failed"]
    interrupted = [u for u in manifest.planned_unit_ids if by_id[u]["status"] == "interrupted"]
    injected = sum(int(a["injected_failure"]) for a in attempts)
    if not ledger.event_chain_ok(manifest.run_id):
        notes = ["event hash chain failed verification"]
    else:
        notes = ["event counts taken from append-only ledger events and artifact rows"]
    if by_status.get("completed") == len(manifest.planned_unit_ids):
        if manifest.plan_id == "simulator_repair":
            next_work = (
                "Stage 3.2 review of repair findings; Stage 4 (action model, QUBO) is not authorised; "
                "protocol DRAFT; hardware disabled"
            )
        elif manifest.plan_id == "simulator_followup":
            next_work = (
                "Stage 3.1 review of targeted findings; Stage 4 (action model, QUBO) is not authorised; "
                "protocol DRAFT; hardware disabled"
            )
        elif manifest.plan_id == "simulator_check":
            next_work = (
                "Stage 4 -- action model, QUBO and independent classical references "
                "(awaiting implementation prompt); protocol DRAFT; hardware disabled"
            )
        elif manifest.plan_id == "development_preview":
            next_work = (
                "Stage 3 -- simulator adapter and independent mechanism checks "
                "(awaiting implementation prompt); protocol DRAFT; hardware disabled"
            )
        else:
            next_work = (
                "Stage 2 awaiting its implementation prompt; research protocol remains DRAFT; hardware disabled"
            )
    else:
        next_work = f"resume remaining {manifest.plan_id} units"
    if manifest.evidence_kind == "development":
        notes.append("This receipt is development-preview evidence, not a scientific observation or validated race checkpoint.")
    else:
        notes.append("This receipt is setup-fixture evidence, not a scientific observation.")
    return Receipt(
        run_id=manifest.run_id,
        plan_id=manifest.plan_id,
        stage=manifest.stage,
        evidence_kind=manifest.evidence_kind,
        status=manifest.status,
        configuration_hash=manifest.configuration_hash,
        source_snapshot_hash=manifest.source_snapshot_hash,
        dossier_sha256=manifest.dossier_sha256,
        git_commit=manifest.git_commit,
        git_dirty=manifest.git_dirty,
        planned_unit_ids=list(manifest.planned_unit_ids),
        completed_unit_ids=completed,
        failed_unit_ids=failed,
        interrupted_unit_ids=interrupted,
        attempt_count=len(attempts),
        injected_failure_count=injected,
        artifact_count=len(artifacts),
        event_count=len(events),
        started_at_utc=manifest.started_at_utc,
        ended_at_utc=manifest.ended_at_utc,
        duration_monotonic_s=manifest.duration_monotonic_s,
        next_permitted_work=next_work,
        notes=notes,
    )


def write_receipt(root, receipt: Receipt) -> dict:
    payload = receipt.model_dump(mode="json")
    if receipt.plan_id == "bootstrap":
        sub = "bootstrap"
    elif receipt.plan_id in {"simulator_check", "simulator_followup", "simulator_repair"}:
        sub = "simulator"
    elif receipt.plan_id == "formulation_check":
        sub = "formulation"
    else:
        sub = "development"
    json_rel = f"evidence/{sub}/receipts/{receipt.run_id}.json"
    md_rel = f"evidence/{sub}/receipts/{receipt.run_id}.md"
    json_path = resolve_within(root, json_rel)
    md_path = resolve_within(root, md_rel)
    atomic_write_text(json_path, canonical_json(payload).decode("utf-8") + "\n")
    atomic_write_text(md_path, render_markdown(receipt))
    payload["receipt_json"] = json_rel
    payload["receipt_md"] = md_rel
    return payload


def render_markdown(receipt: Receipt) -> str:
    lines = [
        f"# Receipt {receipt.run_id}",
        "",
        f"- plan: `{receipt.plan_id}`",
        f"- stage: {receipt.stage}",
        f"- evidence kind: `{receipt.evidence_kind}` (not a scientific observation)",
        f"- status: `{receipt.status}`",
        f"- scientific protocol: {receipt.scientific_protocol}",
        f"- hardware execution enabled: {receipt.hardware_execution_enabled}",
        f"- QPU usage: {receipt.qpu_usage_seconds} seconds",
        f"- physical QPU jobs submitted: {receipt.new_physical_qpu_jobs_submitted}",
        f"- configuration hash (draft, not frozen protocol): `{receipt.configuration_hash}`",
        f"- source snapshot: `{receipt.source_snapshot_hash}`",
        f"- dossier SHA-256: `{receipt.dossier_sha256}`",
        f"- git commit: `{receipt.git_commit or 'none'}` dirty={receipt.git_dirty}",
        f"- planned units: {', '.join(receipt.planned_unit_ids)}",
        f"- completed units: {', '.join(receipt.completed_unit_ids) or 'none'}",
        f"- failed units: {', '.join(receipt.failed_unit_ids) or 'none'}",
        f"- interrupted units: {', '.join(receipt.interrupted_unit_ids) or 'none'}",
        f"- attempts: {receipt.attempt_count} (injected failures: {receipt.injected_failure_count})",
        f"- artifacts: {receipt.artifact_count}",
        f"- events: {receipt.event_count}",
        f"- started: {receipt.started_at_utc}",
        f"- ended: {receipt.ended_at_utc}",
        f"- monotonic duration (s): {receipt.duration_monotonic_s}",
        f"- next permitted work: {receipt.next_permitted_work}",
        "",
        "Notes:",
    ]
    for note in receipt.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)
