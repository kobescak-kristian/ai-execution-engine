from datetime import datetime
from typing import Optional

from pipeline.normalizer import normalize
from pipeline.router import route_lead
from database import db
from models.schemas import SourceType
from utils.logger import get_logger

logger = get_logger("workflow_engine")


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


# ─── Ingest Pipeline ──────────────────────────────────────────────────────────

def ingest_lead(source_type: str, raw_data: dict) -> dict:
    """
    Full ingest pipeline:
    1. Normalize raw input into unified lead schema
    2. Score and route to appropriate queue/stage
    3. Persist lead record + initial transition
    4. Return stored lead record
    """

    # Step 1: Normalize
    normalized = normalize(source_type, raw_data)

    # Step 2: Check for duplicate by source_ref
    existing = db.get_lead_by_source_ref(normalized.source_ref)
    if existing:
        logger.info(f"Duplicate source_ref {normalized.source_ref}, skipping ingest")
        return existing

    # Step 3: Route
    routing = route_lead(normalized)

    # Step 4: Build DB record
    now = _now_iso()
    lead_record = {
        "source_type": normalized.source_type.value,
        "source_ref": normalized.source_ref,
        "full_name": normalized.full_name,
        "email": normalized.email,
        "company": normalized.company,
        "phone": normalized.phone,
        "message_snippet": normalized.message_snippet,
        "company_size": normalized.company_size,
        "industry": normalized.industry,
        "lead_score": normalized.lead_score,
        "current_stage": routing.initial_stage,
        "assigned_queue": routing.assigned_queue,
        "owner_notes": routing.reason,
        "created_at": normalized.received_at.strftime("%Y-%m-%dT%H:%M:%S"),
        "updated_at": now,
        "last_contacted_at": None,
        "outcome": None,
    }

    # Step 5: Persist lead
    lead_id = db.insert_lead(lead_record)

    # Step 6: Record initial transition
    db.insert_transition({
        "lead_id": lead_id,
        "from_stage": "ingested",
        "to_stage": routing.initial_stage,
        "trigger": "ingest_routing",
        "transitioned_at": now,
        "notes": routing.reason,
    })

    stored = db.get_lead_by_id(lead_id)
    logger.info(
        f"Lead ingested: id={lead_id} | name={normalized.full_name} | "
        f"stage={routing.initial_stage} | queue={routing.assigned_queue}"
    )
    return stored


# ─── Bulk Ingest ──────────────────────────────────────────────────────────────

def bulk_ingest(leads: list) -> dict:
    """
    Ingest a list of raw lead dicts (each with 'source_type' and 'raw_data').
    Returns summary of ingested, skipped, failed.
    """
    results = {"ingested": 0, "skipped": 0, "failed": 0, "errors": []}

    for entry in leads:
        try:
            normalized = normalize(entry["source_type"], entry["raw_data"])
            is_duplicate = bool(db.get_lead_by_source_ref(normalized.source_ref))
            ingest_lead(entry["source_type"], entry["raw_data"])
            if is_duplicate:
                results["skipped"] += 1
            else:
                results["ingested"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))
            logger.error(f"Ingest failed for entry: {e}")

    logger.info(
        f"Bulk ingest complete: {results['ingested']} ingested, "
        f"{results['skipped']} skipped, {results['failed']} failed"
    )
    return results
