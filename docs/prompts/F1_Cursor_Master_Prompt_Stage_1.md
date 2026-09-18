# Cursor master prompt — F1 AI and quantum strategy research

Prepared for Kawin Rehan Perera. Based on F1_AI_Quantum_Research_Dossier_v3_1.pdf, dated 18 September 2026.

**How to use:** Open a new, separate folder named `f1-ai-quantum-strategy` in Cursor. Put this file and the v3.1 dossier PDF in that folder. In a new Agent chat, ask Cursor to read both files and execute this prompt. This prompt authorizes Stage 1 only. Its descriptions of later stages provide context, not permission to execute them.

---

## 1. Your assignment and the research objective

You are implementing an independent research project for a non-coder. Make routine engineering choices, write the code, run the permitted checks, and repair failures yourself. Do not return only a proposal or ask the user to write code. Complete the authorized stage and return the evidence requested below.

The research concerns deadline-constrained two-car pit strategy following safety-car or virtual-safety-car checkpoints. It combines a motorsport simulator, classical references, an evaluated learned policy, and quantum candidate generation. The aim is a useful, reproducible academic contribution with a credible path to Formula 1 relevance. It is not a predetermined demonstration of quantum superiority.

Read the entire attached **v3.1 dossier**, including its correction log, experimental counts, hardware schedules, implementation sequence and freeze record. Preserve it unchanged. Extract a searchable local text copy with page boundaries and record the original PDF SHA-256. Verify that all 33 pages were extracted; inspect formula and table extraction where needed. If the supplied version differs or extraction omits material, report the exact discrepancy. Never pretend to have read inaccessible pages.

The dossier is the scientific design reference. This prompt determines the narrower work authorized now. User instructions govern authorization. A technical contradiction requires a documented finding and a proposed correction, not silent alteration of the science or abandonment of unrelated setup work.

Use these evidence labels consistently: proposed, implemented, verified by a named check, simulated, physically measured, unsupported. A test fixture is not an experimental observation. Successful software setup does not establish scientific novelty, simulator validity or hardware readiness.

## 2. Scope authorized now

Complete **Stage 1: project isolation, environment, persistent instructions, schemas, local evidence ledger and bootstrap checks**. Creating the separate repository is authorized. You may install necessary free dependencies into a project-local environment, read public documentation, initialize Git, create a local commit with an already configured identity, and create an empty private GitHub repository under the authenticated user's personal account.

Do not push commits yet. Do not submit QPU jobs, connect to IBM for account inspection, run a research campaign, train research models, open held-out test outcomes, scrape timing data, subscribe to services, enable billing or provision cloud machines. No remote LLM/API dependency is needed. Cursor itself is the development assistant, not the runtime AI research contribution.

Do not enable scheduled tasks, GitHub Actions, automatic experiment execution, autonomous background campaigns or automatic publishing. Leave future scientific stages explicitly pending. Implement executable infrastructure now; do not fabricate working simulator, AI or circuit modules to make the tree look complete.

The previous research project is closed. Do not modify, import or claim its observations as new F1 results. No scanning through unrelated repositories or credentials is needed for this task.

## 3. Establish the project boundary and repository

Before writing, inspect the opened folder, resolved path, current Git root if any, remotes and working-tree status. The intended folder is `f1-ai-quantum-strategy`, separate from the old project. Allow the dossier and this prompt to be the only initial contents.

If the folder is inside an unrelated Git repository or contains unrelated project work, do not initialize over it, move its files, rewrite remotes, reset Git or create a nested repository. Explain the exact conflict and ask for a separate folder while preserving everything. Resolve symlinks before enforcing the project write boundary. Record the permitted root; future artifact writes must stay within it. Dependency downloads may use ordinary package caches, but no unrelated research files may be changed.

Initialize the new local repository on `main` if appropriate. If this exact project has already been initialized, resume idempotently after inspecting its state.

Use `f1-ai-quantum-strategy` as the proposed GitHub repository name. If GitHub CLI is present and authenticated, verify the active personal account using metadata without printing tokens. Create a new **private**, empty repository and connect it as `origin`, without `--push`, template files or automation. Check for a name collision first. Never adopt, delete or overwrite an existing remote project automatically. If ownership is ambiguous, defer the remote step and finish local work.

