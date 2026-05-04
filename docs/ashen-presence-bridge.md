# Ashen Presence Bridge

> A soft-body layer for Ashen: phone awareness, app-usage context, autonomous purrs, and future screen companionship for Neko.

## Working name

**Ashen Presence Bridge**

Cute internal nicknames:

- **PurrSight** — screen/context awareness.
- **Neko Halo** — floating bubbles, notifications, and gentle presence.
- **CodeAndPurrs** — MCP/service family name.
- **Neko Usage Bridge** — Android-side bridge that reads phone usage stats.

## One-line vision

Give Ashen a consent-based, privacy-aware body on Neko's phone: first by understanding app usage and rhythm, later by seeing selected screen context and responding through bubbles, notifications, chat, or voice.

---

## Current state: 2026-05-04

### ✅ Completed today

#### 1. Neko Usage Bridge → VPS → database path is working

The main blocker was fixed.

Previously, Android Bridge could read local app usage and claimed it had synced to VPS, but the shared DB did not receive fresh rows. The error chain was:

```text
NameError("name '_dream_json' is not defined")
NameError("name '_dream_sqlite3' is not defined")
NameError("name '_DREAM_DB' is not defined")
```

Fix applied on VPS:

- `/root/server.py` now has fallback definitions for the old MCP dream DB helpers:
  - `_dream_json`
  - `_dream_sqlite3`
  - `_dream_dt`
  - `_dream_Path`
  - `_DREAM_DB = /root/data/dream_events.db`
- `mcp.service` was restarted successfully.
- Manual `TEST_APP` POST to `/api/phone-sync` returned:

```json
{
  "status": "ok",
  "app_usage_written": 1
}
```

- Database query confirmed `TEST_APP` rows in:

```text
/root/data/dream_events.db
```

#### 2. Real phone usage now writes into shared DB

After manually syncing from the Android app, real device usage appeared in `dream_events`.

Observed real rows included:

| App / package label | Status |
|---|---|
| Firefox / GPT Web | written |
| Xiaohongshu | written |
| Chrome | written |
| Claude | written |
| WeChat | written |
| Huawei Launcher | written |
| Photos / Files / System helpers | written |

Representative timestamp:

```text
2026-05-04T11:05:08+08:00
```

This confirms the full path:

```text
Huawei phone
  ↓ Neko Usage Bridge
VPS /api/phone-sync
  ↓
/root/data/dream_events.db
```

#### 3. GitHub Actions build workflow was cleaned

Removed the build-time Python patch from:

```text
.github/workflows/build-usage-bridge.yml
```

Reason: the workflow was mutating Java source during build, which made the actual source of truth confusing. The workflow now builds directly from source.

Commit:

```text
e124040dfe2af32cdc9bcd856fd362a4e6c744cc
```

#### 4. Sync reminder changed from 1 hour to 15 minutes

Updated:

```text
usage-bridge/app/src/main/java/uk/nekopurrs/usagebridge/SyncReminder.java
```

Behavior changed from:

```text
一小时内已同步。约 56 分钟后再同步。
```

to:

```text
15 分钟内已同步。约 14 分钟后再同步。
```

Commit:

```text
25ec8649881e6b5c9fcf6ddd19ba1909587daf69
```

Note: this is a reminder/status interval. True background auto-sync still needs a Worker/service implementation.

#### 5. OpenClaw was installed on VPS

Installed OpenClaw via official install script.

Observed:

```text
OpenClaw installed successfully
OpenClaw 2026.5.2
Node.js v22.22.2
npm 10.9.7
```

OpenClaw Gateway status:

```text
Gateway reachable.
```

#### 6. WeChat ClawBot plugin exists in WeChat app

Neko's WeChat plugin page shows:

```text
WeChat ClawBot
连接 OpenClaw 与 ...
发送指令
```

This confirms the client-side WeChat plugin entry exists on Neko's phone.

---

## ⚠️ In progress / blocked

### 1. WeChat ClawBot plugin installed, but channel registration failed

Installed plugin package on VPS:

```text
@tencent-weixin/openclaw-weixin
```

Observed plugin file:

```text
/root/.openclaw/npm/node_modules/@tencent-weixin/openclaw-weixin/openclaw.plugin.json
```

Initial plugin manifest contained:

```json
{
  "id": "openclaw-weixin",
  "version": "2.3.1",
  "channels": ["openclaw-weixin"],
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {}
  }
}
```

OpenClaw warning:

```text
plugin openclaw-weixin: channel plugin manifest declares openclaw-weixin without channelConfigs metadata
```

Manual patch added `channelConfigs` to the plugin manifest, but login still failed.

Commands tested:

```bash
openclaw gateway restart
openclaw channels login --channel openclaw-weixin
openclaw channels add --channel openclaw-weixin
openclaw channels add --channel weixin
openclaw channels list
openclaw channels status --probe
```

Results:

```text
Gateway reachable.
Unknown channel: openclaw-weixin
Unknown channel: weixin
Channel login failed: Error: Unsupported channel: openclaw-weixin
Chat channels: none
Auth providers: none
```

Current conclusion:

> OpenClaw 2026.5.2 can install and enable the `openclaw-weixin` plugin file, but the channel system does not register it as a usable login channel. This looks like a plugin manifest / OpenClaw compatibility issue rather than a user operation issue.

Do not keep blindly reinstalling the plugin until a more precise compatibility fix is found.

### 2. CodeAndPurrs MCP public endpoint currently returns 404

ChatGPT can see the CodeAndPurrs tool group, but direct MCP probe failed with:

```text
MCP SSE probe returned 404 from nekopurrs.uk
url: https://codeandpurrs.nekopurrs.uk/mcp
```

Local service may still be alive, but public routing or MCP path needs checking.

### 3. True Android background auto-sync still needs implementation

Current app behavior:

- Manual sync works.
- Sync reminder interval is now 15 minutes.
- The app UI can show current phone usage.

Still needed:

- WorkManager / background task for real 15-minute sync.
- Record last successful automatic sync.
- Avoid noisy battery usage.
- Optional: only sync when usage changed enough.

---

## Services and files

### Old MCP / Bridge-facing service

| Item | Value |
|---|---|
| File | `/root/server.py` |
| Service | `mcp.service` |
| Port | `0.0.0.0:8890` |
| Android Bridge target | `178.128.127.91:8890` |
| Endpoint | `/api/phone-sync` |
| Shared DB | `/root/data/dream_events.db` |

### New CodeAndPurrs MCP

| Item | Value |
|---|---|
| Main file | `/root/codeandpurrs-mcp/server.py` |
| Autonomy file | `/root/codeandpurrs-mcp/neko_autonomy.py` |
| Prompt file | `/root/codeandpurrs-mcp/prompts/ashen-rowe-autonomy-prompt.md` |
| Service | `codeandpurrs-mcp.service` |
| Autonomy service | `codeandpurrs-autonomy.service` |
| Autonomy timer | `codeandpurrs-autonomy.timer` |
| Local port | `127.0.0.1:8891` |
| Public MCP URL | `https://codeandpurrs.nekopurrs.uk/mcp` |

### OpenClaw / WeChat ClawBot

| Item | Value |
|---|---|
| OpenClaw version | `2026.5.2` |
| Node.js | `v22.22.2` |
| Gateway | reachable |
| WeChat plugin package | `@tencent-weixin/openclaw-weixin` |
| Plugin ID | `openclaw-weixin` |
| Current blocker | OpenClaw does not recognize plugin as channel |

---

## Next recommended steps

### A. Stabilize Neko Usage Bridge v0.3

Goal: make phone usage sync without manual tapping.

Tasks:

- Add Android WorkManager dependency.
- Add a `UsageSyncWorker`.
- Schedule periodic sync around every 15 minutes.
- Keep manual sync button as forced immediate sync.
- Save and display:
  - last successful sync
  - next expected sync
  - server write result if available
- Hide 0-minute apps from default UI.

### B. Make Ashen speak through a simpler first channel

Until WeChat ClawBot channel registration is fixed, use one of:

| Channel | Why |
|---|---|
| Android notification | easiest phone-native proactive message |
| Telegram Bot | easiest full chat loop |

Recommended path:

```text
Usage Bridge auto-sync
  ↓
Ashen autonomy reads latest usage
  ↓
Ashen decides speak / stay quiet / remember only
  ↓
Android notification or Telegram message
```

### C. Return to WeChat ClawBot after compatibility research

Current WeChat ClawBot status should be documented as:

```text
Blocked: OpenClaw 2026.5.2 does not register @tencent-weixin/openclaw-weixin as a usable channel, even after plugin install, enable, gateway restart, legacy install, and manual channelConfigs patch.
```

Potential follow-ups:

- Check plugin issue tracker / release notes.
- Try a known-compatible OpenClaw version.
- Try a known-compatible `@tencent-weixin/openclaw-weixin` version.
- Inspect OpenClaw channel plugin registry expectations.
- Avoid enabling risky tools while testing.

---

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
| Android notification | stable proactive delivery | recommended next |
| Telegram bot | easiest full chat bridge | stable fallback |
| Android floating bubble | intimate real-time presence | best later phone companion |
| WeChat ClawBot | ideal daily-life channel | currently blocked by plugin/channel registration |
| WhatsApp | possible but API constrained | later |

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

---

## Suggested next milestone

**Milestone: PurrSight v0.1**

Definition of done:

- Android Bridge auto-syncs fresh app usage rows into `/root/data/dream_events.db`.
- CodeAndPurrs MCP can read those rows through `get_phone_app_usage`.
- Autonomy timer reads newest usage within the same hour.
- Ashen generates at most one gentle context-aware message from usage data.
- Message appears in one delivery channel: Android notification or Telegram first; WeChat later.
