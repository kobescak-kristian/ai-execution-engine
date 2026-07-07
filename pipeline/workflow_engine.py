from datetime import datetime
from typing import Optional

from pipeline.normalizer import normalize
from pipeline.router import route_lead
from database import db
from models.schemas import SourceType, NormalizedLead
from utils.logger import get_logger

logger = get_logger("workflow_engine")


class DuplicateConflictError(Exception):
    """Raised when a source_ref repeats but the incoming data disagrees with
    what's already stored — the existing lead is never overwritten."""

    def __init__(self, existing_lead_id: int, message: str):
        super().__init__(message)
        self.existing_lead_id = existing_lead_id


# Fields compared to decide "same data" vs "conflicting data" for a repeated
# source_ref. Compared on the NORMALIZED lead (post source_ref derivation),
# not raw_data — an API web-form ingest only carries a form_id, not the full
# stored shape, so raw payloads across sources aren't directly comparable.
_DEDUP_COMPARE_FIELDS = [
    "full_name", "email", "company", "phone", "message_snippet",
    "company_size", "industry", "lead_score",
]


def _matches_existing(normalized: NormalizedLead, existing: dict) -> bool:
    return all(
        getattr(normalized, field) == existing.get(field)
        for field in _DEDUP_COMPARE_FIELDS
    )


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


# ─── Ingest Pipeline ──────────────────────────────────────────────────────────

def ingest_lead(source_type: str, raw_data: dict) -> dict:
    """
    Full ingest pipeline:
    1. Normalize raw input into unified lead schema
    2. Check for a duplicate/conflicting source_ref
    3. Score and route to appropriate queue/stage
    4. Persist lead record + initial transition
    5. Return the stored lead record, tagged with an ingest status

    Returned dict includes "status": "ingested" | "duplicate".
    Raises DuplicateConflictError if the source_ref repeats with different data.
    """

    # Step 1: Normalize
    normalized = normalize(source_type, raw_data)

    # Step 2: Check for duplicate/conflict by source_ref
    existing = db.get_lead_by_source_ref(normalized.source_ref)
    if existing:
        if _matches_existing(normalized, existing):
            db.increment_duplicate_count(existing["id"])
            logger.info(
                f"Duplicate source_ref {normalized.source_ref} (lead_id={existing['id']}), "
                f"same data, skipping ingest"
            )
            return {"status": "duplicate", **db.get_lead_by_id(existing["id"])}
        else:
            logger.warning(
                f"Duplicate source_ref {normalized.source_ref} (lead_id={existing['id']}) "
                f"has conflicting data, rejecting ingest"
            )
            raise DuplicateConflictError(
                existing["id"],
                f"source_ref {normalized.source_ref} already exists as lead "
                f"{existing['id']} with different data"
            )

    # Step 3: Route
    routing = route_lead(normalized)

    # Step 4: Build DB record
    now = _now_iso()
    received_at_iso = normalized.received_at.strftime("%Y-%m-%dT%H:%M:%S")
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
        "created_at": received_at_iso,
        # "Last updated" starts equal to the lead's actual arrival time, not
        # the wall-clock moment this script happens to run -- otherwise a
        # lead's freshness is measured from an artifact of when the demo was
        # executed rather than when it was truly last touched, and time-based
        # checks (stuck-in-'new') could never fire on a freshly seeded lead
        # even when its real-world submission date is well past the threshold.
        "updated_at": received_at_iso,
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
        f"stage={routing.initial_stage.value} | queue={routing.assigned_queue}"
    )
    return {"status": "ingested", **stored}
