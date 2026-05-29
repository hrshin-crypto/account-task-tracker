"""
app.py — Flask backend for Account Task Tracker
Run: python app.py
"""

import os
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request, send_file
from dotenv import load_dotenv
from db import (
    init_db, migrate_db, get_or_create_user,
    create_account, delete_account, list_accounts,
    create_parent_task, delete_parent_task, list_parent_tasks,
    upsert_account_task, update_account_task, get_full_matrix, get_upcoming_tasks,
    update_parent_task_kanban,
    add_candidate, list_candidates, update_candidate, confirm_candidate,
)

load_dotenv()

app = Flask(__name__)

# initialized after _scheduler is defined (see bottom of file)

USER_EMAIL = os.environ.get("USER_EMAIL", "hr.shin@teamsparta.co")
USER_NAME  = os.environ.get("USER_NAME",  "신해람")


def uid():
    return get_or_create_user(USER_EMAIL, USER_NAME)


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_file("index.html")


# ── Accounts ──────────────────────────────────────────────────────────────────

@app.route("/api/accounts", methods=["GET"])
def api_list_accounts():
    return jsonify(list_accounts(uid()))


@app.route("/api/accounts", methods=["POST"])
def api_create_account():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    user_id = uid()
    aid = create_account(user_id, data["name"], data.get("track_name"),
                         data.get("grade"), data.get("contact_email"),
                         data.get("contact_name"))
    for t in list_parent_tasks(user_id):
        upsert_account_task(t["id"], aid, user_id)
    return jsonify({"id": aid}), 201


@app.route("/api/accounts/<int:aid>", methods=["DELETE"])
def api_delete_account(aid):
    delete_account(aid)
    return jsonify({"ok": True})


# ── Google Sheets Sync ────────────────────────────────────────────────────────

@app.route("/api/sync", methods=["POST"])
def api_sync():
    try:
        from sheets_sync import sync_to_db
        result = sync_to_db(uid())
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Parent tasks ──────────────────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    user_id = uid()
    tasks = list_parent_tasks(user_id)
    accounts = list_accounts(user_id)
    n = len(accounts)
    matrix_data = get_full_matrix(user_id)
    for t in tasks:
        done = sum(
            1 for a in accounts
            if matrix_data["cell_map"].get(f"{a['id']}_{t['id']}", {}).get("status") == "done"
        )
        t["done_count"]    = done
        t["account_count"] = n
        t["pct"]           = round(done / n * 100) if n else 0
        # sample cells for kanban preview (first 6)
        t["preview_cells"] = [
            {
                "account_name": a["name"],
                "status": matrix_data["cell_map"].get(f"{a['id']}_{t['id']}", {}).get("status", "not_started")
            }
            for a in accounts[:6]
        ]
    return jsonify(tasks)


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    user_id = uid()
    tid = create_parent_task(user_id, data["title"],
                              data.get("description", ""), data.get("due_date"))
    for a in list_accounts(user_id):
        upsert_account_task(tid, a["id"], user_id)
    return jsonify({"id": tid}), 201


@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
def api_delete_task(tid):
    delete_parent_task(tid)
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:tid>", methods=["PUT"])
def api_update_task(tid):
    data = request.json or {}
    from db import get_conn
    conn = get_conn()
    if "due_date" in data:
        conn.execute("UPDATE parent_tasks SET due_date=?, updated_at=datetime('now') WHERE id=?",
                     (data["due_date"] or None, tid))
    if "title" in data and data["title"]:
        conn.execute("UPDATE parent_tasks SET title=?, updated_at=datetime('now') WHERE id=?",
                     (data["title"], tid))
    if "description" in data:
        conn.execute("UPDATE parent_tasks SET description=?, updated_at=datetime('now') WHERE id=?",
                     (data["description"], tid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:tid>/kanban", methods=["PUT"])
def api_task_kanban(tid):
    data = request.json or {}
    update_parent_task_kanban(tid, data["kanban_status"])
    return jsonify({"ok": True})


# ── Matrix ────────────────────────────────────────────────────────────────────

@app.route("/api/matrix", methods=["GET"])
def api_matrix():
    return jsonify(get_full_matrix(uid()))


@app.route("/api/matrix/toggle", methods=["POST"])
def api_toggle():
    data = request.json or {}
    user_id = uid()
    at_id = upsert_account_task(data["task_id"], data["account_id"], user_id)
    update_account_task(at_id, status=data["status"])
    return jsonify({"ok": True, "at_id": at_id})


@app.route("/api/account_tasks/<int:at_id>", methods=["PUT"])
def api_update_at(at_id):
    data = request.json or {}
    update_account_task(at_id,
                        status=data.get("status"),
                        note=data.get("note"),
                        due_date=data.get("due_date"))
    return jsonify({"ok": True})


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.route("/api/upcoming", methods=["GET"])
def api_upcoming():
    return jsonify(get_upcoming_tasks(uid()))


@app.route("/api/alerts/run", methods=["POST"])
def api_run_alerts():
    try:
        from alert import send_alerts
        send_alerts()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Inbox (task candidates) ───────────────────────────────────────────────────

@app.route("/api/inbox", methods=["GET"])
def api_inbox_list():
    return jsonify(list_candidates(uid()))


@app.route("/api/inbox", methods=["POST"])
def api_inbox_add():
    data = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    cid = add_candidate(
        uid(), data.get("source", "manual"), data["title"],
        raw_text=data.get("raw_text", ""),
        account_ids=data.get("account_ids", []),
        eta=data.get("eta"),
        source_ref=data.get("source_ref"),
    )
    return jsonify({"id": cid}), 201


@app.route("/api/inbox/<int:cid>", methods=["PUT"])
def api_inbox_update(cid):
    data = request.json or {}
    update_candidate(cid,
                     title=data.get("title"),
                     account_ids=data.get("account_ids"),
                     eta=data.get("eta"))
    return jsonify({"ok": True})


@app.route("/api/inbox/<int:cid>/confirm", methods=["POST"])
def api_inbox_confirm(cid):
    data = request.json or {}
    user_id = uid()
    # apply any last-minute edits before confirming
    if data:
        update_candidate(cid,
                         title=data.get("title"),
                         account_ids=data.get("account_ids"),
                         eta=data.get("eta"))
    tid = confirm_candidate(cid, user_id)
    return jsonify({"ok": True, "task_id": tid})


@app.route("/api/inbox/<int:cid>", methods=["DELETE"])
def api_inbox_dismiss(cid):
    update_candidate(cid, status="dismissed")
    return jsonify({"ok": True})


@app.route("/api/inbox/scan", methods=["POST"])
def api_inbox_scan():
    """Trigger a manual inbox scan (called by the morning Claude Code schedule)."""
    try:
        from inbox import run_scan
        result = run_scan(uid())
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Background scheduler (daily 09:00 alert) ─────────────────────────────────

def _scheduler():
    import schedule
    schedule.every().day.at("09:00").do(_run_alert_job)
    while True:
        schedule.run_pending()
        time.sleep(60)


def _run_alert_job():
    try:
        from alert import send_alerts
        send_alerts()
        print(f"[{datetime.now():%H:%M}] 자동 알림 발송 완료")
    except Exception as e:
        print(f"[알림 오류] {e}")


init_db()
migrate_db()
threading.Thread(target=_scheduler, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server → http://0.0.0.0:{port}")
    print("ETA 알림: 매일 09:00 자동 발송")
    app.run(debug=False, host="0.0.0.0", port=port)
