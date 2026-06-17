from datetime import datetime, timedelta
from typing import Optional

from database import db
from models.schemas import WorkflowMetrics
from config.settings import (
    FOLLOW_UP_THRESHOLD_DAYS,
    STUCK_LEAD_THRESHOLD_DAYS,
    AGING_LEAD_THRESHOLD_DAYS,
)
from utils.logger import get_logger

logger = get_logger("metrics_evaluator")

ACTIVE_STAGES = ["new", "qualified", "assigned", "contacted", "proposal", "manual_review"]
TERMINAL_STAGES = ["won", "lost"]


def compute_metrics() -> WorkflowMetrics:
    all_leads = db.get_all_leads_raw()
    total = len(all_leads)

    if total == 0:
        return WorkflowMetrics(
            total_leads=0,
            leads_by_stage={},
            stage_conversion_rates={},
            manual_review_volume=0,
            manual_review_rate=0.0,
            stuck_leads=0,
            aging_leads=0,
            owner_workload={},
            won_count=0,
            lost_count=0,
            win_rate=0.0,
            avg_follow_up_lag_days=None,
            follow_up_overdue_count=0,
        )

    # Leads by stage
    leads_by_stage = {}
    for lead in all_leads:
        stage = lead["current_stage"]
        leads_by_stage[stage] = leads_by_stage.get(stage, 0) + 1

    # Conversion rates (stage count / total leads)
    stage_conversion_rates = {
        stage: round(count / total, 3)
        for stage, count in leads_by_stage.items()
    }

    # Manual review metrics
    manual_review_volume = leads_by_stage.get("manual_review", 0)
    manual_review_rate = round(manual_review_volume / total, 3)

    # Time-based flags
    now = datetime.utcnow()
    stuck_cutoff = (now - timedelta(days=STUCK_LEAD_THRESHOLD_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    aging_cutoff = (now - timedelta(days=AGING_LEAD_THRESHOLD_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    follow_up_cutoff = (now - timedelta(days=FOLLOW_UP_THRESHOLD_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")

    stuck_leads = 0
    aging_leads = 0
    follow_up_overdue = 0
    follow_up_lags = []

    for lead in all_leads:
        if lead["current_stage"] in TERMINAL_STAGES:
            continue

        updated = lead.get("updated_at", "")
        created = lead.get("created_at", "")

        if updated and updated < stuck_cutoff:
            stuck_leads += 1
        if created and created < aging_cutoff:
            aging_leads += 1

        # Follow-up overdue: assigned stage, no contact, past threshold
        if lead["current_stage"] == "assigned" and updated and updated < follow_up_cutoff:
            follow_up_overdue += 1

        # Follow-up lag: time between created and last_contacted
        if lead.get("last_contacted_at") and lead.get("created_at"):
            try:
                created_dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S")
                contacted_dt = datetime.strptime(lead["last_contacted_at"], "%Y-%m-%dT%H:%M:%S")
                lag_days = (contacted_dt - created_dt).total_seconds() / 86400
                follow_up_lags.append(lag_days)
            except Exception:
                pass

    avg_lag = round(sum(follow_up_lags) / len(follow_up_lags), 2) if follow_up_lags else None

    # Owner workload
    owner_workload = db.count_leads_by_queue()

    # Win / loss
    won_count = leads_by_stage.get("won", 0)
    lost_count = leads_by_stage.get("lost", 0)
    closed_total = won_count + lost_count
    win_rate = round(won_count / closed_total, 3) if closed_total > 0 else 0.0

    metrics = WorkflowMetrics(
        total_leads=total,
        leads_by_stage=leads_by_stage,
        stage_conversion_rates=stage_conversion_rates,
        manual_review_volume=manual_review_volume,
        manual_review_rate=manual_review_rate,
        stuck_leads=stuck_leads,
        aging_leads=aging_leads,
        owner_workload=owner_workload,
        won_count=won_count,
        lost_count=lost_count,
        win_rate=win_rate,
        avg_follow_up_lag_days=avg_lag,
        follow_up_overdue_count=follow_up_overdue,
    )

    logger.info(
        f"Metrics computed: total={total} | won={won_count} | lost={lost_count} | "
        f"manual_review={manual_review_volume} | stuck={stuck_leads}"
    )
    return metrics
