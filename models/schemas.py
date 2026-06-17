from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    WEB_FORM = "web_form"
    EMAIL = "email"
    AD_PLATFORM = "ad_platform"


class LeadStage(str, Enum):
    NEW = "new"
    QUALIFIED = "qualified"
    ASSIGNED = "assigned"
    CONTACTED = "contacted"
    PROPOSAL = "proposal"
    WON = "won"
    LOST = "lost"
    MANUAL_REVIEW = "manual_review"


class QueueName(str, Enum):
    INBOUND = "inbound_queue"
    SMB = "smb_sales"
    ENTERPRISE = "enterprise_sales"
    MANUAL_REVIEW = "manual_review_queue"
    REENGAGEMENT = "reengagement_queue"


# ─── Raw Input Schemas (per source) ───────────────────────────────────────────

class WebFormRawInput(BaseModel):
    form_id: str
    first_name: str
    last_name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    utm_source: Optional[str] = None
    submitted_at: str


class EmailRawInput(BaseModel):
    message_id: str
    sender_name: str
    sender_email: str
    subject: str
    body_snippet: str
    company_domain: Optional[str] = None
    received_at: str


class AdPlatformRawInput(BaseModel):
    campaign_id: str
    ad_id: str
    lead_name: str
    lead_email: str
    company_size: Optional[str] = None
    industry: Optional[str] = None
    platform: str
    clicked_at: str


# ─── Normalized Lead Schema ────────────────────────────────────────────────────

class NormalizedLead(BaseModel):
    source_type: SourceType
    source_ref: str
    full_name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message_snippet: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    lead_score: int = Field(default=0, ge=0, le=100)
    received_at: datetime


# ─── Lead Record (stored in DB) ───────────────────────────────────────────────

class LeadRecord(BaseModel):
    id: Optional[int] = None
    source_type: str
    source_ref: str
    full_name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message_snippet: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    lead_score: int
    current_stage: str
    assigned_queue: Optional[str] = None
    owner_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime] = None
    outcome: Optional[str] = None


# ─── Stage Transition ─────────────────────────────────────────────────────────

class StageTransition(BaseModel):
    id: Optional[int] = None
    lead_id: int
    from_stage: str
    to_stage: str
    trigger: str
    transitioned_at: datetime
    notes: Optional[str] = None


# ─── Ingest Request (API) ─────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    source_type: SourceType
    raw_data: dict


# ─── Stage Progress Request (API) ─────────────────────────────────────────────

class ProgressRequest(BaseModel):
    lead_id: int
    trigger: str
    notes: Optional[str] = None


# ─── Workflow Metrics ─────────────────────────────────────────────────────────

class WorkflowMetrics(BaseModel):
    total_leads: int
    leads_by_stage: dict
    stage_conversion_rates: dict
    manual_review_volume: int
    manual_review_rate: float
    stuck_leads: int
    aging_leads: int
    owner_workload: dict
    won_count: int
    lost_count: int
    win_rate: float
    avg_follow_up_lag_days: Optional[float] = None
    follow_up_overdue_count: int


# ─── Agent Recommendation ─────────────────────────────────────────────────────

class AgentRecommendation(BaseModel):
    issue: str
    recommendation: str
    expected_effect: str
    trade_off: str
    priority: Literal["high", "medium", "low"] = "medium"


class AgentAnalysisResult(BaseModel):
    generated_at: datetime
    metrics_snapshot: WorkflowMetrics
    recommendations: List[AgentRecommendation]
    analysis_source: Literal["openai", "deterministic"]
    summary: str
