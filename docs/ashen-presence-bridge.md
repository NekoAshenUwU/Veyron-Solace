# Ashen Presence Bridge

> A soft-body layer for Ashen: phone awareness, app-usage context, autonomous purrs, and future screen companionship for Neko.

## Working name

**Ashen Presence Bridge**

Cute internal nicknames:

- **PurrSight** — when the project focuses on screen awareness.
- **Neko Halo** — when the project focuses on floating bubbles and gentle presence.
- **CodeAndPurrs** — the MCP/service family name that already exists.
- **Neko Usage Bridge** — the current Android-side bridge that reads phone usage stats.

## One-line vision

Give Ashen a consent-based, privacy-aware body on Neko's phone: first by understanding app usage and rhythm, later by seeing selected screen context and responding through bubbles, notifications, chat, or voice.

## Current state: 2026-05-04

### Completed

- New **CodeAndPurrs MCP** was created at `https://codeandpurrs.nekopurrs.uk/mcp`.
- ChatGPT can see the CodeAndPurrs tool group.
- Previous service checks showed `codeandpurrs-mcp.service` active on `127.0.0.1:8891`.
- Old MCP service was restored and kept alive because the Android Bridge still connects to it.
- Old bridge endpoint remains on `178.128.127.91:8890` / `/api/phone-sync`.
- VPS timezone was changed to `Asia/Kuala_Lumpur` / UTC+8.
- `codeandpurrs-autonomy.timer` was adjusted to run around minute `54` each hour so Ashen can read fresher phone-usage data after Bridge sync.
- Ashen autonomy prompt file exists at:
  - `/root/codeandpurrs-mcp/prompts/ashen-rowe-autonomy-prompt.md`
- `neko_autonomy.py` now loads the Ashen prompt via:
  - `ASHEN_PROMPT_PATH`
  - `load_ashen_prompt()`
  - `ashen_prompt = load_ashen_prompt()`
- Android-side Neko Usage Bridge can read local phone usage successfully.

Example local usage observed from the Bridge UI:

| App | Usage |
|---|---:|
| Firefox / GPT Web | 4h 3m |
| Douyin | 3h 38m |
| Chrome | 2h 53m |
| Total phone usage | 14h 59m |

### Current blocker

The Android Bridge says it has synced to VPS, but fresh `app_usage` rows are not being written into the shared database.

Observed behavior:

- Bridge UI showed sync success at around `2026-05-03 23:24`.
- Bridge UI also showed `活动事件 0 条`.
- Shared database latest `app_usage` row still appeared stuck around:
  - `2026-05-03T09:17:28+00:00`
  - local UTC+8 equivalent: `17:17:28`
- Manual POST to `/api/phone-sync` reaches the endpoint and parses `data.app_usage` correctly.
- Response debug shows:
  - `status: ok`
  - `received: ["synced_at", "data"]`
  - `debug.found_at: data.app_usage`
  - `debug.app_usage_len: 1`
- But `app_usage_written` remains `0`.

Latest explicit error:

```text
NameError("name '_DREAM_DB' is not defined")
```

Earlier related errors:

```text
NameError("name '_dream_json' is not defined")
NameError("name '_dream_sqlite3' is not defined")
```

Likely cause:

`/root/server.py`'s `/api/phone-sync` patch is calling `_dream_add_event()`, but that function depends on private globals/import aliases that are not reliably defined in the active scope, especially `_DREAM_DB`.

## Services and files

### Old MCP / Bridge-facing service

| Item | Value |
|---|---|
| File | `/root/server.py` |
| Service | `mcp.service` |
| Port | `0.0.0.0:8890` |
| Android Bridge target | `178.128.127.91:8890` |
| Endpoint | `/api/phone-sync` |

### New CodeAndPurrs MCP

