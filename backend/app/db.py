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
from typing import Optional, List, Any, Dict

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
    safety_flag BOOLEAN DEFAULT FALSE,
    q9_score INTEGER DEFAULT 0,
    follow_up_data JSONB DEFAULT '{}'::jsonb,
    llm_summary TEXT DEFAULT '',
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
    safety_flag INTEGER DEFAULT 0,
    q9_score INTEGER DEFAULT 0,
    follow_up_data TEXT DEFAULT '{}',
    llm_summary TEXT DEFAULT '',
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


_pg_available: Optional[bool] = None
_pg_pool = None  # psycopg2.pool.ThreadedConnectionPool when available


def init_pg_pool(minconn: int = 1, maxconn: int = 10) -> bool:
    """Initialize a thread-safe PostgreSQL connection pool.

    Returns True if pool was created, False otherwise.
    Called by init_db() and optionally by FastAPI lifespan.
    """
    global _pg_pool, _pg_available
    if not DATABASE_URL or "postgresql" not in DATABASE_URL:
        return False
    try:
        from psycopg2.pool import ThreadedConnectionPool
        _pg_pool = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL, connect_timeout=3)
        _pg_available = True
        logger.info(f"PostgreSQL connection pool initialized (min={minconn}, max={maxconn})")
        return True
    except Exception as e:
        logger.warning(f"Connection pool init failed: {e}")
        _pg_pool = None
        _pg_available = False
        return False


def close_pg_pool():
    """Close all connections in the pool. Called on application shutdown."""
    global _pg_pool
    if _pg_pool is not None:
        try:
            _pg_pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.warning(f"Error closing pool: {e}")
        _pg_pool = None


def _get_pg_connection():
    """Get a PostgreSQL connection from the pool, or create one directly.

    If a pool is available, checks out a connection (must be returned via putconn).
    Otherwise falls back to a direct per-request connection.
    """
    global _pg_available
    if _pg_available is False or not DATABASE_URL:
        return None

    # Try pool first
    if _pg_pool is not None:
        try:
            conn = _pg_pool.getconn()
            _pg_available = True
            return conn
        except Exception as e:
            logger.debug(f"Pool checkout failed: {e}")

    # Fallback to direct connection
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=2)
        _pg_available = True
        return conn
    except Exception as e:
        logger.debug(f"PostgreSQL connection unavailable: {e}")
        _pg_available = False
        return None


def _put_pg_connection(conn):
    """Return a PostgreSQL connection to the pool, or close it if no pool."""
    if conn is None:
        return
    if _pg_pool is not None:
        try:
            _pg_pool.putconn(conn)
            return
        except Exception:
            pass
    # No pool or putconn failed — close directly
    try:
        conn.close()
    except Exception:
        pass


def _get_sqlite_connection():
    """Create or connect to local SQLite database file, auto-creating table if needed."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=5.0)
    conn.executescript(SQLITE_TABLE_SQL)
    conn.commit()
    return conn


def _migrate_assessment_table_sqlite(conn: sqlite3.Connection):
    """Ensure assessment_attempts table in SQLite has all upgraded columns."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(assessment_attempts);")
        cols = {row[1] for row in cur.fetchall()}
        if "safety_flag" not in cols:
            cur.execute("ALTER TABLE assessment_attempts ADD COLUMN safety_flag INTEGER DEFAULT 0;")
        if "q9_score" not in cols:
            cur.execute("ALTER TABLE assessment_attempts ADD COLUMN q9_score INTEGER DEFAULT 0;")
        if "follow_up_data" not in cols:
            cur.execute("ALTER TABLE assessment_attempts ADD COLUMN follow_up_data TEXT DEFAULT '{}';")
        if "llm_summary" not in cols:
            cur.execute("ALTER TABLE assessment_attempts ADD COLUMN llm_summary TEXT DEFAULT '';")
        conn.commit()
    except Exception as e:
        logger.warning(f"SQLite assessment table migration note: {e}")


def _migrate_assessment_table_pg(cur):
    """Ensure assessment_attempts table in PostgreSQL has all upgraded columns."""
    try:
        cur.execute("""
            ALTER TABLE assessment_attempts ADD COLUMN IF NOT EXISTS safety_flag BOOLEAN DEFAULT FALSE;
            ALTER TABLE assessment_attempts ADD COLUMN IF NOT EXISTS q9_score INTEGER DEFAULT 0;
            ALTER TABLE assessment_attempts ADD COLUMN IF NOT EXISTS follow_up_data JSONB DEFAULT '{}'::jsonb;
            ALTER TABLE assessment_attempts ADD COLUMN IF NOT EXISTS llm_summary TEXT DEFAULT '';
        """)
    except Exception as e:
        logger.warning(f"PostgreSQL assessment table migration note: {e}")


