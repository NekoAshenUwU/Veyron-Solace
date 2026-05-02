package uk.nekopurrs.usagebridge;

import java.util.Locale;

public class PlatformNames {
    public static String friendlyName(String packageName, String fallback) {
        if (packageName == null) return fallback;
        switch (packageName) {
            case "org.mozilla.firefox": return "Firefox（GPT 网页版）";
            case "com.xingin.xhs": return "小红书";
            case "com.ss.android.ugc.aweme": return "抖音";
            case "com.tencent.mm": return "微信";
            case "com.whatsapp": return "WhatsApp";
            case "com.android.chrome": return "Chrome";
            case "com.huawei.browser": return "华为浏览器";
            case "com.deepseek.chat": return "DeepSeek";
            case "com.anthropic.claude": return "Claude";
            case "com.google.android.apps.bard": return "Gemini";
            case "ai.x.grok": return "Grok";
            case "com.sina.weibo": return "微博";
            case "com.shuiyinyu.dashen": return "独播库（刷剧）";
            default:
                if (packageName.toLowerCase(Locale.ROOT).contains("gbox")) return "GBox / Google 应用容器";
                return fallback;
        }
    }

    public static boolean isTracked(String packageName) {
        if (packageName == null) return false;
        return friendlyName(packageName, null) != null;
    }
}
