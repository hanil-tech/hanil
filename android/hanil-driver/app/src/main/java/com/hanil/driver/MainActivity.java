package com.hanil.driver;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

/**
 * 🚚⭐⭐⭐ 한일 기사 — 기사님 폰 전용 앱(v1)
 *
 *  사용자 「기사용 프로그램 안드로이드로 만들어 줄 수 있어? 웹방식이다 보니 너무 안 되네」
 *
 *  ⚠⚠⚠ **화면을 새로 만들지 않는다.** 이 앱은 포털의 기사용 출고 화면(/driver)을 그대로 띄우는
 *    **껍데기**다. 그래야 포털 판을 올리면 앱도 함께 새로워진다 — 앱을 다시 깔 일이 없다.
 *    (포털이 「만드는 것이 하나(웹)라 판을 올리면 앱도 함께 새로워진다」고 적어 둔 그대로다.)
 *
 *  ⭐ **브라우저로는 안 되던 것을 앱이 해 준다** — 이것이 앱을 만드는 이유의 전부다:
 *    ① 카메라  — 크롬이 「차단」으로 기억하면 물어보지도 않는다. 앱은 **앱 권한 하나**로 끝나고,
 *                화면이 카메라를 달라고 하면 **앱이 그 자리에서 내준다**(onPermissionRequest).
 *    ② 로그인  — 앱의 쿠키통은 앱이 지키므로 열쇠(hdev, 3년)가 안 날아간다.
 *                브라우저는 「저장 공간 정리」 한 번에 지워져 기사님이 다시 로그인해야 했다.
 *    ③ 사진    — 파일 고르기·사진 찍기를 앱이 받아 준다(WebView 는 이것을 스스로 못 한다).
 *    ④ 내려받기 — 전표 PDF 같은 것을 앱이 받아 준다(WebView 는 이것도 스스로 못 한다).
 *    ⑤ 인쇄    — window.print() 가 WebView 에서는 아무 일도 안 한다. 앱이 안드로이드 인쇄로 잇는다.
 *    ⑥ 새 창   — window.open 이 WebView 에서는 조용히 막힌다. 앱이 창을 띄워 준다.
 *    ⑦ 화면    — 주소창이 없고, 화면이 안 꺼지고, 뒤로 가기가 제대로 돈다.
 */
public class MainActivity extends Activity {

    /** ⚠ 포털이 이 글자를 보고 「앱 안이다」를 안다(driver.html 의 /HanilDriverApp/i). 바꾸면 안 된다. */
    private static final String UA_TAG = "HanilDriverApp";

    private static final int REQ_FILE = 1001;
    private static final int REQ_CAMERA = 1002;

