package main

// ── 자동 로그인 ─────────────────────────────────────────────
//
//	사용자 「로그인하는 메뉴를 없애자 — 클라이언트라」
//	⭐ 현장 사람은 로그인 화면을 보지 않는다. 키오스크마다 **처음 한 번** 현장용 계정을 넣어 두면
//	  관문이 포털에 대신 로그인하고, 세션이 끊기면 저절로 다시 로그인한다.
//	⭐ 포털 세션 쿠키는 **관문만** 들고 있다(브라우저 화면에는 주지 않는다).
//	⚠ 비밀번호는 윈도우 DPAPI 로 **이 PC·이 사용자만** 풀 수 있게 암호화해 둔다(account.dat).
//	  파일을 다른 PC 로 가져가도 못 푼다.
//	⚠ 로그인이 실패하면(비밀번호가 바뀜 등) 다시 시도하지 않고 계정 화면을 띄운다 —
//	  자꾸 두드리면 포털이 그 PC 의 IP 를 잠근다(5번 실패 = 10분 잠금).

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const setupPath = "/__label/account"

func accountFile() string { return filepath.Join(profileDir(), "account.dat") }

type accountRec struct {
	User string `json:"user"`
	Enc  string `json:"enc"`
}

func loadAccount() (string, string, bool) {
	b, err := os.ReadFile(accountFile())
	if err != nil {
		return "", "", false
	}
	var a accountRec
	if json.Unmarshal(b, &a) != nil || a.User == "" || a.Enc == "" {
		return "", "", false
	}
	raw, err := base64.StdEncoding.DecodeString(a.Enc)
	if err != nil {
		return "", "", false
	}
	pw, err := unprotect(raw)
	if err != nil {
		logf("계정 비밀번호를 풀지 못함(다른 PC·다른 사용자에서 만든 파일?): %v", err)
		return "", "", false
	}
	return a.User, string(pw), true
}

func saveAccount(user, pass string) error {
	enc, err := protect([]byte(pass))
	if err != nil {
		return err
	}
	_ = os.MkdirAll(profileDir(), 0o755)
	b, _ := json.Marshal(accountRec{User: user, Enc: base64.StdEncoding.EncodeToString(enc)})
	return os.WriteFile(accountFile(), b, 0o600)
}

// 설정 파일에 적힌 PASSWORD= 는 한 번 읽어 암호화해 두고 **파일에서는 지운다**
func scrubIniPassword(ini string) {
	b, err := os.ReadFile(ini)
	if err != nil {
		return
	}
	lines := strings.Split(string(b), "\n")
	changed := false
	for i, ln := range lines {
		t := strings.TrimSpace(ln)
		if strings.HasPrefix(strings.ToUpper(t), "PASSWORD=") && strings.TrimSpace(t[len("PASSWORD="):]) != "" {
			lines[i] = "PASSWORD=\r"
			changed = true
		}
	}
	if changed {
		_ = os.WriteFile(ini, []byte(strings.Join(lines, "\n")), 0o644)
		logf("설정 파일의 비밀번호를 암호화해 옮기고 지웠습니다")
	}
}

// ── 관문 쪽 ────────────────────────────────────────────────

// 포털에 로그인한다. 성공하면 관문의 쿠키 상자(jar)에 세션이 들어간다.
func (g *gateway) login(up *url.URL) error {
	user, pass, ok := loadAccount()
	if !ok {
		return errNoAccount
	}
	cl := &http.Client{
		Transport:     g.transport(up),
		Jar:           g.jar,
		Timeout:       20 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	form := url.Values{"username": {user}, "password": {pass}, "remember": {"1"}, "next": {startPath}}
	r, err := cl.PostForm(up.String()+"/login", form)
	if err != nil {
		return errors.New("포털에 연결하지 못했습니다")
	}
	r.Body.Close()
	loc := r.Header.Get("Location")
	if lu, err := url.Parse(loc); err == nil {
		if e := lu.Query().Get("err"); e != "" {
			return errors.New(e)
		}
		if strings.HasPrefix(lu.Path, "/2fa") {
			return errors.New("이 계정은 2단계 인증을 씁니다 — 키오스크에는 2단계 인증이 없는 현장용 계정을 넣어 주세요")
		}
	}
	if r.StatusCode >= 400 {
		return errors.New("포털이 로그인을 받지 않았습니다 (" + r.Status + ")")
	}
	g.mu.Lock()
	g.loggedIn = up.String()
	g.lastLogin = time.Now()
	g.acctErr = ""
	g.mu.Unlock()
	logf("포털에 자동 로그인했습니다 (%s · %s)", user, up.Host)
	return nil
}

var errNoAccount = errors.New("계정이 아직 없습니다")

// 로그인이 풀린 것을 알았을 때 — 곧바로 다시 로그인했는데 또 풀렸으면 멈춘다(무한 반복 막기)
func (g *gateway) loggedOut() {
	g.mu.Lock()
	defer g.mu.Unlock()
	if g.loggedIn != "" && time.Since(g.lastLogin) < 5*time.Second {
		g.acctErr = "로그인은 됐지만 포털이 이 계정으로 라벨 화면을 열어 주지 않습니다 — 라벨 권한이 있는 계정인지 확인해 주세요"
	}
	g.loggedIn = ""
}

// 필요하면 로그인한다. 참이면 계속, 거짓이면 계정 화면으로 보냈다.
func (g *gateway) ensureLogin(w http.ResponseWriter, r *http.Request, up *url.URL) bool {
	//  ⚠ 화면과 숨은 라벨 엔진이 한꺼번에 부르면 로그인이 겹친다 — 한 번에 하나만
	g.loginMu.Lock()
	defer g.loginMu.Unlock()
	g.mu.Lock()
	ok := g.loggedIn == up.String()
	stuck := g.acctErr
	g.mu.Unlock()
	if ok {
		return true
	}
	err := errors.New(stuck)
	if stuck == "" {
		err = g.login(up)
		if err == nil {
			return true
		}
		if err != errNoAccount {
			g.mu.Lock()
			g.acctErr = err.Error()
			g.mu.Unlock()
			logf("자동 로그인 실패: %v", err)
		}
	}
	if strings.HasPrefix(r.URL.Path, "/api/") || (r.Method != http.MethodGet && r.Method != http.MethodHead) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": false, "error": "로그인이 필요합니다"})
		return false
	}
	http.Redirect(w, r, setupPath, http.StatusFound)
	return false
}

