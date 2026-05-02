package uk.nekopurrs.usagebridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class HourlySyncReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        if (!HourlySyncScheduler.ACTION_HOURLY_SYNC.equals(intent.getAction())) return;
        final PendingResult pendingResult = goAsync();
        new Thread(() -> {
            try {
                UsageSyncer.syncDreamEvents(context.getApplicationContext(), true);
                HourlySyncScheduler.schedule(context.getApplicationContext());
            } catch (Exception ignored) {
            } finally {
                pendingResult.finish();
            }
        }).start();
    }
}