def _migrate_therapy_sessions_sqlite(conn: sqlite3.Connection):
    """Ensure therapy_sessions table in SQLite has session-state tracking columns."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(therapy_sessions);")
        cols = {row[1] for row in cur.fetchall()}
        fields = {
            "current_stage": "TEXT DEFAULT 'opening'",
            "main_concern": "TEXT DEFAULT ''",
            "user_goal": "TEXT DEFAULT ''",
            "emotions_expressed": "TEXT DEFAULT '[]'",
            "thoughts_beliefs": "TEXT DEFAULT '[]'",
            "patterns_explored": "TEXT DEFAULT '[]'",
            "interventions_used": "TEXT DEFAULT '[]'",
            "next_steps": "TEXT DEFAULT '[]'",
            "safety_status": "TEXT DEFAULT 'safe'",
            "session_notes": "TEXT DEFAULT '{}'",
        }
        for col_name, col_def in fields.items():
            if col_name not in cols:
                cur.execute(f"ALTER TABLE therapy_sessions ADD COLUMN {col_name} {col_def};")
        conn.commit()
    except Exception as e:
        logger.warning(f"SQLite therapy_sessions migration note: {e}")


def _migrate_therapy_sessions_pg(cur):
    """Ensure therapy_sessions table in PostgreSQL has session-state tracking columns."""
    try:
        cur.execute("""
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS current_stage VARCHAR(50) DEFAULT 'opening';
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS main_concern TEXT DEFAULT '';
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS user_goal TEXT DEFAULT '';
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS emotions_expressed JSONB DEFAULT '[]'::jsonb;
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS thoughts_beliefs JSONB DEFAULT '[]'::jsonb;
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS patterns_explored JSONB DEFAULT '[]'::jsonb;
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS interventions_used JSONB DEFAULT '[]'::jsonb;
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS next_steps JSONB DEFAULT '[]'::jsonb;
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS safety_status VARCHAR(50) DEFAULT 'safe';
            ALTER TABLE therapy_sessions ADD COLUMN IF NOT EXISTS session_notes JSONB DEFAULT '{}'::jsonb;
        """)
    except Exception as e:
        logger.warning(f"PostgreSQL therapy_sessions migration note: {e}")


def _migrate_therapy_messages_sqlite(conn: sqlite3.Connection):
    """Ensure any legacy messages are consolidated into therapy_messages."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
        if cur.fetchone():
            cur.execute("""
                INSERT OR IGNORE INTO therapy_messages (id, session_id, role, content, risk_tier, created_at)
                SELECT id, session_id, role, content, risk_tier, created_at FROM messages;
            """)
            conn.commit()
    except Exception as e:
        logger.warning(f"SQLite therapy_messages migration note: {e}")