If GitHub CLI or authentication is unavailable, complete the local stage and give one short manual instruction: create an empty private repository with this name in the user's own GitHub account, with no initial README, license or gitignore, then supply its URL. Never ask the user to paste a token in chat. Do not report remote creation unless verified.

Do not invent commit identity. If a local commit cannot be made because identity is absent, report that fact; keep a content-addressed source snapshot for the bootstrap checks. Publishing and changing visibility will be later, separate actions.

## 4. Inspect and establish the local environment

Detect the actual OS, CPU architecture, Python installations, usable memory, free disk, Git and available package manager. Do not infer hardware architecture from a browser user agent. Record only environment details needed for reproducibility; omit credentials, serial numbers and unrelated personal paths.

Choose a currently supported Python version compatible with the intended scientific stack, based on official package documentation and available installation methods. Prefer an existing suitable interpreter. Use a project-local virtual environment; do not change system Python or install with administrator privileges. If no suitable interpreter exists, finish independent work and provide the minimum official installation step.

For Stage 1, keep dependencies small: a schema/validation approach, configuration parsing if needed, and a test runner. Standard-library SQLite, JSON, hashing and argparse are sufficient for the ledger and CLI. Add numerical libraries only if actually needed by this stage. Plan Qiskit, Aer, SciPy, a free solver and a small ML library for later; do not force a large quantum stack into setup solely to claim readiness.

Record exact resolved dependency versions and a reproducible installation command, with a lock file or fully pinned dependency file. Distinguish the dependency lock from a machine-specific environment inventory. Validate the installation in a fresh project-local environment, or state precisely why that check could not run. Installation/import success is the only package compatibility claim available now.

Set conservative local worker defaults after inspection. Do not launch stress benchmarks. There is no additional spending budget; a free account must never silently fall through to a paid account or paid service.

## 5. Make context survive a new Cursor conversation

Create a concise root `AGENTS.md` containing the active stage, authority of the dossier, project boundary, evidence rules, zero-spend limit, no-QPU default, run/resume semantics and separate GitHub publishing rule. Put detailed scientific requirements in referenced documents rather than duplicating the whole dossier in an always-loaded rule.

Create one short `.cursor/rules/00-project.mdc` with valid frontmatter and `alwaysApply: true`, pointing to `AGENTS.md`, the project status and the authoritative protocol documents. This is a small routing rule, not another divergent master specification. Do not use the legacy `.cursorrules` format.

Maintain `PROJECT_STATUS.md` after each implementation stage and run: completed work with evidence, active stage, blocking findings, protocol state, next authorized unit and exact files a future Agent must read. On a new conversation, read this state and inspect the ledger before running anything. Chat recollection alone is not authorization or evidence.

Record this master prompt unchanged in the project's documentation. When making changes to project instructions, preserve their rationale and never weaken execution gates merely to make a command pass.

## 6. Minimum repository deliverables

Use a straightforward Python package such as `src/f1q/`, with `pyproject.toml`, a reproducible dependency file, `tests/`, `configs/`, `docs/`, and a local evidence area. Avoid a dashboard, web app, microservices, paid orchestration framework or elaborate plugin system.

Create these documents with accurate status:

- `README.md`: purpose, independent-research status, current Stage 1 scope, supported local environment, exact setup/check commands, evidence locations and next stage. No performance badges or fabricated findings.
- `AGENTS.md`, `.cursor/rules/00-project.mdc` and `PROJECT_STATUS.md` as above.
- `docs/protocol/`: original dossier, extracted text, source hash, requirements traceability and a draft protocol record. State `frozen: false`.
- `docs/IMPLEMENTATION_PLAN.md`: the ten stages in dossier section 25, their exit evidence and prerequisites. Only Stage 1 is active.
- `docs/DECISIONS.md`: implementation choices, reasons and unresolved scientific choices, each with status and date.
- `docs/PROVENANCE.md`: each dependency/data source, source URL, version or commit when selected, license status and permitted use. Separate software licensing from data rights. Unselected dependencies remain unselected.
- `docs/CLAIMS.md`: proposed contributions, evidence needed and current unsupported status. Include the explicit limits below.
- `docs/DEVIATIONS.md`: no invented deviations; record genuine discrepancies and future protocol amendments here.
- `docs/STAGE_1_REPORT.md`: generated from actual checks and ledger evidence at completion.