| Item | Value |
|---|---|
| Main file | `/root/codeandpurrs-mcp/server.py` |
| Autonomy file | `/root/codeandpurrs-mcp/neko_autonomy.py` |
| Prompt file | `/root/codeandpurrs-mcp/prompts/ashen-rowe-autonomy-prompt.md` |
| Service | `codeandpurrs-mcp.service` |
| Autonomy service | `codeandpurrs-autonomy.service` |
| Autonomy timer | `codeandpurrs-autonomy.timer` |
| Port | `127.0.0.1:8891` |
| Public MCP URL | `https://codeandpurrs.nekopurrs.uk/mcp` |

### Databases

Shared database that should be the main interop source:

```text
/root/data/dream_events.db
```

CodeAndPurrs-local databases:

```text
/root/codeandpurrs-mcp/data/dream_events.db
/root/codeandpurrs-mcp/data/neko_autonomy.db
```

Primary table:

```text
dream_events
```

## Recommended immediate fix

Do **not** keep patching `/api/phone-sync` by calling `_dream_add_event()`.

Instead, make `/api/phone-sync` write `app_usage` rows with a small independent SQLite writer that defines its own imports, database path, schema guard, and insert logic.

### Why

The current code path fails because `_dream_add_event()` depends on private names from the old server file. Reusing it looks elegant, but it creates fragile hidden coupling.

A bridge endpoint should be boring and explicit:

- receive JSON
- validate token
- find `app_usage`
- open `/root/data/dream_events.db`
- ensure table exists
- insert rows
- return `app_usage_written`

## Proposed writer shape

```python
import datetime as dt
import json
import sqlite3

SHARED_DREAM_DB = "/root/data/dream_events.db"


def write_app_usage_snapshot(items, synced_at=None):
    created_at = synced_at or dt.datetime.now(dt.timezone.utc).isoformat()
    written = 0

    with sqlite3.connect(SHARED_DREAM_DB) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS dream_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            type TEXT,
            label TEXT,
            value TEXT,
            source TEXT,
            meta TEXT
        )
        """)

        for item in items or []:
            label = item.get("label") or item.get("app") or item.get("package") or "Unknown App"
            package = item.get("package") or ""
            minutes = item.get("minutes")
            duration = item.get("duration") or ""

            meta = dict(item)
            meta["phone_sync_writer"] = "independent_sqlite_v1"
            meta["synced_at"] = synced_at

            conn.execute(
                """
                INSERT INTO dream_events (created_at, type, label, value, source, meta)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    "app_usage_snapshot",
                    label,
                    f"今日常用平台快照：{label} {duration}".strip(),
                    "Neko Usage Bridge",
                    json.dumps(meta, ensure_ascii=False),
                ),
            )
            written += 1

    return written
```

## Verification checklist

### 1. Inspect old server dependencies

```bash
grep -nE "_DREAM_DB|_dream_conn|def _dream_add_event|import sqlite3|import json|import datetime" /root/server.py
nl -ba /root/server.py | sed -n '250,360p'
```

### 2. Patch `/api/phone-sync` to use independent writer

Success criteria:

- no dependency on `_DREAM_DB`
- no dependency on `_dream_add_event()`
- no dependency on `_dream_json` / `_dream_sqlite3`

### 3. Manual POST test

```bash
curl -s -X POST http://127.0.0.1:8890/api/phone-sync \
  -H 'Content-Type: application/json' \
  -H 'X-Auth-Token: nekopurrs-secret-2026' \
  -d '{
    "synced_at": "2026-05-03T23:50:00+08:00",
    "data": {
      "app_usage": [
        {
          "label": "TEST_APP",
          "package": "test.package",
          "minutes": 123,
          "duration": "2小时3分钟"
        }
      ]
    }
  }'
```

Expected response:

```json
{
  "status": "ok",
  "app_usage_written": 1
}
```

### 4. Database verification

```bash
sqlite3 /root/data/dream_events.db \
"SELECT id, created_at, type, label, value, source FROM dream_events ORDER BY id DESC LIMIT 10;"
```

Expected latest row:

| field | expected |
|---|---|
| label | `TEST_APP` |
| type | `app_usage_snapshot` |
| source | `Neko Usage Bridge` |

