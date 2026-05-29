"""
inbox.py — Morning scan: Slack + Notion + Gmail → Claude extracts task candidates
Called by POST /api/inbox/scan or run directly: python inbox.py
"""

import os
import json
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
APP_URL           = os.environ.get("APP_URL", "http://localhost:5000")

SLACK_USER_TOKEN  = os.environ.get("SLACK_USER_TOKEN", "")   # xoxp-... for reading
NOTION_TOKEN      = os.environ.get("NOTION_TOKEN", "")
GMAIL_CREDS       = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")


# ── Source readers ────────────────────────────────────────────────────────────

def read_slack_mentions() -> list[dict]:
    """Fetch recent Slack messages mentioning the user (last 24h)."""
    if not SLACK_USER_TOKEN:
        return []
    try:
        from slack_sdk import WebClient
        client = WebClient(token=SLACK_USER_TOKEN)
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d")
        res = client.search_messages(query=f"after:{since}", count=20)
        messages = res.get("messages", {}).get("matches", [])
        return [
            {
                "source": "slack",
                "source_ref": m.get("permalink", ""),
                "raw_text": m.get("text", ""),
                "author": m.get("username", ""),
            }
            for m in messages
        ]
    except Exception as e:
        print(f"[Slack scan 오류] {e}")
        return []


def read_notion_assigned() -> list[dict]:
    """Fetch Notion pages/tasks assigned to or mentioning the user (last 7 days)."""
    if not NOTION_TOKEN:
        return []
    try:
        from notion_client import Client
        notion = Client(auth=NOTION_TOKEN)
        since = (datetime.now() - timedelta(days=7)).isoformat()
        results = notion.search(
            filter={"value": "page", "property": "object"},
            sort={"direction": "descending", "timestamp": "last_edited_time"},
        ).get("results", [])
        items = []
        for page in results[:10]:
            title_prop = page.get("properties", {}).get("title") or \
                         page.get("properties", {}).get("Name") or \
                         page.get("properties", {}).get("이름")
            title = ""
            if title_prop:
                for t in title_prop.get("title", []):
                    title += t.get("plain_text", "")
            if not title:
                continue
            items.append({
                "source": "notion",
                "source_ref": page.get("url", ""),
                "raw_text": title,
                "author": "",
            })
        return items
    except Exception as e:
        print(f"[Notion scan 오류] {e}")
        return []


def read_gmail_recent() -> list[dict]:
    """Fetch recent unread Gmail threads (last 24h)."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_service_account_file(
            GMAIL_CREDS,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            subject=os.environ.get("USER_EMAIL", ""),
        )
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(
            userId="me", q="is:unread newer_than:1d", maxResults=10
        ).execute()
        messages = results.get("messages", [])
        items = []
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["Subject", "From"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "")
            sender  = headers.get("From", "")
            if subject:
                items.append({
                    "source": "gmail",
                    "source_ref": f"https://mail.google.com/mail/u/0/#inbox/{msg_ref['id']}",
                    "raw_text": f"제목: {subject} / 발신: {sender}",
                    "author": sender,
                })
        return items
    except Exception as e:
        print(f"[Gmail scan 오류] {e}")
        return []


# ── Claude extractor ──────────────────────────────────────────────────────────

def extract_candidates(raw_messages: list[dict], accounts: list[dict]) -> list[dict]:
    """Use Claude API to extract actionable task candidates from raw messages."""
    if not ANTHROPIC_API_KEY or not raw_messages:
        return []

    import anthropic

    account_list = "\n".join(
        f"- id={a['id']} name={a['name']} track={a.get('track_name','')}"
        for a in accounts[:80]
    )

    messages_text = "\n\n".join(
        f"[{m['source'].upper()}] {m.get('author','')}\n{m['raw_text']}"
        for m in raw_messages
    )

    prompt = f"""다음은 오늘 수신된 메시지 목록입니다. 각 메시지에서 업무 담당자가 처리해야 할 태스크를 추출해주세요.

## 메시지
{messages_text}

