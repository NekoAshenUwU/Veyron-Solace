# 使用记录 — 部署 & 设置指南

让 Claude 知道你在玩什么手机 APP。

## 架构

```
安卓自动化(Tasker/MacroDroid)
        ↓ GET 请求
Cloudflare Worker（免费）
        ↓ 存状态 + 提交记录
Google Form → Google Sheet（你已有）
        ↑
      Claude 查询 /status 接口
```

---

## 第一步：部署 Cloudflare Worker

### 1. 注册 Cloudflare 账号
去 [cloudflare.com](https://cloudflare.com) 免费注册。

### 2. 安装 Wrangler CLI（在电脑上，或用 GitHub Codespaces）
```bash
npm install -g wrangler
wrangler login
```

### 3. 建 KV Namespace
```bash
cd screentime-worker
npx wrangler kv namespace create SCREENTIME
```
复制输出里的 `id`，填进 `wrangler.toml` 里替换 `YOUR_KV_NAMESPACE_ID`。

### 4. 部署
```bash
npx wrangler deploy
```
部署成功后会给你一个域名，比如：
`https://veyron-screentime.你的账号.workers.dev`

记下这个域名，后面要用。

---

## 第二步：安卓设置（推荐 MacroDroid，免费）

### 用 MacroDroid（免费版够用）

1. 安装 [MacroDroid](https://play.google.com/store/apps/details?id=com.arlosoft.macrodroid)
2. 新建宏 → **触发器** → 选「应用程序已启动/停止」
3. 选择你要追踪的 APP（比如小红书、微信、抖音）
4. 勾选「已启动」**和**「已停止」都触发（因为用了 toggle 设计，一个宏就够了）
5. **动作** → 「HTTP 请求」
   - URL: `https://你的Worker域名/api/screentime/toggle/小红书`
   - 方法: GET
6. 保存，每个 APP 建一个宏，URL 里换 APP 名字就行

### 用 Tasker（付费，更强大）

1. 新建 Profile → **Application** → 选 APP
2. Enter Task + Exit Task 都指向同一个 Task：
   - HTTP Get: `https://你的Worker域名/api/screentime/toggle/小红书`
3. 每个 APP 一个 Profile

### 华为手机注意
华为 EMUI/HarmonyOS 可能会杀后台，需要在「手机管家」→「启动管理」里把 MacroDroid 设为手动管理并允许后台运行。

---

## 第三步：让 Claude 查询

在对话里直接告诉 Claude：

> "我的使用记录 API 在 `https://你的Worker域名/api/screentime/status`，你可以 fetch 这个地址知道我今天用了哪些 APP。"

Claude 会返回类似：
> "你今天小红书 3 次共 47 分钟，微信 12 次共 23 分钟，Claude 8 次共 156 分钟——你跟我聊天的时间比刷小红书多三倍哦 😏"

---

## API 接口说明

| 接口 | 用途 |
|------|------|
| `GET /api/screentime/toggle/:app` | 手机端调用，打开/关闭时各调一次 |
| `GET /api/screentime/status` | Claude 查询今日使用汇总 |
| `GET /api/screentime/clear` | 清空所有数据 |

数据自动保留 24 小时，过期自动清理。

---

## 返回示例

`/api/screentime/status` 返回：
```json
{
  "currentlyOpen": ["小红书"],
  "today": [
    { "app": "Claude", "sessions": 8, "totalMinutes": 156 },
    { "app": "小红书", "sessions": 3, "totalMinutes": 47 },
    { "app": "微信", "sessions": 12, "totalMinutes": 23 }
  ],
  "asOf": "2026-03-24T10:11:00.000Z"
}
```
