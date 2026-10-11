package com.hanilsteel.portal;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.webkit.CookieManager;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

//  🔔 메신저 새 쪽지 알림 — 앱을 닫아 두어도 메신저에 새 글이 오면 폰 알림을 띄운다.
//   ⭐ 포털은 손대지 않는다: 메신저 화면이 쓰는 /api/chat/channels(방마다 안 읽은 수·마지막 글)를 앱이 30초마다 본다.
//   ⚠ 안드로이드는 앱이 몰래 뒤에서 도는 것을 막으므로 「쪽지 알림 받는 중」 작은 알림을 하나 띄워 두고 돈다(조용한 알림).
//   ⚠ 화면이 꺼져 오래 있으면 폰이 잠들어 몇 분 늦을 수 있다 — 5분마다 깨우는 알람을 덧대 둔다.
//   ⚠ 로그인은 앱 화면(WebView)의 로그인을 그대로 쓴다(같은 쿠키). 로그아웃 상태면 조용히 쉰다.
public class ChatWatch extends Service {

    static final String CH_MSG = "chat";        //  새 쪽지(소리·진동)
    static final String CH_RUN = "watch";       //  「알림 받는 중」(조용히)
    static final int ID_RUN = 1;
    static final long EVERY = 30_000;

    //  앱 화면이 메신저를 보고 있으면 알림을 띄우지 않는다(이미 보고 있다)
    static volatile boolean viewingChat;
    static volatile ChatWatch running;

    HandlerThread th;
    Handler h;

    static void start(Context c) {
        ChatWatch w = running;
        if (w != null && w.h != null) {
            //  이미 돌고 있으면 깨워서 한 번 보게만 한다(뒤에서 서비스를 또 켜는 것은 안드로이드가 막을 수 있다)
            w.h.removeCallbacks(w.loop);
            w.h.post(w.loop);
            arm(c);
            return;
        }
        try {
            ContextCompat.startForegroundService(c, new Intent(c, ChatWatch.class));
        } catch (Exception e) {
            //  안드로이드가 지금은 못 띄우게 하면(뒤에서 켜기 제한) 다음 알람 때 다시 한다
        }
        arm(c);
    }

    //  ⏰ 5분마다 깨우는 알람 — 폰이 잠들어 있어도 한 번씩 본다
    static void arm(Context c) {
        try {
            AlarmManager am = (AlarmManager) c.getSystemService(ALARM_SERVICE);
            PendingIntent pi = PendingIntent.getBroadcast(c, 7, new Intent(c, Wake.class),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            am.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + 5 * 60_000, pi);
        } catch (Exception e) {
            //  알람이 안 되어도 30초 돌기는 그대로
        }
    }