def _migrate_therapy_messages_pg(cur):
    """Ensure any legacy messages are consolidated into therapy_messages."""
    try:
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'messages') THEN
                    INSERT INTO therapy_messages (id, session_id, role, content, risk_tier, created_at)
                    SELECT id, session_id, role, content, risk_tier, created_at FROM messages
                    ON CONFLICT (id) DO NOTHING;
                END IF;
            END $$;
        """)
    except Exception as e:
        logger.warning(f"PostgreSQL therapy_messages migration note: {e}")


def init_db():
    """Initialize database tables for PostgreSQL or local SQLite."""
    global _pg_available
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(PG_TABLE_SQL)
                _migrate_assessment_table_pg(cur)
                _migrate_therapy_sessions_pg(cur)
                _migrate_therapy_messages_pg(cur)
            pg_conn.commit()
            _put_pg_connection(pg_conn)
            _pg_available = True
            logger.info("Connected to PostgreSQL — all tables initialized.")
            return "postgresql"
        except Exception as e:
            logger.warning(f"PostgreSQL init failed: {e}. Falling back to SQLite.")
            _pg_available = False
            if pg_conn:
                try:
                    _put_pg_connection(pg_conn)
                except Exception:
                    pass

    # Fallback to SQLite
    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.executescript(SQLITE_TABLE_SQL)
        _migrate_assessment_table_sqlite(conn)
        _migrate_therapy_sessions_sqlite(conn)
        _migrate_therapy_messages_sqlite(conn)
        conn.commit()
        conn.close()
        _pg_available = False
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
    safety_flag: bool = False,
    q9_score: Optional[int] = None,
    follow_up_data: Optional[Dict[str, Any]] = None,
    llm_summary: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> Optional[int]:
    """
    Save assessment to PostgreSQL if available, otherwise to local SQLite database.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    follow_up_json = json.dumps(follow_up_data or {})
    summary_str = llm_summary or ""
    q9_val = q9_score if q9_score is not None else 0

    # 1. Try PostgreSQL
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assessment_attempts (
                        user_id, test_type, responses, total_score, severity_band, risk_tier,
                        safety_flag, q9_score, follow_up_data, llm_summary, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
                        test_type,
                        json.dumps(responses),
                        total_score,
                        severity_band,
                        risk_tier,
                        safety_flag,
                        q9_val,
                        follow_up_json,
                        summary_str,
                        timestamp,
                    ),
                )
                inserted_id = cur.fetchone()[0]
            pg_conn.commit()
            _put_pg_connection(pg_conn)
            return inserted_id
        except Exception as e:
            logger.error(f"PostgreSQL insert failed: {e}. Falling back to SQLite.")
            if pg_conn:
                _put_pg_connection(pg_conn)

    # 2. Fallback to SQLite (built-in, zero config)
    try:
        conn = _get_sqlite_connection()
        _migrate_assessment_table_sqlite(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO assessment_attempts (
                user_id, test_type, responses, total_score, severity_band, risk_tier,
                safety_flag, q9_score, follow_up_data, llm_summary, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                test_type,
                json.dumps(responses),
                total_score,
                severity_band,
                risk_tier,
                1 if safety_flag else 0,
                q9_val,
                follow_up_json,
                summary_str,
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


def get_user_assessment_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve user's historical self-assessment attempts for progress tracking.
    Ordered newest to oldest.
    """
    results: List[Dict[str, Any]] = []

    # 1. Try PostgreSQL
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, test_type, responses, total_score, severity_band, risk_tier,
                           safety_flag, q9_score, follow_up_data, llm_summary, timestamp
                    FROM assessment_attempts
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s;
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "user_id": row[1],
                        "test_type": row[2],
                        "responses": _parse_json(row[3]),
                        "total_score": row[4],
                        "max_score": 27 if row[2].lower().startswith("phq") else 21,
                        "severity_band": row[5],
                        "risk_tier": row[6],
                        "safety_flag": bool(row[7]),
                        "q9_score": row[8] or 0,
                        "follow_up_data": _parse_json(row[9]),
                        "llm_summary": row[10] or "",
                        "timestamp": row[11].isoformat() if hasattr(row[11], "isoformat") else str(row[11]),
                    })
            _put_pg_connection(pg_conn)
            return results
        except Exception as e:
            logger.error(f"PostgreSQL fetch history failed: {e}. Falling back to SQLite.")
            if pg_conn:
                _put_pg_connection(pg_conn)

    # 2. SQLite fallback
    try:
        conn = _get_sqlite_connection()
        _migrate_assessment_table_sqlite(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, test_type, responses, total_score, severity_band, risk_tier,
                   safety_flag, q9_score, follow_up_data, llm_summary, timestamp
            FROM assessment_attempts
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?;
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
        for row in rows:
            results.append({
                "id": row[0],
                "user_id": row[1],
                "test_type": row[2],
                "responses": _parse_json(row[3]),
                "total_score": row[4],
                "max_score": 27 if row[2].lower().startswith("phq") else 21,
                "severity_band": row[5],
                "risk_tier": row[6],
                "safety_flag": bool(row[7]),
                "q9_score": row[8] or 0,
                "follow_up_data": _parse_json(row[9]),
                "llm_summary": row[10] or "",
                "timestamp": str(row[11]),
            })
        conn.close()
        return results
    except Exception as e:
        logger.error(f"SQLite fetch assessment history failed: {e}")
        return []


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
            _put_pg_connection(pg_conn)
            return session_id
        except Exception as e:
            logger.error(f"PG create_therapy_session failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

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
            _put_pg_connection(pg_conn)
            return True
        except Exception as e:
            logger.error(f"PG end_therapy_session failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

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


def get_therapy_session(session_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full therapy session details including current stage and tracking state."""
    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """SELECT id, user_id, mode, started_at, ended_at, objective,
                              current_stage, main_concern, user_goal, emotions_expressed,
                              thoughts_beliefs, patterns_explored, interventions_used,
                              next_steps, safety_status, session_notes
                       FROM therapy_sessions WHERE id = %s;""",
                    (session_id,),
                )
                r = cur.fetchone()
            _put_pg_connection(pg_conn)
            if r:
                return {
                    "id": r[0], "user_id": r[1], "mode": r[2],
                    "started_at": str(r[3]), "ended_at": str(r[4]) if r[4] else None,
                    "objective": r[5], "current_stage": r[6] or "opening",
                    "main_concern": r[7] or "", "user_goal": r[8] or "",
                    "emotions_expressed": _parse_json(r[9]),
                    "thoughts_beliefs": _parse_json(r[10]),
                    "patterns_explored": _parse_json(r[11]),
                    "interventions_used": _parse_json(r[12]),
                    "next_steps": _parse_json(r[13]),
                    "safety_status": r[14] or "safe",
                    "session_notes": _parse_json(r[15]),
                }
            return None
        except Exception as e:
            logger.error(f"PG get_therapy_session failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

    try:
        conn = _get_sqlite_connection()
        _migrate_therapy_sessions_sqlite(conn)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_id, mode, started_at, ended_at, objective,
                      current_stage, main_concern, user_goal, emotions_expressed,
                      thoughts_beliefs, patterns_explored, interventions_used,
                      next_steps, safety_status, session_notes
               FROM therapy_sessions WHERE id = ?;""",
            (session_id,),
        )
        r = cur.fetchone()
        conn.close()
        if r:
            return {
                "id": r[0], "user_id": r[1], "mode": r[2],
                "started_at": str(r[3]), "ended_at": str(r[4]) if r[4] else None,
                "objective": r[5], "current_stage": r[6] or "opening",
                "main_concern": r[7] or "", "user_goal": r[8] or "",
                "emotions_expressed": _parse_json(r[9]),
                "thoughts_beliefs": _parse_json(r[10]),
                "patterns_explored": _parse_json(r[11]),
                "interventions_used": _parse_json(r[12]),
                "next_steps": _parse_json(r[13]),
                "safety_status": r[14] or "safe",
                "session_notes": _parse_json(r[15]),
            }
        return None
    except Exception as e:
        logger.error(f"SQLite get_therapy_session failed: {e}")
        return None


def update_therapy_session_state(session_id: int, **kwargs) -> bool:
    """Update structured state fields on a therapy session."""
    valid_fields = {
        "current_stage", "main_concern", "user_goal", "emotions_expressed",
        "thoughts_beliefs", "patterns_explored", "interventions_used",
        "next_steps", "safety_status", "session_notes", "objective",
    }
    updates = {}
    for k, v in kwargs.items():
        if k in valid_fields:
            if isinstance(v, (list, dict)):
                updates[k] = json.dumps(v)
            else:
                updates[k] = v

    if not updates:
        return True

    pg_conn = _get_pg_connection()
    if pg_conn:
        try:
            set_clauses = [f"{k} = %s" for k in updates.keys()]
            values = list(updates.values()) + [session_id]
            sql = f"UPDATE therapy_sessions SET {', '.join(set_clauses)} WHERE id = %s;"
            with pg_conn.cursor() as cur:
                cur.execute(sql, tuple(values))
            pg_conn.commit()
            _put_pg_connection(pg_conn)
            return True
        except Exception as e:
            logger.error(f"PG update_therapy_session_state failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

    try:
        conn = _get_sqlite_connection()
        _migrate_therapy_sessions_sqlite(conn)
        cur = conn.cursor()
        set_clauses = [f"{k} = ?" for k in updates.keys()]
        values = list(updates.values()) + [session_id]
        sql = f"UPDATE therapy_sessions SET {', '.join(set_clauses)} WHERE id = ?;"
        cur.execute(sql, tuple(values))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"SQLite update_therapy_session_state failed: {e}")
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
                    """INSERT INTO therapy_messages (session_id, role, content, risk_tier, created_at)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id;""",
                    (session_id, role, content, risk_tier, now),
                )
                msg_id = cur.fetchone()[0]
            pg_conn.commit()
            _put_pg_connection(pg_conn)
            return msg_id
        except Exception as e:
            logger.error(f"PG save_therapy_message failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO therapy_messages (session_id, role, content, risk_tier, created_at)
               VALUES (?, ?, ?, ?, ?);""",
            (session_id, role, content, risk_tier, now.isoformat()),
        )
        msg_id = cur.lastrowid
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
                       FROM therapy_messages WHERE session_id = %s
                       ORDER BY created_at ASC;""",
                    (session_id,),
                )
                rows = cur.fetchall()
            _put_pg_connection(pg_conn)
            return [
                {"id": r[0], "role": r[1], "content": r[2], "risk_tier": r[3], "created_at": str(r[4])}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"PG get_session_messages failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

    try:
        conn = _get_sqlite_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, role, content, risk_tier, created_at
               FROM therapy_messages WHERE session_id = ?
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
            _put_pg_connection(pg_conn)
            return summary_id
        except Exception as e:
            logger.error(f"PG save_session_summary failed: {e}")
            if pg_conn:
                _put_pg_connection(pg_conn)

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
            _put_pg_connection(pg_conn)
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
                _put_pg_connection(pg_conn)

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
            _put_pg_connection(pg_conn)
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
                _put_pg_connection(pg_conn)

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

