"""
Generates raw_inputs.json — 75 simulated leads across 3 source types.
Run once to regenerate the dataset file.
"""
import json
import random
from datetime import datetime, timedelta


random.seed(42)

INDUSTRIES = ["fintech", "saas", "healthcare", "legal", "e-commerce", "insurance",
              "logistics", "real-estate", "education", "manufacturing"]
COMPANY_SIZES = ["enterprise", "mid-market", "smb", "startup", "solo"]
AD_PLATFORMS = ["LinkedIn", "Google Ads", "Meta", "TikTok", "Twitter"]
CAMPAIGNS = ["Q1_ROI_Push", "Spring_Demo", "Enterprise_Reach", "SMB_Growth", "Brand_Awareness"]

WEB_FIRST = ["Alice", "Ben", "Clara", "David", "Elena", "Frank", "Grace", "Hugo",
             "Iris", "James", "Kate", "Leo", "Maria", "Noel", "Olivia", "Paul",
             "Quinn", "Rachel", "Sam", "Tara", "Uma", "Victor", "Wendy"]
WEB_LAST = ["Taylor", "Morgan", "Chen", "Patel", "Kowalski", "Nakamura", "Garcia",
            "Williams", "Osei", "Kovač", "Tanaka", "Romero", "Müller", "Singh"]
COMPANIES = ["Apex Solutions", "NovaTech", "Vertex Digital", "BluePeak", "CoreFlow",
             "Prism Analytics", "DeltaOps", "Nimbus Systems", "Zenith Partners",
             "Catalyst Group", "Orbit Ventures", "Meridian AI", "Pinnacle SaaS",
             "Flare Technologies", "Quantum Bridge", "SilverLine Corp", "IronGate Ltd",
             "Cobalt Digital", "Ember Analytics", "Frost Dynamics"]
UTM_SOURCES = ["google", "linkedin", "referral", "organic", "email_campaign"]

EMAIL_SUBJECTS = [
    "Interested in your automation platform",
    "Partnership inquiry — workflow automation",
    "Demo request for our ops team",
    "Evaluating CRM tools for Q2",
    "Quick question about your pricing",
    "Re: integrations with HubSpot",
    "Request for enterprise proposal",
    "CRM workflow inquiry from our team",
]
EMAIL_BODIES = [
    "Hi, we're evaluating automation tools for our sales pipeline. Can we schedule a demo?",
    "We have a team of 50+ and are looking for a scalable CRM workflow system.",
    "Our current tool is not meeting our needs. Happy to jump on a call this week.",
    "We came across your platform via a referral. Please send over pricing details.",
    "Looking to automate our lead qualification process. Would love to discuss.",
    "We run a lean ops team and need something that integrates with our existing stack.",
    "Could you share a case study relevant to our industry?",
    "We have budget approved and are ready to move quickly if there's a good fit.",
]
DOMAINS = ["apexsol.com", "novatech.io", "vertexdigital.co", "bluepeak.com",
           "coreflow.io", "prismanalytics.com", "deltaops.com", "nimbussys.com"]


def rand_dt(days_back_min=1, days_back_max=21) -> str:
    delta = timedelta(
        days=random.randint(days_back_min, days_back_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )
    return (datetime.utcnow() - delta).strftime("%Y-%m-%dT%H:%M:%S")


def gen_email(first: str, last: str, domain: str = None) -> str:
    d = domain or f"{first.lower()}{last.lower()}.com"
    return f"{first.lower()}.{last.lower()}@{d}"


# ─── Web Form Leads (25) ──────────────────────────────────────────────────────

def gen_web_forms(n: int) -> list:
    leads = []
    for i in range(n):
        first = random.choice(WEB_FIRST)
        last = random.choice(WEB_LAST)
        company = random.choice(COMPANIES) if random.random() > 0.15 else None
        phone = f"+356 99{random.randint(100000, 999999)}" if random.random() > 0.4 else None
        message_options = [
            "We're looking for a scalable CRM workflow system for our sales team.",
            "Can we book a demo for next week?",
            "Interested in enterprise pricing and integration options.",
            "We currently use HubSpot and are evaluating alternatives.",
            None, None  # some leads submit without a message
        ]
        leads.append({
            "source_type": "web_form",
            "raw_data": {
                "form_id": f"WF-{1000 + i}",
                "first_name": first,
                "last_name": last,
                "email": gen_email(first, last, "workmail.com"),
                "company": company,
                "phone": phone,
                "message": random.choice(message_options),
                "utm_source": random.choice(UTM_SOURCES),
                "submitted_at": rand_dt(1, 18)
            }
        })
    return leads


# ─── Email Leads (25) ─────────────────────────────────────────────────────────

def gen_emails(n: int) -> list:
    leads = []
    for i in range(n):
        first = random.choice(WEB_FIRST)
        last = random.choice(WEB_LAST)
        domain = random.choice(DOMAINS) if random.random() > 0.2 else None
        leads.append({
            "source_type": "email",
            "raw_data": {
                "message_id": f"MSG-{2000 + i}",
                "sender_name": f"{first} {last}",
                "sender_email": gen_email(first, last, domain),
                "subject": random.choice(EMAIL_SUBJECTS),
                "body_snippet": random.choice(EMAIL_BODIES),
                "company_domain": domain,
                "received_at": rand_dt(1, 20)
            }
        })
    return leads


# ─── Ad Platform Leads (25) ───────────────────────────────────────────────────

def gen_ad_platform(n: int) -> list:
    leads = []
    for i in range(n):
        first = random.choice(WEB_FIRST)
        last = random.choice(WEB_LAST)
        # Ad platform leads have company_size and industry but less personal signal
        company_size = random.choice(COMPANY_SIZES) if random.random() > 0.1 else None
        industry = random.choice(INDUSTRIES) if random.random() > 0.1 else None
        leads.append({
            "source_type": "ad_platform",
            "raw_data": {
                "campaign_id": random.choice(CAMPAIGNS),
                "ad_id": f"AD-{3000 + i}",
                "lead_name": f"{first} {last}",
                "lead_email": gen_email(first, last, "leads.io"),
                "company_size": company_size,
                "industry": industry,
                "platform": random.choice(AD_PLATFORMS),
                "clicked_at": rand_dt(1, 21)
            }
        })
    return leads


# ─── Assemble & Write ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    all_leads = gen_web_forms(25) + gen_emails(25) + gen_ad_platform(25)
    random.shuffle(all_leads)

    output_path = os.path.join(os.path.dirname(__file__), "data", "raw_inputs.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(all_leads, f, indent=2)

    print(f"Generated {len(all_leads)} leads → {output_path}")
