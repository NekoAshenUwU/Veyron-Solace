#!/usr/bin/env bash
# 把缓存保活心跳接上定时器。
# heartbeat.mjs 早就写好了，只是从来没有任何东西叫过它（2026-08-20 查明：
# package.json / pm2 / crontab / systemd 里都没有引用，日志里跑过 0 次）。
set -euo pipefail

APP="${APP:-/var/www/codeandpurrs}"
SRC="$(cd "$(dirname "$0")" && pwd)"

[[ -f "$APP/server/heartbeat.mjs" ]] || { echo "找不到 $APP/server/heartbeat.mjs"; exit 1; }

echo "== 先看 MAX_SNAPSHOT_AGE_HOURS 是怎么取值的"
grep -n "MAX_SNAPSHOT_AGE_HOURS" "$APP/server/heartbeat.mjs" | head -5
echo "   ↑ 它读的环境变量叫 HEARTBEAT_MAX_AGE_HOURS（不是 MAX_SNAPSHOT_AGE_HOURS，"
echo "     后者只是代码里的常量名）。service 里设的就是前者。"
echo

echo "== 装 systemd unit"
install -m 644 "$SRC/codeandpurrs-heartbeat.service" "$SRC/codeandpurrs-heartbeat.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now codeandpurrs-heartbeat.timer

echo
echo "== 立刻跑一次看看"
systemctl start codeandpurrs-heartbeat.service || true
sleep 2
journalctl -u codeandpurrs-heartbeat.service -n 20 --no-pager

echo
echo "== 下次什么时候跑"
systemctl list-timers codeandpurrs-heartbeat.timer --no-pager
