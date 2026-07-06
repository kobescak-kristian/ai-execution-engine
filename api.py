import sys

# Windows consoles often default to a legacy codepage (e.g. cp1252) that cannot
# encode arbitrary Unicode lead data (e.g. names like "Kovač"). Backslash-escape
# unencodable characters when rendering to the console instead of crashing;
# this affects console output only, never what gets stored in the database.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.stderr.reconfigure(errors="backslashreplace")

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from datetime import datetime

from database import db
from pipeline.workflow_engine import ingest_lead
from pipeline.state_manager import transition_lead, run_automated_checks, TransitionError
from pipeline.metrics_evaluator import compute_metrics
from pipeline.agent_analyzer import run_agent_analysis
from pipeline.router import get_valid_next_stages
from models.schemas import IngestRequest, ProgressRequest
from utils.logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="CRM Workflow Automation System",
    description=(
        "A stateful CRM workflow engine with deterministic routing, "
        "lifecycle stage management, and a bounded agent recommendation layer."
    ),
    version="1.0.0",
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "crm-workflow-system"
    }


# ─── Ingest ───────────────────────────────────────────────────────────────────

@app.post("/ingest", tags=["Leads"])
def ingest(request: IngestRequest):
    """
    Accept a raw lead from any supported source type and run it through
    the full normalization → scoring → routing → persistence pipeline.
    """
    try:
        lead = ingest_lead(request.source_type.value, request.raw_data)
        return {
            "status": "ingested",
            "lead_id": lead["id"],
            "current_stage": lead["current_stage"],
            "assigned_queue": lead["assigned_queue"],
            "lead_score": lead["lead_score"],
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")


# ─── Leads ────────────────────────────────────────────────────────────────────

@app.get("/leads", tags=["Leads"])
def list_leads(
    stage: Optional[str] = Query(None, description="Filter by lifecycle stage"),
    queue: Optional[str] = Query(None, description="Filter by assigned queue")
):
    """
    Return all leads, optionally filtered by stage or queue.
    """
    leads = db.get_all_leads(stage=stage, queue=queue)
    return {
        "total": len(leads),
        "filters": {"stage": stage, "queue": queue},
        "leads": leads
    }


@app.get("/leads/{lead_id}", tags=["Leads"])
def get_lead(lead_id: int):
    """
    Return a single lead record and its full stage transition history.
    """
    lead = db.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")

    transitions = db.get_transitions_for_lead(lead_id)
    valid_next = get_valid_next_stages(lead["current_stage"])

    return {
        "lead": lead,
        "transition_history": transitions,
        "valid_next_stages": valid_next,
    }


# ─── Stage Progression ────────────────────────────────────────────────────────

@app.post("/progress", tags=["Leads"])
def progress_lead(request: ProgressRequest):
    """
    Manually advance a lead to a new stage.
    Trigger describes what caused this transition (e.g. 'positive_reply', 'proposal_sent').
    """
    try:
        updated = transition_lead(
            lead_id=request.lead_id,
            to_stage=request.trigger.split("→")[-1].strip() if "→" in request.trigger else _infer_stage(request),
            trigger=request.trigger,
            notes=request.notes,
        )
        return {
            "status": "updated",
            "lead_id": updated["id"],
            "current_stage": updated["current_stage"],
            "updated_at": updated["updated_at"],
        }
    except TransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Progress error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _infer_stage(request: ProgressRequest) -> str:
    # Convenience: if the trigger is a plain stage name, use it directly
    from models.schemas import LeadStage
    try:
        LeadStage(request.trigger)
        return request.trigger
    except ValueError:
        raise TransitionError(
            f"Cannot infer target stage from trigger '{request.trigger}'. "
            "Use a valid stage name or 'from_stage → to_stage' format."
        )


@app.post("/progress/stage", tags=["Leads"])
def progress_to_stage(lead_id: int, to_stage: str, trigger: str, notes: Optional[str] = None):
    """
    Explicit stage update with separate to_stage parameter.
    """
    lead = db.get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    previous_stage = lead["current_stage"]
    try:
        updated = transition_lead(
            lead_id=lead_id,
            to_stage=to_stage,
            trigger=trigger,
            notes=notes,
        )
        return {
            "status": "updated",
            "lead_id": updated["id"],
            "previous_stage": previous_stage,
            "current_stage": updated["current_stage"],
        }
    except TransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Automated Checks ─────────────────────────────────────────────────────────

@app.post("/workflow/run-checks", tags=["Workflow"])
def run_workflow_checks():
    """
    Trigger automated time-based workflow rules:
    escalate overdue assigned leads, requeue stuck contacts, flag stale new leads.
    """
    result = run_automated_checks()
    return {
        "status": "checks_complete",
        "result": result
    }


# ─── Stats ────────────────────────────────────────────────────────────────────

@app.get("/stats", tags=["Analytics"])
def get_stats():
    """
    Return computed workflow metrics: stage breakdown, conversion rates,
    win rate, manual review volume, stuck/aging leads, queue workload.
    """
    metrics = compute_metrics()
    return metrics.model_dump()


# ─── Agent ────────────────────────────────────────────────────────────────────

@app.get("/agent/recommendations", tags=["Agent"])
def get_recommendations():
    """
    Run the agent analysis layer against current workflow metrics.
    Returns structured recommendations with issue, action, expected effect, and trade-off.
    Agent is recommendation-only — it does not modify any CRM state.
    """
    result = run_agent_analysis()
    return result.model_dump()
