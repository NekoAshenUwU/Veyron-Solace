package uk.nekopurrs.usagebridge;

import android.app.Activity;
import android.app.AppOpsManager;
import android.app.usage.UsageStats;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public class TrackedActivity extends Activity {
    private static final String ENDPOINT = "http://178.128.127.91:8890/api/phone-sync";
    private static final String DREAM_EVENT_ENDPOINT = "http://178.128.127.91:8890/api/dream/event";
    private static final String TOKEN = "nekopurrs-secret-2026";
    private TextView status;
    private TextView output;

    static class AppUsage {
        String packageName;
        String appName;
        long foregroundMs;
        boolean favorite;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        refreshSummary();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshSummary();
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(26), dp(20), dp(26));
        root.setBackgroundColor(0xFFFFF4FA);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("🐱 Neko Usage Bridge");
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(0xFF2D2435);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("常用平台统计 · 活动时间线 · 同步到 VPS / MCP");
        subtitle.setTextSize(14);
        subtitle.setTextColor(0xFF8A7A94);
        subtitle.setPadding(0, dp(8), 0, dp(18));
        root.addView(subtitle);

        status = new TextView(this);
        status.setTextSize(14);
        status.setTextColor(0xFF5D4C68);
        status.setPadding(dp(14), dp(14), dp(14), dp(14));
        status.setBackgroundColor(0xFFFFFFFF);
        root.addView(status);

        Button perm = button("打开使用情况访问权限");
        perm.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)));
        root.addView(perm);

        Button refresh = button("刷新今日统计");
        refresh.setOnClickListener(v -> refreshSummary());
        root.addView(refresh);

        Button sync = button("立即同步到 VPS");
        sync.setOnClickListener(v -> syncNow());
        root.addView(sync);

        output = new TextView(this);
        output.setTextSize(13);
        output.setTextColor(0xFF2D2435);
        output.setPadding(0, dp(18), 0, 0);
        output.setLineSpacing(4, 1.0f);
        root.addView(output);
        setContentView(scroll);
    }

    private Button button(String text) {
        Button btn = new Button(this);
        btn.setText(text);
        btn.setTextSize(15);
        btn.setTextColor(0xFFFFFFFF);
        btn.setAllCaps(false);
        btn.setBackgroundColor(0xFFB995DD);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(14), 0, 0);
        btn.setLayoutParams(lp);
        btn.setGravity(Gravity.CENTER);
        return btn;
    }

    private boolean hasUsageAccess() {
        AppOpsManager appOps = (AppOpsManager) getSystemService(Context.APP_OPS_SERVICE);
        int mode = appOps.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, android.os.Process.myUid(), getPackageName());
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

    private List<AppUsage> getTodayUsage() {
        UsageStatsManager manager = (UsageStatsManager) getSystemService(Context.USAGE_STATS_SERVICE);
        List<UsageStats> stats = manager.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, startOfToday(), System.currentTimeMillis());
        List<AppUsage> result = new ArrayList<>();
        if (stats == null) return result;
        for (UsageStats s : stats) {
            long ms = s.getTotalTimeInForeground();
            if (ms < 1000) continue;
            AppUsage item = new AppUsage();
            item.packageName = s.getPackageName();
            item.appName = getAppName(item.packageName);
            item.foregroundMs = ms;
            item.favorite = PlatformNames.isTracked(item.packageName);
            result.add(item);
        }
        Collections.sort(result, (a, b) -> Long.compare(b.foregroundMs, a.foregroundMs));
        return result;
    }

    private String getAppName(String packageName) {
        try {
            PackageManager pm = getPackageManager();
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

    private JSONObject buildPayload() throws Exception {
        List<AppUsage> usage = getTodayUsage();
        long total = 0;
        JSONArray apps = new JSONArray();
        JSONArray favorites = new JSONArray();
        for (AppUsage u : usage) {
            total += u.foregroundMs;
            JSONObject app = new JSONObject();
            app.put("package", u.packageName);
            app.put("name", u.appName);
            app.put("duration_ms", u.foregroundMs);
            app.put("minutes", u.foregroundMs / 60000);
            app.put("favorite", u.favorite);
            apps.put(app);
            if (u.favorite) favorites.put(app);
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
        root.put("source", "Neko Usage Bridge");
        return root;
    }

    private void refreshSummary() {
        boolean allowed = hasUsageAccess();
        status.setText(allowed ? "✅ 使用情况权限已开启" : "⚠️ 还没开启使用情况权限。点上面的按钮，允许 Neko Usage Bridge。");
        if (!allowed) {
            output.setText("授权后回到这里，点“刷新今日统计”。");
            return;
        }
        List<AppUsage> usage = getTodayUsage();
        long total = 0;
        for (AppUsage u : usage) total += u.foregroundMs;
        StringBuilder fav = new StringBuilder();
        int favCount = 0;
        for (AppUsage u : usage) {
            if (!u.favorite) continue;
            favCount++;
            fav.append(favCount).append(". ").append(u.appName).append(" — ").append(formatMs(u.foregroundMs)).append("\n   ").append(u.packageName).append("\n\n");
        }
        StringBuilder all = new StringBuilder();
        int limit = Math.min(20, usage.size());
        for (int i = 0; i < limit; i++) {
            AppUsage u = usage.get(i);
            all.append(i + 1).append(". ").append(u.appName).append("\n   ").append(formatMs(u.foregroundMs)).append(" · ").append(u.packageName).append("\n\n");
        }
        output.setText("今日总使用：" + formatMs(total) + "\n\n常用平台：\n" + (fav.length() == 0 ? "暂时没读到常用平台。\n\n" : fav.toString()) + "全部记录 Top 20：\n" + (all.length() == 0 ? "暂时没有读到记录。" : all.toString()));
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

    private int syncDreamEvents() throws Exception {
        List<AppUsage> usage = getTodayUsage();
        int sent = 0;
        int limit = 0;
        String device = android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL;
        for (AppUsage u : usage) {
            if (!u.favorite || u.foregroundMs < 60000) continue;
            JSONObject meta = new JSONObject();
            meta.put("duration_ms", u.foregroundMs);
            meta.put("duration", formatMs(u.foregroundMs));
            meta.put("minutes", u.foregroundMs / 60000);
            JSONObject event = new JSONObject();
            event.put("device_id", device);
            event.put("type", "app_usage_snapshot");
            event.put("package", u.packageName);
            event.put("label", u.appName);
            event.put("value", "今日常用平台快照：" + u.appName);
            event.put("source", "Neko Usage Bridge");
            event.put("meta", meta);
            int code = postJson(DREAM_EVENT_ENDPOINT, event);
            if (code >= 200 && code < 300) sent++;
            limit++;
            if (limit >= 8) break;
        }
        return sent;
    }

    private void syncNow() {
        if (!hasUsageAccess()) {
            status.setText("⚠️ 请先开启使用情况访问权限。");
            return;
        }
        status.setText("同步中…");
        new Thread(() -> {
            try {
                JSONObject payload = buildPayload();
                int usageCode = postJson(ENDPOINT, payload);
                int eventCount = usageCode >= 200 && usageCode < 300 ? syncDreamEvents() : 0;
                runOnUiThread(() -> status.setText(usageCode >= 200 && usageCode < 300 ? "✅ 已同步到 VPS · 活动事件 " + eventCount + " 条" : "⚠️ 同步失败 HTTP " + usageCode));
            } catch (Exception e) {
                runOnUiThread(() -> status.setText("⚠️ 同步失败：" + e.getMessage()));
            }
        }).start();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
