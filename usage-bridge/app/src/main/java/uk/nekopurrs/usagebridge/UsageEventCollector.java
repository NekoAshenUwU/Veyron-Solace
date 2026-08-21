package uk.nekopurrs.usagebridge;

import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 把 UsageStatsManager 的原始事件流，配对成「一段一段的使用会话」。
 *
 * 为什么不继续用 queryUsageStats：那个只给「今天这个 app 累计用了多久」，
 * 还原不出时段。区分不了「连续刷到两点」和「九点睡、两点醒来摸一下、又睡回去」——
 * 而后者才是真正想知道的事。
 */
public class UsageEventCollector {

    private static final String PREFS = "neko_usage_bridge";
    private static final String KEY_CURSOR = "last_synced_event_ts";

    /** 首次运行回溯多久 */
    private static final long FIRST_RUN_BACKFILL_MS = 3L * 24 * 60 * 60 * 1000;

    /**
     * 游标最多往回退多久。系统事件多数机型只留 7 天，更早的查了也是空，
     * 白白拉长查询。留 6 天余量。
     */
    private static final long MAX_LOOKBACK_MS = 6L * 24 * 60 * 60 * 1000;

    /** 短于这个的会话丢掉，都是切来切去的噪音 */
    private static final long MIN_SESSION_MS = 1000L;

    // 用数值而不是常量名比较：API 29 以下叫 MOVE_TO_FOREGROUND / MOVE_TO_BACKGROUND，
    // 29 起改名 ACTIVITY_RESUMED / ACTIVITY_PAUSED，数值没变。用数值就不必care编译期 SDK 版本。
    private static final int EV_RESUMED = 1;
    private static final int EV_PAUSED = 2;
    private static final int EV_SCREEN_INTERACTIVE = 15;
    private static final int EV_SCREEN_NON_INTERACTIVE = 16;
    private static final int EV_KEYGUARD_SHOWN = 17;
    private static final int EV_KEYGUARD_HIDDEN = 18;

    public static class Result {
        public final JSONArray sessions;
        public final JSONArray screenEvents;
        /** 这次查询窗口的右端。上报成功后把游标推到这里，不要用「提交那一刻」，否则会留缝或重叠。 */
        public final long windowEnd;

        Result(JSONArray sessions, JSONArray screenEvents, long windowEnd) {
            this.sessions = sessions;
            this.screenEvents = screenEvents;
            this.windowEnd = windowEnd;
        }

        public boolean isEmpty() {
            return sessions.length() == 0 && screenEvents.length() == 0;
        }
    }

    public static long cursor(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long saved = prefs.getLong(KEY_CURSOR, 0L);
        long now = System.currentTimeMillis();

        if (saved <= 0) {
            return now - FIRST_RUN_BACKFILL_MS;   // 第一次跑，回溯三天
        }
        long floor = now - MAX_LOOKBACK_MS;
        return Math.max(saved, floor);            // 太久没同步的，超出保留期的部分本来也没了
    }

    /** 只在上报成功之后调，失败了游标必须留在原地，下次重来。 */
    public static void commitCursor(Context context, long windowEnd) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putLong(KEY_CURSOR, windowEnd)
                .apply();
    }

    public static Result collect(Context context) {
        long begin = cursor(context);
        long end = System.currentTimeMillis();
        return collect(context, begin, end);
    }

    public static Result collect(Context context, long begin, long end) {
        JSONArray sessions = new JSONArray();
        JSONArray screenEvents = new JSONArray();

        UsageStatsManager manager =
                (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);
        if (manager == null) {
            return new Result(sessions, screenEvents, begin);   // 拿不到就别推游标
        }

        UsageEvents events = manager.queryEvents(begin, end);
        if (events == null) {
            return new Result(sessions, screenEvents, begin);
        }

        // 同一时刻只有一个 app 在前台，所以只维护一个「当前打开的」就够，
        // 也天然处理了 A 还没 PAUSED 就来了 B 的 RESUMED 这种交错。
        String openPkg = null;
        long openStart = 0L;

        UsageEvents.Event e = new UsageEvents.Event();
        while (events.hasNextEvent()) {
            events.getNextEvent(e);
            int type = e.getEventType();
            long ts = e.getTimeStamp();

            switch (type) {
                case EV_RESUMED: {
                    // 连着两个 RESUMED（切后台没触发 PAUSED）：用后一个把前一段封口
                    if (openPkg != null) {
                        addSession(context, sessions, openPkg, openStart, ts, false);
                    }
                    openPkg = e.getPackageName();
                    openStart = ts;
                    break;
                }
                case EV_PAUSED: {
                    if (openPkg != null && openPkg.equals(e.getPackageName())) {
                        addSession(context, sessions, openPkg, openStart, ts, false);
                        openPkg = null;
                        openStart = 0L;
                    }
                    // openPkg 对不上说明这条 PAUSED 的开头在窗口之前，没有起点就不造一条
                    break;
                }
                case EV_SCREEN_INTERACTIVE:
                    addScreenEvent(screenEvents, "interactive", ts);
                    break;
                case EV_SCREEN_NON_INTERACTIVE:
                    addScreenEvent(screenEvents, "non_interactive", ts);
                    break;
                case EV_KEYGUARD_SHOWN:
                    addScreenEvent(screenEvents, "keyguard_shown", ts);
                    break;
                case EV_KEYGUARD_HIDDEN:
                    addScreenEvent(screenEvents, "keyguard_hidden", ts);
                    break;
                default:
                    break;
            }
        }

        // 扫完还开着 = app 现在就在前台。先用同步时刻封口并标 open，
        // 下次真的 PAUSED 回来时靠 UNIQUE(package, start_ts) UPSERT 覆盖成真实值。
        if (openPkg != null) {
            addSession(context, sessions, openPkg, openStart, end, true);
        }

        return new Result(sessions, screenEvents, end);
    }

    private static void addSession(Context context, JSONArray out,
                                   String pkg, long startMs, long endMs, boolean open) {
        long duration = endMs - startMs;
        if (duration < MIN_SESSION_MS) return;   // 噪音

        try {
            JSONObject o = new JSONObject();
            o.put("package", pkg);
            o.put("label", label(context, pkg));
            o.put("start_ts", iso(startMs));
            o.put("end_ts", iso(endMs));
            o.put("duration_ms", duration);
            o.put("open", open);
            out.put(o);
        } catch (Exception ignored) {
            // 单条坏了不该拖垮整次采集
        }
    }

    private static void addScreenEvent(JSONArray out, String type, long ts) {
        try {
            JSONObject o = new JSONObject();
            o.put("event_type", type);
            o.put("ts", iso(ts));
            out.put(o);
        } catch (Exception ignored) {
        }
    }

    private static String label(Context context, String pkg) {
        try {
            PackageManager pm = context.getPackageManager();
            ApplicationInfo info = pm.getApplicationInfo(pkg, 0);
            CharSequence l = pm.getApplicationLabel(info);
            return PlatformNames.friendlyName(pkg, l == null ? pkg : l.toString());
        } catch (Exception e) {
            return PlatformNames.friendlyName(pkg, pkg);
        }
    }

    /** ISO8601 带时区偏移，跟现有上报的 synced_at 格式保持一致 */
    private static String iso(long ms) {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.getDefault())
                .format(new Date(ms));
    }

    private UsageEventCollector() {
    }
}
