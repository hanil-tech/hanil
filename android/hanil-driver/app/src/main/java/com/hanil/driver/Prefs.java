package com.hanil.driver;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * 폰에 저장해 두는 것 — 서버 주소 하나뿐이다.
 *
 * ⚠⚠ 로그인·열쇠(hdev 쿠키)는 여기 두지 않는다. 그것은 WebView 의 쿠키통이 갖고 있고,
 *   앱을 지우지 않는 한 3년 동안 남는다. 두 곳에 두면 언젠가 어긋난다.
 */
public final class Prefs {
    private static final String FILE = "hanil-driver";
    private static final String K_SERVER = "server";

    /** ⭐ 기본 주소 — 대부분 이대로 쓴다. 바뀌면 여기 한 곳만 고친다. */
    public static final String DEFAULT_SERVER = "https://work.hanil-steel.com";

    private Prefs() { }

    private static SharedPreferences sp(Context c) {
        return c.getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    public static String server(Context c) {
        return sp(c).getString(K_SERVER, "");
    }

    public static void setServer(Context c, String v) {
        sp(c).edit().putString(K_SERVER, normalize(v)).apply();
    }

    public static boolean isSet(Context c) {
        return server(c).length() > 0;
    }

    /**
     * 사람이 적은 주소를 쓸 수 있는 모양으로 고친다.
     * ⚠ 현장에서는 「work.hanil-steel.com」 처럼 앞을 빼고 적는다 — 그대로 두면 열리지 않는다.
     */
    public static String normalize(String raw) {
        String s = raw == null ? "" : raw.trim();
        if (s.length() == 0) return "";
        s = s.replaceAll("\\s+", "");
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "https://" + s;
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s;
    }
}
