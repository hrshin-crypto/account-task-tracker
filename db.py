"""
db.py — SQLite schema and helper functions for Account Task Tracker
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "tracker.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT UNIQUE NOT NULL,
            name       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            name          TEXT NOT NULL,
            track_name    TEXT,
            grade         TEXT,
            contact_email TEXT,
            contact_name  TEXT,
            funnel        TEXT,
            sheet_key     TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS parent_tasks (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL REFERENCES users(id),
            title          TEXT NOT NULL,
            description    TEXT,
            due_date       TEXT,
            status         TEXT DEFAULT 'active',
            kanban_status  TEXT DEFAULT 'planned',
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS account_tasks (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_task_id INTEGER NOT NULL REFERENCES parent_tasks(id) ON DELETE CASCADE,
            account_id     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            user_id        INTEGER NOT NULL REFERENCES users(id),
            status         TEXT DEFAULT 'not_started',
            due_date       TEXT,
            note           TEXT,
            alerted_d3     INTEGER DEFAULT 0,
            alerted_d1     INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now')),
            updated_at     TEXT DEFAULT (datetime('now')),
            UNIQUE(parent_task_id, account_id)
        );

        CREATE TABLE IF NOT EXISTS alert_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_task_id INTEGER NOT NULL REFERENCES account_tasks(id),
            alert_type      TEXT NOT NULL,
            sent_at         TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS task_candidates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            source      TEXT NOT NULL,
            source_ref  TEXT,
            raw_text    TEXT,
            title       TEXT NOT NULL,
            account_ids TEXT DEFAULT '[]',
            eta         TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Users ─────────────────────────────────────────────────────────────────────

def get_or_create_user(email: str, name: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        conn.close()
        return row["id"]
    c = conn.execute("INSERT INTO users (email, name) VALUES (?,?)", (email, name))
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid


# ── Accounts ──────────────────────────────────────────────────────────────────

def create_account(user_id, name, track_name=None, grade=None, contact_email=None,
                   contact_name=None, funnel=None, sheet_key=None) -> int:
    conn = get_conn()
    c = conn.execute(
        """INSERT INTO accounts (user_id, name, track_name, grade, contact_email,
               contact_name, funnel, sheet_key) VALUES (?,?,?,?,?,?,?,?)""",
        (user_id, name, track_name, grade, contact_email, contact_name, funnel, sheet_key)
    )
    conn.commit()
    aid = c.lastrowid
    conn.close()
    return aid


def delete_account(account_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.commit()
    conn.close()


def list_accounts(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM accounts WHERE user_id=? ORDER BY track_name, name", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Parent tasks ──────────────────────────────────────────────────────────────

def create_parent_task(user_id, title, description="", due_date=None) -> int:
    conn = get_conn()
    c = conn.execute(
        "INSERT INTO parent_tasks (user_id, title, description, due_date) VALUES (?,?,?,?)",
        (user_id, title, description, due_date)
    )
    conn.commit()
    tid = c.lastrowid
    conn.close()
    return tid


def delete_parent_task(task_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM parent_tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def list_parent_tasks(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM parent_tasks WHERE user_id=? AND status!='archived' ORDER BY due_date",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Account tasks ─────────────────────────────────────────────────────────────

def upsert_account_task(parent_task_id, account_id, user_id, due_date=None) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM account_tasks WHERE parent_task_id=? AND account_id=?",
        (parent_task_id, account_id)
    ).fetchone()
    if row:
        conn.close()
        return row["id"]
    c = conn.execute(
        "INSERT INTO account_tasks (parent_task_id, account_id, user_id, due_date) VALUES (?,?,?,?)",
        (parent_task_id, account_id, user_id, due_date)
    )
    conn.commit()
    atid = c.lastrowid
    conn.close()
    return atid


def update_account_task(at_id: int, status: str = None, note: str = None, due_date: str = None):
    conn = get_conn()
    if status is not None:
        conn.execute(
            "UPDATE account_tasks SET status=?, note=?, updated_at=datetime('now') WHERE id=?",
            (status, note, at_id)
        )
    if due_date is not None:
        conn.execute(
            "UPDATE account_tasks SET due_date=?, updated_at=datetime('now') WHERE id=?",
            (due_date, at_id)
        )
    conn.commit()
    conn.close()


def get_full_matrix(user_id: int) -> dict:
    conn = get_conn()
    tasks = [dict(r) for r in conn.execute(
        "SELECT * FROM parent_tasks WHERE user_id=? AND status!='archived' ORDER BY due_date",
        (user_id,)
    ).fetchall()]
    accounts = [dict(r) for r in conn.execute(
        "SELECT * FROM accounts WHERE user_id=? ORDER BY track_name, name", (user_id,)
    ).fetchall()]
    cells = conn.execute(
        "SELECT * FROM account_tasks WHERE user_id=?", (user_id,)
    ).fetchall()
    conn.close()

    cell_map = {f"{c['account_id']}_{c['parent_task_id']}": dict(c) for c in cells}
    return {"tasks": tasks, "accounts": accounts, "cell_map": cell_map}


def get_upcoming_tasks(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT at.id, at.due_date, at.status, at.alerted_d3, at.alerted_d1,
               a.name AS account_name, pt.title AS task_title
        FROM account_tasks at
        JOIN accounts a ON a.id = at.account_id
        JOIN parent_tasks pt ON pt.id = at.parent_task_id
        WHERE at.user_id=? AND at.due_date IS NOT NULL AND at.status NOT IN ('done','na')
        ORDER BY at.due_date
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_alert_sent(account_task_id: int, alert_type: str):
    conn = get_conn()
    if alert_type == "d3":
        conn.execute("UPDATE account_tasks SET alerted_d3=1 WHERE id=?", (account_task_id,))
    elif alert_type == "d1":
        conn.execute("UPDATE account_tasks SET alerted_d1=1 WHERE id=?", (account_task_id,))
    conn.execute(
        "INSERT INTO alert_log (account_task_id, alert_type) VALUES (?,?)",
        (account_task_id, alert_type)
    )
    conn.commit()
    conn.close()


# ── Task candidates (inbox) ───────────────────────────────────────────────────

def add_candidate(user_id: int, source: str, title: str,
                  raw_text: str = "", account_ids=None, eta: str = None,
                  source_ref: str = None) -> int:
    import json
    conn = get_conn()
    c = conn.execute(
        """INSERT INTO task_candidates (user_id, source, source_ref, raw_text, title, account_ids, eta)
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, source, source_ref, raw_text, title,
         json.dumps(account_ids or []), eta)
    )
    conn.commit()
    cid = c.lastrowid
    conn.close()
    return cid


