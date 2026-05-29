import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv; load_dotenv()
import os, requests

webhook = os.environ.get('SLACK_WEBHOOK_URL', '')
if not webhook:
    print('❌ SLACK_WEBHOOK_URL이 .env에 없어요.')
    sys.exit(1)

r = requests.post(webhook, json={'text': '테스트: Account Task Tracker DM 연결 확인'}, timeout=10)
r.raise_for_status()
print('✅ 전송 완료')
