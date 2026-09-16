package com.hanil.driver;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/**
 * ⚙ 처음 한 번만 보는 화면 — **두 칸**뿐이다.
 *
 *  ⚠⚠ 기사님께 이 화면을 맡기지 않는다. 대표님·담당자가 폰을 받아 30초 만에 끝내는 화면이다.
 *    그래서 주소는 **이미 적혀 있고**, 등록 코드는 **숫자 여섯 자리**다.
 *
 *  🔑 등록 코드를 넣으면 포털이 이 폰에 **열쇠**를 심는다(3년). 그다음부터는 아이디·비밀번호가 없다.
 *    ⚠ 스캐너(EY-017P)를 붙이면 폰 자판이 안 올라와 **아예 못 치는** 일이 있다 — 그래서 열쇠가 낫다.
 *    ⚠⚠ 브라우저에서 열쇠를 심어도 **이 앱에는 안 들어온다**(쿠키통이 다르다) — 반드시 여기서 넣는다.
 */
public class SetupActivity extends Activity {

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);

        ScrollView sc = new ScrollView(this);
        LinearLayout v = new LinearLayout(this);
        v.setOrientation(LinearLayout.VERTICAL);
        v.setPadding(dp(22), dp(28), dp(22), dp(28));
        v.setBackgroundColor(Color.parseColor("#f2f4f8"));
        sc.addView(v);

        v.addView(text("🚚 한일 기사", 26, "#1b1f27", Gravity.CENTER));
        v.addView(text("처음 한 번만 넣으면 됩니다", 15, "#666e7d", Gravity.CENTER));

        v.addView(gap(dp(22)));
        v.addView(text("① 서버 주소", 16, "#1b1f27", Gravity.START));
        final EditText host = new EditText(this);
        host.setText(TextUtils.isEmpty(Prefs.server(this)) ? Prefs.DEFAULT_SERVER : Prefs.server(this));
        host.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        host.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        v.addView(host);
        v.addView(text("그대로 두시면 됩니다. 사무실에서 달리 알려 준 주소가 있을 때만 고치세요.",
            13, "#666e7d", Gravity.START));

        v.addView(gap(dp(20)));
        v.addView(text("② 등록 코드 (숫자 6자리)", 16, "#1b1f27", Gravity.START));
        final EditText code = new EditText(this);
        code.setHint("예: 481203 — 없으면 비워 두세요");
        code.setInputType(InputType.TYPE_CLASS_NUMBER);
        code.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        v.addView(code);
        v.addView(text("포털 → 기사 폰 등록 에서 만든 숫자입니다. 넣으면 로그인 없이 바로 열립니다.\n"
            + "⚠ 만든 지 1시간이 지나면 못 씁니다 — 그때는 새로 만드세요.\n"
            + "코드가 없으면 비워 두고 시작한 뒤, 기사님 아이디로 한 번 로그인하셔도 됩니다.",
            13, "#666e7d", Gravity.START));

        v.addView(gap(dp(26)));
        Button go = new Button(this);
        go.setText("시작하기");
        go.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        go.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View b) {
                String h = Prefs.normalize(host.getText().toString());
                if (TextUtils.isEmpty(h)) {
                    Toast.makeText(SetupActivity.this, "서버 주소를 넣어 주세요.", Toast.LENGTH_LONG).show();
                    return;
                }
                Prefs.setServer(SetupActivity.this, h);
                String c = code.getText().toString().trim();
                //  ⚠ 코드가 숫자가 아니면 **주소에 붙이지 않는다** — 엉뚱한 주소를 여는 것보다 낫다
                String url = (c.matches("\\d{4,10}")) ? (h + "/driver/key?c=" + c) : (h + "/driver");
                Intent i = new Intent(SetupActivity.this, MainActivity.class);
                i.putExtra("url", url);
                startActivity(i);
                finish();
            }
        });
        v.addView(go);

        v.addView(gap(dp(18)));
        v.addView(text("🔫 스캐너(EY-017P)를 쓰실 때\n"
            + "폰 설정 → 블루투스 에서 스캐너를 먼저 연결해 두세요. 스캐너는 키보드처럼 붙습니다.\n"
            + "⚠ 스캐너를 연결하면 폰 자판이 안 올라올 수 있으니, 이 화면을 먼저 끝내고 연결하세요.",
            13, "#666e7d", Gravity.START));

        setContentView(sc);
    }

    private TextView text(String s, int sp, String color, int gravity) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(Color.parseColor(color));
        t.setGravity(gravity);
        t.setPadding(0, dp(4), 0, dp(4));
        t.setLineSpacing(0, 1.3f);
        return t;
    }

    private View gap(int h) {
        View v = new View(this);
        v.setLayoutParams(new LinearLayout.LayoutParams(-1, h));
        return v;
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }
}
