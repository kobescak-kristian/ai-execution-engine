import json
from datetime import datetime
from typing import List

from models.schemas import (
    WorkflowMetrics, AgentRecommendation, AgentAnalysisResult
)
from pipeline.metrics_evaluator import compute_metrics
from config.settings import (
    OPENAI_API_KEY, OPENAI_MODEL,
    AGENT_MANUAL_REVIEW_THRESHOLD,
    AGENT_CONVERSION_WARNING_THRESHOLD,
    AGENT_STUCK_LEAD_WARNING_COUNT,
)
from utils.logger import get_logger

logger = get_logger("agent_analyzer")

# Known placeholder values that mean "no real key" even though the env var
# is technically set (e.g. a .env copied from .env.example without editing).
_PLACEHOLDER_OPENAI_KEYS = {"your_openai_api_key_here"}


def _is_openai_key_configured() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    return bool(key) and key not in _PLACEHOLDER_OPENAI_KEYS


# ─── Deterministic Fallback ───────────────────────────────────────────────────

def _deterministic_recommendations(metrics: WorkflowMetrics) -> List[AgentRecommendation]:
    recommendations = []

    # Manual review overload
    if metrics.manual_review_rate > AGENT_MANUAL_REVIEW_THRESHOLD:
        recommendations.append(AgentRecommendation(
            issue=f"Manual review queue contains {metrics.manual_review_volume} leads "
                  f"({metrics.manual_review_rate:.0%} of total). This volume reduces throughput "
                  f"and risks delayed follow-up on recoverable leads.",
            recommendation=(
                "Lower the manual review routing threshold by 5 points to qualify "
                "more leads automatically. Introduce a secondary scoring pass for "
                "leads currently flagged as incomplete."
            ),
            expected_effect="Estimated 20-30% reduction in manual review volume, "
                            "faster average cycle time for mid-range leads.",
            trade_off="Some lower-quality leads may enter the active pipeline, "
                      "increasing noise for sales queues.",
            priority="high"
        ))

    # Low win rate
    if 0 < metrics.win_rate < AGENT_CONVERSION_WARNING_THRESHOLD:
        recommendations.append(AgentRecommendation(
            issue=f"Win rate is {metrics.win_rate:.0%} against a baseline target of "
                  f"{AGENT_CONVERSION_WARNING_THRESHOLD:.0%}. "
                  f"High loss volume ({metrics.lost_count} leads) suggests proposal stage drop-off "
                  f"or premature disqualification.",
            recommendation=(
                "Audit the proposal -> lost transition triggers. Review whether leads are "
                "being lost due to no follow-up, pricing mismatch, or wrong qualification "
                "criteria upstream. Consider adding a re-engagement path before marking lost."
            ),
            expected_effect="If 15% of currently lost leads are recoverable, "
                            "win rate could increase by 3-5 percentage points.",
            trade_off="Re-engagement effort requires queue capacity and increases cycle time.",
            priority="high"
        ))

    # Stuck leads
    if metrics.stuck_leads >= AGENT_STUCK_LEAD_WARNING_COUNT:
        recommendations.append(AgentRecommendation(
            issue=f"{metrics.stuck_leads} leads have not progressed in over 7 days. "
                  f"These are stalling in active stages without closure or escalation.",
            recommendation=(
                "Reduce the automated escalation threshold from 7 days to 4 days for "
                "leads in 'assigned' and 'contacted' stages. Add an explicit re-assignment "
                "trigger if the same lead is stuck twice consecutively."
            ),
            expected_effect="Faster identification of stuck leads, reduced manual review "
                            "backlog, cleaner pipeline view.",
            trade_off="Shorter threshold increases automated escalation volume "
                      "and may create noise in the manual review queue.",
            priority="medium"
        ))

    # Workload imbalance
    if metrics.owner_workload:
        workload_vals = list(metrics.owner_workload.values())
        if max(workload_vals) > 2 * min(workload_vals) and len(workload_vals) > 1:
            max_queue = max(metrics.owner_workload, key=metrics.owner_workload.get)
            min_queue = min(metrics.owner_workload, key=metrics.owner_workload.get)
            recommendations.append(AgentRecommendation(
                issue=f"Queue workload imbalance detected: '{max_queue}' has "
                      f"{metrics.owner_workload[max_queue]} leads while '{min_queue}' has "
                      f"{metrics.owner_workload[min_queue]}. This creates processing bottlenecks.",
                recommendation=(
                    f"Adjust routing score thresholds to redirect overflow from '{max_queue}' "
                    f"toward '{min_queue}'. Consider adding a load-balancing check at routing "
                    f"time if a queue exceeds a configurable capacity ceiling."
                ),
                expected_effect="More even lead distribution, reduced risk of queue-specific delays.",
                trade_off="Score-based routing adjustments may mismatch lead quality to queue capability.",
                priority="medium"
            ))

    # Follow-up lag
    if metrics.avg_follow_up_lag_days and metrics.avg_follow_up_lag_days > 3:
        recommendations.append(AgentRecommendation(
            issue=f"Average follow-up lag is {metrics.avg_follow_up_lag_days:.1f} days. "
                  f"Leads are being contacted later than the 3-day best-practice threshold.",
            recommendation=(
                "Add an automated Slack or email nudge at T+48h for any lead in 'assigned' "
                "stage with no contact recorded. Reduce the follow-up overdue threshold from "
                "3 days to 2 days."
            ),
            expected_effect="Faster first contact improves conversion probability by 20-40% "
                            "based on standard SDR benchmarks.",
            trade_off="Requires notification infrastructure. Risk of over-notification "
                      "if not scoped to the right queue.",
            priority="medium"
        ))

    # Aging leads
    if metrics.aging_leads > 0:
        recommendations.append(AgentRecommendation(
            issue=f"{metrics.aging_leads} leads are over 14 days old without reaching a "
                  f"terminal stage (won/lost). These consume pipeline capacity without signal.",
            recommendation=(
                "Introduce a 14-day aging policy: any lead still in a pre-proposal stage "
                "after 14 days should be auto-closed as 'lost' with reason 'aged_out', "
                "unless manually overridden by a queue owner."
            ),
            expected_effect="Cleaner pipeline, more accurate conversion metrics, "
                            "reduced review burden.",
            trade_off="Some long-cycle legitimate deals may be incorrectly closed. "
                      "Requires a manual override mechanism.",
            priority="low"
        ))

    if not recommendations:
        recommendations.append(AgentRecommendation(
            issue="No significant workflow issues detected.",
            recommendation="Continue monitoring. Review again when pipeline volume increases.",
            expected_effect="Stable workflow performance.",
            trade_off="None.",
            priority="low"
        ))

    return recommendations