    //  ⏰ 알람·폰 켜짐 → 감시를 다시 세운다
    public static class Wake extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            if (!c.getSharedPreferences("hanil", MODE_PRIVATE).getBoolean("chatNotify", true)) return;
            start(c);
        }
    }

    static void channels(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        NotificationChannel m = new NotificationChannel(CH_MSG, "메신저 새 쪽지", NotificationManager.IMPORTANCE_HIGH);
        m.setDescription("포털 메신저에 새 글이 오면 알려 드립니다");
        m.enableVibration(true);
        nm.createNotificationChannel(m);
        NotificationChannel r = new NotificationChannel(CH_RUN, "쪽지 알림 받는 중", NotificationManager.IMPORTANCE_MIN);
        r.setDescription("앱이 꺼져 있어도 새 쪽지를 받기 위해 늘 떠 있는 알림입니다(꺼도 됩니다)");
        r.setShowBadge(false);
        nm.createNotificationChannel(r);
    }

    @Override
    public void onCreate() {
        super.onCreate();
        channels(this);
        Notification n = new NotificationCompat.Builder(this, CH_RUN)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("한일특장 포털")
                .setContentText("메신저 새 쪽지를 받고 있습니다")
                .setPriority(NotificationCompat.PRIORITY_MIN)
                .setOngoing(true)
                .setShowWhen(false)
                .setContentIntent(openApp(this, null, 0))
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(ID_RUN, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(ID_RUN, n);
            }
        } catch (Exception e) {
            stopSelf();
            return;
        }
        th = new HandlerThread("chatwatch");
        th.start();
        h = new Handler(th.getLooper());
        h.post(loop);
        running = this;
    }

    final Runnable loop = new Runnable() {
        @Override
        public void run() {
            PowerManager.WakeLock wl = null;
            try {
                wl = ((PowerManager) getSystemService(POWER_SERVICE))
                        .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "hanil:chat");
                wl.acquire(20_000);         //  한 번 묻는 동안만 깨어 있는다
                check();
            } catch (Exception e) {
                //  못 물어봐도 다음에 다시
            } finally {
                if (wl != null && wl.isHeld()) wl.release();
            }
            if (h != null) h.postDelayed(this, EVERY);
        }
    };

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (h != null) {
            h.removeCallbacks(loop);
            h.post(loop);           //  알람으로 깨었으면 곧바로 한 번 본다
        }
        arm(this);
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = null;
        if (th != null) th.quitSafely();
        h = null;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // ── 새 글이 왔나 ───────────────────────────────────────────
    void check() throws Exception {
        if (!getSharedPreferences("hanil", MODE_PRIVATE).getBoolean("chatNotify", true)) {
            stopSelf();
            return;
        }
        String base = null;
        String body = null;
        //  ⭐ 마지막으로 붙었던 곳부터(회사 와이파이 ↔ 밖) — 로그인 쿠키는 주소마다 따로다
        String last = getSharedPreferences("hanil", MODE_PRIVATE).getString("base", MainActivity.WAN);
        for (String b : new String[]{last, last.equals(MainActivity.LAN) ? MainActivity.WAN : MainActivity.LAN}) {
            body = get(b + "/api/chat/channels", b.equals(MainActivity.LAN) ? 1500 : 5000);
            if (body != null) {
                base = b;
                break;
            }
        }
        if (base == null) return;
        JSONObject o = new JSONObject(body);
        JSONArray chans = o.optJSONArray("channels");
        if (chans == null) return;

        SharedPreferences sp = getSharedPreferences("hanilChat", MODE_PRIVATE);
        SharedPreferences.Editor ed = sp.edit();
        boolean first = !sp.getBoolean("_init", false);     //  처음 돌 때는 지난 글로 알림을 쏟지 않는다
        for (int i = 0; i < chans.length(); i++) {
            JSONObject c = chans.getJSONObject(i);
            int id = c.optInt("id");
            int unread = c.optInt("unread");
            JSONObject lm = c.optJSONObject("last");
            String key = "c" + id;
            String sig = lm == null ? "" : (lm.optString("at") + "|" + lm.optString("body"));
            String seen = sp.getString(key, "");
            if (unread <= 0) {
                ed.putString(key, sig);
                NotificationManagerCompat.from(this).cancel(1000 + id);     //  다른 곳에서 읽었으면 알림도 걷는다
                continue;
            }
            if (sig.equals(seen)) continue;
            ed.putString(key, sig);
            if (first || viewingChat || lm == null) continue;
            boolean dm = "dm".equals(c.optString("kind"));
            String name = c.optString("name", "메신저");
            String who = lm.optString("who", "");
            String title = dm ? name : ("# " + name);
            String text = (dm || who.isEmpty() ? "" : who + ": ") + lm.optString("body", "");
            if (unread > 1) title += "  (" + unread + ")";
            notifyMsg(id, title, text);
        }
        ed.putBoolean("_init", true).apply();
    }

    void notifyMsg(int id, String title, String text) {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return;
        }
        Notification n = new NotificationCompat.Builder(this, CH_MSG)
                .setSmallIcon(R.drawable.ic_stat)
                .setColor(0xFF1B2A4A)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setCategory(NotificationCompat.CATEGORY_MESSAGE)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setDefaults(NotificationCompat.DEFAULT_ALL)
                .setAutoCancel(true)
                .setContentIntent(openApp(this, "/chat", id))
                .build();
        NotificationManagerCompat.from(this).notify(1000 + id, n);
    }

    //  알림을 누르면 앱이 열리고 그 대화방으로 간다
    static PendingIntent openApp(Context c, String path, int cid) {
        Intent i = new Intent(c, MainActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (path != null) {
            i.putExtra("path", path);
            i.putExtra("cid", cid);
        }
        return PendingIntent.getActivity(c, 2000 + cid, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    String get(String url, int connectMs) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(connectMs);
            c.setReadTimeout(10000);
            c.setUseCaches(false);
            c.setInstanceFollowRedirects(false);
            String ck = CookieManager.getInstance().getCookie(url);
            if (ck == null || ck.isEmpty()) return null;            //  이 주소로는 로그인한 적이 없다
            c.setRequestProperty("Cookie", ck);
            c.setRequestProperty("Accept", "application/json");
            if (c.getResponseCode() != 200) return null;             //  로그아웃(401) 등
            InputStream in = c.getInputStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) > 0) out.write(buf, 0, r);
            String s = out.toString("UTF-8");
            return s.trim().startsWith("{") ? s : null;
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }
}
