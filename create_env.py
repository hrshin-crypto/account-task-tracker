"""
create_env.py — Run once to create .env
Usage: python create_env.py
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')

ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')

print("=== Account Task Tracker — .env 세팅 ===\n")

if os.path.exists(ENV_PATH):
    print(f".env 파일이 이미 있어요: {ENV_PATH}")
    ow = input("덮어쓸까요? (y/N): ").strip().lower()
    if ow != 'y':
        sys.exit(0)

print("\n[Slack Incoming Webhook 설정]")
print("  1. https://api.slack.com/apps 접속 → 'Create New App' → 'From scratch'")
print("  2. 앱 이름: TaskTracker, 워크스페이스 선택 후 Create")
print("  3. 'Incoming Webhooks' 클릭 → Activate 켜기")
print("  4. 'Add New Webhook to Workspace' → 'Direct Messages > 나 자신' 선택 → Allow")
print("  5. 생성된 URL 복사 (https://hooks.slack.com/services/...)")
webhook = input("\nSLACK_WEBHOOK_URL: ").strip()

print("\n[Claude API — 생략 가능, Enter로 넘기기]")
print("  ANTHROPIC_API_KEY: console.anthropic.com/settings/keys")
api_key = input("ANTHROPIC_API_KEY: ").strip()

content = f"""GOOGLE_SERVICE_ACCOUNT_JSON=credentials.json
USER_EMAIL=hr.shin@teamsparta.co
USER_NAME=신해람
DB_PATH=tracker.db
SLACK_WEBHOOK_URL={webhook}
ANTHROPIC_API_KEY={api_key}
"""

with open(ENV_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ .env 저장 완료: {ENV_PATH}")
print("이제 python smoke_test.py 실행해서 연결 확인하세요.")
