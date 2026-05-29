"""
smoke_test.py — Run this FIRST before writing any integration code.
Verifies credentials in order: Sheets → Slack → Claude API
Usage: python smoke_test.py
"""

import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

PASS = "✅"
FAIL = "❌"
results = []


def check(label, fn):
    try:
        fn()
        print(f"{PASS} {label}")
        results.append((label, True))
    except Exception as e:
        print(f"{FAIL} {label}")
        print(f"   오류: {e}")
        results.append((label, False))


# ── 1. Google Sheets ──────────────────────────────────────────────────────────

def test_sheets():
    import gspread
    from google.oauth2.service_account import Credentials

    creds_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"credentials.json 파일이 없어요: {creds_path}\n"
            "   → Google Cloud Console에서 서비스 계정 키를 다운로드한 뒤\n"
            "     이 프로젝트 폴더에 credentials.json 이름으로 저장하세요."
        )

    creds = Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    gc = gspread.authorize(creds)

    # Sheet 1: 참여기업 현황판
    sheet_id_1 = os.environ.get("SHEET_ID_STATUS", "").strip()
    if not sheet_id_1:
        raise ValueError("SHEET_ID_STATUS가 .env에 없어요.")
    sh1 = gc.open_by_key(sheet_id_1)
    ws1 = sh1.get_worksheet(0)
    headers1 = ws1.row_values(1)
    print(f"   참여기업 현황판 컬럼: {headers1}")

    # Sheet 2: [S/A] 채용 수요
    sheet_id_2 = os.environ.get("SHEET_ID_DEMAND", "").strip()
    if not sheet_id_2:
        raise ValueError("SHEET_ID_DEMAND가 .env에 없어요.")
    sh2 = gc.open_by_key(sheet_id_2)
    ws2 = sh2.get_worksheet(0)
    headers2 = ws2.row_values(1)
    print(f"   채용 수요 컬럼: {headers2}")

    print("   ⚠️  위 컬럼명을 메모해두세요 → sheets_import.py에서 사용합니다.")


check("Google Sheets 접근 (읽기 전용)", test_sheets)


# ── 2. Slack Webhook ─────────────────────────────────────────────────────────

def test_slack():
    import requests

    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook or not webhook.startswith("https://hooks.slack.com/"):
        raise ValueError(
            "SLACK_WEBHOOK_URL이 .env에 없어요.\n"
            "   → api.slack.com/apps → Incoming Webhooks → Add New Webhook to Workspace\n"
            "     'Direct Messages > 나 자신' 선택 후 URL 복사"
        )

    r = requests.post(webhook, json={"text": "🧪 Smoke test: Slack 연결 확인 — Account Task Tracker"}, timeout=10)
    r.raise_for_status()
    print("   DM 전송 완료 → Slack에서 메시지 확인해주세요")


check("Slack Incoming Webhook + DM 전송", test_slack)


# ── 3. Claude API ─────────────────────────────────────────────────────────────

def test_claude():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "sk-ant-":
        raise ValueError("ANTHROPIC_API_KEY가 .env에 없어요.")

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": "ping"}],
    )
    print(f"   응답: {msg.content[0].text.strip()}")


check("Claude API (Anthropic)", test_claude)


# ── 결과 요약 ─────────────────────────────────────────────────────────────────

print("\n" + "─" * 50)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"결과: {passed}/{total} 통과")

if passed < total:
    print("\n실패한 항목을 먼저 해결하세요.")
    print(".env 파일과 credentials.json 위치를 다시 확인해주세요.")
    sys.exit(1)
else:
    print("모두 통과! db.py 작성으로 넘어가세요.")