    private WebView web;
    private FrameLayout root;
    private ProgressBar bar;
    private View errorBox;
    private ValueCallback<Uri[]> filePath;
    private Uri cameraOut;
    private PermissionRequest pendingWebPerm;
    private long lastBack = 0;
    private String server = "";

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        server = Prefs.server(this);
        if (TextUtils.isEmpty(server)) {
            startActivity(new Intent(this, SetupActivity.class));
            finish();
            return;
        }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);   // 🔋 짐 싣는 동안 화면이 꺼지면 안 된다

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));

        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        root.addView(bar, new FrameLayout.LayoutParams(-1, dp(3), Gravity.TOP));

        root.addView(menuButton(), buttonParams());
        setContentView(root);

        setupWeb(web);

        //  📷 카메라 권한은 **앱을 열 때 한 번** 묻는다.
        //   ⚠ 화면이 카메라를 달라고 할 때 묻게 두면, 그 순간 안드로이드 창이 뜨면서
        //     찍던 흐름이 끊긴다(현장에서는 「또 안 되네」로 보인다). 미리 받아 둔다.
        if (!hasCamera()) {
            requestPermissions(new String[]{ Manifest.permission.CAMERA }, REQ_CAMERA);
        }

        String start = getIntent() != null ? getIntent().getStringExtra("url") : null;
        if (TextUtils.isEmpty(start)) start = server + "/driver";
        web.loadUrl(start);
    }

    // ────────────────────────────── WebView 차리기 ──────────────────────────────

    private void setupWeb(final WebView w) {
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(false);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setSupportZoom(false);
        s.setAllowFileAccess(false);                 // ⚠ 웹 화면이 폰 파일을 읽을 까닭이 없다
        s.setAllowContentAccess(false);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setSupportMultipleWindows(true);           // ⚠ window.open 을 쓰는 화면이 있다(안내문 인쇄·리더기 시험)
        s.setMediaPlaybackRequiresUserGesture(false);// 📷 카메라 화면이 저절로 돌아야 스캐너처럼 쓰인다
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setUserAgentString(s.getUserAgentString() + " " + UA_TAG + "/" + version());

        //  🍪 쿠키 — **열쇠(hdev)가 여기 산다.** 지우지 않는다.
        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(w, true);

        w.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                return handleUrl(req.getUrl());
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                hideError();
                //  🖨 window.print() 는 WebView 안에서 **아무 일도 안 한다** — 앱의 인쇄로 잇는다.
                v.evaluateJavascript(
                    "(function(){try{if(!window.__hanilPrint){window.__hanilPrint=1;"
                        + "window.print=function(){try{HanilApp.print();}catch(e){}};}}catch(e){}})();", null);
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                //  ⚠ 화면 안 작은 요청이 실패한 것까지 「못 열었습니다」로 덮으면 안 된다 — 본문일 때만.
                if (req != null && req.isForMainFrame()) showError();
            }
        });

        w.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView v, int p) {
                bar.setProgress(p);
                bar.setVisibility(p >= 100 ? View.GONE : View.VISIBLE);
            }

            /**
             * 📷⭐⭐⭐ **이 앱을 만든 가장 큰 까닭.**
             * 브라우저는 한 번 「차단」을 기억하면 물어보지도 않고 거절한다 — 기사님은 손쓸 방법이 없다.
             * 앱은 **앱 권한만 있으면** 그 자리에서 내준다. 설정을 헤맬 일이 없어진다.
             */
            @Override
            public void onPermissionRequest(final PermissionRequest req) {
                runOnUiThread(new Runnable() {
                    @Override public void run() {
                        if (hasCamera()) {
                            req.grant(req.getResources());
                        } else {
                            pendingWebPerm = req;                    // 권한을 받고 나서 내준다
                            requestPermissions(new String[]{ Manifest.permission.CAMERA }, REQ_CAMERA);
                        }
                    }
                });
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest req) {
                pendingWebPerm = null;
            }

            /** 📸 사진 고르기·찍기 — WebView 는 이것을 스스로 못 한다. 앱이 받아 준다. */
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (filePath != null) filePath.onReceiveValue(null);
                filePath = cb;
                try {
                    startActivityForResult(chooserIntent(params), REQ_FILE);
                    return true;
                } catch (Exception e) {
                    filePath = null;
                    toast("사진을 고를 수 없습니다: " + e.getMessage());
                    return false;
                }
            }

            /** 🪟 새 창(window.open) — 안 받아 주면 단추를 눌러도 아무 일이 없다. */
            @Override
            public boolean onCreateWindow(WebView v, boolean dialog, boolean gesture, android.os.Message resultMsg) {
                WebView child = new WebView(MainActivity.this);
                setupWeb(child);
                final AlertDialog d = new AlertDialog.Builder(MainActivity.this)
                    .setView(child)
                    .setPositiveButton("닫기", null)
                    .create();
                child.setWebChromeClient(new WebChromeClient() {
                    @Override public void onCloseWindow(WebView w2) { d.dismiss(); }
                });
                d.show();
                ((WebView.WebViewTransport) resultMsg.obj).setWebView(child);
                resultMsg.sendToTarget();
                return true;
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, android.webkit.GeolocationPermissions.Callback cb) {
                cb.invoke(origin, false, false);   // ⚠ 위치는 쓸 일이 없다 — 묻지도 않는다
            }
        });

        //  ⬇ 내려받기(전표 PDF 등) — WebView 는 이것도 스스로 못 한다.
        w.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String ua, String disp, String mime, long size) {
                try {
                    DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
                    r.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
                    r.addRequestHeader("User-Agent", ua);
                    r.setMimeType(mime);
                    String name = android.webkit.URLUtil.guessFileName(url, disp, mime);
                    r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                    r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(r);
                    toast("받는 중입니다 — 「다운로드」 폴더에 저장됩니다");
                } catch (Exception e) {
                    toast("받지 못했습니다: " + e.getMessage());
                }
            }
        });

        w.addJavascriptInterface(new Bridge(), "HanilApp");
    }

    /** 🖨 화면에서 window.print() 를 부르면 여기로 온다. */
    public class Bridge {
        @android.webkit.JavascriptInterface
        public void print() {
            runOnUiThread(new Runnable() {
                @Override public void run() { doPrint(); }
            });
        }
    }

    private void doPrint() {
        try {
            PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
            String job = "한일 기사 " + System.currentTimeMillis();
            pm.print(job, web.createPrintDocumentAdapter(job), new PrintAttributes.Builder().build());
        } catch (Exception e) {
            toast("인쇄를 열지 못했습니다: " + e.getMessage());
        }
    }

    // ────────────────────────────── 길 가리기 ──────────────────────────────

    /** true 를 주면 앱이 그 주소를 안 연다(밖으로 내보냈다는 뜻). */
    private boolean handleUrl(Uri u) {
        if (u == null) return false;
        String sc = u.getScheme() == null ? "" : u.getScheme();
        if (sc.equals("http") || sc.equals("https")) {
            String host = u.getHost() == null ? "" : u.getHost();
            String mine = Uri.parse(server).getHost() == null ? "" : Uri.parse(server).getHost();
            if (host.equalsIgnoreCase(mine)) return false;          // 우리 포털이면 앱 안에서
            return openOutside(u);                                   // 바깥 주소는 브라우저로
        }
        //  ⚠ tel: · sms: · intent: 는 앱이 처리하지 않으면 **눌러도 아무 일이 없다**
        return openOutside(u);
    }

    private boolean openOutside(Uri u) {
        try {
            if ("intent".equals(u.getScheme())) {
                Intent i = Intent.parseUri(u.toString(), Intent.URI_INTENT_SCHEME);
                startActivity(i);
                return true;
            }
            startActivity(new Intent(Intent.ACTION_VIEW, u));
            return true;
        } catch (ActivityNotFoundException e) {
            toast("이 주소를 열 수 있는 앱이 없습니다.");
            return true;
        } catch (Exception e) {
            return true;
        }
    }

    // ────────────────────────────── 사진 고르기 ──────────────────────────────

    private Intent chooserIntent(WebChromeClient.FileChooserParams params) {
        Intent pick = new Intent(Intent.ACTION_GET_CONTENT);
        pick.addCategory(Intent.CATEGORY_OPENABLE);
        pick.setType("image/*");
        String[] accept = params != null ? params.getAcceptTypes() : null;
        if (accept != null && accept.length > 0 && !TextUtils.isEmpty(accept[0]) && !accept[0].startsWith("image")) {
            pick.setType("*/*");
        }

        Intent cam = null;
        if (hasCamera()) {
            try {
                ContentValues cv = new ContentValues();
                cv.put(MediaStore.Images.Media.DISPLAY_NAME, "hanil_" + System.currentTimeMillis() + ".jpg");
                cv.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                cameraOut = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
                if (cameraOut != null) {
                    cam = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                    cam.putExtra(MediaStore.EXTRA_OUTPUT, cameraOut);
                    cam.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                }
            } catch (Exception e) {
                cameraOut = null; cam = null;      // ⚠ 사진 찍기가 안 되어도 **고르기는 되어야** 한다
            }
        }

        Intent chooser = Intent.createChooser(pick, "사진 고르기");
        if (cam != null) chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Intent[]{ cam });
        return chooser;
    }

    @Override
    protected void onActivityResult(int req, int result, Intent data) {
        if (req != REQ_FILE) { super.onActivityResult(req, result, data); return; }
        if (filePath == null) return;
        Uri[] out = null;
        if (result == RESULT_OK) {
            if (data != null && data.getData() != null) out = new Uri[]{ data.getData() };
            else if (cameraOut != null) out = new Uri[]{ cameraOut };     // 사진 찍기는 결과에 주소를 안 싣는다
        }
        filePath.onReceiveValue(out);
        filePath = null;
        cameraOut = null;
    }

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] grants) {
        if (req != REQ_CAMERA) return;
        boolean ok = grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED;
        if (pendingWebPerm != null) {
            if (ok) pendingWebPerm.grant(pendingWebPerm.getResources());
            else pendingWebPerm.deny();
            pendingWebPerm = null;
        }
        if (!ok) {
            //  ⚠ 거절해도 앱은 돌아간다 — 스캐너(총)로 쓰시는 분은 카메라가 필요 없다.
            toast("카메라를 안 쓰기로 하셨습니다. 나중에 쓰시려면 ⋮ → 카메라 권한 에서 켜세요.");
        }
    }

    private boolean hasCamera() {
        return checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
    }

    // ────────────────────────────── 못 열었을 때 ──────────────────────────────

    private void showError() {
        if (errorBox != null) { errorBox.setVisibility(View.VISIBLE); return; }
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(Color.parseColor("#f2f4f8"));
        box.setPadding(dp(26), dp(26), dp(26), dp(26));

        TextView t = new TextView(this);
        t.setText("📴 포털에 닿지 못했습니다");
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 21);
        t.setGravity(Gravity.CENTER);
        box.addView(t);

        TextView d = new TextView(this);
        boolean net = online();
        d.setText(net
            ? "인터넷은 되는데 포털이 안 열립니다.\n잠시 뒤 다시 해 보시고, 계속 그러면 사무실에 알려 주세요.\n\n주소: " + server
            : "폰이 인터넷에 안 붙어 있습니다.\n와이파이나 데이터를 켜고 다시 해 주세요.");
        d.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        d.setGravity(Gravity.CENTER);
        d.setPadding(0, dp(10), 0, dp(18));
        box.addView(d);

        Button b = new Button(this);
        b.setText("🔄 다시 해 보기");
        b.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { hideError(); web.reload(); }
        });
        box.addView(b);

        Button b2 = new Button(this);
        b2.setText("⚙ 주소 바꾸기");
        b2.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { openSetup(); }
        });
        box.addView(b2);

        errorBox = box;
        root.addView(errorBox, new FrameLayout.LayoutParams(-1, -1));
    }

    private void hideError() {
        if (errorBox != null) errorBox.setVisibility(View.GONE);
    }

    private boolean online() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo n = cm.getActiveNetworkInfo();
            return n != null && n.isConnected();
        } catch (Exception e) { return true; }
    }

    // ────────────────────────────── ⋮ 단추 ──────────────────────────────

    /**
     * ⚠ 기사님은 이 단추를 쓸 일이 거의 없다(대표님·담당자용) — 그래서 **작고 흐리게** 둔다.
     *   그렇다고 숨기면 주소를 바꿀 길이 없어진다. 왼쪽 위 구석에 흐린 점 세 개.
     */
    private View menuButton() {
        TextView b = new TextView(this);
        b.setText("⋮");
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        b.setTextColor(Color.parseColor("#88000000"));
        b.setPadding(dp(10), dp(4), dp(10), dp(8));
        b.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { openMenu(); }
        });
        return b;
    }

    private FrameLayout.LayoutParams buttonParams() {
        FrameLayout.LayoutParams p = new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.START);
        p.topMargin = dp(2);
        return p;
    }

    private void openMenu() {
        final String[] items = {
            "🔄 새로고침",
            "🚚 출고 화면으로",
            "🖨 이 화면 인쇄",
            "📷 카메라 권한 설정 열기",
            "⚙ 서버 주소·등록 바꾸기",
            "ℹ 앱 정보",
        };
        new AlertDialog.Builder(this)
            .setTitle("한일 기사")
            .setItems(items, new DialogInterface.OnClickListener() {
                @Override public void onClick(DialogInterface d, int i) {
                    switch (i) {
                        case 0: web.reload(); break;
                        case 1: web.loadUrl(server + "/driver"); break;
                        case 2: doPrint(); break;
                        case 3: openAppSettings(); break;
                        case 4: openSetup(); break;
                        default: about(); break;
                    }
                }
            })
            .show();
    }

    private void openAppSettings() {
        try {
            Intent i = new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            i.setData(Uri.parse("package:" + getPackageName()));
            startActivity(i);
        } catch (Exception e) {
            toast("설정을 열지 못했습니다.");
        }
    }

    private void openSetup() {
        startActivity(new Intent(this, SetupActivity.class));
        finish();
    }

    private void about() {
        new AlertDialog.Builder(this)
            .setTitle("한일 기사")
            .setMessage("판 " + version() + "\n주소 " + server
                + "\n\n화면은 포털에서 옵니다 — 포털 판을 올리면 이 앱도 함께 새로워집니다."
                + "\n앱을 다시 깔 일은 없습니다.")
            .setPositiveButton("닫기", null)
            .show();
    }

    private String version() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) { return "1.0"; }
    }

    // ────────────────────────────── 나머지 ──────────────────────────────

    @Override
    public boolean onKeyDown(int code, KeyEvent e) {
        if (code == KeyEvent.KEYCODE_BACK && web != null) {
            if (web.canGoBack()) { web.goBack(); return true; }
            //  ⚠ 한 번에 꺼지면 **담아 둔 것이 날아간다.** 두 번 눌러야 나간다.
            long now = System.currentTimeMillis();
            if (now - lastBack < 2000) return super.onKeyDown(code, e);
            lastBack = now;
            toast("한 번 더 누르면 앱이 닫힙니다");
            return true;
        }
        return super.onKeyDown(code, e);
    }

    @Override
    protected void onPause() {
        super.onPause();
        //  🍪 ⚠ 쿠키를 여기서 **디스크에 적어 둔다** — 앱이 갑자기 죽어도 열쇠가 살아 있게.
        try { CookieManager.getInstance().flush(); } catch (Exception ignored) { }
        if (web != null) web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onDestroy() {
        try { CookieManager.getInstance().flush(); } catch (Exception ignored) { }
        super.onDestroy();
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_LONG).show();
    }
}