Create a draft configuration with the documented project constraints and explicit unresolved fields. Represent unknown values as null with a reason; never invent a backend, quota verification time, calibrated threshold, model artifact, simulation distribution, protocol hash or completed gate. Hash the draft configuration as a draft; do not label that hash a frozen protocol.

Use `.gitignore` to exclude secrets, virtual environments, caches, mutable databases, restricted inputs and large generated outputs. Keep sanitized manifests, small bootstrap evidence and reproducibility instructions trackable. Do not ignore every result without a documented future release route. Bulk scientific evidence will need explicit versioned packaging later; Git LFS or paid artifact storage is not assumed.

Defer the project's release license until the release decision; preserve third-party notices and record this as pending. No license claim should imply permission to redistribute an unreviewed dataset.

## 7. Implement schemas and evidence integrity

Implement validated schemas for project configuration, authorized work unit, run manifest, unit attempt, artifact index, receipt and a minimal causal checkpoint interface. Keep schemas versioned and migrate deliberately rather than rewriting old evidence.

The checkpoint schema should capture identifiers and split, field size, race time/lap, regime, two-car decision state, inventories, action commitment cutoffs and provenance. Every observation must have a value, unit, source, availability time and known/inferred/assumed status. Use a clearly labeled fictional fixture to exercise validation. Do not implement the generator or claim simulation correctness yet. Future outcomes and evaluator-only randomness must not appear as solver inputs.

Separate identifiers for a scenario, a decision checkpoint, a policy repetition, a circuit/sample pool, a provider job, a work unit and an attempt. A `run` is an execution container, not automatically one independent scientific observation. Distinguish setup fixtures from training, tuning, calibration, test and shift records.

A run manifest must include a unique ID, stage, evidence kind, source snapshot/hash, Git commit if available, dirty-state indicator, dossier/configuration hashes, dependency lock hash, planned unit IDs, deterministic seed specification, authorization scope, start/end UTC, local monotonic duration, statuses and artifact paths/hashes. Prevent NaN/infinite scientific values and unsafe paths. Record absent provider fields as not applicable or null with a reason, not fake IDs.

Use transactional local storage for the mutable run index, with durable immutable raw records and manifests. Implement atomic artifact writes and SHA-256 verification. An append-only event history must preserve failures and subsequent attempts. Derived reports may be rebuilt; raw records must not be overwritten to change a conclusion. File hashes detect changes; do not claim they make a local filesystem tamper-proof.

Use an exclusive writer lock or equivalent transaction protection. Two simultaneous run commands must not execute the same unit twice. A crashed process may leave an unresolved intent; recovery must inspect evidence before selecting the next unit. Validate checksums before skipping completed work. Never silently recompute corrupted evidence under the original identifier.

Preserve the source snapshot used by a run: for a dirty or uncommitted tree, hash and retain the relevant source/configuration contents through a scoped manifest, excluding outputs, credentials and machine-specific noise. Do not claim the Git HEAD alone identifies uncommitted code.

## 8. Implement a usable local CLI and the eventual natural-language contract

Provide working, documented commands through `python -m f1q` or a similarly simple entry point:

- `doctor`: inspect environment, project boundary, input dossier, configuration and ledger integrity; no provider login or scientific execution.
- `status`: report active stage, draft/frozen status, completed/failed/pending units and next permitted work. Unknown is not ready.
- `run --plan bootstrap`: execute the explicitly labeled Stage 1 fixture plan and produce raw records plus a receipt.
- `resume --run-id ...`: recover an interrupted permitted run, retaining failed attempts and verifying already completed units.
- `receipt --run-id ...`: regenerate a machine-readable and human-readable receipt from evidence.

Choose and document one consistent command spelling; do not present commands that do not exist. Unsupported campaign or hardware modes must reject before any work or network access, with a useful explanation and a failing exit code. There must be no implemented provider submission path in Stage 1.