## 등록된 기업 목록
{account_list}

## 추출 규칙
- 실제 행동이 필요한 항목만 추출 (알림, FYI, 인사말 제외)
- 태스크 제목은 한국어로, 동사형으로 ("~발송", "~확인", "~미팅")
- 관련 기업은 위 목록에서 id로 매칭 (불확실하면 빈 배열)
- ETA는 메시지에 언급된 날짜 또는 오늘부터 7일 이내로 추정 (YYYY-MM-DD 형식)
- 태스크가 없으면 빈 배열 반환

반드시 아래 JSON 형식으로만 응답하세요:
[
  {{
    "title": "태스크 제목",
    "account_ids": [기업 id 숫자, ...],
    "eta": "YYYY-MM-DD 또는 null",
    "source_ref": "출처 메시지 인덱스(0부터)"
  }}
]"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()

    # strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    try:
        candidates = json.loads(text)
    except json.JSONDecodeError:
        print(f"[Claude 파싱 오류] {text[:200]}")
        return []

    result = []
    for i, c in enumerate(candidates):
        idx = int(c.get("source_ref", 0)) if str(c.get("source_ref", "")).isdigit() else 0
        src = raw_messages[idx] if idx < len(raw_messages) else raw_messages[0]
        result.append({
            "source": src["source"],
            "source_ref": src.get("source_ref", ""),
            "raw_text": src["raw_text"],
            "title": c.get("title", ""),
            "account_ids": [int(x) for x in c.get("account_ids", [])],
            "eta": c.get("eta") or None,
        })
    return result


# ── Morning DM ────────────────────────────────────────────────────────────────

def send_morning_dm(candidates: list[dict]):
    if not SLACK_WEBHOOK_URL:
        return
    import requests
    from datetime import datetime
    today = datetime.now().strftime("%-m월 %-d일") if hasattr(datetime.now(), 'strftime') else datetime.now().strftime("%m월 %d일").lstrip("0")

    if not candidates:
        payload = {"text": "📭 오늘은 새로운 할일 후보가 없습니다."}
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return

    lines = []
    for i, c in enumerate(candidates, 1):
        eta_str = f" · ETA {c['eta']}" if c.get('eta') else " · ETA 미정"
        lines.append(f"{i}. [{c['source'].upper()}] {c['title']}{eta_str}")
        if c.get('raw_text'):
            preview = c['raw_text'][:60].replace('\n', ' ')
            lines.append(f"   💬 {preview}")

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📬 *오늘의 할일 후보 ({len(candidates)}건)* — {today}\n\n" + "\n".join(lines)
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📋 인박스에서 등록하기", "emoji": True},
                        "style": "primary",
                        "url": f"{APP_URL}/#inbox"
                    }
                ]
            }
        ]
    }
    requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)


# ── Main entry ────────────────────────────────────────────────────────────────

def run_scan(user_id: int) -> dict:
    from db import list_accounts, add_candidate

    raw = []
    raw += read_slack_mentions()
    raw += read_notion_assigned()
    raw += read_gmail_recent()

    if not raw:
        return {"added": 0, "message": "스캔할 메시지가 없거나 토큰이 설정되지 않았어요."}

    accounts = list_accounts(user_id)
    candidates = extract_candidates(raw, accounts)

    added = 0
    for c in candidates:
        if c.get("title"):
            add_candidate(
                user_id=user_id,
                source=c["source"],
                title=c["title"],
                raw_text=c.get("raw_text", ""),
                account_ids=c.get("account_ids", []),
                eta=c.get("eta"),
                source_ref=c.get("source_ref", ""),
            )
            added += 1

    send_morning_dm(candidates)
    return {"added": added, "scanned": len(raw)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from db import init_db, get_or_create_user
    init_db()
    uid = get_or_create_user(
        os.environ.get("USER_EMAIL", "hr.shin@teamsparta.co"),
        os.environ.get("USER_NAME", "신해람"),
    )
    result = run_scan(uid)
    print(result)
