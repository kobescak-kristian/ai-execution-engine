from models.schemas import NormalizedLead, LeadStage, QueueName
from config.settings import (
    ENTERPRISE_SCORE_THRESHOLD,
    SMB_SCORE_THRESHOLD,
    MANUAL_REVIEW_SCORE_THRESHOLD,
    QUEUE_ENTERPRISE,
    QUEUE_SMB,
    QUEUE_INBOUND,
    QUEUE_MANUAL_REVIEW,
)
from utils.logger import get_logger

logger = get_logger("router")


# ─── Routing Result ───────────────────────────────────────────────────────────

class RoutingDecision:
    def __init__(self, initial_stage: str, assigned_queue: str, reason: str):
        self.initial_stage = initial_stage
        self.assigned_queue = assigned_queue
        self.reason = reason

    def __repr__(self):
        return f"RoutingDecision(stage={self.initial_stage}, queue={self.assigned_queue})"


# ─── Router Logic ─────────────────────────────────────────────────────────────

def route_lead(lead: NormalizedLead) -> RoutingDecision:
    score = lead.lead_score

    # Below minimum threshold — incomplete or low-quality signal
    if score < MANUAL_REVIEW_SCORE_THRESHOLD:
        logger.info(f"Lead {lead.email} -> manual_review (score={score}, below threshold)")
        return RoutingDecision(
            initial_stage=LeadStage.MANUAL_REVIEW,
            assigned_queue=QUEUE_MANUAL_REVIEW,
            reason=f"Score {score} below minimum threshold ({MANUAL_REVIEW_SCORE_THRESHOLD})"
        )

    # High score — enterprise routing
    if score >= ENTERPRISE_SCORE_THRESHOLD:
        logger.info(f"Lead {lead.email} -> enterprise_sales (score={score})")
        return RoutingDecision(
            initial_stage=LeadStage.QUALIFIED,
            assigned_queue=QUEUE_ENTERPRISE,
            reason=f"Score {score} meets enterprise threshold ({ENTERPRISE_SCORE_THRESHOLD})"
        )

    # Mid score — SMB routing
    if score >= SMB_SCORE_THRESHOLD:
        logger.info(f"Lead {lead.email} -> smb_sales (score={score})")
        return RoutingDecision(
            initial_stage=LeadStage.QUALIFIED,
            assigned_queue=QUEUE_SMB,
            reason=f"Score {score} meets SMB threshold ({SMB_SCORE_THRESHOLD})"
        )

    # Low-mid score — inbound queue for triage
    logger.info(f"Lead {lead.email} -> inbound_queue (score={score})")
    return RoutingDecision(
        initial_stage=LeadStage.NEW,
        assigned_queue=QUEUE_INBOUND,
        reason=f"Score {score} below SMB threshold, routed to inbound triage"
    )


# ─── Progression Rules ────────────────────────────────────────────────────────
# These define valid stage transitions and what triggers them.

VALID_TRANSITIONS = {
    LeadStage.NEW: [LeadStage.QUALIFIED, LeadStage.MANUAL_REVIEW, LeadStage.LOST],
    LeadStage.QUALIFIED: [LeadStage.ASSIGNED, LeadStage.MANUAL_REVIEW, LeadStage.LOST],
    LeadStage.ASSIGNED: [LeadStage.CONTACTED, LeadStage.MANUAL_REVIEW, LeadStage.LOST],
    LeadStage.CONTACTED: [LeadStage.PROPOSAL, LeadStage.LOST, LeadStage.MANUAL_REVIEW],
    LeadStage.PROPOSAL: [LeadStage.WON, LeadStage.LOST, LeadStage.MANUAL_REVIEW],
    LeadStage.MANUAL_REVIEW: [LeadStage.QUALIFIED, LeadStage.ASSIGNED, LeadStage.LOST],
    LeadStage.WON: [],
    LeadStage.LOST: [],
}


def is_valid_transition(from_stage: str, to_stage: str) -> bool:
    valid_next = VALID_TRANSITIONS.get(LeadStage(from_stage), [])
    return LeadStage(to_stage) in valid_next


def get_valid_next_stages(current_stage: str) -> list:
    return [s.value for s in VALID_TRANSITIONS.get(LeadStage(current_stage), [])]
