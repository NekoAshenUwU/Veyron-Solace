package uk.nekopurrs.usagebridge;

import android.content.Context;

public class HourlySyncScheduler {
    public static void schedule(Context context) {
        UsageSyncWorker.schedule(context);
    }
}
