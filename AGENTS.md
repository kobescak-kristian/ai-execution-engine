# AGENTS.md — ai-execution-engine

Tool-neutral context router for coding agents working in this repository.
It points to where repository truth lives. It is not evidence of how the
system behaves or what state the project is in: cite the source it routes
to, never this file.

## Repository purpose

Stateful CRM workflow execution engine. Leads from several source types are
ingested, normalised into one schema, scored and routed deterministically to
a queue and lifecycle stage, persisted with their transition history, and
moved through the lifecycle by explicit API triggers or automated time-based
checks. Workflow metrics are computed from stored state. A bounded agent
layer reads those metrics and recommends improvements; it never mutates CRM
or workflow state. Human overview: `README.md`.

## Authority and conflict handling

| Question | Canonical source |
|---|---|
| What the system is and claims publicly | `README.md` |
| Material design decisions and their rationale | `adr/` |
| Documented version history | `README.md` Version Log |
| What the implementation actually does | affected source, tests and configuration inspected together |

When sources disagree:

- An adopted ADR governs the decision it records.
- Documentation states intent; implementation, tests and configuration state
  actual behaviour. Surface any disagreement between them as a finding;
  never reconcile it silently.
- If the requested task materially depends on an unresolved conflict, stop
  and ask the owner.

## Task routing

These are starting points, not exhaustive reading lists.

| Task class | Start here |
|---|---|
| Understand or explain the system | `README.md` |
| Ingest, normalisation, scoring, duplicate and conflict handling | `pipeline/normalizer.py`, `pipeline/workflow_engine.py`, `database/db.py`, `models/schemas.py` |
| Routing, lifecycle transitions, automated checks | `pipeline/router.py`, `pipeline/state_manager.py`, `config/settings.py` |
| Workflow metrics and the bounded agent | `pipeline/metrics_evaluator.py`, `pipeline/agent_analyzer.py`, `adr/0001-bounded-agent-no-state-mutation.md` |
| HTTP API | `api.py`, then the pipeline and persistence routes above |
| Demo run and local execution | `main.py`, `data/` |
| Persistence and transition history | `database/db.py` |
| Material design decision | `adr/` |
| Documentation, README or ADR work | the affected artifact; `.githooks/validate_artifacts.py` for enforced structure |
| CI, hooks, publishing | `.github/workflows/ci.yml`, `.githooks/`, `.publicgate-allow` |

## Always-on constraints

- Scoring, routing, lifecycle transitions and automated checks are
  deterministic rules in source and configuration. The agent layer is
  recommendation-only: it reads computed metrics and must not call, or be
  given, any path that changes lead stage, queue or other stored state.
  Do not add model-driven state mutation as a shortcut. See `adr/0001`.
- State changes stay auditable. Ingest records the initial routing
  transition; every later stage change goes through the transition path in
  `pipeline/state_manager.py`, which checks it against the allowed
  transitions and persists a transition record. Do not add writes that
  change a lead's stage or queue without that record.
- A repeated `source_ref` never silently overwrites or merges data: a
  same-data repeat follows the existing duplicate path (flagged on the
  stored lead, no new row), and a conflicting repeat is rejected with the
  existing lead left untouched.
- Without a usable model credential, and on any authentication, network or
  model failure, analysis falls back explicitly to the deterministic
  recommendation path and reports that source. Keep this fallback explicit;
  never let a failure become state mutation or silent model-driven
  degradation.
- Development and verification use the keyless deterministic path. Do not
  run paid or real-model execution without explicit owner authorization.
- Committed gates, frozen test assertions and published results are
  evidence. Do not adjust thresholds or expected values after a run, or
  rewrite them to make a check green.
- No secrets or machine-local absolute paths in tracked files.
  Machine-specific values go to the gitignored `.env`.
- Git history is evidence and commits are hash-pinned externally. Never
  rewrite repository history.
- Trigger-gated artifacts such as `CHANGELOG.md`, `RUNBOOK.md` and
  `SYSTEM_WALKTHROUGH.md` are not created without a decision record citing
  the trigger. ADRs are written only for genuine material decisions; there
  is no hard maximum. The version log lives in `README.md`.
- `AGENTS.md` is an instruction surface, not a security boundary. Hooks, CI
  and tests remain the enforcement.

## Verification

Keyless and bounded; no model or API calls. Requires
`pip install -r requirements.txt` and `pytest`.

```bash
python .githooks/validate_artifacts.py .
pytest tests/ -v
```

`tests/test_ci.py` runs the demo with an empty model key and asserts only
time-invariant output lines. The demo database it writes is gitignored.
