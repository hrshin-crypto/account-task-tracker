# Account Task Tracker — 작업 로그

> 작성일: 2026-05-29 | 담당: 신해람 (hr.shin@teamsparta.co)

---

## 프로젝트 개요

40개 기업을 담당하는 Account Manager를 위한 태스크 추적 + Slack 알림 통합 대시보드.

- **로컬**: `python app.py` → http://localhost:5000
- **배포 URL**: https://account-task-tracker.onrender.com
- **GitHub**: https://github.com/hrshin-crypto/account-task-tracker
- **Slack 알림 스케줄**: https://claude.ai/code/routines/trig_017a5burGNjc2hjmZuvwtBCs

---

## 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | Python 3, Flask, SQLite |
| 프론트엔드 | Vanilla HTML/CSS/JS (단일 파일) |
| DB | SQLite (`tracker.db`) |
| 알림 | Slack Incoming Webhook |
| 배포 | Render (무료 티어) |
| 스케줄 | Claude Code Remote Routine (매일 09:00 KST) |

---

## 파일 구조

```
account-task-tracker/
├── app.py              # Flask 서버 (모든 API 엔드포인트)
├── db.py               # SQLite 스키마 + 헬퍼 함수
├── alert.py            # Slack Webhook ETA 알림 (D-3/D-1/초과)
├── sheets_sync.py      # Google Sheets → DB 동기화
├── inbox.py            # Slack/Notion/Gmail 스캔 + Claude 추출
├── index.html          # 4탭 대시보드 (단일 파일 SPA)
├── create_env.py       # .env 초기 세팅 스크립트
├── smoke_test.py       # 크레덴셜 연결 검증
├── Procfile            # gunicorn 배포 설정
├── requirements.txt    # 의존성
├── credentials.json    # Google 서비스 계정 키 (git 제외)
├── .env                # 환경변수 (git 제외)
└── docs/
    ├── PRD.md          # 제품 요구사항
    └── WORK_LOG.md     # 이 파일
```

---

## DB 스키마

```sql
users          -- 사용자 (멀티유저 대비)
accounts       -- 참여기업 (127개, Google Sheets 동기화)
parent_tasks   -- 부모 태스크 (칸반 카드)
account_tasks  -- 기업별 서브태스크 (매트릭스 셀)
task_candidates -- 인박스 후보 (AI 추출, 미확인)
alert_log      -- Slack 알림 발송 이력
```

---

## 구현된 기능

### Priority 1 — 핵심 대시보드

#### 칸반 보드 (`/` → 칸반 탭)
- 태스크 카드: ETA 배지(D-N/초과), 진행률 바, 기업 미리보기 칩
- 3컬럼: 예정 / 진행중 / 완료
- 카드 이동 버튼 (← 예정 / 진행중 → 등)
- **카드 클릭 → 우측 슬라이드 패널**: 기업별 상세 현황

#### 매트릭스 (`매트릭스` 탭)
- 행: 참여기업 / 열: 부모 태스크
- 셀 클릭으로 상태 순환: ⬜ → 🔄 → ✅ → ➖
- 트랙별 그룹 행 구분

#### 기업 관리 (`기업 관리` 탭)
- 기업 목록 테이블 (트랙/등급/퍼널/이메일)
- **행 클릭 → 우측 슬라이드 패널**: 담당자 정보 + 전체 태스크 현황
- Google Sheets 싱크 버튼

#### 상단 통계 카드 (클릭 가능)
- 전체 태스크 → 전체 목록 패널
- 완료 → 완료 태스크 필터 패널
- 기한 초과 → 초과 태스크 필터 패널
- **기업 수 → 기업 목록 패널** (대분류/소분류 토글, 넘버링, 등급 뱃지)

#### 슬라이드 디테일 패널 (공통)
- 기업 목록: 🤖 AI 캠퍼스 / ⭐ 고성과 대분류 토글
- 소분류: 트랙명별 토글 (접기/펼치기)
- 정렬: 네임드 → S → A → B
- 등급 뱃지: `네임드`(노랑) + `A`(파랑) 이중 뱃지, `S`(보라), `B`(회색)
- 넘버링 표시, 담당자명 표시
- **태스크 카드 디테일**: 연결된 기업만 표시 (전체 127개 아님)
- **ETA 인라인 수정**: 상단 📅 날짜 입력창 → 변경 즉시 저장, ✕로 마감일 제거

#### ETA 알림 (`alert.py`)
- D-3 / D-1 / 기한 초과 시 Slack DM 자동 발송
- 매일 09:00 app.py 내장 스케줄러 실행
- Webhook: `https://hooks.slack.com/services/TQ595477U/...`

