"""
main.py — Local demo runner for CRM Workflow Automation System.

This is NOT a uvicorn launcher.
Run this directly to:
  1. Seed the database from raw_inputs.json
  2. Run automated workflow checks
  3. Simulate manual stage progressions
  4. Print metrics and agent recommendations

Usage:
    python main.py
    python main.py --reset   (wipe DB and re-seed)
"""

import sys
import json
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db, reset_db
from pipeline.workflow_engine import ingest_lead, bulk_ingest
from pipeline.state_manager import transition_lead, run_automated_checks, TransitionError
from pipeline.metrics_evaluator import compute_metrics
from pipeline.agent_analyzer import run_agent_analysis
from database import db
from utils.logger import get_logger

logger = get_logger("main")


# ─── Seed ─────────────────────────────────────────────────────────────────────

def seed_from_file(path: str = "data/raw_inputs.json") -> int:
    with open(path) as f:
        leads = json.load(f)

    results = {"ingested": 0, "failed": 0, "errors": []}
    for entry in leads:
        try:
            ingest_lead(entry["source_type"], entry["raw_data"])
            results["ingested"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))

    print(f"\n[SEED] Ingested: {results['ingested']} | Failed: {results['failed']}")
    if results["errors"]:
        for err in results["errors"][:5]:
            print(f"  Error: {err}")
    return results["ingested"]


# ─── Simulate Lifecycle Progressions ─────────────────────────────────────────

def simulate_progressions():
    """
    Advance a representative subset of leads through lifecycle stages
    to demonstrate stateful workflow behavior.
    """
    print("\n[SIM] Running lifecycle simulations...")

    all_leads = db.get_all_leads_raw()
    qualified = [l for l in all_leads if l["current_stage"] == "qualified"]
    assigned = [l for l in all_leads if l["current_stage"] == "assigned"]
    new_leads = [l for l in all_leads if l["current_stage"] == "new"]
    manual = [l for l in all_leads if l["current_stage"] == "manual_review"]

    # Move qualified → assigned
    for lead in qualified[:8]:
        try:
            transition_lead(lead["id"], "assigned", "manual_assignment",
                            notes="Assigned by sales manager after qualification review")
        except TransitionError:
            pass

    # Move assigned → contacted
    all_leads = db.get_all_leads_raw()
    newly_assigned = [l for l in all_leads if l["current_stage"] == "assigned"]
    for lead in newly_assigned[:6]:
        try:
            transition_lead(lead["id"], "contacted", "initial_outreach_sent",
                            notes="First contact email sent, awaiting reply")
        except TransitionError:
            pass

    # Move some contacted → proposal
    all_leads = db.get_all_leads_raw()
    contacted = [l for l in all_leads if l["current_stage"] == "contacted"]
    for lead in contacted[:3]:
        try:
            transition_lead(lead["id"], "proposal", "positive_reply_received",
                            notes="Lead confirmed interest, proposal requested")
        except TransitionError:
            pass

    # Move some proposals → won
    all_leads = db.get_all_leads_raw()
    proposals = [l for l in all_leads if l["current_stage"] == "proposal"]
    for lead in proposals[:2]:
        try:
            transition_lead(lead["id"], "won", "contract_signed",
                            outcome="closed_won",
                            notes="Contract signed, onboarding initiated")
        except TransitionError:
            pass

    # Move some proposals → lost
    for lead in proposals[2:4]:
        try:
            transition_lead(lead["id"], "lost", "no_response_after_proposal",
                            outcome="no_response",
                            notes="No reply to proposal after 5 days")
        except TransitionError:
            pass

    # Move some new → lost (disqualified on review)
    for lead in new_leads[:3]:
        try:
            transition_lead(lead["id"], "manual_review", "low_quality_signal",
                            notes="Inbound lead lacks company or contact info")
        except TransitionError:
            pass

    # Move some manual_review → qualified (recovered)
    for lead in manual[:2]:
        try:
            transition_lead(lead["id"], "qualified", "manual_review_passed",
                            notes="Reviewed by ops team, meets qualification criteria")
        except TransitionError:
            pass

    # Move some manual_review → lost (confirmed disqualified)
    for lead in manual[2:5]:
        try:
            transition_lead(lead["id"], "lost", "disqualified_after_review",
                            outcome="disqualified",
                            notes="Lead confirmed as outside ICP after manual review")
        except TransitionError:
            pass

    print("[SIM] Lifecycle simulations complete.")


# ─── Print Metrics ────────────────────────────────────────────────────────────

def print_metrics():
    metrics = compute_metrics()
    print("\n" + "═" * 60)
    print("WORKFLOW METRICS")
    print("═" * 60)
    print(f"  Total leads:          {metrics.total_leads}")
    print(f"  Won:                  {metrics.won_count}")
    print(f"  Lost:                 {metrics.lost_count}")
    print(f"  Win rate:             {metrics.win_rate:.0%}")
    print(f"  Manual review rate:   {metrics.manual_review_rate:.0%}")
    print(f"  Stuck leads:          {metrics.stuck_leads}")
    print(f"  Aging leads:          {metrics.aging_leads}")
    print(f"  Follow-up overdue:    {metrics.follow_up_overdue_count}")
    print(f"\n  Leads by stage:")
    for stage, count in sorted(metrics.leads_by_stage.items()):
        print(f"    {stage:<20} {count}")
    print(f"\n  Queue workload:")
    for queue, count in sorted(metrics.owner_workload.items()):
        print(f"    {queue:<25} {count}")
    if metrics.avg_follow_up_lag_days:
        print(f"\n  Avg follow-up lag:    {metrics.avg_follow_up_lag_days:.1f} days")
    print("═" * 60)


# ─── Print Agent Recommendations ─────────────────────────────────────────────

def print_recommendations():
    print("\n" + "═" * 60)
    print("AGENT RECOMMENDATIONS")
    print("═" * 60)
    result = run_agent_analysis()
    print(f"\nSource: {result.analysis_source}")
    print(f"Summary: {result.summary}\n")

    for i, rec in enumerate(result.recommendations, 1):
        print(f"[{i}] [{rec.priority.upper()}] {rec.issue}")
        print(f"     → {rec.recommendation}")
        print(f"     Effect:    {rec.expected_effect}")
        print(f"     Trade-off: {rec.trade_off}")
        print()
    print("═" * 60)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reset = "--reset" in sys.argv

    print("\n" + "═" * 60)
    print("CRM WORKFLOW AUTOMATION SYSTEM — DEMO RUN")
    print("═" * 60)

    if reset:
        print("\n[DB] Resetting database...")
        reset_db()
    else:
        init_db()

    print("\n[DB] Database ready.")

    # Seed
    total = seed_from_file("data/raw_inputs.json")

    # Run automated checks (time-based rules)
    print("\n[WORKFLOW] Running automated checks...")
    check_results = run_automated_checks()
    print(f"  Follow-up escalations: {len(check_results['follow_up_triggered'])}")
    print(f"  Stuck escalations:     {len(check_results['stuck_escalated'])}")
    print(f"  Reengagement queued:   {len(check_results['reengagement_queued'])}")

    # Simulate lifecycle progressions
    simulate_progressions()

    # Print metrics
    print_metrics()

    # Print agent recommendations
    print_recommendations()

    print("\n[DONE] Demo run complete.")
    print("[API]  To start the HTTP server: uvicorn api:app --reload")
    print()
