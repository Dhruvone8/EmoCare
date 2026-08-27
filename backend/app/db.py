"""
Database helper for EmoCare.

Manages:
- Self-assessment attempts (PHQ-9 / GAD-7)
- Therapy sessions (chat & voice)
- Therapy messages (per-turn conversation log)
- Session summaries (structured memory for LLM context)

Supports:
1. PostgreSQL (production / Docker) via psycopg2 if configured and running.
2. Built-in SQLite local file fallback (zero configuration needed) saved to `data/assessments.db`.
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any

# Auto-load .env from backend/ or project root
try:
    from dotenv import load_dotenv
    # Check backend/.env first, then root .env
    backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(backend_env):
        load_dotenv(backend_env)
    elif os.path.exists(root_env):
        load_dotenv(root_env)
    else:
        load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("emocare.db")

# Read database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")


def _parse_json(val: Any) -> Any:
    """Safely parse JSON — handles both PG (auto-deserialized) and SQLite (string) cases."""
    if val is None:
        return []
    if isinstance(val, (list, dict)):
        return val  # PG psycopg2 already deserialized JSONB
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []

# Local SQLite database path (ensures data is persisted without any DB setup)
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
SQLITE_DB_PATH = os.path.join(DATA_DIR, "assessments.db")


# SQL DDL for PostgreSQL
PG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    test_type VARCHAR(50) NOT NULL,
    responses JSONB NOT NULL,
    total_score INTEGER NOT NULL,
    severity_band VARCHAR(50) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assessment_user_id ON assessment_attempts (user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_timestamp ON assessment_attempts (timestamp DESC);

CREATE TABLE IF NOT EXISTS therapy_sessions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('chat', 'voice')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMPTZ,
    objective TEXT
);
CREATE INDEX IF NOT EXISTS idx_therapy_sessions_user ON therapy_sessions (user_id);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES therapy_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    risk_tier VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id);

CREATE TABLE IF NOT EXISTS therapy_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES therapy_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    risk_tier VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_therapy_messages_session ON therapy_messages (session_id);

CREATE TABLE IF NOT EXISTS session_summaries (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES therapy_sessions(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    summary_text TEXT NOT NULL,
    concerns JSONB DEFAULT '[]'::jsonb,
    goals JSONB DEFAULT '[]'::jsonb,
    techniques_used JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_session_summaries_user ON session_summaries (user_id);
"""

# SQL DDL for SQLite
SQLITE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    test_type TEXT NOT NULL,
    responses TEXT NOT NULL,
    total_score INTEGER NOT NULL,
    severity_band TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sqlite_user_id ON assessment_attempts (user_id);