def list_candidates(user_id: int, status: str = "pending") -> list:
    import json
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM task_candidates WHERE user_id=? AND status=? ORDER BY created_at DESC",
        (user_id, status)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["account_ids"] = json.loads(d.get("account_ids") or "[]")
        except Exception:
            d["account_ids"] = []
        result.append(d)
    return result


def update_candidate(cid: int, title: str = None, account_ids=None,
                     eta: str = None, status: str = None):
    import json
    conn = get_conn()
    if title is not None:
        conn.execute("UPDATE task_candidates SET title=? WHERE id=?", (title, cid))
    if account_ids is not None:
        conn.execute("UPDATE task_candidates SET account_ids=? WHERE id=?",
                     (json.dumps(account_ids), cid))
    if eta is not None:
        conn.execute("UPDATE task_candidates SET eta=? WHERE id=?", (eta, cid))
    if status is not None:
        conn.execute("UPDATE task_candidates SET status=? WHERE id=?", (status, cid))
    conn.commit()
    conn.close()


def confirm_candidate(cid: int, user_id: int) -> int:
    """Promote candidate → parent task + account_tasks. Returns new task id."""
    import json
    conn = get_conn()
    row = conn.execute("SELECT * FROM task_candidates WHERE id=?", (cid,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"candidate {cid} not found")
    row = dict(row)
    try:
        account_ids = json.loads(row.get("account_ids") or "[]")
    except Exception:
        account_ids = []

    c = conn.execute(
        "INSERT INTO parent_tasks (user_id, title, due_date) VALUES (?,?,?)",
        (user_id, row["title"], row["eta"])
    )
    tid = c.lastrowid
    for aid in account_ids:
        conn.execute(
            "INSERT OR IGNORE INTO account_tasks (parent_task_id, account_id, user_id) VALUES (?,?,?)",
            (tid, aid, user_id)
        )
    conn.execute("UPDATE task_candidates SET status='confirmed' WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return tid


def update_parent_task_kanban(task_id: int, kanban_status: str):
    conn = get_conn()
    conn.execute(
        "UPDATE parent_tasks SET kanban_status=?, updated_at=datetime('now') WHERE id=?",
        (kanban_status, task_id)
    )
    conn.commit()
    conn.close()


def migrate_db():
    """Add new columns to existing DB if not present."""
    conn = get_conn()
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    for col, typedef in [("contact_name", "TEXT"), ("funnel", "TEXT"), ("sheet_key", "TEXT")]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE accounts ADD COLUMN {col} {typedef}")
    task_cols = {row[1] for row in conn.execute("PRAGMA table_info(parent_tasks)").fetchall()}
    if "kanban_status" not in task_cols:
        conn.execute("ALTER TABLE parent_tasks ADD COLUMN kanban_status TEXT DEFAULT 'planned'")
    # task_candidates table (may not exist on older DBs)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_candidates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            source      TEXT NOT NULL,
            source_ref  TEXT,
            raw_text    TEXT,
            title       TEXT NOT NULL,
            account_ids TEXT DEFAULT '[]',
            eta         TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("DB initialized:", DB_PATH)