---

### Priority 2 — 인박스 (`인박스` 탭)

#### 아침 스캔 루틴
- **Claude Code 스케줄**: 매일 09:00 KST 자동 실행
- Slack / Gmail / Notion 최근 24시간 스캔
- Claude API로 업무 후보 추출 (최대 5건)
- Block Kit 버튼 포함 Slack DM 발송

#### DM 형식
```
📬 오늘의 할일 후보 (N건) — M월 D일

1. [SLACK] 태스크 제목 · ETA 날짜
   💬 원본 메시지 요약

[📋 인박스에서 등록하기]  ← 버튼 클릭 시 localhost:5000/#inbox
```

#### 인박스 UI
- 후보 카드: 소스 배지(SLACK/GMAIL/NOTION), 원본 내용, 제목
- **[검토] 버튼** → 모달 (720px, 좌우 2분할)
  - 좌: 태스크 제목 수정 + **ETA 설정** (노란 테두리 강조, 필수 안내)
  - 우: 기업 선택 (2열 그리드, 검색, 전체선택, 등급 뱃지)
- **[✅ 태스크 추가]** → parent_task + account_tasks 생성 → 칸반/매트릭스 즉시 반영
- **[무시]** → candidates 상태 dismissed 처리

---

## API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/accounts` | 기업 목록 |
| POST | `/api/accounts` | 기업 추가 |
| DELETE | `/api/accounts/:id` | 기업 삭제 |
| GET | `/api/tasks` | 태스크 목록 (진행률 포함) |
| POST | `/api/tasks` | 태스크 생성 |
| DELETE | `/api/tasks/:id` | 태스크 삭제 |
| PUT | `/api/tasks/:id` | 태스크 수정 (title, due_date, description) |
| PUT | `/api/tasks/:id/kanban` | 칸반 상태 변경 |
| GET | `/api/matrix` | 전체 매트릭스 데이터 |
| POST | `/api/matrix/toggle` | 셀 상태 토글 |
| PUT | `/api/account_tasks/:id` | 서브태스크 상태/메모/ETA 수정 |
| GET | `/api/upcoming` | 마감 임박/초과 목록 |
| POST | `/api/alerts/run` | 알림 수동 발송 |
| POST | `/api/sync` | Google Sheets 동기화 |
| GET | `/api/inbox` | 인박스 후보 목록 |
| POST | `/api/inbox` | 후보 수동 추가 |
| PUT | `/api/inbox/:id` | 후보 수정 |
| POST | `/api/inbox/:id/confirm` | 후보 확인 → 태스크 생성 |
| DELETE | `/api/inbox/:id` | 후보 무시 |
| POST | `/api/inbox/scan` | 인박스 스캔 트리거 |

---

## 환경변수 (.env)

```
GOOGLE_SERVICE_ACCOUNT_JSON=credentials.json
GOOGLE_CREDENTIALS_B64=<base64 인코딩된 credentials.json>
USER_EMAIL=hr.shin@teamsparta.co
USER_NAME=신해람
DB_PATH=tracker.db  (Render: /tmp/tracker.db)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ANTHROPIC_API_KEY=  (인박스 Claude 추출 기능용, 선택)
SLACK_USER_TOKEN=   (Slack 메시지 읽기용, 선택)
NOTION_TOKEN=       (Notion 읽기용, 선택)
```

---

## 실행 방법

```bash
# 로컬 실행
python app.py
# → http://localhost:5000

# 의존성 설치
pip install -r requirements.txt

# 연결 테스트
python smoke_test.py

# Slack 테스트
python test_slack.py

# 인박스 수동 스캔
python inbox.py
```

---

## 배포 (Render)

- **서비스**: account-task-tracker
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
- **URL**: https://account-task-tracker.onrender.com
- GitHub push → 자동 재배포

> ⚠️ Render 무료 티어: 15분 미사용 시 슬립 (첫 요청 ~30초 대기)
> ⚠️ DB가 `/tmp`에 저장되므로 재배포 시 초기화 → **시트 싱크** 버튼으로 기업 재동기화 필요

---

## 향후 개선 사항

- [ ] Render Disk 추가 ($0.25/GB) → DB 영구 저장
- [ ] ANTHROPIC_API_KEY 설정 → 인박스 자동 분류 활성화
- [ ] SLACK_USER_TOKEN 설정 → Slack 메시지 자동 읽기
- [ ] NOTION_TOKEN 설정 → Notion 할일 자동 읽기
- [ ] 팀 멀티유저 (schema 준비됨, UI 미구현)
- [ ] 모바일 반응형 개선
