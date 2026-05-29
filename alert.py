"""
alert.py — Send Slack alerts for approaching/overdue ETAs via Incoming Webhook
Run manually or triggered via /api/alerts/run endpoint
"""

import os
import sys
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from db import init_db, get_or_create_user, get_upcoming_tasks, mark_alert_sent

USER_EMAIL    = os.environ.get("USER_EMAIL", "hr.shin@teamsparta.co")
USER_NAME     = os.environ.get("USER_NAME",  "신해람")
WEBHOOK_URL   = os.environ.get("SLACK_WEBHOOK_URL", "")


def _post(text: str):
    if not WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL이 .env에 없어요. Slack Webhook URL을 설정해주세요.")
    r = requests.post(WEBHOOK_URL, json={"text": text}, timeout=10)
    r.raise_for_status()


def send_alerts():
    init_db()
    user_id = get_or_create_user(USER_EMAIL, USER_NAME)
    tasks = get_upcoming_tasks(user_id)
    today = date.today()

    sent = 0
    for t in tasks:
        due = date.fromisoformat(t["due_date"])
        days_left = (due - today).days

        if days_left == 3 and not t["alerted_d3"]:
            msg = f"📌 [{t['account_name']}] {t['task_title']} — 3일 후 마감"
            alert_type = "d3"
        elif days_left == 1 and not t["alerted_d1"]:
            msg = f"⚠️ [{t['account_name']}] {t['task_title']} — 내일 마감"
            alert_type = "d1"
        elif days_left < 0:
            overdue_days = abs(days_left)
            msg = f"🔴 [{t['account_name']}] {t['task_title']} — {overdue_days}일 초과"
            alert_type = "overdue"
        else:
            continue

        _post(msg)
        mark_alert_sent(t["id"], alert_type)
        print(f"  SENT: {msg}")
        sent += 1

    print(f"\n완료: {sent}건 발송 / {len(tasks)}건 검토")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    send_alerts()
