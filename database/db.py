import sqlite3
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

from config.settings import DATABASE_PATH
from utils.logger import get_logger

logger = get_logger("database")


# ─── Connection ───────────────────────────────────────────────────────────────

@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema Init ──────────────────────────────────────────────────────────────

def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                phone TEXT,
                message_snippet TEXT,
                company_size TEXT,
                industry TEXT,
                lead_score INTEGER NOT NULL DEFAULT 0,
                current_stage TEXT NOT NULL DEFAULT 'new',
                assigned_queue TEXT,
                owner_notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_contacted_at TEXT,
                outcome TEXT,
                duplicate_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS stage_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                from_stage TEXT NOT NULL,
                to_stage TEXT NOT NULL,
                trigger TEXT NOT NULL,
                transitioned_at TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(current_stage);
            CREATE INDEX IF NOT EXISTS idx_leads_queue ON leads(assigned_queue);
            CREATE INDEX IF NOT EXISTS idx_transitions_lead ON stage_transitions(lead_id);
        """)
    logger.info("Database initialized")


def reset_db():
    with get_connection() as conn:
        conn.executescript("""
            DROP TABLE IF EXISTS stage_transitions;
            DROP TABLE IF EXISTS leads;
        """)
    logger.info("Database reset")
    init_db()


# ─── Lead Writes ──────────────────────────────────────────────────────────────

def insert_lead(lead: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO leads (
                source_type, source_ref, full_name, email, company, phone,
                message_snippet, company_size, industry, lead_score,
                current_stage, assigned_queue, owner_notes,
                created_at, updated_at, last_contacted_at, outcome
            ) VALUES (
                :source_type, :source_ref, :full_name, :email, :company, :phone,
                :message_snippet, :company_size, :industry, :lead_score,
                :current_stage, :assigned_queue, :owner_notes,
                :created_at, :updated_at, :last_contacted_at, :outcome
            )
        """, lead)
        return cursor.lastrowid


def update_lead_stage(lead_id: int, new_stage: str, updated_at: str,
                      assigned_queue: Optional[str] = None,
                      last_contacted_at: Optional[str] = None,
                      outcome: Optional[str] = None,
                      owner_notes: Optional[str] = None):
    fields = ["current_stage = :stage", "updated_at = :updated_at"]
    params = {"lead_id": lead_id, "stage": new_stage, "updated_at": updated_at}

    if assigned_queue is not None:
        fields.append("assigned_queue = :assigned_queue")
        params["assigned_queue"] = assigned_queue
    if last_contacted_at is not None:
        fields.append("last_contacted_at = :last_contacted_at")
        params["last_contacted_at"] = last_contacted_at
    if outcome is not None:
        fields.append("outcome = :outcome")
        params["outcome"] = outcome
    if owner_notes is not None:
        fields.append("owner_notes = :owner_notes")
        params["owner_notes"] = owner_notes

    with get_connection() as conn:
        conn.execute(
            f"UPDATE leads SET {', '.join(fields)} WHERE id = :lead_id",
            params
        )


def increment_duplicate_count(lead_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET duplicate_count = duplicate_count + 1 WHERE id = ?",
            (lead_id,)
        )


# ─── Transition Writes ────────────────────────────────────────────────────────

def insert_transition(transition: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO stage_transitions (
                lead_id, from_stage, to_stage, trigger, transitioned_at, notes
            ) VALUES (
                :lead_id, :from_stage, :to_stage, :trigger, :transitioned_at, :notes
            )
        """, transition)


# ─── Lead Reads ───────────────────────────────────────────────────────────────

def get_lead_by_id(lead_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
        return dict(row) if row else None


def get_lead_by_source_ref(source_ref: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM leads WHERE source_ref = ?", (source_ref,)
        ).fetchone()
        return dict(row) if row else None


def get_all_leads(stage: Optional[str] = None, queue: Optional[str] = None) -> List[dict]:
    with get_connection() as conn:
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        if stage:
            query += " AND current_stage = ?"
            params.append(stage)
        if queue:
            query += " AND assigned_queue = ?"
            params.append(queue)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_transitions_for_lead(lead_id: int) -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stage_transitions WHERE lead_id = ? ORDER BY transitioned_at ASC",
            (lead_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_leads_raw() -> List[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def count_leads_by_stage() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT current_stage, COUNT(*) as cnt FROM leads GROUP BY current_stage"
        ).fetchall()
        return {r["current_stage"]: r["cnt"] for r in rows}


def count_leads_by_queue() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT assigned_queue, COUNT(*) as cnt FROM leads WHERE assigned_queue IS NOT NULL GROUP BY assigned_queue"
        ).fetchall()
        return {r["assigned_queue"]: r["cnt"] for r in rows}


def get_leads_updated_before(cutoff_iso: str, stages: List[str]) -> List[dict]:
    placeholders = ",".join("?" * len(stages))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM leads WHERE updated_at < ? AND current_stage IN ({placeholders})",
            [cutoff_iso] + stages
        ).fetchall()
        return [dict(r) for r in rows]
