# ⛔ 这个目录已经停用 —— 是旧手机（华为）时代的 Bridge

**不要在这里继续开发。红米现在跑的是另一个仓库：**

## 👉 https://github.com/NekoAshenUwU/neko-usage-bridge

---

## 怎么分辨这两个

| | 这里（停用）| neko-usage-bridge（现役）|
|---|---|---|
| 语言 | Java | **Kotlin** |
| 设备 | 华为 / HarmonyOS | **红米 / HyperOS** |
| Gradle 工程名 | —— | **NekoUsageBridge** |
| GitHub workflow | `build-usage-bridge` | **`build-apk`** |
| 产物 | —— | **`neko-usage-bridge-debug-apk`** |
| 上报端点 | `178.128.127.91:8890/api/phone-sync` | **`api.nekopurrs.uk/api/usage/ingest`** |
| 认证头 | `X-Auth-Token` | **`X-Bridge-Token`** |
| 最后一次真实提交 | 2026-05-12 | 2026-06-16（+ 一个开着的 PR）|

**最快的判断方法**：去 GitHub Actions 看跑的是哪个 workflow。看到 `build-apk` /
`neko-usage-bridge-debug-apk` / `NekoUsageBridge`，那就是现役那个，不是这里。

## 2026-08-21 的一次教训

那天把「事件式会话记录」（`UsageEventCollector.java` 等）写进了这个目录，
第二天才发现——**红米上装的 APK 根本不是从这里出的**，改了也白改。

之所以会认错：任务描述里写的是「Android 端（Java）」，而这里恰好是 Java，
就没再往下核对。真正该核对的是 **Actions 打出来的 artifact 名字**——那才
说明手机上装的是谁。

留在这里的那几个提交是死代码，别照着改。事件采集要重做在 Kotlin 那边，
架构不一样（OkHttp + kotlinx.serialization），不是照搬。

## 服务端那半边还是有效的

`usage-bridge/migrations/002_usage_events.py`（建两张表）和
`usage-bridge/server/patch-phone-sync.py`（入库）**跟手机端无关，仍然有用**。
只是接收端点要跟着现役 App 走 —— 现役走的是 `/api/usage/ingest`，
不是这里的 `/api/phone-sync`。