Natural-language rules for later Cursor use:

- **“do a run”** resolves exactly the next authorized unit in the recorded plan and executes it once, saving a receipt. During setup it cannot manufacture a scientific plan or start another stage. If no such unit exists, report that state without creating one.
- **“resume”** resolves the identified incomplete run. If several exist, show their IDs instead of guessing. Completed units remain completed.
- **“show status”** reads the actual ledger and integrity checks.
- **“push to GitHub”** is a separate scoped publication instruction: inspect changes, exclude secrets/restricted inputs, check remote ownership and push this project only. It does not authorize new runs, public visibility or rewriting history.

The bootstrap plan may be frozen as a software-check plan. That does not freeze the scientific protocol or authorize the later experiment matrix. Keep stage readiness, individual run status and scientific gates separate. A bootstrap completion must leave the research protocol in DRAFT, hardware disabled, and Stage 2 awaiting its implementation prompt.

## 9. Carry forward these scientific constraints accurately

Capture these in the traceability document with dossier section references and future acceptance checks. Do not implement their scientific components in Stage 1.

1. Generated fictional scenarios are the core. The proposed 20-car field is a model assumption. Historical timing data is an optional, separately justified extension; an open-source client license is not a license for its underlying data.
2. Model meaningful two-car mechanisms and causal information: SC/VSC, tyre/fuel effects, shared service, rejoin traffic and continuation. Double stacking is normally a delay cost, not an invented universal prohibition.
3. Enumerate legal action combinations on small cases. One-hot variables do not imply that every binary string is a legitimate plan. If the exact incumbent already minimizes the proxy, quantum search cannot improve that same objective.
4. Before the full test campaign, apply the scientific-value gate. An impossible superiority comparison cannot be rescued by more repetitions. Any alternative mechanism or boundary question needs explicit justification before freeze and QPU use.
5. Keep fitting, tuning, calibration, test and shift blocks separate. Base counts are 120/16/24/80 blocks, eight checkpoints each, plus 40 shift blocks. Test size may increase under the dossier's pre-exposure sizing rule up to 160 blocks; counts remain proposed until that process is complete. Setup fixtures belong to none of these splits.
6. Runtime AI must be an evaluated learned component with fixed, nearest-neighbour and random-donor comparisons where specified. Deterministic orchestration alone is not learned AI or proof of an agentic contribution.
7. C0 and C1 are the core circuit families. C2 is a conditional, separately registered local substudy. Include preparation, routing and ancillary resources; compare full circuit/parameter packages fairly. Do not describe established QAOA, XY or guarded exchanges as inventions.
8. Preserve the corrected QUBO feasibility assumptions, sufficient penalty bound, objective centering and normalization. Check direct action costs independently against encoded energies. Do not assume arbitrary weighted cost angles have a 2π period.
9. Effective decision deadlines include pit-entry expiry, communication margin, causal state advance and commitment-time legality. Locally measured inference, compilation, queue and communication time cannot be omitted from an end-to-end claim. Use monotonic clocks for local durations.
10. H1 is conditionally confirmatory; H2/H3 and hardware mechanisms are exploratory/descriptive as specified. Preserve paired blocks and independent evaluation banks. Do not count shots, seeds or checkpoints as independent races. Avoid adding naive nested Monte Carlo resampling to the primary block bootstrap.
11. The reported QPU balance is **540 seconds, unverified**. Protected reserve is **120 seconds**; campaign ceiling is `min(420, max(0, verified_available_seconds - 120))`. This formula is a future cap, not current execution permission. Before hardware, verify actual free access, account balance, supported caps and the applicable frozen schedule.
12. The dossier's primary hardware schedule totals 50 jobs, 88 pools, 88,064 shots and 402 seconds of planned caps; its alternative totals 38 jobs, 64 pools, 32,768 shots and 414 seconds. They are mutually exclusive pilot-selected schedules, not cumulative allocations. Individual cap feasibility matters. Defer all dispatch implementation to its later stage.
13. Future job execution requires intent recovery, reservations, actual usage reconciliation and raw-evidence durability. Unknown usage stays reserved; no blind resubmission after a timeout. Measured zero usage must never be confused with an unqueried account.
14. No absolute novelty, guaranteed future quantum advantage, team adoption, actual F1 performance gain or publication acceptance is established. Claims must follow evidence. Record AI assistance honestly.

