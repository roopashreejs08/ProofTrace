import json
import sqlite3
import time
import uuid

from contextlib import contextmanager

from .config import settings
from .schemas import Item


AGENTS = [
    "claim_extractor",
    "paper_finder",
    "retraction_checker",
    "evidence_analyst",
    "verification_agent",
]


SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    input_text TEXT,
    status TEXT,
    created_at REAL,
    report_json TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    investigation_id TEXT,
    agent TEXT,
    status TEXT,
    message TEXT,
    progress_done INTEGER DEFAULT 0,
    progress_total INTEGER DEFAULT 0,
    started_at REAL,
    finished_at REAL,
    PRIMARY KEY (investigation_id, agent)
);

CREATE TABLE IF NOT EXISTS items (
    id TEXT,
    investigation_id TEXT,
    position INTEGER,
    claim TEXT,
    citation_json TEXT,
    PRIMARY KEY (investigation_id, id)
);

CREATE TABLE IF NOT EXISTS findings (
    investigation_id TEXT,
    item_id TEXT,
    agent TEXT,
    data_json TEXT,
    PRIMARY KEY (investigation_id, item_id, agent)
);

CREATE TABLE IF NOT EXISTS api_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT,
    source TEXT,
    url TEXT,
    status INTEGER,
    ms INTEGER,
    cached INTEGER,
    ts REAL
);

CREATE TABLE IF NOT EXISTS http_cache (
    key TEXT PRIMARY KEY,
    body TEXT,
    ts REAL
);
"""


class Memory:

    def __init__(self, path=None):
        self.path = path or settings.db_path

        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")

        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---- Investigations ----

    def create_investigation(self, text):
        inv = uuid.uuid4().hex[:12]

        with self.conn() as c:
            c.execute(
                """
                INSERT INTO investigations
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (inv, text, "queued", time.time(), None, None),
            )

            for agent in AGENTS:
                c.execute(
                    """
                    INSERT INTO agent_runs
                    (investigation_id, agent, status, message)
                    VALUES (?, ?, ?, ?)
                    """,
                    (inv, agent, "waiting", ""),
                )

        return inv

    def get_input(self, inv):
        with self.conn() as c:
            row = c.execute(
                "SELECT input_text FROM investigations WHERE id=?",
                (inv,),
            ).fetchone()

            return row["input_text"] if row else None

    def set_status(self, inv, status, report=None, error=None):
        with self.conn() as c:
            c.execute(
                """
                UPDATE investigations
                SET status=?,
                    report_json=COALESCE(?, report_json),
                    error=?
                WHERE id=?
                """,
                (
                    status,
                    json.dumps(report) if report is not None else None,
                    error,
                    inv,
                ),
            )

    def update_agent(self, inv, agent, **fields):
        allowed = (
            "status",
            "message",
            "progress_done",
            "progress_total",
            "started_at",
            "finished_at",
        )

        keys = [key for key in fields if key in allowed]

        if not keys:
            return

        sql = (
            "UPDATE agent_runs SET "
            + ", ".join(key + "=?" for key in keys)
            + " WHERE investigation_id=? AND agent=?"
        )

        with self.conn() as c:
            c.execute(
                sql,
                [fields[key] for key in keys] + [inv, agent],
            )

    def get_investigation(self, inv):
        with self.conn() as c:

            row = c.execute(
                "SELECT * FROM investigations WHERE id=?",
                (inv,),
            ).fetchone()

            if not row:
                return None

            agents = [
                dict(agent)
                for agent in c.execute(
                    """
                    SELECT agent, status, message,
                           progress_done, progress_total,
                           started_at, finished_at
                    FROM agent_runs
                    WHERE investigation_id=?
                    """,
                    (inv,),
                )
            ]

            api = [
                dict(activity)
                for activity in c.execute(
                    """
                    SELECT source, url, status, ms, cached, ts
                    FROM api_log
                    WHERE investigation_id=?
                    ORDER BY id DESC
                    LIMIT 40
                    """,
                    (inv,),
                )
            ]

            count = c.execute(
                """
                SELECT COUNT(*) AS n
                FROM items
                WHERE investigation_id=?
                """,
                (inv,),
            ).fetchone()["n"]

        agents.sort(key=lambda a: AGENTS.index(a["agent"]))

        return {
            "id": inv,
            "status": row["status"],
            "created_at": row["created_at"],
            "error": row["error"],
            "citation_count": count,
            "agents": agents,
            "api_activity": api,
            "report": (
                json.loads(row["report_json"])
                if row["report_json"]
                else None
            ),
        }

    def list_investigations(self, limit=20):
        with self.conn() as c:
            rows = c.execute(
                """
                SELECT id, status, created_at,
                       substr(input_text, 1, 120) AS preview
                FROM investigations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    # ---- Items and findings (shared blackboard) ----

    def save_items(self, inv, items):
        with self.conn() as c:
            for position, item in enumerate(items):
                c.execute(
                    """
                    INSERT OR REPLACE INTO items
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        inv,
                        position,
                        item.claim,
                        item.citation.model_dump_json(),
                    ),
                )

    def get_items(self, inv):
        with self.conn() as c:
            rows = c.execute(
                """
                SELECT *
                FROM items
                WHERE investigation_id=?
                ORDER BY position
                """,
                (inv,),
            ).fetchall()

        return [
            Item(
                id=row["id"],
                claim=row["claim"],
                citation=json.loads(row["citation_json"]),
            )
            for row in rows
        ]

    def save_finding(self, inv, item_id, agent, data):
        with self.conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO findings
                VALUES (?, ?, ?, ?)
                """,
                (inv, item_id, agent, json.dumps(data)),
            )

    def get_findings(self, inv, agent):
        with self.conn() as c:
            rows = c.execute(
                """
                SELECT item_id, data_json
                FROM findings
                WHERE investigation_id=? AND agent=?
                """,
                (inv, agent),
            ).fetchall()

        return {
            row["item_id"]: json.loads(row["data_json"])
            for row in rows
        }

    # ---- API log and HTTP cache ----

    def log_api(self, inv, source, url, status, ms, cached):
        if not inv:
            return

        with self.conn() as c:
            c.execute(
                """
                INSERT INTO api_log
                (investigation_id, source, url, status, ms, cached, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inv,
                    source,
                    url,
                    status,
                    ms,
                    int(cached),
                    time.time(),
                ),
            )

    def cache_get(self, key, ttl_hours):
        with self.conn() as c:
            row = c.execute(
                """
                SELECT body, ts
                FROM http_cache
                WHERE key=?
                """,
                (key,),
            ).fetchone()

        if row and time.time() - row["ts"] < ttl_hours * 3600:
            return json.loads(row["body"])

        return None

    def cache_set(self, key, body):
        with self.conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO http_cache
                VALUES (?, ?, ?)
                """,
                (key, json.dumps(body), time.time()),
            )