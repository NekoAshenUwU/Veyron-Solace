# Neko Usage Bridge - Tracked Apps

Neko 常用平台映射表，用来把 Android package name 显示成更好懂的名字，并在后续统计里优先展示。

| 平台 | Package / 识别方式 | 备注 |
|---|---|---|
| Firefox | `org.mozilla.firefox` | GPT 网页版常用入口 |
| 小红书 | `com.xingin.xhs` | 已在截图中确认 |
| 抖音 | `com.ss.android.ugc.aweme` | 已在截图中确认 |
| 微信 | `com.tencent.mm` | 已在截图中确认 |
| WhatsApp | `com.whatsapp` | 已在截图中确认 |
| Chrome | `com.android.chrome` | 已在截图中确认 |
| 华为浏览器 | `com.huawei.browser` | 已在截图中确认 |
| DeepSeek | `com.deepseek.chat` | 待手机统计确认 |
| Claude | `com.anthropic.claude` | 待手机统计确认 |
| Gemini | `com.google.android.apps.bard` 或 GBox 容器 | 待手机统计确认 |
| Grok | `ai.x.grok` 或 GBox 容器 | 待手机统计确认 |
| 微博 | `com.sina.weibo` | 待手机统计确认 |
| 独播库 | `com.shuiyinyu.dashen` | 截图中出现，疑似刷剧 App |
| GBox | package 包含 `gbox` | Google 应用容器，可能承载 Gemini / Grok |

下一步：在 `MainActivity.java` 里增加 friendly name mapping、tracked app section，并过滤系统应用。