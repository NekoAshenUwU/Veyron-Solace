#!/usr/bin/env python3
"""
第 3 步：让 /api/phone-sync 把 usage_sessions / screen_events 写进库。

关键：入库代码必须插在 app_usage 那个 422 早退【之前】。
原handler 里有这么一段——

    if not app_usage:
        return JSONResponse({... 'status': 'empty' ...}, status_code=422)

它在写库之前就 return 了。要是哪次上报只带会话不带 app_usage（比如冷启动
补同步那条路），会话会被整个丢掉，而且悄无声息。

只动 receive_phone_data 一个函数，匹配不上就中止、不落盘。
"""

import pathlib
import sys

SERVER = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/root/server.py")

BLOCK = '''        # ── 事件式会话入库 ───────────────────────────────────────────
        # 必须在下面 app_usage 的 422 早退之前：那个早退在写库前就 return，
        # 只带 sessions 不带 app_usage 的上报会被整个丢掉。
        sessions_written = 0
        screen_written = 0
        try:
            _sessions = body.get("usage_sessions") or []
            _screen = body.get("screen_events") or []
            if _sessions or _screen:
                _now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
                _conn = _dream_conn()
                try:
                    _before = _conn.total_changes
                    for _s in _sessions:
                        if not isinstance(_s, dict):
                            continue
                        _pkg = _s.get("package")
                        _start = _s.get("start_ts")
                        _end = _s.get("end_ts")
                        if not _pkg or not _start or not _end:
                            continue
                        # open=1 的会话下次会带真实 end_ts 回来覆盖同一行。
                        # 但已经封口的（库里 open=0）不再允许被改——迟到的重复
                        # 上报不该把一条正确的记录改坏。
                        _conn.execute(
                            "INSERT INTO usage_sessions "
                            "(package, label, start_ts, end_ts, duration_ms, open, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT(package, start_ts) DO UPDATE SET "
                            "  end_ts = excluded.end_ts, "
                            "  duration_ms = excluded.duration_ms, "
                            "  open = excluded.open, "
                            "  label = COALESCE(excluded.label, usage_sessions.label) "
                            "WHERE usage_sessions.open = 1",
                            (_pkg, _s.get("label"), _start, _end,
                             int(_s.get("duration_ms") or 0),
                             1 if _s.get("open") else 0, _now_iso),
                        )
                    sessions_written = _conn.total_changes - _before

                    _before = _conn.total_changes
                    for _e in _screen:
                        if not isinstance(_e, dict):
                            continue
                        _type = _e.get("event_type")
                        _ts = _e.get("ts")
                        if not _type or not _ts:
                            continue
                        _conn.execute(
                            "INSERT INTO screen_events (event_type, ts, created_at) "
                            "VALUES (?, ?, ?) ON CONFLICT(event_type, ts) DO NOTHING",
                            (_type, _ts, _now_iso),
                        )
                    screen_written = _conn.total_changes - _before
                    _conn.commit()
                finally:
                    _conn.close()
                print(f"phone-sync: sessions={sessions_written} screen={screen_written}")
        except Exception as _err:
            # 事件入库失败不该连累旧的 app_usage 快照上报
            print("phone-sync: 事件入库失败:", _err)
        # ─────────────────────────────────────────────────────────────

'''

ANCHOR = "        app_usage_written = 0\n        debug = {}"


def main() -> int:
    t = SERVER.read_text()

    if "usage_sessions" in t:
        print("  · 已经打过补丁，跳过")
        return 0

    n = t.count(ANCHOR)
    if n != 1:
        print(f"× 锚点匹配到 {n} 处（需要正好 1 处），已中止，文件未改动", file=sys.stderr)
        return 1

    SERVER.write_text(t.replace(ANCHOR, BLOCK + ANCHOR, 1))
    print("  ✓ 事件入库已插入（在 422 早退之前）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