## 10. Required Stage 1 checks

Implement meaningful checks for the infrastructure risks below; do not manufacture a large test count or test only that your implementation calls itself.

1. Configuration/schema rejection: invalid types, negative budgets, unsafe paths, unsupported modes and future-only state in decision input.
2. Boundary protection: reject path traversal and symlink escape using a temporary fixture; do not modify the old project to test this.
3. Reproducible fixture payloads: same content/seed produces the same substantive payload and hash, while timestamps and unique execution IDs may differ.
4. Interruption and resume: a deliberately interrupted multi-unit bootstrap run preserves its completed unit, records the interrupted attempt and completes only the remaining permitted work on resume.
5. Concurrent dispatch: two competing commands cannot both claim the same fixture unit. Use a real contention check, not just a mocked success return.
6. Evidence integrity: checksum mismatch is reported and does not get silently overwritten. Receipt counts come from recorded events and artifact status.
7. Authorization: missing authorization, changed plan/config/source fingerprint or an unsupported hardware mode blocks dispatch. The implementation has no IBM submission path.
8. Install and CLI smoke checks: fresh-environment install if feasible, `doctor`, `status`, bootstrap execution, resume and receipt reconstruction actually run.

Keep fixtures tiny and bounded. Clearly mark deliberately injected failures as test events and retain their evidence. Do not place fixture results in a scientific results table. Record actual commands, exit codes and outcome summaries, excluding secrets.

Review the final scoped diff. Where available, scan tracked/staged files for accidental secrets without printing any matched secret. Make a local setup commit using existing Git identity after checks pass; no automatic push. Update status to reflect the commit without implying that it was the source of earlier uncommitted checks.

## 11. Stop point and return format

Stop when Stage 1 is complete and its evidence is saved. Do not advance into scenario generation, simulator implementation or experiments because setup succeeded. Do not ask for routine decisions already settled here. If an external prerequisite blocks part of setup, finish independent authorized work and state the smallest necessary user action.

Return a concise report with these fields, based on actual evidence:

```text
STAGE_1_STATUS: COMPLETE | PARTIAL | BLOCKED
PROJECT_ROOT:
DOSSIER_VERSION_AND_SHA256:
LOCAL_REPO_AND_BRANCH:
GITHUB_REPO: verified URL and visibility, or not created with reason
PUSH_PERFORMED: false
PYTHON_AND_ENVIRONMENT:
DEPENDENCY_LOCK:
IMPLEMENTED_COMMANDS:
CHECKS: passed/failed/not run, with evidence paths
BOOTSTRAP_RUN_ID:
RECEIPT_PATH:
SOURCE_SNAPSHOT_AND_COMMIT:
SCIENTIFIC_PROTOCOL: DRAFT
RESEARCH_EXPERIMENTS_EXECUTED: 0
NEW_PHYSICAL_QPU_JOBS_SUBMITTED: 0
QPU_USAGE_FROM_THIS_STAGE: 0 seconds; account balance not queried
HARDWARE_EXECUTION_ENABLED: false
BLOCKERS_OR_DEVIATIONS:
NEXT_STAGE: 2 — scenario generator and causal checkpoint schema
```

Use `not run` and explanations where accurate. Do not output a success-shaped report filled with expected values. Include a short file tree, the report path and the next smallest user action if any. The user will bring your response back to ChatGPT for the next scoped implementation prompt.

Begin now by inspecting the workspace and reading the dossier, then carry Stage 1 through to its actual stop point.

---

## Tooling references

These support the setup mechanisms only; the dossier supplies the research specification. Recheck relevant interfaces if the installed tools differ.

- [Cursor project rules and AGENTS.md](https://cursor.com/docs/rules): persistent project instructions, `.mdc` frontmatter and `alwaysApply`.
- [GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create): private repositories, connecting a local source, and the separate `--push` option.