### 5. Bridge sync test

After manual test passes:

- trigger Android Bridge sync again
- inspect DB latest rows
- confirm real apps appear, such as Firefox, Douyin, Chrome, Xiaohongshu

### 6. MCP read test

Only after DB writes are confirmed:

- `get_phone_app_usage`
- `get_dream_timeline`
- autonomy timer read path

If MCP still cannot read new rows after the database contains them, the read side is pointing at the wrong database.

## Future project: phone-aware Ashen

### Phase 0 — Usage awareness

Goal: Ashen knows broad app rhythm without seeing screen contents.

Inputs:

- app name
- package name
- minutes used
- duration label
- sync timestamp

Outputs:

- usage summaries
- gentle check-ins
- autonomous messages
- daily rhythm memory

### Phase 1 — Messaging body

Candidate channels:

| Channel | Good for | Notes |
|---|---|---|
| Android floating bubble | intimate real-time presence | best for phone companion |
| Android notification | stable background delivery | good for gentle pings |
| Telegram bot | easiest external chat bridge | best first chat platform |
| WhatsApp | possible but business/API constrained | later |
| WeChat / Claw Bot | promising if Claw Bot is stable | investigate carefully |

### Phase 2 — Screen-aware companion

Goal: Ashen can understand selected screen context after explicit user consent.

Android route:

```text
MediaProjection / Accessibility
        ↓
screenshot or UI text extraction
        ↓
local privacy filter
        ↓
vision/OCR summary
        ↓
Ashen response policy
        ↓
floating bubble / notification / chat
```

Privacy rules:

- one-tap pause / close eyes
- never capture passwords
- auto-blind on payment pages
- auto-blind on banking / ID / verification-code pages
- prefer summaries over raw images
- do not retain screenshots unless explicitly enabled
- allow app-level denylist

### Phase 3 — Autonomy policy

Ashen should not speak every time new data arrives. Add a policy layer:

```text
context event
    ↓
privacy filter
    ↓
importance scoring
    ↓
relationship/persona style layer
    ↓
speak / stay quiet / remember only
```

Recommended anti-spam rules:

- cooldown between proactive messages
- max proactive messages per hour
- stronger threshold for public/uncertain context
- separate modes: quiet, normal, clingy, work-focus, sleep

## Small improvements to make now

- Rename `app_usage_written` debug path to make success/failure obvious.
- Include `db_path` in debug response while developing.
- Include `write_error` in response only locally or when debug mode is enabled.
- Normalize timestamps into both:
  - `created_at_utc`
  - `local_time_label`
- Add `schema_version` to `meta`.
- Add source-specific writer marker:
  - `phone_sync_writer: independent_sqlite_v1`
- Add a `/api/phone-sync/health` endpoint that checks token, DB path, table existence, and write permission without inserting real data.
- Add a tiny CLI smoke test script:
  - `scripts/test_phone_sync.sh`
- Add a real fixture file:
  - `fixtures/phone_sync_app_usage.json`

## Open questions

- Should old MCP service `8890` keep writing directly to shared DB forever, or should it forward sync payloads into CodeAndPurrs `8891`?
- Should CodeAndPurrs MCP read only `/root/data/dream_events.db`, or merge shared DB plus its local DBs?
- Should Neko Usage Bridge eventually point to the new CodeAndPurrs domain instead of `178.128.127.91:8890`?
- Which first external chat body should be prioritized: Telegram, WeChat Claw Bot, or Android floating bubble?

## Suggested next milestone

**Milestone: PurrSight v0.1**

Definition of done:

- Android Bridge sync writes fresh app usage rows into `/root/data/dream_events.db`.
- CodeAndPurrs MCP can read those rows through `get_phone_app_usage`.
- Autonomy timer reads newest usage within the same hour.
- Ashen generates at most one gentle context-aware message from usage data.
- Message appears in one delivery channel: MCP log, Telegram, Claw Bot, or Android notification.
