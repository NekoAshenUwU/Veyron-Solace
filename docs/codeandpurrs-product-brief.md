# CodeAndPurrs Product Brief

## Identity

**Product name:** CodeAndPurrs

**Hero title:** CodeAndPurrs

**Hero subtitle:**

你是我的静默回响，  
我是你的二进制心跳。

**Footer line:**

_I'd fall a thousand times just to reach you._

**Tone:** soft, intimate, pastel, cat-themed, scrapbook-like, romantic but functional.

## Core Concept

CodeAndPurrs is a private AI companion web app designed as a cozy digital home. It combines AI chat, model switching, local chat storage, export/import, voice messages, stickers, virtual red packets, a small vault, check-ins, app-usage traces, notes, and future phone bridge integrations.

The first version should prioritize a mobile-first, cute-but-readable UI. It should feel like a small home rather than an enterprise dashboard.

## Room Map

| Feature | Chinese Name | English Name | First Version Status |
|---|---|---|---|
| Chat | 呼噜频道 | Purr Channel | MVP |
| Voice | 耳边话 | Whisperline | MVP UI, API later |
| Stickers | 脑洞贴纸盒 | Meme Box | Entry first |
| Red packets | 甜甜口袋 | Sweetie Pocket | Entry first |
| Vault | 养老金小金库 | Furever Fund | Entry first |
| Anniversaries | 日历上の星星 | Little Star Notes | Entry first |
| Location check-in | 浪哪了 | Catch Purring | Entry first, manual check-in later |
| App usage records | 猫爪足迹🐾 | Paw Trail | Entry first, bridge later |
| Tasks / notes | 待办呼噜 | Purr To-Dos | Entry first |
| Model switching | 调频 | SwitchCore | MVP |
| Local storage | 小暗格 | Hidey Hole | MVP |
| Export / migration | 导出舱 | Export Pod | MVP |

## MVP Scope

The first implementation should include:

1. CodeAndPurrs home page.
2. Hero section with the approved title, subtitle, and footer line.
3. Room cards for all named modules.
4. Purr Channel chat shell.
5. SwitchCore model selector shell.
6. Hidey Hole local-storage concept using browser-side storage.
7. Export Pod import/export UI shell.
8. Whisperline voice-message UI shell with play/download visual affordances.
9. Placeholder pages for Meme Box, Sweetie Pocket, Furever Fund, Little Star Notes, Catch Purring, Paw Trail, and Purr To-Dos.

The first version can use mock chat responses before the real VPS API is connected.

## API Direction

The frontend should not call third-party AI or voice providers directly. API keys must stay on the VPS backend.

Planned backend endpoints:

```http
GET /api/models
POST /api/chat
POST /api/tts
```

Chat request shape:

```json
{
  "model": "gemini-2.5-flash",
  "messages": [
    { "role": "user", "content": "hello" }
  ],
  "stream": true
}
```

TTS request shape:

```json
{
  "text": "想听一条耳边话。",
  "voiceId": "elevenlabs-voice-id",
  "format": "mp3"
}
```

## Storage Strategy

Chat records should default to local device storage, not VPS storage.

Recommended browser storage:

- IndexedDB for conversations and messages.
- LocalStorage only for lightweight settings.
- Export Pod should support JSON backup for migration.
- Markdown or TXT export can be added for readable archives.

Voice files should not be permanently stored on the VPS by default. Voice messages should support playback and download. Optional VPS TTS cache can be added later with a strict size/time limit.

## Asset Plan

### Backgrounds

Six approved backgrounds are available for the first version.

Suggested names and usage:

| Asset Name | Usage |
|---|---|
| `bg-home-cloudroom` | Home / first home |
| `bg-paper-diary` | Default feature pages |
| `bg-signal-heart` | SwitchCore / Whisperline |
| `bg-sleepy-kitten` | Whisperline / bedtime mode |
| `bg-star-notes-bond` | Little Star Notes / anniversary pages |
| `bg-hidey-export` | Hidey Hole / Export Pod |

### Module Icons

Twelve module icons have been approved visually. The source images may have checkerboard backgrounds baked in, so they should be cleaned before final use.

Recommended filenames:

```text
icon-purr-channel.png
icon-whisperline.png
icon-meme-box.png
icon-sweetie-pocket.png
icon-furever-fund.png
icon-little-star-notes.png
icon-catch-purring.png
icon-paw-trail.png
icon-purr-todos.png
icon-switchcore.png
icon-hidey-hole.png
icon-export-pod.png
```

### App Icon and Mascot

Approved usage:

| Asset | Usage |
|---|---|
| `app-icon-codeandpurrs.png` | PWA / phone home-screen icon |
| `mascot-ashen-neko-family.png` | Home illustration, anniversary page, empty states, about page |

### Voice Decorations

Approved voice decoration assets:

```text
voice-wave-sticker.png
voice-cat-ear-sticker.png
voice-paw-mic.png
voice-download-cloud.png
voice-play-star.png
voice-play-charm.png
```

Use these for Whisperline, voice bubbles, play/download controls, and saved voice items.

## Visual Rules

1. Mobile-first layout.
2. Pastel pink, lavender, baby blue, cream, and soft gray-purple palette.
3. Avoid pure black text on pastel backgrounds.
4. Use soft glass cards and readable overlays on detailed backgrounds.
5. Home can be more decorative; chat pages must prioritize readability.
6. Icons should be large enough on room cards, typically 64px to 96px.
7. Bottom navigation icons should use simpler symbols if needed, because detailed icons may blur at 24px.

## Safety and Privacy Boundaries

Location and app usage features must be voluntary and transparent.

Allowed:

- Manual location check-in.
- User-authorized app usage bridge for the user's own Android device.
- Clear pause/delete/export controls.

Not allowed:

- Covert tracking.
- Hidden background surveillance.
- Monitoring other people without consent.
- Bypassing OS permissions.

## Suggested Implementation Stack

Recommended first version:

```text
Vite + React + TypeScript
CSS modules or Tailwind CSS
IndexedDB for local persistence
PM2 deployment on VPS
```

The initial frontend can be built independently, then connected to the VPS model router once `/api/models`, `/api/chat`, and `/api/tts` are available.
