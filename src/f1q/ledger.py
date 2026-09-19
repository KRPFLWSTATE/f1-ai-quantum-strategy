from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from f1q.errors import IntegrityError, LedgerLocked
from f1q.hashing import atomic_write_bytes, canonical_json, sha256_json
from f1q.schemas import utc_now

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    stage INTEGER NOT NULL,
    evidence_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS units (
    run_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    status TEXT NOT NULL,
    seed INTEGER,
    substantive_payload_sha256 TEXT,
    PRIMARY KEY (run_id, unit_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    duration_monotonic_s REAL,
    error TEXT,
    injected_failure INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    ts_utc TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_event_hash TEXT,
    event_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    unit_id TEXT,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rejections (
    rejection_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    unit_id TEXT,
    attempt_id TEXT,
    code TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
);
"""

PLAN_EVIDENCE_DIR = {
    "bootstrap": "bootstrap",
    "development_preview": "development",
    "simulator_check": "simulator",
    "simulator_followup": "simulator",
    "simulator_repair": "simulator",
}


class Ledger:
    def __init__(self, db_path: Path, lock_path: Path, root: Path | None = None):
        self.db_path = db_path
        self.lock_path = lock_path
        self.root = Path(root).resolve() if root is not None else db_path.parent.parent.parent
        self._lock_fd: int | None = None
        self.conn: sqlite3.Connection | None = None

    def _run_dir(self, run_id: str) -> Path:
        plan_id = "bootstrap"
        if self.conn is not None:
            row = self.conn.execute("SELECT plan_id FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is not None:
                plan_id = row["plan_id"]
        folder = PLAN_EVIDENCE_DIR.get(plan_id, "other")
        return self.root / "evidence" / folder / "runs" / run_id

    def _ensure_schema_version(self) -> None:
        from f1q import LEDGER_SCHEMA_VERSION

        conn = self._require()
        row = conn.execute("SELECT value FROM ledger_meta WHERE key='schema_version'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO ledger_meta(key, value) VALUES('schema_version', ?)",
                (str(LEDGER_SCHEMA_VERSION),),
            )

    def __enter__(self) -> Ledger:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def acquire(self, *, blocking: bool = False) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(self._lock_fd, flags)
        except BlockingIOError as exc:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise LedgerLocked("another writer holds the ledger lock") from exc
        self.conn = sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA_SQL)
        self._ensure_schema_version()

    def release(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
            finally:
                self._lock_fd = None

    def _require(self) -> sqlite3.Connection:
        if self.conn is None:
            raise IntegrityError("ledger connection is not open")
        return self.conn

    def tx(self):
        return Transaction(self._require())

    def insert_run(self, manifest: dict[str, Any]) -> None:
        conn = self._require()
        now = utc_now()
        conn.execute(
            """
            INSERT INTO runs(run_id, plan_id, stage, evidence_kind, status, manifest_json, created_at_utc, updated_at_utc)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                manifest["run_id"],
                manifest["plan_id"],
                manifest["stage"],
                manifest["evidence_kind"],
                manifest["status"],
                json.dumps(manifest, sort_keys=True),
                now,
                now,
            ),
        )
        for unit_id in manifest["planned_unit_ids"]:
            conn.execute(
                "INSERT INTO units(run_id, unit_id, status, seed, substantive_payload_sha256) VALUES(?,?,?,?,?)",
                (manifest["run_id"], unit_id, "pending", None, None),
            )
        self._write_manifest_file(manifest, final=False)

    def update_manifest(self, manifest: dict[str, Any]) -> None:
        conn = self._require()
        conn.execute(
            "UPDATE runs SET status=?, manifest_json=?, updated_at_utc=? WHERE run_id=?",
            (
                manifest["status"],
                json.dumps(manifest, sort_keys=True),
                utc_now(),
                manifest["run_id"],
            ),
        )
        self._write_manifest_file(manifest, final=manifest.get("status") != "running")

    def _write_manifest_file(self, manifest: dict[str, Any], *, final: bool) -> None:
        run_dir = self._run_dir(manifest["run_id"])
        atomic_write_bytes(run_dir / "manifest.json", canonical_json(manifest) + b"\n", overwrite=True)
        if final:
            final_path = run_dir / "manifest.final.json"
            if not final_path.exists():
                atomic_write_bytes(final_path, canonical_json(manifest) + b"\n", overwrite=False)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._require().execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self._require().execute("SELECT * FROM runs ORDER BY created_at_utc").fetchall()
        return [dict(r) for r in rows]

    def incomplete_runs(self) -> list[dict[str, Any]]:
        rows = (
            self._require()
            .execute(
                "SELECT * FROM runs WHERE status IN ('running','interrupted','pending') ORDER BY created_at_utc"
            )
            .fetchall()
        )
        return [dict(r) for r in rows]

    def units_for(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self._require()
            .execute("SELECT * FROM units WHERE run_id=? ORDER BY unit_id", (run_id,))
            .fetchall()
        )
        return [dict(r) for r in rows]

    def claim_unit(self, run_id: str, unit_id: str, attempt_id: str, *, seed: int | None) -> bool:
        conn = self._require()
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE units SET status='running', seed=? WHERE run_id=? AND unit_id=? AND status='pending'",
                (seed, run_id, unit_id),
            )
            if cur.rowcount != 1:
                conn.execute("COMMIT")
                return False
        except Exception:
            conn.execute("ROLLBACK")
            raise
        now = utc_now()
        conn.execute(
            """
            INSERT INTO attempts(attempt_id, run_id, unit_id, status, started_at_utc, ended_at_utc,
                                 duration_monotonic_s, error, injected_failure)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (attempt_id, run_id, unit_id, "running", now, None, None, None, 0),
        )
        self.append_event(
            run_id,
            "unit_claimed",
            {"unit_id": unit_id, "attempt_id": attempt_id},
        )
        conn.execute("COMMIT")
        return True

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        error: str | None,
        duration_monotonic_s: float,
        injected_failure: bool = False,
        substantive_payload_sha256: str | None = None,
    ) -> None:
        conn = self._require()
        row = conn.execute(
            "SELECT run_id, unit_id FROM attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise IntegrityError(f"unknown attempt {attempt_id}")
        conn.execute(
            """
            UPDATE attempts SET status=?, ended_at_utc=?, duration_monotonic_s=?, error=?, injected_failure=?
            WHERE attempt_id=?
            """,
            (
                status,
                utc_now(),
                duration_monotonic_s,
                error,
                int(injected_failure),
                attempt_id,
            ),
        )
        unit_status = {
            "completed": "completed",
            "failed": "failed",
            "interrupted": "interrupted",
        }[status]
        conn.execute(
            "UPDATE units SET status=?, substantive_payload_sha256=COALESCE(?, substantive_payload_sha256) WHERE run_id=? AND unit_id=?",
            (unit_status, substantive_payload_sha256, row["run_id"], row["unit_id"]),
        )
        self.append_event(
            row["run_id"],
            "attempt_finished",
            {
                "attempt_id": attempt_id,
                "unit_id": row["unit_id"],
                "status": status,
                "injected_failure": injected_failure,
                "error": error,
            },
        )

    def reset_interrupted_to_pending(self, run_id: str, unit_id: str) -> None:
        conn = self._require()
        conn.execute(
            "UPDATE units SET status='pending' WHERE run_id=? AND unit_id=? AND status='interrupted'",
            (run_id, unit_id),
        )
        self.append_event(run_id, "unit_requeued_after_interrupt", {"unit_id": unit_id})

    def add_artifact(self, record: dict[str, Any]) -> None:
        conn = self._require()
        conn.execute(
            """
            INSERT INTO artifacts(artifact_id, run_id, unit_id, relative_path, sha256, kind, created_at_utc)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                record["artifact_id"],
                record["run_id"],
                record.get("unit_id"),
                record["relative_path"],
                record["sha256"],
                record["kind"],
                record["created_at_utc"],
            ),
        )
        self.append_event(
            record["run_id"],
            "artifact_recorded",
            {
                "artifact_id": record["artifact_id"],
                "relative_path": record["relative_path"],
                "sha256": record["sha256"],
            },
        )

    def artifacts_for(self, run_id: str, unit_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._require()
        if unit_id is None:
            rows = conn.execute("SELECT * FROM artifacts WHERE run_id=?", (run_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE run_id=? AND unit_id=?", (run_id, unit_id)
            ).fetchall()
        return [dict(r) for r in rows]

    def attempts_for(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self._require()
            .execute("SELECT * FROM attempts WHERE run_id=? ORDER BY started_at_utc", (run_id,))
            .fetchall()
        )
        return [dict(r) for r in rows]

    def events_for(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self._require()
            .execute("SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))
            .fetchall()
        )
        return [dict(r) for r in rows]

    def last_event_hash(self, run_id: str) -> str | None:
        row = (
            self._require()
            .execute("SELECT event_hash FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 1", (run_id,))
            .fetchone()
        )
        return None if row is None else row["event_hash"]

    def append_event(self, run_id: str, kind: str, payload: dict[str, Any]) -> str:
        conn = self._require()
        prev = self.last_event_hash(run_id)
        ts = utc_now()
        event_id = sha256_json({"run_id": run_id, "kind": kind, "ts": ts, "payload": payload, "n": time.time_ns()})
        body = {
            "event_id": event_id,
            "run_id": run_id,
            "ts_utc": ts,
            "kind": kind,
            "payload": payload,
            "prev_event_hash": prev,
        }
        event_hash = sha256_json(body)
        conn.execute(
            """
            INSERT INTO events(event_id, run_id, ts_utc, kind, payload_json, prev_event_hash, event_hash)
            VALUES(?,?,?,?,?,?,?)
            """,
            (event_id, run_id, ts, kind, json.dumps(payload, sort_keys=True), prev, event_hash),
        )
        event_path = self._run_dir(run_id) / "events" / f"{event_id}.json"
        try:
            atomic_write_bytes(event_path, canonical_json(body) + b"\n", overwrite=False)
        except FileExistsError as exc:
            raise IntegrityError(f"refusing to overwrite event record {event_path}") from exc
        return event_hash

    def add_rejection(self, record: dict[str, Any]) -> None:
        conn = self._require()
        conn.execute(
            """
            INSERT INTO rejections(rejection_id, run_id, unit_id, attempt_id, code, reason, payload_json, created_at_utc)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                record["rejection_id"],
                record["run_id"],
                record.get("unit_id"),
                record.get("attempt_id"),
                record["code"],
                record["reason"],
                json.dumps(record.get("payload") or {}, sort_keys=True),
                record.get("created_at_utc") or utc_now(),
            ),
        )
        self.append_event(
            record["run_id"],
            "rejection_recorded",
            {"rejection_id": record["rejection_id"], "code": record["code"], "unit_id": record.get("unit_id")},
        )

    def rejections_for(self, run_id: str) -> list[dict[str, Any]]:
        rows = (
            self._require()
            .execute("SELECT * FROM rejections WHERE run_id=? ORDER BY created_at_utc", (run_id,))
            .fetchall()
        )
        return [dict(r) for r in rows]

    def event_chain_ok(self, run_id: str) -> bool:
        prev = None
        for event in self.events_for(run_id):
            payload = json.loads(event["payload_json"])
            body = {
                "event_id": event["event_id"],
                "run_id": event["run_id"],
                "ts_utc": event["ts_utc"],
                "kind": event["kind"],
                "payload": payload,
                "prev_event_hash": event["prev_event_hash"],
            }
            expected = sha256_json(body)
            if event["prev_event_hash"] != prev:
                return False
            if event["event_hash"] != expected:
                return False
            prev = event["event_hash"]
        return True


class Transaction:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.execute("COMMIT")
        else:
            self.conn.execute("ROLLBACK")
        return False
