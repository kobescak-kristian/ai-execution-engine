# STATE — ai-execution-engine

**Classification:** PROJECT · T0 (stateful CRM workflow execution engine with a bounded, recommendation-only agent layer; `domains/github-ops/CONVENTIONS.md` PROJECT/SYSTEM/EXPERIMENT taxonomy).

**RECONSTRUCTED** (GOVERNANCE.md Build-repo STATE rule, clause 7): derived from git history and the README Version Log at scaffold time (2026-09-19, Q-72(f)), not written contemporaneously. Reconstructed entries are retrospective evidence, not contemporaneous record — the commit that adds this file begins the contemporaneous record going forward.

## Current state

**Status: Complete — v1.0** (README). One ADR: `adr/0001-bounded-agent-no-state-mutation.md` (the agent layer recommends only, never mutates CRM/workflow state).

## Version Log (from README, verbatim)

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-06-17 | Initial commit — AI execution engine (workflow automation pipeline) |
| v1.0 | 2026-06-17 | Docs: add case-study README + architecture diagram |
| v1.0 | 2026-06-18 | Docs: consistency pass — canonical System Context order + AI engine names |
| v1.0 | 2026-06-18 | Docs: standardize naming — fix Impact Engine URL, dash bullets in System Context |
| v1.0 | 2026-06-20 | Fix execution engine audit findings — release |
| v1.0 | 2026-07-04 | Adopt ARTIFACT_STANDARD Tier 0 — CLAUDE.md, pre-push validation, README restructure, first ADR |
| v1.0 | 2026-07-07 | Remediation release — cp1252 console safety, placeholder-key no-network fallback, duplicate/conflict enforcement, manual_review_queue reachability + stage/queue desync fixes, deterministic automated checks, API robustness, full docs re-derivation |
| v1.0 | 2026-07-27 | Docs: Outcome restricted to time-invariant run-figures |

## Build history since the Version Log's last entry (from `git log --reverse`)

- **2026-07-27** (`b5137cd`) — Publish-gate coverage canary added (Q-60 push unblock).
- **2026-07-28** (`90e6192`, `10c399e`) — Allowlist migrated to entry-exact format; adjudicated-secrets entry added (owner ruling 2026-07-27).
- **2026-08-04** (`c01175a`, `0da7e96`) — Apache-2.0 license added; Q-35 hook rollout.
- **2026-09-15** (`afba682`) — Canonical AGENTS.md router adopted (Q-93).
- **2026-09-19** (this commit) — Q-72(f): STATE.md added (this file); validator gains a STATE.md-existence check, the obsolete 5-record decision cap is removed, and the six-name BANNED_WITHOUT_TRIGGER list is propagated (live-file precondition checked, clear).

## Open loops

None on disk.
