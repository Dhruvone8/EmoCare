"""
Database helper for EmoCare self-assessment attempts.

Supports:
1. PostgreSQL (production / Docker) via psycopg2 if configured and running.
2. Built-in SQLite local file fallback (zero configuration needed) saved to `data/assessments.db`.
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Any

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
            logger.info("Connected to PostgreSQL — assessment table initialized.")
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
