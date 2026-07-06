import hashlib
from datetime import datetime
from typing import Union

from models.schemas import (
    NormalizedLead, SourceType,
    WebFormRawInput, EmailRawInput, AdPlatformRawInput
)
from utils.logger import get_logger

logger = get_logger("normalizer")


# ─── Score Computation ────────────────────────────────────────────────────────

def _compute_score(
    has_company: bool,
    has_phone: bool,
    has_message: bool,
    company_size: str = None,
    industry: str = None,
    source_type: SourceType = None
) -> int:
    """
    Scoring rules (base 30, then signal adjustments):
      - company identified: +10; not identified: -15. A lead with no
        identifiable company/industry signal at all is a real quality
        problem, not merely the absence of a bonus — this is what makes
        MANUAL_REVIEW_SCORE_THRESHOLD reachable for genuinely incomplete
        leads instead of only ever routing to inbound/SMB/enterprise.
      - phone / message present: +10 each; no penalty for absence, since
        plenty of legitimate leads simply don't share these.
      - company size / high-value industry: bonus only (unchanged).
      - source: email +5 (intentional outreach), ad_platform -5 (lower
        intent, unsolicited click).
    Result is capped at 100.
    """
    score = 30  # base

    if has_company:
        score += 10
    else:
        score -= 15  # no identifiable company/industry signal is a real quality problem
    if has_phone:
        score += 10
    if has_message:
        score += 10

    # Company size signals
    size_scores = {
        "enterprise": 25,
        "mid-market": 20,
        "smb": 10,
        "startup": 8,
        "solo": 3,
    }
    if company_size:
        score += size_scores.get(company_size.lower(), 5)

    # Industry signals
    high_value_industries = {"fintech", "saas", "healthcare", "legal", "insurance"}
    if industry and industry.lower() in high_value_industries:
        score += 10

    # Source bonus
    if source_type == SourceType.EMAIL:
        score += 5  # intentional outreach
    elif source_type == SourceType.AD_PLATFORM:
        score -= 5  # lower intent signal

    return min(score, 100)


def _source_ref(prefix: str, identifier: str) -> str:
    return f"{prefix}_{hashlib.md5(identifier.encode()).hexdigest()[:8]}"


def _parse_dt(raw: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {raw}")


# ─── Per-source normalizers ───────────────────────────────────────────────────

def _normalize_web_form(raw: dict) -> NormalizedLead:
    data = WebFormRawInput(**raw)
    full_name = f"{data.first_name} {data.last_name}".strip()
    score = _compute_score(
        has_company=bool(data.company),
        has_phone=bool(data.phone),
        has_message=bool(data.message),
        source_type=SourceType.WEB_FORM
    )
    return NormalizedLead(
        source_type=SourceType.WEB_FORM,
        source_ref=_source_ref("wf", data.form_id),
        full_name=full_name,
        email=data.email,
        company=data.company,
        phone=data.phone,
        message_snippet=data.message[:200] if data.message else None,
        lead_score=score,
        received_at=_parse_dt(data.submitted_at)
    )


def _normalize_email(raw: dict) -> NormalizedLead:
    data = EmailRawInput(**raw)
    company = None
    if data.company_domain:
        company = data.company_domain.replace(".com", "").replace(".io", "").title()

    score = _compute_score(
        has_company=bool(company),
        has_phone=False,
        has_message=bool(data.body_snippet),
        source_type=SourceType.EMAIL
    )
    return NormalizedLead(
        source_type=SourceType.EMAIL,
        source_ref=_source_ref("em", data.message_id),
        full_name=data.sender_name,
        email=data.sender_email,
        company=company,
        message_snippet=f"{data.subject} — {data.body_snippet[:150]}",
        lead_score=score,
        received_at=_parse_dt(data.received_at)
    )


def _normalize_ad_platform(raw: dict) -> NormalizedLead:
    data = AdPlatformRawInput(**raw)
    score = _compute_score(
        has_company=bool(data.industry),
        has_phone=False,
        has_message=False,
        company_size=data.company_size,
        industry=data.industry,
        source_type=SourceType.AD_PLATFORM
    )
    return NormalizedLead(
        source_type=SourceType.AD_PLATFORM,
        source_ref=_source_ref("ad", data.ad_id),
        full_name=data.lead_name,
        email=data.lead_email,
        company_size=data.company_size,
        industry=data.industry,
        message_snippet=f"Platform: {data.platform} | Campaign: {data.campaign_id}",
        lead_score=score,
        received_at=_parse_dt(data.clicked_at)
    )


# ─── Public Entry Point ───────────────────────────────────────────────────────

NORMALIZERS = {
    SourceType.WEB_FORM: _normalize_web_form,
    SourceType.EMAIL: _normalize_email,
    SourceType.AD_PLATFORM: _normalize_ad_platform,
}


def normalize(source_type: Union[str, SourceType], raw_data: dict) -> NormalizedLead:
    source_type = SourceType(source_type)
    normalizer = NORMALIZERS.get(source_type)
    if not normalizer:
        raise ValueError(f"No normalizer registered for source type: {source_type}")

    lead = normalizer(raw_data)
    logger.info(f"Normalized lead: {lead.full_name} | score={lead.lead_score} | source={source_type.value}")
    return lead
