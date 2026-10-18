package com.hanilsteel.portal;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Base64;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.webkit.WebViewAssetLoader;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

//  🧊 도면 보기 — 3D: STEP(.stp/.step) · IGES(.igs/.iges) · 2D: DWG · DXF
//   ⭐ 포털에서 도면 파일을 누르면 내려받는 대신 여기서 바로 본다(설치·서버 없이 — 앱 안의 viewer3d).
//   ⚠ 파일은 로그인(쿠키)을 붙여 앱 안 임시 칸(cache/view3d)에 받고, 화면은 그 파일을 읽는다. 밖으로 안 나간다.
//   ⚠ 뷰어는 assets/viewer3d (viewer3d/ 에서 만든 것 — 포털에 올리는 것과 같은 뷰어).
public class Viewer3dActivity extends Activity {

    static final Pattern EXT = Pattern.compile("\\.(stp|step|igs|iges|dwg|dxf)(\\?|#|$)", Pattern.CASE_INSENSITIVE);

    static boolean is3d(String s) {
        return s != null && EXT.matcher(s).find();
    }

    //  받는 이름 — filename*=UTF-8''… (한글 이름) 을 먼저, 없으면 filename="…", 없으면 주소 끝
    static String fileName(String url, String cd) {
        try {
            if (cd != null) {
                Matcher m = Pattern.compile("filename\\*\\s*=\\s*[^']*'[^']*'([^;]+)", Pattern.CASE_INSENSITIVE).matcher(cd);
                if (m.find()) return URLDecoder.decode(m.group(1).trim().replace("+", "%2B"), "UTF-8");
                m = Pattern.compile("filename\\s*=\\s*\"?([^\";]+)\"?", Pattern.CASE_INSENSITIVE).matcher(cd);
                if (m.find()) return m.group(1).trim();
            }
            String p = Uri.parse(url).getLastPathSegment();
            return p == null ? "model.stp" : p;
        } catch (Exception e) {
            return "model.stp";
        }
    }

    //  받아서 연다(받는 동안은 원래 화면에 「여는 중」)
    static void open(Activity from, String url, String name, String ua) {
        Toast.makeText(from, "도면을 여는 중… " + name, Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            HttpURLConnection c = null;
            try {
                File dir = new File(from.getCacheDir(), "view3d");
                dir.mkdirs();
                File[] old = dir.listFiles();
                if (old != null) for (File o : old) o.delete();              //  지난번 것은 지운다
                String safe = name.replaceAll("[\\\\/:*?\"<>|]", "_");
                if (!is3d(safe)) safe = safe + ".stp";
                File f = new File(dir, safe);
                c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(60000);
                String ck = CookieManager.getInstance().getCookie(url);
                if (ck != null) c.setRequestProperty("Cookie", ck);
                if (ua != null) c.setRequestProperty("User-Agent", ua);
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                try (InputStream in = c.getInputStream(); OutputStream out = new FileOutputStream(f)) {
                    byte[] buf = new byte[65536];
                    int r;
                    while ((r = in.read(buf)) > 0) out.write(buf, 0, r);
                }
                final String nm = safe;
                from.runOnUiThread(() -> from.startActivity(new Intent(from, Viewer3dActivity.class).putExtra("name", nm)));
            } catch (Exception e) {
                from.runOnUiThread(() -> Toast.makeText(from, "도면을 받지 못했습니다: " + e.getMessage(), Toast.LENGTH_LONG).show());
            } finally {
                if (c != null) c.disconnect();
            }
        }).start();
    }

    WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        String name = getIntent().getStringExtra("name");
        if (name == null) { finish(); return; }

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#eef1f6"));
        setContentView(web);
        //  ⚠ 안드로이드 15 는 화면 끝까지 그린다 — 위 시계 줄·아래 버튼만큼 비켜 앉는다
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(Color.parseColor("#1b2a4a"));
        ViewCompat.setOnApplyWindowInsetsListener(web, (v, in) -> {
            Insets s = in.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            v.setPadding(s.left, s.top, s.right, s.bottom);
            return WindowInsetsCompat.CONSUMED;
        });
        View root = getWindow().getDecorView();
        root.setBackgroundColor(Color.parseColor("#1b2a4a"));

        WebSettings st = web.getSettings();
        st.setJavaScriptEnabled(true);
        st.setDomStorageEnabled(true);
        st.setAllowFileAccess(false);
        st.setAllowContentAccess(false);

        //  앱 안 주소(https://appassets.androidplatform.net)로 뷰어와 받은 파일을 내준다
        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .addPathHandler("/files/", new WebViewAssetLoader.InternalStoragePathHandler(this, new File(getCacheDir(), "view3d")))
                .build();
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return loader.shouldInterceptRequest(req.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return !"appassets.androidplatform.net".equals(req.getUrl().getHost());   //  밖으로는 안 나간다
            }
        });
        web.addJavascriptInterface(new Bridge(), "HanilApp");
        try {
            web.loadUrl("https://appassets.androidplatform.net/assets/viewer3d/index.html?src="
                    + URLEncoder.encode("/files/" + URLEncoder.encode(name, "UTF-8").replace("+", "%20"), "UTF-8")
                    + "&name=" + URLEncoder.encode(name, "UTF-8"));
        } catch (Exception e) {
            finish();
        }
    }

    //  뷰어의 「⬇ 저장」·「📷 그림」 → 다운로드 폴더
    class Bridge {
        @JavascriptInterface
        public void saveBase64(String name, String mime, String b64) {
            try {
                MainActivity.saveToDownloads(Viewer3dActivity.this, name, mime, Base64.decode(b64, Base64.DEFAULT));
                toast("다운로드 폴더에 저장했습니다: " + name);
            } catch (Exception e) {
                toast("저장하지 못했습니다: " + e.getMessage());
            }
        }

        @JavascriptInterface
        public String version() {
            return BuildConfig.VERSION_NAME;
        }
    }

    void toast(String t) {
        new Handler(Looper.getMainLooper()).post(() -> Toast.makeText(this, t, Toast.LENGTH_LONG).show());
    }

    @Override
    protected void onDestroy() {
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
