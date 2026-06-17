import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "crm_workflow.db")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Workflow timing thresholds (days)
FOLLOW_UP_THRESHOLD_DAYS = int(os.getenv("FOLLOW_UP_THRESHOLD_DAYS", "3"))
STUCK_LEAD_THRESHOLD_DAYS = int(os.getenv("STUCK_LEAD_THRESHOLD_DAYS", "7"))
AGING_LEAD_THRESHOLD_DAYS = int(os.getenv("AGING_LEAD_THRESHOLD_DAYS", "14"))

# Routing thresholds
ENTERPRISE_SCORE_THRESHOLD = int(os.getenv("ENTERPRISE_SCORE_THRESHOLD", "70"))
SMB_SCORE_THRESHOLD = int(os.getenv("SMB_SCORE_THRESHOLD", "40"))
MANUAL_REVIEW_SCORE_THRESHOLD = int(os.getenv("MANUAL_REVIEW_SCORE_THRESHOLD", "20"))

# Queue names
QUEUE_INBOUND = "inbound_queue"
QUEUE_SMB = "smb_sales"
QUEUE_ENTERPRISE = "enterprise_sales"
QUEUE_MANUAL_REVIEW = "manual_review_queue"
QUEUE_REENGAGEMENT = "reengagement_queue"

# Agent
AGENT_MANUAL_REVIEW_THRESHOLD = float(os.getenv("AGENT_MANUAL_REVIEW_THRESHOLD", "0.20"))
AGENT_CONVERSION_WARNING_THRESHOLD = float(os.getenv("AGENT_CONVERSION_WARNING_THRESHOLD", "0.10"))
AGENT_STUCK_LEAD_WARNING_COUNT = int(os.getenv("AGENT_STUCK_LEAD_WARNING_COUNT", "5"))