# ─── OpenAI Analysis ──────────────────────────────────────────────────────────

def _openai_recommendations(metrics: WorkflowMetrics) -> List[AgentRecommendation]:
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        metrics_summary = {
            "total_leads": metrics.total_leads,
            "leads_by_stage": metrics.leads_by_stage,
            "manual_review_rate": metrics.manual_review_rate,
            "win_rate": metrics.win_rate,
            "stuck_leads": metrics.stuck_leads,
            "aging_leads": metrics.aging_leads,
            "avg_follow_up_lag_days": metrics.avg_follow_up_lag_days,
            "follow_up_overdue_count": metrics.follow_up_overdue_count,
            "owner_workload": metrics.owner_workload,
            "won_count": metrics.won_count,
            "lost_count": metrics.lost_count,
        }

        prompt = f"""You are a CRM workflow analyst. Analyze the following workflow metrics 
and return a JSON array of recommendations. Each recommendation must have exactly these fields:
- issue: string (what problem was detected)
- recommendation: string (what to change)
- expected_effect: string (measurable expected outcome)
- trade_off: string (downside or risk)
- priority: "high" | "medium" | "low"

Metrics:
{json.dumps(metrics_summary, indent=2)}

Return ONLY a valid JSON array. No explanation, no markdown, no extra text.
Generate 3–5 recommendations based on the most significant issues in the data."""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        recommendations = []
        for item in parsed:
            recommendations.append(AgentRecommendation(
                issue=item["issue"],
                recommendation=item["recommendation"],
                expected_effect=item["expected_effect"],
                trade_off=item["trade_off"],
                priority=item.get("priority", "medium")
            ))

        logger.info(f"OpenAI agent returned {len(recommendations)} recommendations")
        return recommendations

    except Exception as e:
        logger.warning(f"OpenAI agent failed: {e}. Falling back to deterministic.")
        raise


# ─── Public Entry Point ───────────────────────────────────────────────────────

def run_agent_analysis() -> AgentAnalysisResult:
    metrics = compute_metrics()
    analysis_source = "deterministic"
    recommendations = []

    if _is_openai_key_configured():
        try:
            recommendations = _openai_recommendations(metrics)
            analysis_source = "openai"
        except Exception:
            recommendations = _deterministic_recommendations(metrics)
    else:
        logger.info("No OpenAI key configured. Using deterministic agent.")
        recommendations = _deterministic_recommendations(metrics)

    total_leads = metrics.total_leads
    high_count = sum(1 for r in recommendations if r.priority == "high")
    summary = (
        f"Workflow analysis complete. {total_leads} leads in pipeline. "
        f"{len(recommendations)} recommendations generated "
        f"({high_count} high priority). "
        f"Win rate: {metrics.win_rate:.0%}. "
        f"Manual review rate: {metrics.manual_review_rate:.0%}. "
        f"Analysis source: {analysis_source}."
    )

    return AgentAnalysisResult(
        generated_at=datetime.utcnow(),
        metrics_snapshot=metrics,
        recommendations=recommendations,
        analysis_source=analysis_source,
        summary=summary
    )
