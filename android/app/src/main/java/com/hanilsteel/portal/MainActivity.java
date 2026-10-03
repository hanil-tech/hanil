package com.hanilsteel.portal;

// ════════════════════════════════════════════════════════════════════
//
//   📱 한일 포털 — 안드로이드 앱
//
// ════════════════════════════════════════════════════════════════════
//
//   ⭐ 회사 포털을 주소창 없는 앱 하나로 연다. 자료는 전부 포털에 있다(앱은 화면만 보여 준다).
//   ⭐ 어느 주소로 붙을지 스스로 고른다: 회사 와이파이면 사내 서버(192.168.1.30:8820),
//      아니면 도메인(work.hanil-steel.com). 사람이 고르지 않게.
//   ⭐ 폰에서 포털을 쓸 때 브라우저로는 안 되던 것들을 앱이 채운다:
//      ① 카메라(QR·바코드 찍기, 사진 올리기)  ② 내려받기(엑셀·PDF — blob 포함)
//      ③ 인쇄(window.print → 안드로이드 인쇄)  ④ 새 창(미리보기·인쇄 창)
//      ⑤ 전화·메일·카카오 같은 바깥 링크  ⑥ 로그인 유지(쿠키 보관, 「로그인 유지」 자동 체크)
//   ⚠ 사내 서버만 http 를 허락한다(network_security_config) — 바깥은 https 만.

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Dialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

public class MainActivity extends AppCompatActivity {

    static final String LAN = "http://192.168.1.30:8820";
    static final String WAN = "https://work.hanil-steel.com";

    //  앱 안에서 여는 주소(나머지는 바깥 브라우저·앱으로)
    static boolean isPortalHost(String host) {
        if (host == null) return false;
        return host.equals("192.168.1.30") || host.equals("work.hanil-steel.com");
    }

    //  🖨 window.print() 를 안드로이드 인쇄로 잇는다. 틀(iframe) 안에서 부르면 그 틀의 내용만 인쇄한다.
    static final String PRINT_JS = "(function(){try{if(!window.HanilApp)return;"
            + "window.print=function(){try{if(window.top===window){HanilApp.printPage();}"
            + "else{HanilApp.printHtml('<!doctype html>'+document.documentElement.outerHTML,location.href);}}catch(e){}};"
            + "}catch(e){}})();";

    //  🔓 로그인 화면이면 「로그인 유지」를 미리 켜 둔다(폰은 한 사람이 쓰는 기기)
    static final String REMEMBER_JS = "(function(){try{var r=document.querySelector('input[name=remember]');"
            + "if(r&&!r.checked){r.checked=true;}}catch(e){}})();";

    WebView web;
    SwipeRefreshLayout swipe;
    View splash;
    TextView splashMsg;
    ProgressBar bar;
    String base;

    ValueCallback<Uri[]> fileCb;
    WebChromeClient.FileChooserParams fileParams;
    Uri cameraUri;
    PermissionRequest pendingPerm;
    GeolocationPermissions.Callback geoCb;
    String geoOrigin;
    int permPurpose; // 1 = 화면 카메라(QR), 2 = 사진 올리기, 3 = 위치

    ActivityResultLauncher<Intent> fileLauncher;
    ActivityResultLauncher<String[]> permLauncher;
    final List<WebView> printers = new ArrayList<>();   // 인쇄가 끝날 때까지 붙잡아 둔다
    Dialog popup;
    long backAt;

    //  📱 아래 탭 — {그림, 이름, 주소}. 주소가 null 이면 폰용 전체 메뉴를 연다
    static final String[][] TABS = {
            {"🏠", "홈", "/m"},
            {"✅", "결재", "/appr"},
            {"💬", "메신저", "/chat"},
            {"🔔", "할 일", "/mywork"},
            {"☰", "메뉴", null},
    };
    LinearLayout tabs;
    final TextView[] tabIcon = new TextView[TABS.length];
    final TextView[] tabLabel = new TextView[TABS.length];
    final TextView[] tabBadge = new TextView[TABS.length];
    String mobileJs = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        web = findViewById(R.id.web);
        swipe = findViewById(R.id.swipe);
        splash = findViewById(R.id.splash);
        splashMsg = findViewById(R.id.splashMsg);
        bar = findViewById(R.id.bar);
        tabs = findViewById(R.id.tabs);
        mobileJs = readAsset("mobile.js");
        buildTabs();