// 계정 넣는 화면(처음 한 번 · 비밀번호가 바뀌었을 때)
func (g *gateway) serveAccount(w http.ResponseWriter, r *http.Request, up *url.URL) {
	msg := ""
	user, _, _ := loadAccount()
	if r.Method == http.MethodPost {
		_ = r.ParseForm()
		u := strings.TrimSpace(r.PostForm.Get("u"))
		p := r.PostForm.Get("p")
		if u == "" || p == "" {
			msg = "아이디와 비밀번호를 넣어 주세요."
		} else if up == nil {
			msg = "회사 포털에 연결되지 않았습니다 — 잠시 뒤 다시 해 주세요."
		} else {
			old, oldOK := []byte(nil), false
			if b, err := os.ReadFile(accountFile()); err == nil {
				old, oldOK = b, true
			}
			if err := saveAccount(u, p); err != nil {
				msg = "저장하지 못했습니다: " + err.Error()
			} else {
				g.mu.Lock()
				g.acctErr, g.loggedIn = "", ""
				g.mu.Unlock()
				if err := g.login(up); err != nil {
					//  ⚠ 틀린 것은 남기지 않는다 — 예전 계정으로 되돌린다
					if oldOK {
						_ = os.WriteFile(accountFile(), old, 0o600)
					} else {
						_ = os.Remove(accountFile())
					}
					msg = err.Error()
				} else {
					http.Redirect(w, r, startPath, http.StatusFound)
					return
				}
			}
			user = u
		}
	} else {
		g.mu.Lock()
		msg = g.acctErr
		g.mu.Unlock()
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	errHTML := ""
	if msg != "" {
		errHTML = `<div class="err">` + htmlEsc(msg) + `</div>`
	}
	_, _ = w.Write([]byte(strings.NewReplacer("{{ERR}}", errHTML, "{{USER}}", htmlEsc(user), "{{VER}}", VERSION).Replace(ACCOUNT_HTML)))
}

const ACCOUNT_HTML = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>한일 라벨 발행 · 계정</title>
<style>
 body{margin:0;background:#f4f6fa;color:#222;font:17px/1.6 "Segoe UI","Malgun Gothic",sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
 .card{background:#fff;border:1px solid #e3e8f0;border-radius:16px;padding:30px 34px;max-width:520px;width:92%}
 h1{font-size:24px;margin:0 0 4px;color:#1b2a4a}
 .sub{color:#6b7684;font-size:15px;margin-bottom:18px}
 label{display:block;font-size:14px;color:#6b7684;font-weight:700;margin:12px 0 4px}
 input{width:100%;box-sizing:border-box;border:2px solid #e3e8f0;border-radius:12px;padding:12px 14px;font-size:19px}
 input:focus{border-color:#2954A5;outline:0}
 button{margin-top:20px;width:100%;border:0;background:#2954A5;color:#fff;border-radius:12px;padding:16px;font-size:20px;font-weight:800;cursor:pointer}
 .err{background:#fdecea;color:#c0392b;border-radius:10px;padding:10px 14px;font-size:15px;margin-bottom:6px}
 .hint{font-size:13.5px;color:#6b7684;margin-top:16px;border-top:1px solid #f0f2f6;padding-top:12px}
</style></head><body>
<form class="card" method="post" action="` + setupPath + `">
  <h1>🏷 이 키오스크의 계정</h1>
  <div class="sub">처음 한 번만 넣으면 됩니다. 그 뒤로는 저절로 로그인합니다.</div>
  {{ERR}}
  <label>아이디</label><input name="u" value="{{USER}}" autocomplete="off" autofocus>
  <label>비밀번호</label><input name="p" type="password" autocomplete="off">
  <button>저장하고 시작</button>
  <div class="hint">· <b>라벨 권한만 있는 현장용 계정</b>을 넣어 주세요(2단계 인증이 없는 계정).<br>
  · 비밀번호는 이 PC 에서만 풀리게 암호화해 저장합니다.<br>
  · 포털에서 그 계정의 비밀번호를 바꾸면 이 화면이 다시 나옵니다. <span style="float:right">v{{VER}}</span></div>
</form>
<script>try{fetch('/__label/alive',{cache:'no-store'})}catch(e){}</script>
</body></html>`
