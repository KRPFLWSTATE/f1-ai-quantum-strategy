# Local evidence

- `evidence/var/` holds the mutable SQLite ledger and lock files. It is gitignored.
- `evidence/bootstrap/receipts/` holds regenerated receipts (JSON and Markdown).
- `evidence/bootstrap/snapshots/` holds source snapshots used by runs (required when the tree is dirty).
- `evidence/bootstrap/artifacts/` holds tiny setup-fixture payloads. These are **not** scientific observations.
- `evidence/bootstrap/checks/` holds command transcripts from Stage 1 verification.

Bulk scientific evidence will need versioned packaging later. Git LFS and paid artifact storage are not assumed.