        fileLauncher = registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), r -> {
            Uri[] out = null;
            if (r.getResultCode() == RESULT_OK) {
                Intent d = r.getData();
                if (d != null && d.getClipData() != null) {
                    int n = d.getClipData().getItemCount();
                    out = new Uri[n];
                    for (int i = 0; i < n; i++) out[i] = d.getClipData().getItemAt(i).getUri();
                } else if (d != null && d.getData() != null) {
                    out = new Uri[]{d.getData()};
                } else if (cameraUri != null) {
                    out = new Uri[]{cameraUri};      // 카메라로 찍은 사진
                }
            }
            if (fileCb != null) fileCb.onReceiveValue(out);
            fileCb = null;
            cameraUri = null;
        });
        permLauncher = registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), this::onPerms);

        CookieManager.getInstance().setAcceptCookie(true);
        setupWeb(web, false);
        swipe.setColorSchemeColors(Color.parseColor("#2954A5"));
        swipe.setOnRefreshListener(() -> web.reload());
        swipe.setOnChildScrollUpCallback((parent, child) -> web.getScrollY() > 0);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (web.canGoBack()) {
                    web.goBack();
                    return;
                }
                long now = System.currentTimeMillis();
                if (now - backAt < 2000) {
                    finish();
                } else {
                    backAt = now;
                    Toast.makeText(MainActivity.this, "한 번 더 누르면 닫힙니다", Toast.LENGTH_SHORT).show();
                }
            }
        });
        start();
    }

    // ── 어느 주소로 붙을까 ─────────────────────────────────────
    void start() {
        splash.setVisibility(View.VISIBLE);
        splashMsg.setText("연결하는 중…");
        new Thread(() -> {
            String u = pick();
            runOnUiThread(() -> {
                if (u == null) {
                    showOffline();
                    return;
                }
                base = u;
                web.loadUrl(u + "/m");      //  ⭐ 폰은 PC 첫 화면이 아니라 폰용 첫 화면(/m)으로
            });
        }).start();
    }

    String pick() {
        //  ⭐ 회사 와이파이일 때만 사내 서버를 먼저 두드린다(밖에서 사내 주소를 두드리면 한참 기다린다)
        if (onWifi() && probe(LAN, 1500)) return LAN;
        if (probe(WAN, 5000)) return WAN;
        if (probe(LAN, 1500)) return LAN;
        return null;
    }

    boolean onWifi() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            Network n = cm.getActiveNetwork();
            NetworkCapabilities c = n == null ? null : cm.getNetworkCapabilities(n);
            return c != null && (c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
                    || c.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
        } catch (Exception e) {
            return false;
        }
    }

    static boolean probe(String u, int ms) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(u + "/").openConnection();
            c.setConnectTimeout(ms);
            c.setReadTimeout(ms + 2000);
            c.setInstanceFollowRedirects(false);
            int code = c.getResponseCode();
            return code > 0 && code < 500;
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    void showOffline() {
        splash.setVisibility(View.GONE);
        web.loadUrl("file:///android_asset/offline.html");
    }

    // ── 화면(WebView) 설정 ─────────────────────────────────────
    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    void setupWeb(WebView w, boolean isPopup) {
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setSupportMultipleWindows(true);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setUserAgentString(s.getUserAgentString() + " HanilPortalApp/" + BuildConfig.VERSION_NAME);
        CookieManager.getInstance().setAcceptThirdPartyCookies(w, true);

        w.addJavascriptInterface(new Bridge(w), "HanilApp");
        if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            //  ⭐ 모든 틀(iframe)의 맨 앞에서 window.print 를 잇는다(라벨 인쇄는 틀 안에서 한다)
            WebViewCompat.addDocumentStartJavaScript(w, PRINT_JS, Collections.singleton("*"));
        }
        w.setWebViewClient(new Client(isPopup));
        w.setWebChromeClient(new Chrome());
        w.setDownloadListener((url, ua, cd, mime, len) -> download(w, url, ua, cd, mime));
    }

    class Client extends WebViewClient {
        final boolean isPopup;

        Client(boolean isPopup) {
            this.isPopup = isPopup;
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            String scheme = u.getScheme() == null ? "" : u.getScheme().toLowerCase();
            if (scheme.equals("http") || scheme.equals("https")) {
                if (isPortalHost(u.getHost()) || !req.isForMainFrame()) return false;
                openOutside(u);          // 포털 밖 누리집은 브라우저로
                return true;
            }
            if (scheme.equals("blob") || scheme.equals("data") || scheme.equals("about") || scheme.equals("file")) {
                return false;
            }
            //  전화·문자·메일·카카오 등
            try {
                if (scheme.equals("intent")) {
                    Intent it = Intent.parseUri(u.toString(), Intent.URI_INTENT_SCHEME);
                    try {
                        startActivity(it);
                    } catch (ActivityNotFoundException e) {
                        String fb = it.getStringExtra("browser_fallback_url");
                        if (fb != null) openOutside(Uri.parse(fb));
                    }
                } else {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                }
            } catch (Exception e) {
                Toast.makeText(MainActivity.this, "열 수 있는 앱이 없습니다", Toast.LENGTH_SHORT).show();
            }
            return true;
        }

        @Override
        public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            if (!isPopup) bar.setVisibility(View.VISIBLE);
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                view.evaluateJavascript(PRINT_JS, null);
            }
            view.evaluateJavascript(REMEMBER_JS, null);
            Uri pu = Uri.parse(url);
            if (isPortalHost(pu.getHost()) && !mobileJs.isEmpty()) view.evaluateJavascript(mobileJs, null);
            if (!isPopup) selectTab(pu.getPath());
            CookieManager.getInstance().flush();
            if (!isPopup) {
                bar.setVisibility(View.GONE);
                swipe.setRefreshing(false);
                splash.setVisibility(View.GONE);
            }
        }

        @Override
        public void doUpdateVisitedHistory(WebView view, String url, boolean isReload) {
            if (!isPopup) selectTab(Uri.parse(url).getPath());
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
            if (req.isForMainFrame() && !isPopup) showOffline();
        }
    }

    class Chrome extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView view, int p) {
            bar.setProgress(p);
        }

        // 📎 파일 올리기 — 사진이면 카메라도 고를 수 있게
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
            if (fileCb != null) fileCb.onReceiveValue(null);
            fileCb = cb;
            fileParams = params;
            if (wantsCamera(params) && !granted(Manifest.permission.CAMERA)) {
                permPurpose = 2;
                permLauncher.launch(new String[]{Manifest.permission.CAMERA});
            } else {
                openChooser();
            }
            return true;
        }

        // 📷 화면이 카메라를 쓰려 할 때(QR·바코드 찍기)
        @Override
        public void onPermissionRequest(PermissionRequest r) {
            runOnUiThread(() -> {
                boolean video = false;
                for (String res : r.getResources()) {
                    if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) video = true;
                }
                if (!video) {
                    r.deny();
                    return;
                }
                if (granted(Manifest.permission.CAMERA)) {
                    r.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
                } else {
                    pendingPerm = r;
                    permPurpose = 1;
                    permLauncher.launch(new String[]{Manifest.permission.CAMERA});
                }
            });
        }

        // 📍 위치(기사님 화면)
        @Override
        public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
            if (granted(Manifest.permission.ACCESS_FINE_LOCATION) || granted(Manifest.permission.ACCESS_COARSE_LOCATION)) {
                cb.invoke(origin, true, false);
            } else {
                geoCb = cb;
                geoOrigin = origin;
                permPurpose = 3;
                permLauncher.launch(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION});
            }
        }

        // 🪟 새 창(미리보기·인쇄 창) — 앱 안에 덮어 띄운다
        @Override
        public boolean onCreateWindow(WebView view, boolean isDialog, boolean userGesture, Message resultMsg) {
            WebView pw = new WebView(MainActivity.this);
            setupWeb(pw, true);
            showPopup(pw);
            WebView.WebViewTransport t = (WebView.WebViewTransport) resultMsg.obj;
            t.setWebView(pw);
            resultMsg.sendToTarget();
            return true;
        }

        @Override
        public void onCloseWindow(WebView window) {
            if (popup != null) popup.dismiss();
        }
    }

    void showPopup(WebView pw) {
        if (popup != null) popup.dismiss();
        Dialog d = new Dialog(this, android.R.style.Theme_Material_Light_NoActionBar_Fullscreen);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        LinearLayout top = new LinearLayout(this);
        top.setBackgroundColor(Color.parseColor("#1b2a4a"));
        top.setGravity(Gravity.CENTER_VERTICAL | Gravity.END);
        Button close = new Button(this);
        close.setText("✕ 닫기");
        close.setOnClickListener(v -> d.dismiss());
        top.addView(close);
        box.addView(top, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        box.addView(pw, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        d.setContentView(box);
        d.setOnDismissListener(x -> {
            pw.destroy();
            if (popup == d) popup = null;
        });
        d.setOnKeyListener((dlg, code, ev) -> {
            if (code == android.view.KeyEvent.KEYCODE_BACK && ev.getAction() == android.view.KeyEvent.ACTION_UP) {
                if (pw.canGoBack()) pw.goBack(); else d.dismiss();
                return true;
            }
            return false;
        });
        popup = d;
        d.show();
    }

    // ── 권한 ───────────────────────────────────────────────────
    boolean granted(String p) {
        return ContextCompat.checkSelfPermission(this, p) == PackageManager.PERMISSION_GRANTED;
    }

    void onPerms(Map<String, Boolean> res) {
        boolean ok = false;
        for (Boolean b : res.values()) if (Boolean.TRUE.equals(b)) ok = true;
        if (permPurpose == 1 && pendingPerm != null) {
            if (ok) pendingPerm.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else pendingPerm.deny();
            pendingPerm = null;
        } else if (permPurpose == 2) {
            openChooser();          // 카메라를 거절해도 갤러리·파일은 고를 수 있게
        } else if (permPurpose == 3 && geoCb != null) {
            geoCb.invoke(geoOrigin, ok, false);
            geoCb = null;
        }
        permPurpose = 0;
    }

    // ── 파일 고르기 ────────────────────────────────────────────
    static boolean wantsCamera(WebChromeClient.FileChooserParams p) {
        if (p == null) return false;
        if (p.isCaptureEnabled()) return true;
        String[] acc = p.getAcceptTypes();
        if (acc == null || acc.length == 0) return true;
        for (String a : acc) {
            if (a == null || a.isEmpty() || a.startsWith("image") || a.equals("*/*")) return true;
        }
        return false;
    }

    void openChooser() {
        if (fileCb == null) return;
        Intent pick;
        try {
            pick = fileParams.createIntent();
        } catch (Exception e) {
            pick = new Intent(Intent.ACTION_GET_CONTENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
        }
        if (fileParams != null && fileParams.getMode() == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE) {
            pick.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        }
        Intent chooser = Intent.createChooser(pick, "파일 고르기");
        if (wantsCamera(fileParams) && granted(Manifest.permission.CAMERA)) {
            try {
                File dir = new File(getCacheDir(), "camera");
                //noinspection ResultOfMethodCallIgnored
                dir.mkdirs();
                File f = new File(dir, "photo_" + System.currentTimeMillis() + ".jpg");
                cameraUri = FileProvider.getUriForFile(this, getPackageName() + ".files", f);
                Intent cam = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                cam.putExtra(MediaStore.EXTRA_OUTPUT, cameraUri);
                cam.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Intent[]{cam});
            } catch (Exception e) {
                cameraUri = null;
            }
        }
        try {
            fileLauncher.launch(chooser);
        } catch (Exception e) {
            fileCb.onReceiveValue(null);
            fileCb = null;
        }
    }

    // ── 내려받기 ───────────────────────────────────────────────
    void download(WebView w, String url, String ua, String cd, String mime) {
        if (url.startsWith("blob:") || url.startsWith("data:")) {
            //  ⚠ blob: 은 그 화면 안에서만 읽힌다 → 화면에서 읽어 앱으로 넘긴다
            String js = "(function(){var u=" + jsStr(url) + ";fetch(u).then(function(r){return r.blob();}).then(function(b){"
                    + "var fr=new FileReader();fr.onloadend=function(){var s=String(fr.result);"
                    + "HanilApp.saveBase64(" + jsStr(URLUtil.guessFileName(url, cd, mime)) + ",b.type||" + jsStr(mime == null ? "" : mime)
                    + ",s.substring(s.indexOf(',')+1));};fr.readAsDataURL(b);}).catch(function(e){alert('내려받지 못했습니다: '+e);});})();";
            w.evaluateJavascript(js, null);
            return;
        }
        try {
            String name = URLUtil.guessFileName(url, cd, mime);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            String cookie = CookieManager.getInstance().getCookie(url);
            if (cookie != null) r.addRequestHeader("Cookie", cookie);
            r.addRequestHeader("User-Agent", ua);
            r.setMimeType(mime);
            r.setTitle(name);
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
            Toast.makeText(this, "내려받는 중: " + name, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            openOutside(Uri.parse(url));
        }
    }

    static String jsStr(String s) {
        StringBuilder b = new StringBuilder("'");
        for (char c : (s == null ? "" : s).toCharArray()) {
            if (c == '\'' || c == '\\') b.append('\\').append(c);
            else if (c == '\n') b.append("\\n");
            else if (c == '\r') b.append("\\r");
            else b.append(c);
        }
        return b.append("'").toString();
    }

    void saveFile(String name, String mime, byte[] data) throws Exception {
        if (mime == null || mime.isEmpty()) {
            String ext = MimeTypeMap.getFileExtensionFromUrl(name);
            mime = ext == null ? null : MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
            if (mime == null) mime = "application/octet-stream";
        }
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime);
            Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new Exception("저장할 곳을 만들지 못했습니다");
            try (OutputStream o = getContentResolver().openOutputStream(uri)) {
                if (o == null) throw new Exception("저장하지 못했습니다");
                o.write(data);
            }
        } else {
            File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            if (!dir.exists() || !dir.canWrite()) dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            try (FileOutputStream o = new FileOutputStream(new File(dir, name))) {
                o.write(data);
            }
        }
    }

    // ── 인쇄 ───────────────────────────────────────────────────
    void printWebView(WebView w, String job) {
        PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
        pm.print(job, w.createPrintDocumentAdapter(job), new PrintAttributes.Builder().build());
    }

    void printHtml(String html, String baseUrl) {
        WebView pw = new WebView(this);
        pw.getSettings().setJavaScriptEnabled(false);
        printers.add(pw);
        pw.setWebViewClient(new WebViewClient() {
            boolean done;

            @Override
            public void onPageFinished(WebView view, String url) {
                if (done) return;
                done = true;
                //  ⚠ 그림(QR·사진)이 다 그려질 틈을 조금 준다
                new Handler(Looper.getMainLooper()).postDelayed(() -> {
                    printWebView(view, "한일 포털 인쇄");
                    new Handler(Looper.getMainLooper()).postDelayed(() -> printers.remove(view), 60000);
                }, 600);
            }
        });
        pw.loadDataWithBaseURL(baseUrl, html, "text/html", "utf-8", null);
    }

    // ── 화면 ↔ 앱 ──────────────────────────────────────────────
    class Bridge {
        final WebView owner;

        Bridge(WebView owner) {
            this.owner = owner;
        }

        @JavascriptInterface
        public String version() {
            return BuildConfig.VERSION_NAME;
        }

        @JavascriptInterface
        public void retry() {
            runOnUiThread(MainActivity.this::start);
        }

        @JavascriptInterface
        public void printPage() {
            runOnUiThread(() -> printWebView(owner, "한일 포털 인쇄"));
        }

        @JavascriptInterface
        public void printHtml(String html, String baseUrl) {
            runOnUiThread(() -> MainActivity.this.printHtml(html, baseUrl));
        }

        @JavascriptInterface
        public void badges(int appr, int chat, int todo) {
            runOnUiThread(() -> {
                setBadge(1, appr);
                setBadge(2, chat);
                setBadge(3, todo);
            });
        }

        @JavascriptInterface
        public void saveBase64(String name, String mime, String b64) {
            try {
                byte[] data = Base64.decode(b64, Base64.DEFAULT);
                String n = (name == null || name.isEmpty()) ? "hanil-" + System.currentTimeMillis() : name;
                saveFile(n, mime, data);
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "다운로드 폴더에 저장했습니다: " + n, Toast.LENGTH_LONG).show());
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "저장하지 못했습니다: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }
    }

    // ── 아래 탭 ────────────────────────────────────────────────
    int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    void buildTabs() {
        for (int i = 0; i < TABS.length; i++) {
            final int idx = i;
            android.widget.FrameLayout cell = new android.widget.FrameLayout(this);
            LinearLayout col = new LinearLayout(this);
            col.setOrientation(LinearLayout.VERTICAL);
            col.setGravity(Gravity.CENTER);
            TextView ic = new TextView(this);
            ic.setText(TABS[i][0]);
            ic.setTextSize(21);
            ic.setGravity(Gravity.CENTER);
            TextView lb = new TextView(this);
            lb.setText(TABS[i][1]);
            lb.setTextSize(12);
            lb.setGravity(Gravity.CENTER);
            col.addView(ic);
            col.addView(lb);
            cell.addView(col, new android.widget.FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            TextView bd = new TextView(this);
            bd.setTextColor(Color.WHITE);
            bd.setTextSize(11);
            bd.setGravity(Gravity.CENTER);
            bd.setPadding(dp(5), 0, dp(5), 0);
            android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
            bg.setColor(Color.parseColor("#D93025"));
            bg.setCornerRadius(dp(9));
            bd.setBackground(bg);
            bd.setMinWidth(dp(18));
            bd.setVisibility(View.GONE);
            android.widget.FrameLayout.LayoutParams bp = new android.widget.FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(18));
            bp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
            bp.topMargin = dp(4);
            bp.leftMargin = dp(18);
            cell.addView(bd, bp);
            android.util.TypedValue tv = new android.util.TypedValue();
            getTheme().resolveAttribute(android.R.attr.selectableItemBackgroundBorderless, tv, true);
            cell.setForeground(ContextCompat.getDrawable(this, tv.resourceId));
            cell.setClickable(true);
            cell.setOnClickListener(v -> onTab(idx));
            tabs.addView(cell, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
            tabIcon[i] = ic;
            tabLabel[i] = lb;
            tabBadge[i] = bd;
        }
        selectTab("/m");
    }

    void onTab(int i) {
        if (base == null) {           //  아직 못 붙었다 — 다시 붙어 본다
            start();
            return;
        }
        if (popup != null) popup.dismiss();
        String path = TABS[i][2];
        if (path == null) {
            web.evaluateJavascript("window.__hanilMenu?window.__hanilMenu():(location.href='/m')", null);
            return;
        }
        web.loadUrl(base + path);
    }

    void selectTab(String path) {
        int sel = -1;
        if (path != null) {
            for (int i = 0; i < TABS.length; i++) {
                String p = TABS[i][2];
                if (p != null && (path.equals(p) || path.startsWith(p + "/"))) sel = i;
            }
        }
        for (int i = 0; i < TABS.length; i++) {
            if (tabLabel[i] == null) continue;
            int c = (i == sel) ? Color.parseColor("#2954A5") : Color.parseColor("#6B7684");
            tabLabel[i].setTextColor(c);
            tabLabel[i].setTypeface(null, i == sel ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
            tabIcon[i].setAlpha(i == sel ? 1f : 0.65f);
        }
    }

    void setBadge(int i, int n) {
        TextView b = tabBadge[i];
        if (b == null) return;
        if (n > 0) {
            b.setText(n > 99 ? "99+" : String.valueOf(n));
            b.setVisibility(View.VISIBLE);
        } else {
            b.setVisibility(View.GONE);
        }
    }

    String readAsset(String name) {
        try (java.io.InputStream in = getAssets().open(name)) {
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) > 0) out.write(buf, 0, r);
            return out.toString("UTF-8");
        } catch (Exception e) {
            return "";
        }
    }

    void openOutside(Uri u) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, u));
        } catch (Exception e) {
            Toast.makeText(this, "열 수 있는 앱이 없습니다", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }
}
