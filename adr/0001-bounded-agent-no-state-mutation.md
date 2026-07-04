# ADR 0001: Bounded Agent — Recommendation-Only, No State Mutation

## Status
Accepted (implemented)

## Date: 2026-07-04

## Context
The workflow engine (ingest → normalize → score → route → stage lifecycle) must run
deterministically and be auditable. An LLM-based agent was added to surface improvement
recommendations from computed workflow metrics. If the agent could write directly to CRM
state (e.g. change a lead's stage or queue), a bad model output would become a bad state
change with no deterministic path back.

## Decision
`pipeline/agent_analyzer.py::run_agent_analysis()` reads only computed metrics via
`compute_metrics()` (`pipeline/metrics_evaluator.py`) and returns structured
`AgentRecommendation` objects (issue, recommendation, expected_effect, trade_off, priority).
It calls no function in `state_manager.py`, `router.py`, or `database/db.py` that mutates
lead state. If `OPENAI_API_KEY` is unset, or the OpenAI call fails, the code falls back to
`_deterministic_recommendations()`, a pure function over metrics with no external call.
Scoring (`pipeline/router.py::route_lead`) and stage transitions (`VALID_TRANSITIONS`) are
deterministic and run independently of the agent.

## Consequences
- Every state change traces to a deterministic rule, never a model output.
- Recommendations require a human to act on them — the agent cannot self-execute its
  own suggestions.
- The system is fully functional (minus AI insight) with no API key configured.
- Trade-off: recommendations aren't auto-applied, so their value depends on a human
  loop; accepted as the cost of auditability.
