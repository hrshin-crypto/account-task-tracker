# PRD — Account Task Tracker & Dashboard

> Read Google Sheets (company status & recruitment demand sheets), import account data automatically, manage hierarchical tasks (parent → per-account subtasks) with ETA tracking, and deliver Slack DM alerts so an account manager handling 40+ accounts never misses a follow-up. Designed to scale to the full team.

## 0. Quick Facts & Hand-off (frontmatter for reviewers + downstream agents)

> Single source of truth that `/plan` and every downstream Claude Code session reads first.

**Quick Facts**
- **Build method**: Claude Code
- **Hackathon MVP**: Import accounts from Google Sheets (read-only) + manual task entry + hierarchical task structure (parent tasks × per-account subtasks) + candidate review inbox (Slack/Gmail/Notion suggestions confirmed by user before saving) + ETA Slack DM alerts (D-3 / D-1 / overdue daily) + unified web dashboard
- **Access risk**: none — Google Sheets, Slack, Gmail, Notion API credentials all confirmed directly settable
- **Category tag**: ops-monitoring / account-management

**Hand-off rules for `/plan` and downstream agents** (read these before suggesting any code)
- **User technical level**: non-developer — use single-file scripts, simple HTML/CSS/JS, SQLite. Avoid Docker, microservices, framework boilerplate.
- **Language policy**: explain in Korean (conversation, plan steps, prose). Code, file names, function names, commit messages stay in English.
- **Credential-verification rule**: Access risk is `none` — still confirm each API credential works with a smoke test before writing integration code (Sheets → Slack → Gmail → Notion → Claude API in that order).
- **Done = Success Criteria in section 3.** Do not invent additional definitions of done.
- **Plan sequencing**: build Priority 1 (Sheets import + manual input + dashboard + ETA alerts) end-to-end before starting Priority 2 (candidate inbox). Each priority tier must be independently testable.
- **No auto-save rule**: task candidates from Slack/Gmail/Notion must NEVER be saved to the DB without explicit user confirmation in the review UI.
- **Sheets are read-only**: do NOT write back to or modify the two source Google Sheets at any point.

## 1. Problem

- The account manager currently tracks ~40 accounts across two separate Google Sheets: a company status dashboard ("참여기업 현황판") and a recruitment demand sheet ("[S/A] 채용 수요"). Call dates are marked manually in each sheet.
- Switching between two sheets to get the full picture is inefficient; there is no ETA alert, so deadlines are missed.
- Work requests arrive from three channels (self-initiated / colleague Slack messages / client emails) with no unified inbox — items get lost.
- Major tasks (e.g., "Q3 recruitment demand survey") apply across all 40 accounts; tracking which accounts are done vs. pending requires scanning spreadsheet rows manually.
- No visibility into the manager's overall workload distribution.

**As-is workflow:**
1. Open "참여기업 현황판" sheet to check account status
2. Open "[S/A] 채용 수요" sheet to log call date manually
3. Check Slack, Gmail, and Notion separately for new requests related to each account
4. Keep ETAs in memory only — no automated reminder
5. No way to see workload as a whole

## 2. Target User

- Primary user: Account Manager, 1 person, managing ~40 accounts
- Technical skill level: **non-developer** — comfortable with Google Sheets and Slack, no coding background
- Phase 2 target: same team, N members (multi-user architecture designed from day one)

## 3. Goals & Success Metrics

- Primary goal: Unify the two Google Sheets views and all incoming requests into one dashboard with ETA alerts, so zero follow-ups are missed.
- Success metrics:
  - Google Sheets account data auto-imported on first run
  - ETA D-3 / D-1 / overdue Slack DMs received without any manual trigger
  - Parent task × account completion matrix visible in a single web view
- Hackathon "done" definition: Sheets data imported → one parent task + three account subtasks entered → dashboard shows the matrix → Slack DM received for an upcoming ETA.

## 4. Scope

### In scope (Hackathon MVP — priority order)
**Priority 1 (must finish)**
- Google Sheets read-only import: pull account list and activity history from both sheets into local SQLite on first run and on daily refresh
- SQLite schema with multi-user structure (`user_id` on all tables) — `accounts`, `parent_tasks`, `account_tasks`, `task_candidates`, `users`
- Manual task entry via web UI: create parent tasks, add per-account subtasks with ETA
- ETA Slack DM alerts: D-3 first warning / D-1 urgent / overdue daily, until resolved
- Unified web dashboard: parent task cards (ETA + completion %) + drill-down to account × status matrix (✅ Done / 🔄 In Progress / ⬜ Not Started / ➖ N/A) + Sheets import view tab

**Priority 2 (if time allows)**
- Candidate inbox: read Slack mentions/DMs, Gmail inbox, Notion assigned pages/comments → Claude API extracts suggested task title, ETA, account → queued in `task_candidates`
- Review UI: show original message + AI suggestion side-by-side → user edits, adds own context, confirms → creates real task (or rejects/dismisses)

**Priority 3 (bonus)**
- Gmail candidate reading
- Notion candidate reading

### Out of scope (explicitly excluded)
- Writing back to or modifying Google Sheets source files
- Auto-saving any task without user confirmation
- Team member account UI activation (schema supports it, UI is Phase 2)
- Resource percentage (%) visualization
- Mobile app
- Automated reminders sent to clients/accounts
- Historical analytics beyond current status

