from datetime import datetime
from typing import Optional

from database import db
from pipeline.router import is_valid_transition, get_valid_next_stages
from config.settings import (
    QUEUE_REENGAGEMENT,
    FOLLOW_UP_THRESHOLD_DAYS,
    STUCK_LEAD_THRESHOLD_DAYS,
)
from utils.logger import get_logger

logger = get_logger("state_manager")


class TransitionError(Exception):
    pass


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


# ─── State Transition ─────────────────────────────────────────────────────────

def transition_lead(
    lead_id: int,
    to_stage: str,
    trigger: str,
    notes: Optional[str] = None,
    assigned_queue: Optional[str] = None,
    outcome: Optional[str] = None,
) -> dict:
    lead = db.get_lead_by_id(lead_id)
    if not lead:
        raise TransitionError(f"Lead {lead_id} not found")

    from_stage = lead["current_stage"]

    if from_stage == to_stage:
        logger.info(f"Lead {lead_id} already in stage '{to_stage}', skipping")
        return lead

    if not is_valid_transition(from_stage, to_stage):
        valid = get_valid_next_stages(from_stage)
        raise TransitionError(
            f"Invalid transition: {from_stage} → {to_stage}. "
            f"Valid next stages: {valid}"
        )

    now = _now_iso()
    last_contacted_at = now if to_stage == "contacted" else None

    db.update_lead_stage(
        lead_id=lead_id,
        new_stage=to_stage,
        updated_at=now,
        assigned_queue=assigned_queue,
        last_contacted_at=last_contacted_at,
        outcome=outcome,
        owner_notes=notes
    )

    db.insert_transition({
        "lead_id": lead_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "trigger": trigger,
        "transitioned_at": now,
        "notes": notes
    })

    logger.info(f"Lead {lead_id}: {from_stage} → {to_stage} (trigger={trigger})")
    return db.get_lead_by_id(lead_id)


# ─── Automated Workflow Checks ────────────────────────────────────────────────

def run_automated_checks(
    follow_up_days: int = FOLLOW_UP_THRESHOLD_DAYS,
    stuck_days: int = STUCK_LEAD_THRESHOLD_DAYS,
) -> dict:
    """
    Scans all active leads and applies time-based automation rules:
    - No contact after X days in 'assigned' → escalate to manual_review
    - No reply after X days in 'contacted' → move to reengagement queue
    - Leads stuck in 'new' too long → flag to manual_review
    """
    from datetime import timedelta

    now = datetime.utcnow()
    follow_up_cutoff = (now - timedelta(days=follow_up_days)).strftime("%Y-%m-%dT%H:%M:%S")
    stuck_cutoff = (now - timedelta(days=stuck_days)).strftime("%Y-%m-%dT%H:%M:%S")

    results = {
        "follow_up_triggered": [],
        "stuck_escalated": [],
        "reengagement_queued": [],
    }

    # Assigned leads not contacted in time
    assigned_stale = db.get_leads_updated_before(follow_up_cutoff, ["assigned"])
    for lead in assigned_stale:
        try:
            transition_lead(
                lead_id=lead["id"],
                to_stage="manual_review",
                trigger="automated_follow_up_overdue",
                notes=f"No contact recorded after {follow_up_days} days in assigned stage",
            )
            results["follow_up_triggered"].append(lead["id"])
        except Exception as e:
            logger.warning(f"Could not auto-escalate lead {lead['id']}: {e}")

    # Contacted leads with no progression after stuck threshold
    contacted_stale = db.get_leads_updated_before(stuck_cutoff, ["contacted"])
    for lead in contacted_stale:
        try:
            transition_lead(
                lead_id=lead["id"],
                to_stage="manual_review",
                trigger="automated_no_reply_stuck",
                notes=f"No progression after {stuck_days} days in contacted stage",
                assigned_queue=QUEUE_REENGAGEMENT
            )
            results["reengagement_queued"].append(lead["id"])
        except Exception as e:
            logger.warning(f"Could not requeue lead {lead['id']}: {e}")

    # New leads stuck too long
    new_stale = db.get_leads_updated_before(stuck_cutoff, ["new"])
    for lead in new_stale:
        try:
            transition_lead(
                lead_id=lead["id"],
                to_stage="manual_review",
                trigger="automated_new_lead_stuck",
                notes=f"Lead remained in 'new' for {stuck_days}+ days without qualification",
            )
            results["stuck_escalated"].append(lead["id"])
        except Exception as e:
            logger.warning(f"Could not escalate stuck new lead {lead['id']}: {e}")

    total = sum(len(v) for v in results.values())
    logger.info(f"Automated checks complete: {total} leads updated")
    return results
