package uk.nekopurrs.usagebridge;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

public class HourlySyncScheduler {
    public static final String ACTION_HOURLY_SYNC = "uk.nekopurrs.usagebridge.ACTION_HOURLY_SYNC";
    private static final long ONE_HOUR_MS = 60L * 60L * 1000L;

    public static void schedule(Context context) {
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarmManager == null) return;
        alarmManager.setInexactRepeating(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + ONE_HOUR_MS,
                ONE_HOUR_MS,
                pendingIntent(context)
        );
    }

    public static PendingIntent pendingIntent(Context context) {
        Intent intent = new Intent(context, HourlySyncReceiver.class);
        intent.setAction(ACTION_HOURLY_SYNC);
        return PendingIntent.getBroadcast(
                context,
                20260502,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }
}