CREATE TABLE IF NOT EXISTS therapy_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    objective TEXT
);
CREATE INDEX IF NOT EXISTS idx_sqlite_therapy_sessions_user ON therapy_sessions (user_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    risk_tier TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sqlite_messages_session ON messages (session_id);

CREATE TABLE IF NOT EXISTS therapy_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    risk_tier TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sqlite_therapy_messages_session ON therapy_messages (session_id);

CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    concerns TEXT,
    goals TEXT,
    techniques_used TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sqlite_session_summaries_user ON session_summaries (user_id);
"""


def _get_pg_connection():
    """Attempt PostgreSQL connection."""
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception:
        return None


def _get_sqlite_connection():
    """Create or connect to local SQLite database file, auto-creating table if needed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.executescript(SQLITE_TABLE_SQL)
    conn.commit()
    return conn



def init_db():
    """Initialize database tables for PostgreSQL or local SQLite."""
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(PG_TABLE_SQL)
            pg_conn.commit()
            pg_conn.close()
            logger.info("Connected to PostgreSQL — all tables initialized.")
            return "postgresql"
        except Exception as e:
            logger.warning(f"PostgreSQL init failed: {e}. Falling back to SQLite.")
            if pg_conn:
                pg_conn.close()

    # Fallback to SQLite
    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.executescript(SQLITE_TABLE_SQL)
        conn.commit()
        conn.close()
        logger.info(f"Using local SQLite database at: {SQLITE_DB_PATH}")
        return "sqlite"
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        return "none"


def save_assessment_attempt(
    user_id: str,
    test_type: str,
    responses: List[int],
    total_score: int,
    severity_band: str,
    risk_tier: str,
    timestamp: Optional[datetime] = None,
) -> Optional[int]:
    """
    Save assessment to PostgreSQL if available, otherwise to local SQLite database.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    # 1. Try PostgreSQL
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessment_attempts (
                        user_id, test_type, responses, total_score, severity_band, risk_tier, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
                        test_type,
                        json.dumps(responses),
                        total_score,
                        severity_band,
                        risk_tier,
                        timestamp,
                    ),
                )
                inserted_id = cur.fetchone()[0]
            pg_conn.commit()
            pg_conn.close()
            return inserted_id
        except Exception as e:
            logger.error(f"PostgreSQL insert failed: {e}. Falling back to SQLite.")
            if pg_conn:
                pg_conn.close()

    # 2. Fallback to SQLite (built-in, zero config)
    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO assessment_attempts (
                user_id, test_type, responses, total_score, severity_band, risk_tier, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                test_type,
                json.dumps(responses),
                total_score,
                severity_band,
                risk_tier,
                timestamp.isoformat(),
            ),
        )
        inserted_id = cur.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Saved assessment (ID: {inserted_id}) to local SQLite ({SQLITE_DB_PATH})")
        return inserted_id
    except Exception as e:
        logger.error(f"SQLite save failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# THERAPY SESSION CRUD
# ═══════════════════════════════════════════════════════════════════════

def create_therapy_session(
    user_id: str,
    mode: str,
    objective: Optional[str] = None,
) -> Optional[int]:
    """
    Create a new therapy session and return its ID.
    Mode must be 'chat' or 'voice'.
    """
    now = datetime.now(timezone.utc)

    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO therapy_sessions (user_id, mode, started_at, objective)
                       VALUES (%s, %s, %s, %s) RETURNING id;""",
                    (user_id, mode, now, objective),
                )
                session_id = cur.fetchone()[0]
            pg_conn.commit()
            pg_conn.close()
            return session_id
        except Exception as e:
            logger.error(f"PG create_therapy_session failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO therapy_sessions (user_id, mode, started_at, objective)
               VALUES (?, ?, ?, ?);""",
            (user_id, mode, now.isoformat(), objective),
        )
        session_id = cur.lastrowid
        conn.commit()
        conn.close()
        return session_id
    except Exception as e:
        logger.error(f"SQLite create_therapy_session failed: {e}")
        return None


def end_therapy_session(session_id: int) -> bool:
    """Mark a therapy session as ended."""
    now = datetime.now(timezone.utc)

    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    "UPDATE therapy_sessions SET ended_at = %s WHERE id = %s;",
                    (now, session_id),
                )
            pg_conn.commit()
            pg_conn.close()
            return True
        except Exception as e:
            logger.error(f"PG end_therapy_session failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE therapy_sessions SET ended_at = ? WHERE id = ?;",
            (now.isoformat(), session_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"SQLite end_therapy_session failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
# THERAPY MESSAGE CRUD
# ═══════════════════════════════════════════════════════════════════════

def save_therapy_message(
    session_id: int,
    role: str,
    content: str,
    risk_tier: Optional[str] = None,
) -> Optional[int]:
    """Persist a single conversation turn (user or assistant)."""
    now = datetime.now(timezone.utc)

    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO messages (session_id, role, content, risk_tier, created_at)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id;""",
                    (session_id, role, content, risk_tier, now),
                )
                msg_id = cur.fetchone()[0]
                # Also keep therapy_messages in sync for backwards-compatibility
                try:
                    cur.execute(
                        """INSERT INTO therapy_messages (id, session_id, role, content, risk_tier, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;""",
                        (msg_id, session_id, role, content, risk_tier, now),
                    )
                except Exception:
                    pass
            pg_conn.commit()
            pg_conn.close()
            return msg_id
        except Exception as e:
            logger.error(f"PG save_therapy_message failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO messages (session_id, role, content, risk_tier, created_at)
               VALUES (?, ?, ?, ?, ?);""",
            (session_id, role, content, risk_tier, now.isoformat()),
        )
        msg_id = cur.lastrowid
        try:
            cur.execute(
                """INSERT OR IGNORE INTO therapy_messages (id, session_id, role, content, risk_tier, created_at)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (msg_id, session_id, role, content, risk_tier, now.isoformat()),
            )
        except Exception:
            pass
        conn.commit()
        conn.close()
        return msg_id
    except Exception as e:
        logger.error(f"SQLite save_therapy_message failed: {e}")
        return None


# Alias for save_therapy_message
save_message = save_therapy_message


