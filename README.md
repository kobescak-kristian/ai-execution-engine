# CRM Workflow Automation System + Controlled Agent

A stateful CRM workflow engine that ingests leads from multiple sources, normalises them into a unified schema, routes them through a deterministic lifecycle, and exposes a bounded agent layer for workflow analysis and improvement recommendations.

---

## Problem Solved

CRM data arrives from multiple channels — web forms, email, ad platforms — each with different structure and signal quality. Most systems handle intake inconsistently, apply routing logic that cannot be audited, and have no mechanism for identifying where leads stall or why.

This project addresses three specific gaps:

1. **Fragmented intake** — raw inputs from three source types are normalised into one schema before any workflow logic runs
2. **Untracked state** — every stage transition is persisted with a trigger and timestamp, making the full lead journey queryable
3. **No feedback loop** — workflow performance metrics feed a controlled agent layer that identifies bottlenecks and recommends rule changes, without modifying system logic directly

---

## How It Works

```
Raw Input (web_form | email | ad_platform)
        ↓
   Normalization Layer
   Score computation, field mapping, source_ref deduplication
        ↓
   Router
   Deterministic score-based queue and stage assignment
        ↓
   Lead Record Created (SQLite)
   Stage: new | qualified | manual_review
   Queue: inbound_queue | smb_sales | enterprise_sales | manual_review_queue
        ↓
   Lifecycle Progression
   Manual triggers via API or automated time-based checks
   Stages: new → qualified → assigned → contacted → proposal → won/lost
        ↓
   Metrics Evaluator
   Stage breakdown, conversion rates, stuck/aging leads, queue workload
        ↓
   Agent Analyzer (OpenAI → deterministic fallback)
   Reads metrics only. Outputs structured recommendations.
   Does not modify any CRM state.
```

---

## Tools

| Layer | Technology |
|---|---|
| API | FastAPI |
| Data validation | Pydantic v2 |
| Persistence | SQLite (stdlib) |
| Agent | OpenAI `gpt-4o-mini` (deterministic fallback if no key) |
| Configuration | python-dotenv |
| Runtime | Python 3.10+ |

---

## Outcome

- 75 leads ingested across 3 source types in a single demo run
- Zero normalisation failures across web form, email, and ad platform inputs
- Full stage history stored and queryable per lead
- Automated checks identify overdue follow-ups, stuck leads, and stale new entries
- Agent layer produces 3–5 structured recommendations with expected effect and trade-off per run
- API exposes all workflow state via 8 endpoints, no authentication required for local use

---

## Known Limitations

- No authentication layer on the API — not production-ready without adding middleware
- SQLite does not support concurrent writes at high throughput; replace with PostgreSQL for production scale
- Agent analysis is stateless per call — no memory of prior recommendations or trend tracking across runs
- Routing thresholds are configurable but not dynamically adjusted; agent recommendations require manual implementation

---

## Status

Complete. Demo-ready. All components functional.

---

## Files

```
crm_workflow_system/
├── api.py                        FastAPI app and route definitions
├── main.py                       Local demo runner and seed entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── pipeline/
│   ├── normalizer.py             Source-specific field mapping and score computation
│   ├── router.py                 Deterministic queue and stage assignment
│   ├── workflow_engine.py        Ingest orchestration and bulk processing
│   ├── state_manager.py          Stage transitions and automated checks
│   ├── metrics_evaluator.py      Workflow KPI computation
│   └── agent_analyzer.py         OpenAI agent with deterministic fallback
├── models/
│   └── schemas.py                Pydantic schemas for all data types
├── database/
│   └── db.py                     SQLite connection, schema init, read/write queries
├── config/
│   └── settings.py               Environment-based configuration
├── utils/
│   └── logger.py                 Shared logger
└── data/
    ├── raw_inputs.json           75 pre-generated leads across 3 source types
    └── generate_dataset.py       Dataset generation script
```

---

## Metadata

| Field | Value |
|---|---|
| Project | P4 — CRM Workflow Automation System + Controlled Agent |
| Stack | Python · FastAPI · SQLite · OpenAI · Pydantic |
| Scope | Multi-source intake, lifecycle management, agent recommendations |
| Status | Complete |
| Version | 1.0 |

---

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add OPENAI_API_KEY if you want AI-powered recommendations

# 3. Run the demo
python main.py --reset

# 4. Start the API server
uvicorn api:app --reload

# 5. Example requests
curl http://localhost:8000/health
curl http://localhost:8000/stats
curl http://localhost:8000/agent/recommendations
curl http://localhost:8000/leads/1
```
