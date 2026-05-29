"""
sheets_sync.py — Sync companies from Google Sheets '참여기업 관리' tab
Excludes funnel values: 결렬, 드랍, 보류
"""

import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread

load_dotenv()

SHEET_ID      = '1klfoCm44AwxJFkz9mRQHCRWrTC_ONmh9RD7JlR1mP_w'
WORKSHEET_IDX = 6
EXCLUDE       = {'결렬', '드랍', '보류'}

# Column indices (0-based), header on row index 2, data from row index 3
COL_TRACK   = 1
COL_NAME    = 2
COL_GRADE   = 4
COL_FUNNEL  = 10
COL_CONTACT = 11
COL_EMAIL   = 13


def _get_creds():
    import base64, tempfile, json as _json
    b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if b64:
        data = base64.b64decode(b64).decode()
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    return os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")


def fetch_companies() -> list[dict]:
    """Fetch filtered company list from sheet."""
    creds = Credentials.from_service_account_file(
        _get_creds(),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).get_worksheet(WORKSHEET_IDX)
    rows = ws.get_all_values()

    companies = []
    for row in rows[3:]:  # data starts row index 3
        name = row[COL_NAME].strip() if len(row) > COL_NAME else ""
        if not name:
            continue
        funnel = row[COL_FUNNEL].strip() if len(row) > COL_FUNNEL else ""
        if funnel in EXCLUDE:
            continue
        companies.append({
            "name":          name,
            "track_name":    row[COL_TRACK].strip() if len(row) > COL_TRACK else "",
            "grade":         row[COL_GRADE].strip() if len(row) > COL_GRADE else "",
            "contact_email": row[COL_EMAIL].strip() if len(row) > COL_EMAIL else "",
            "contact_name":  row[COL_CONTACT].strip() if len(row) > COL_CONTACT else "",
            "funnel":        funnel,
            "sheet_key":     f"{row[COL_TRACK].strip()}::{name}",
        })
    return companies


def sync_to_db(user_id: int) -> dict:
    """Upsert sheet companies into DB. Returns stats."""
    from db import get_conn, list_parent_tasks, upsert_account_task

    companies = fetch_companies()
    conn = get_conn()

    existing = {
        row["sheet_key"]: row
        for row in [
            dict(r) for r in conn.execute(
                "SELECT * FROM accounts WHERE user_id=?", (user_id,)
            ).fetchall()
        ]
        if row.get("sheet_key")
    }

    added = updated = 0
    synced_ids = []

    for c in companies:
        key = c["sheet_key"]
        if key in existing:
            conn.execute("""
                UPDATE accounts SET track_name=?, grade=?, contact_email=?,
                    contact_name=?, funnel=? WHERE id=?
            """, (c["track_name"], c["grade"], c["contact_email"],
                  c["contact_name"], c["funnel"], existing[key]["id"]))
            synced_ids.append(existing[key]["id"])
            updated += 1
        else:
            cur = conn.execute("""
                INSERT INTO accounts (user_id, name, track_name, grade, contact_email,
                    contact_name, funnel, sheet_key)
                VALUES (?,?,?,?,?,?,?,?)
            """, (user_id, c["name"], c["track_name"], c["grade"],
                  c["contact_email"], c["contact_name"], c["funnel"], key))
            synced_ids.append(cur.lastrowid)
            added += 1

    conn.commit()

    # Auto-create account_tasks for new accounts × existing parent tasks
    tasks = list_parent_tasks(user_id)
    for aid in synced_ids:
        for t in tasks:
            upsert_account_task(t["id"], aid, user_id)

    # Remove accounts no longer in sheet (funnel changed to excluded)
    sheet_keys = {c["sheet_key"] for c in companies}
    removed = 0
    for sk, row in existing.items():
        if sk not in sheet_keys:
            conn.execute("DELETE FROM accounts WHERE id=?", (row["id"],))
            removed += 1
    conn.commit()
    conn.close()

    return {"added": added, "updated": updated, "removed": removed, "total": len(companies)}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from db import init_db, get_or_create_user
    init_db()
    uid = get_or_create_user("hr.shin@teamsparta.co", "신해람")
    result = sync_to_db(uid)
    print(result)
