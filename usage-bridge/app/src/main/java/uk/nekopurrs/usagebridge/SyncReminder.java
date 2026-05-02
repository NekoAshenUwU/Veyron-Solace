package uk.nekopurrs.usagebridge;

import android.content.Context;
import android.content.SharedPreferences;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class SyncReminder {
    private static final String PREFS = "neko_usage_bridge";
    private static final String KEY_LAST_SYNC_AT = "last_sync_at";
    private static final long ONE_HOUR_MS = 60L * 60L * 1000L;

    public static long lastSyncAt(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return prefs.getLong(KEY_LAST_SYNC_AT, 0L);
    }

    public static void markSynced(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putLong(KEY_LAST_SYNC_AT, System.currentTimeMillis())
                .apply();
    }

    public static String message(Context context) {
        long last = lastSyncAt(context);
        if (last <= 0) {
            return "⏰ 还没记录同步时间，可以先同步一次活动时间线。";
        }
        long diff = System.currentTimeMillis() - last;
        if (diff >= ONE_HOUR_MS) {
            return "⏰ 距上次同步已超过 1 小时，可以同步一次活动时间线。上次：" + format(last);
        }
        long remain = Math.max(1L, (ONE_HOUR_MS - diff) / 60000L);
        return "✅ 一小时内已同步。上次：" + format(last) + "，约 " + remain + " 分钟后再同步。";
    }

    private static String format(long timeMs) {
        return new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(new Date(timeMs));
    }
}
