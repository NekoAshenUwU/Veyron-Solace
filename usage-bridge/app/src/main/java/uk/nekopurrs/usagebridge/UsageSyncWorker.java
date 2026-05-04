package uk.nekopurrs.usagebridge;

import android.app.AppOpsManager;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;

import androidx.annotation.NonNull;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

public class UsageSyncWorker extends Worker {
    private static final String WORK_NAME = "neko_usage_bridge_auto_sync";

    /*
     * TODO:
     * 这里先沿用当前 Bridge 的 VPS 设置。
     * 之后建议改成 App 设置页填写，不要长期写死在源码里。
     */
    private static final String ENDPOINT = "http://178.128.127.91:8890/api/phone-sync";
    private static final String TOKEN = "nekopurrs-secret-2026";

    public UsageSyncWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    public static void schedule(Context context) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();

        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                UsageSyncWorker.class,
                15,
                TimeUnit.MINUTES
        )
                .setConstraints(constraints)
                .build();

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request
        );
    }

    @NonNull
    @Override
    public Result doWork() {
        Context context = getApplicationContext();

        if (!hasUsageAccess(context)) {
            return Result.success();
        }

        try {
            JSONObject payload = buildPayload(context);
            int code = postJson(ENDPOINT, payload);

            if (code >= 200 && code < 300) {
                SyncReminder.markSynced(context);
                return Result.success();
            }

            return Result.retry();
        } catch (Exception e) {
            return Result.retry();
        }
    }

    private boolean hasUsageAccess(Context context) {
        AppOpsManager appOps = (AppOpsManager) context.getSystemService(Context.APP_OPS_SERVICE);
        int mode = appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                android.os.Process.myUid(),
                context.getPackageName()
        );
        return mode == AppOpsManager.MODE_ALLOWED;
    }

    private long startOfToday() {
        Calendar cal = Calendar.getInstance();
        cal.set(Calendar.HOUR_OF_DAY, 0);
        cal.set(Calendar.MINUTE, 0);
        cal.set(Calendar.SECOND, 0);
        cal.set(Calendar.MILLISECOND, 0);
        return cal.getTimeInMillis();
    }

    private JSONObject buildPayload(Context context) throws Exception {
        UsageStatsManager manager =
                (UsageStatsManager) context.getSystemService(Context.USAGE_STATS_SERVICE);

        List<UsageStats> stats = manager.queryUsageStats(
                UsageStatsManager.INTERVAL_DAILY,
                startOfToday(),
                System.currentTimeMillis()
        );

        long total = 0;
        JSONArray apps = new JSONArray();
        JSONArray favorites = new JSONArray();

        if (stats != null) {
            for (UsageStats s : stats) {
                long ms = s.getTotalTimeInForeground();
                if (ms < 1000) continue;

                String packageName = s.getPackageName();
                String appName = getAppName(context, packageName);
                boolean favorite = PlatformNames.isTracked(packageName);

                total += ms;

                JSONObject app = new JSONObject();
                app.put("package", packageName);
                app.put("name", appName);
                app.put("duration_ms", ms);
                app.put("minutes", ms / 60000);
                app.put("favorite", favorite);

                apps.put(app);
                if (favorite) favorites.put(app);
            }
        }

        String date = new SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(new Date());

        JSONObject usageObj = new JSONObject();
        usageObj.put("date", date);
        usageObj.put("total_screen_time_ms", total);
        usageObj.put("total_screen_time", formatMs(total));
        usageObj.put("apps", apps);
        usageObj.put("favorite_apps", favorites);

        JSONObject root = new JSONObject();
        root.put("app_usage", usageObj);
        root.put("device", android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL);
        root.put("source", "Neko Usage Bridge AutoSync");
        root.put("synced_at", new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.getDefault()).format(new Date()));

        return root;
    }

    private String getAppName(Context context, String packageName) {
        try {
            PackageManager pm = context.getPackageManager();
            ApplicationInfo info = pm.getApplicationInfo(packageName, 0);
            CharSequence label = pm.getApplicationLabel(info);
            String fallback = label == null ? packageName : label.toString();
            return PlatformNames.friendlyName(packageName, fallback);
        } catch (Exception e) {
            return PlatformNames.friendlyName(packageName, packageName);
        }
    }

    private String formatMs(long ms) {
        long minutes = ms / 60000;
        long hours = minutes / 60;
        long rest = minutes % 60;
        if (hours > 0) return hours + "小时" + rest + "分钟";
        return rest + "分钟";
    }

    private int postJson(String endpoint, JSONObject payload) throws Exception {
        URL url = new URL(endpoint);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(10000);
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("X-Auth-Token", TOKEN);

        try (OutputStream os = conn.getOutputStream()) {
            os.write(payload.toString().getBytes("UTF-8"));
        }

        return conn.getResponseCode();
    }
          }