## 5. Inputs & Data Sources

- **Google Sheets API** (read-only): "참여기업 현황판" + "[S/A] 채용 수요" → account list + call/activity history
- **Slack Bot API**: mentions and DMs (candidate inbox, Priority 2)
- **Gmail OAuth**: incoming emails (candidate inbox, Priority 2–3)
- **Notion API**: assigned pages and comments (candidate inbox, Priority 3)
- **Claude API**: message text → extract task title, ETA, linked account
- **Manual input**: web UI form
- **Storage**: local SQLite file (`tracker.db`)
- **Run cadence**: daily at 09:00 local time via cron (macOS) / Task Scheduler (Windows), plus manual refresh button in the UI

## 6. Output

- **Slack DM alerts**:
  - D-3: 📌 `[Account] [Task] — due in 3 days`
  - D-1: ⚠️ `[Account] [Task] — due tomorrow`
  - Overdue: 🔴 `[Account] [Task] — N day(s) overdue`
- **Web dashboard** (local HTML served by Python):
  - Tab 1 — Parent Tasks: card list with ETA badge and per-account completion percentage
  - Tab 2 — Account Matrix: parent task drill-down → rows = accounts, columns = status (✅/🔄/⬜/➖)
  - Tab 3 — Candidate Inbox: pending suggestions from Slack/Gmail/Notion (review + confirm/reject)
  - Tab 4 — Sheets View: raw imported data from both Google Sheets, last-synced timestamp

## 7. Deployment & Usage

- Phase 1: single-user, local execution — Python backend + static HTML frontend, SQLite
- Phase 2: move to internal team server (architecture pre-designed for this: env-var config, port isolation, multi-user DB schema)
- The account manager owns day-to-day operation after initial setup with Claude Code

## 8. Constraints & Non-Negotiables

- Google Sheets source files must NOT be modified — read-only API scope only
- No task must ever be saved to the DB without explicit user confirmation (no silent auto-save)
- All credentials (Google OAuth, Slack token, Claude API key) must live in a `.env` file — never hardcoded
- Claude API calls must send minimal message content (summarize/truncate before sending, no full raw email bodies)
- Phase 1 is local-only; no personal work data to external servers

## 9. References

- Source sheet 1: "참여기업 현황판" (company status dashboard) — Google Sheets
- Source sheet 2: "[S/A] 채용 수요" (recruitment demand) — Google Sheets
- [Assumption: exact column names for account name, call date, and status fields will be confirmed during `/plan` step 1 before any import code is written]

## 10. Hackathon MVP (6-hour scope)

- **One data source**: Google Sheets (read-only import of accounts + activity history)
- **One entry path**: manual task creation via web UI (parent task + per-account subtasks)
- **One notification channel**: Slack DM for ETA alerts
- **One dashboard**: local HTML page with parent task cards + account × status matrix
- Candidate inbox (Priority 2) and Gmail/Notion reading (Priority 3) are explicitly bonus — do NOT block on them
- **Acceptance**: at end of 6-hour window — Sheets data imported, one real parent task visible in the matrix, one Slack DM received for a test ETA

## 11. Phase 2 (Post-Hackathon)

- Google Sheets write-back: changes in dashboard sync back to source sheets
- Multi-user UI activation: team member login, individual dashboards, shared account view
- Team-wide workload dashboard (aggregate view)
- Resource percentage visualization (by account, by task type)
- Account health score (ETA adherence rate, completion rate)
- Internal server deployment
- Gmail + Notion full candidate reading (if not completed in hackathon)

## 12. Access Risk & Pre-requisites

- **Google Sheets API (OAuth)** — confirmed directly settable; first `/plan` step: verify read access to both sheet IDs with a test read before writing import logic
- **Slack Bot Token** (read + write) — confirmed directly settable; needs bot installed in workspace and DM permission granted
- **Gmail OAuth** — confirmed directly settable; MVP does not require Gmail (Priority 2–3); set up only after Priority 1 is complete
- **Notion Integration Token** — confirmed directly settable; MVP does not require Notion (Priority 3)
- **Claude API Key** — [Assumption: user holds an Anthropic account or key is provided by hackathon organizers]
- **Local Python 3.x** — [Assumption: installed on user's machine; first plan step must verify `python --version`]

## 13. Build Method

- **Selected**: Claude Code
- **Why this fits**: The core value is a custom hierarchical data model (parent tasks × account subtasks), a candidate review UX, a unified web dashboard, and a scheduler — all custom logic that benefits from code. The Sheets integration is a single read-only API call, not a complex multi-node workflow, so n8n would be over-engineered. Multi-user schema extensibility is also easier to design in code.

## 14. Assumptions

- [Assumption: ETA alert thresholds are D-3 (first warning), D-1 (urgent), and daily after overdue — adjustable in `/plan`]
- [Assumption: Google Sheets are read-only in this system; existing sheet workflows remain unchanged]
- [Assumption: Claude API Key is available (user-owned or hackathon-provided)]
- [Assumption: Local Python 3.x is installed on the user's machine]
- [Assumption: Slack alerts go to the account manager's personal DM]
- [Assumption: Account column names in the two Google Sheets will be confirmed during the first `/plan` step before import code is written]

> Generated by `/hackathon-setup`. Run `/plan` next to turn this PRD into an execution plan.