def get_session_messages(
    session_id: int,
) -> List[dict]:
    """Retrieve all messages for a session, ordered chronologically."""
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """SELECT id, role, content, risk_tier, created_at
                       FROM messages WHERE session_id = %s
                       ORDER BY created_at ASC;""",
                    (session_id,),
                )
                rows = cur.fetchall()
            pg_conn.close()
            return [
                {"id": r[0], "role": r[1], "content": r[2], "risk_tier": r[3], "created_at": str(r[4])}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"PG get_session_messages failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, role, content, risk_tier, created_at
               FROM messages WHERE session_id = ?
               ORDER BY created_at ASC;""",
            (session_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "role": r[1], "content": r[2], "risk_tier": r[3], "created_at": r[4]}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"SQLite get_session_messages failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# SESSION SUMMARY CRUD
# ═══════════════════════════════════════════════════════════════════════

def save_session_summary(
    session_id: int,
    user_id: str,
    summary_text: str,
    concerns: Optional[list] = None,
    goals: Optional[list] = None,
    techniques_used: Optional[list] = None,
) -> Optional[int]:
    """Store a structured session summary for long-term memory."""
    now = datetime.now(timezone.utc)
    concerns_json = json.dumps(concerns) if concerns else None
    goals_json = json.dumps(goals) if goals else None
    techniques_json = json.dumps(techniques_used) if techniques_used else None

    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO session_summaries
                       (session_id, user_id, summary_text, concerns, goals, techniques_used, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;""",
                    (session_id, user_id, summary_text, concerns_json, goals_json, techniques_json, now),
                )
                summary_id = cur.fetchone()[0]
            pg_conn.commit()
            pg_conn.close()
            return summary_id
        except Exception as e:
            logger.error(f"PG save_session_summary failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO session_summaries
               (session_id, user_id, summary_text, concerns, goals, techniques_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            (session_id, user_id, summary_text, concerns_json, goals_json, techniques_json, now.isoformat()),
        )
        summary_id = cur.lastrowid
        conn.commit()
        conn.close()
        return summary_id
    except Exception as e:
        logger.error(f"SQLite save_session_summary failed: {e}")
        return None


def get_recent_session_summaries(
    user_id: str,
    limit: int = 3,
) -> List[dict]:
    """
    Retrieve the most recent N session summaries for a user.
    Used to inject session memory context into LLM prompts.
    """
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """SELECT ss.id, ss.session_id, ss.summary_text, ss.concerns, ss.goals,
                              ss.techniques_used, ss.created_at, ts.mode
                       FROM session_summaries ss
                       JOIN therapy_sessions ts ON ts.id = ss.session_id
                       WHERE ss.user_id = %s
                       ORDER BY ss.created_at DESC LIMIT %s;""",
                    (user_id, limit),
                )
                rows = cur.fetchall()
            pg_conn.close()
            return [
                {
                    "id": r[0], "session_id": r[1], "summary_text": r[2],
                    "concerns": _parse_json(r[3]),
                    "goals": _parse_json(r[4]),
                    "techniques_used": _parse_json(r[5]),
                    "created_at": str(r[6]), "mode": r[7],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"PG get_recent_session_summaries failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT ss.id, ss.session_id, ss.summary_text, ss.concerns, ss.goals,
                      ss.techniques_used, ss.created_at, ts.mode
               FROM session_summaries ss
               JOIN therapy_sessions ts ON ts.id = ss.session_id
               WHERE ss.user_id = ?
               ORDER BY ss.created_at DESC LIMIT ?;""",
            (user_id, limit),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "session_id": r[1], "summary_text": r[2],
                "concerns": _parse_json(r[3]),
                "goals": _parse_json(r[4]),
                "techniques_used": _parse_json(r[5]),
                "created_at": r[6], "mode": r[7],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"SQLite get_recent_session_summaries failed: {e}")
        return []


def get_all_user_sessions(
    user_id: str,
) -> List[dict]:
    """
    Retrieve all therapy sessions (with summaries) for a user.
    Used by the /insights page to display session history.
    """
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """SELECT ts.id, ts.mode, ts.started_at, ts.ended_at, ts.objective,
                              ss.summary_text, ss.concerns, ss.goals, ss.techniques_used
                       FROM therapy_sessions ts
                       LEFT JOIN session_summaries ss ON ss.session_id = ts.id
                       WHERE ts.user_id = %s
                       ORDER BY ts.started_at DESC;""",
                    (user_id,),
                )
                rows = cur.fetchall()
            pg_conn.close()
            return [
                {
                    "id": r[0],
                    "session_id": r[0],
                    "mode": r[1],
                    "started_at": str(r[2]),
                    "ended_at": str(r[3]) if r[3] else None,
                    "objective": r[4],
                    "summary_text": r[5],
                    "concerns": _parse_json(r[6]),
                    "goals": _parse_json(r[7]),
                    "techniques_used": _parse_json(r[8]),
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"PG get_all_user_sessions failed: {e}")
            if pg_conn:
                pg_conn.close()

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT ts.id, ts.mode, ts.started_at, ts.ended_at, ts.objective,
                      ss.summary_text, ss.concerns, ss.goals, ss.techniques_used
               FROM therapy_sessions ts
               LEFT JOIN session_summaries ss ON ss.session_id = ts.id
               WHERE ts.user_id = ?
               ORDER BY ts.started_at DESC;""",
            (user_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "session_id": r[0],
                "mode": r[1],
                "started_at": r[2],
                "ended_at": r[3],
                "objective": r[4],
                "summary_text": r[5],
                "concerns": _parse_json(r[6]),
                "goals": _parse_json(r[7]),
                "techniques_used": _parse_json(r[8]),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"SQLite get_all_user_sessions failed: {e}")
        return []

