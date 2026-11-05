package main

// ── 관문(127.0.0.1) ─────────────────────────────────────────
//
//	달력 화면은 이 관문에만 붙고, 관문이 포털에 대신 묻는다(라벨 발행기와 같은 방식).
//
//	⭐ 왜 관문을 두나
//	  ① **달력이 쓰는 길만 연다** — 결재함 목록·문서 보기·오늘 할 일·쪽지/알림(읽기)과
//	     회사 일정(/api/cal/events — 읽기·등록·고치기·지우기, 포털의 calendar-route.js).
//	     바탕화면에 늘 깔려 있는 창이라, 실수로 누른 것이 승인·반려가 되면 안 된다 → 결재 쓰기는 막는다.
//	     결재 처리는 「포털에서 열기」로 평소 브라우저에서 한다.
//	  ② 포털 세션 쿠키를 관문이 들고 있다가 껐다 켜도 이어 쓴다(DPAPI 로 암호화해 보관).
//	  ③ 포털이 멎거나 선이 빠지면 달력은 그대로 보이고 「연결 끊김」만 띄운다.
//
//	⚠ 포털의 문지기(로그인·권한·CSRF)는 그대로 거친다 — 관문은 **좁히기만** 하고 넓히지 않는다.

import (
	"crypto/tls"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"path"
	"regexp"
	"strings"
	"sync"
	"time"
)

//go:embed page.html
var pageHTML []byte

const (
	pingPath   = "/__cal/ping"
	focusPath  = "/__cal/focus"
	quitPath   = "/__cal/quit"
	dataPath   = "/__cal/data"
	statePath  = "/__cal/state"
	retryPath  = "/__cal/retry"
	openPath   = "/__cal/open"
	notifyPath = "/__cal/notify"
	winPath    = "/__cal/win"
	logoutPath = "/__cal/logout"
	discPath   = "/__cal/discover"
)

type gateway struct {
	mu       sync.Mutex
	upstream *url.URL
	tried    []string
	box      *cookieBox
	tr       map[string]*http.Transport
}

func newGateway() *gateway {
	loadDiscovered()
	return &gateway{tr: map[string]*http.Transport{}, box: newCookieBox()}
}

func (g *gateway) pickUpstream() bool {
	u, tried := pick(conf.URLs)
	g.mu.Lock()
	defer g.mu.Unlock()
	g.tried = tried
	if u == "" {
		g.upstream = nil
		logf("포털에 못 붙음: %v", tried)
		return false
	}
	g.upstream, _ = url.Parse(u)
	logf("포털 주소: %s", u)
	return true
}

func (g *gateway) current() *url.URL {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.upstream
}

func (g *gateway) transport(u *url.URL) *http.Transport {
	g.mu.Lock()
	defer g.mu.Unlock()
	k := u.Scheme + "://" + u.Host
	if t, ok := g.tr[k]; ok {
		return t
	}
	t := http.DefaultTransport.(*http.Transport).Clone()
	//  ⚠ 사내 주소는 인증서가 제 이름이 아닐 수 있다 — **사내망 주소일 때만** 눈감아 준다
	t.TLSClientConfig = &tls.Config{InsecureSkipVerify: isLAN(u.String())}
	t.ResponseHeaderTimeout = 30 * time.Second
	g.tr[k] = t
	return t
}

// ── 어느 길을 통과시키나 ─────────────────────────────────────
var (
	reApprDoc   = regexp.MustCompile(`^/api/appr/\d+$`)
	reApprPrint = regexp.MustCompile(`^/api/appr/\d+/print$`)
	reCalEvent  = regexp.MustCompile(`^/api/cal/events/[0-9a-f]{16}$`)
)

// 읽기만 하는 포털 API — 달력이 쓰는 것뿐
var apiOK = map[string]bool{
	"/api/apprdoc/list":       true, //  결재함: 내가 올린 것(mine) · 내 차례(waiting) · 끝난 것(done)
	"/api/my-today":           true, //  오늘 할 일(결재·업무지시 …) 수
	"/api/deskmsg":            true, //  업무 쪽지함 — 쪽지·알림
	"/api/chat/unread":        true,
	"/api/chat/channels":      true,
	"/api/version":            true,
	"/api/cal/mydata/history": true, //  내 달력 자료(메모·할 일·기념일)의 지난 판 목록 — 되돌리기용
}

var staticOK = map[string]bool{
	"/menulog.js": true, "/hanil-logo.png": true, "/favicon.ico": true, "/wm.js": true,
}
var staticPrefix = []string{"/css/", "/js/", "/fonts/", "/img/", "/app-icons/"}

func allowed(method, p string) bool {
	get := method == http.MethodGet || method == http.MethodHead
	switch {
	case strings.HasSuffix(p, "/sw.js"):
		return false //  ⚠ 포털 앱 설치용 서비스 워커 — 이 창에 깔리면 요청을 가로챈다
	//  로그인 · 2단계 인증
	case p == "/" && get:
		return true
	case p == "/login" && method == http.MethodPost:
		return true
	case p == "/2fa" || p == "/2fa/resend" || p == "/2fa/cancel":
		return true
	//  📅 회사 일정 — 달력에서 보고·올리고·고치고·지운다(누가 무엇을 고칠 수 있는지는 포털이 정한다)
	case p == "/api/cal/holidays" && get:
		return true
	//  ☁ 내 달력 자료(메모·할 일·기념일·설정) — 여러 PC·폰 사이 동기화 · 지난 판으로 되돌리기
	case p == "/api/cal/mydata" && (get || method == http.MethodPut):
		return true
	case p == "/api/cal/mydata/rollback" && method == http.MethodPost:
		return true
	//  🟦 구글 캘린더 — 내 구글 일정 읽기(포털이 대신 받아 온다) · 구글로 보낼 구독 주소 만들기
	case p == "/api/cal/gcal" && (get || method == http.MethodPut):
		return true
	case p == "/api/cal/feed" && method == http.MethodPost:
		return true
	case p == "/api/cal/events" && (get || method == http.MethodPost):
		return true
	case reCalEvent.MatchString(p) && (method == http.MethodPut || method == http.MethodDelete):
		return true
	case !get:
		return false //  ⭐ 그 밖의 쓰기는 하나도 통과시키지 않는다
	case apiOK[p], reApprDoc.MatchString(p), reApprPrint.MatchString(p), strings.HasPrefix(p, "/api/appr/file/"):
		return true
	//  📅 포털에 원래 있는 달력 — 스스로 찾아낸 그 주소(읽기만)
	case p != "" && p == discoveredAPI():
		return true
	case staticOK[p]:
		return true
	}
	for _, x := range staticPrefix {
		if strings.HasPrefix(p, x) {
			return true
		}
	}
	return false
}

func (g *gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	p := r.URL.Path
	if strings.HasPrefix(p, "/__cal/") {
		g.serveLocal(w, r)
		return
	}
	if p == startPath && (r.Method == http.MethodGet || r.Method == http.MethodHead) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write([]byte(strings.Replace(string(pageHTML), "{{VER}}", VERSION, -1)))
		return
	}
	isAPI := strings.HasPrefix(p, "/api/")
	if !allowed(r.Method, p) {
		if isAPI || (r.Method != http.MethodGet && r.Method != http.MethodHead) {
			jsonErr(w, http.StatusForbidden, map[string]any{"ok": false, "error": "달력에서는 쓸 수 없는 기능입니다 — 「포털에서 열기」로 해 주세요."})
			return
		}
		if path.Ext(p) != "" {
			http.NotFound(w, r)
			return
		}
		http.Redirect(w, r, startPath, http.StatusFound)
		return
	}
	up := g.current()
	if up == nil {
		if isAPI {
			jsonErr(w, http.StatusBadGateway, map[string]any{"ok": false, "offline": true, "error": "회사 포털에 연결되지 않았습니다"})
			return
		}
		http.Redirect(w, r, startPath, http.StatusFound)
		return
	}
	g.proxy(up).ServeHTTP(w, r)
}

func jsonErr(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

// ── 이 프로그램 자신의 길 ───────────────────────────────────
func (g *gateway) serveLocal(w http.ResponseWriter, r *http.Request) {
	//  ⚠ 다른 웹사이트가 127.0.0.1 로 몰래 부르는 것을 막는다 — 쓰기는 이 창(같은 출처)에서 온 것만
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		if o := r.Header.Get("Origin"); o != "" && o != "http://"+r.Host {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
	}
	w.Header().Set("Cache-Control", "no-store")
	switch r.URL.Path {
	case pingPath:
		fmt.Fprint(w, "hanil-cal "+VERSION)
	case focusPath:
		if focusWindow() {
			fmt.Fprint(w, "ok")
		} else {
			http.NotFound(w, r)
		}
	case quitPath:
		fmt.Fprint(w, "ok")
		go func() { time.Sleep(200 * time.Millisecond); quitApp() }()
	case dataPath:
		if r.Method == http.MethodPut || r.Method == http.MethodPost {
			b, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
			if err == nil {
				err = saveData(b)
			}
			if err != nil {
				jsonErr(w, http.StatusBadRequest, map[string]any{"ok": false, "error": err.Error()})
				return
			}
			fmt.Fprint(w, `{"ok":true}`)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_, _ = w.Write(loadData())
	case statePath, retryPath:
		if r.URL.Path == retryPath {
			g.pickUpstream()
		}
		up := g.current()
		g.mu.Lock()
		tried := append([]string{}, g.tried...)
		g.mu.Unlock()
		portal := ""
		if up != nil {
			portal = up.String()
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"ok": true, "version": VERSION, "portal": portal, "tried": tried,
			"session": !g.box.empty(), "pinned": isPinned(), "desktop": hasDesktop(), "alpha": currentAlpha(),
			"portalCal": discoveredAPI(), "portalCalPage": discNow.Page, "portalCalAt": discNow.At,
		})
	case "/__cal/diag":
		//  🩺 화면이 포털 자료의 «모양»(칸 이름·첫 줄)을 기록에 남긴다 — 칸 이름이 예상과 다를 때 맞추려고
		b, _ := io.ReadAll(io.LimitReader(r.Body, 8<<10))
		logf("진단: %s", string(b))
		fmt.Fprint(w, "ok")
	case discPath:
		//  📅 포털 달력 찾기 — ?run=1 이면 지금 다시 찾는다(로그인돼 있어야)
		d := discNow
		if r.URL.Query().Get("run") == "1" {
			d = g.discover()
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(d)
	case openPath:
		//  🌐 평소 쓰는 브라우저로 포털의 그 화면을 연다(결재·답장은 거기서)
		u := r.URL.Query().Get("u")
		up := g.current()
		if !strings.HasPrefix(u, "/") || strings.HasPrefix(u, "//") {
			http.Error(w, "bad", http.StatusBadRequest)
			return
		}
		base := conf.URLs[0]
		if up != nil {
			base = up.String()
		}
		openExternal(strings.TrimRight(base, "/") + u)
		fmt.Fprint(w, "ok")
	case notifyPath:
		var n struct{ Title, Text, U string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 64<<10)).Decode(&n)
		showNotice(n.Title, n.Text, n.U)
		fmt.Fprint(w, "ok")
	case winPath:
		windowCmd(r.URL.Query().Get("m"), r.URL.Query().Get("v"))
		fmt.Fprint(w, "ok")
	case logoutPath:
		if up := g.current(); up != nil {
			cl := &http.Client{Transport: g.transport(up), Timeout: 5 * time.Second,
				CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
			if req, err := http.NewRequest(http.MethodGet, up.String()+"/logout", nil); err == nil {
				for _, c := range g.box.list() {
					req.AddCookie(c)
				}
				if res, err := cl.Do(req); err == nil {
					res.Body.Close()
				}
			}
		}
		g.box.clear()
		logf("로그아웃")
		fmt.Fprint(w, `{"ok":true}`)
	default:
		http.NotFound(w, r)
	}
}

func (g *gateway) proxy(up *url.URL) *httputil.ReverseProxy {
	return &httputil.ReverseProxy{
		Transport: g.transport(up),
		Rewrite: func(pr *httputil.ProxyRequest) {
			pr.SetURL(up)
			//  ⚠ 포털은 Origin/Referer 가 **제 주소**인지 본다(CSRF 방어) — 관문 주소를 포털 주소로 바꿔 준다
			if o := pr.In.Header.Get("Origin"); o != "" {
				pr.Out.Header.Set("Origin", up.Scheme+"://"+up.Host)
			}
			if ref := pr.In.Header.Get("Referer"); ref != "" {
				if ru, err := url.Parse(ref); err == nil {
					ru.Scheme, ru.Host = up.Scheme, up.Host
					pr.Out.Header.Set("Referer", ru.String())
				}
			}
			//  🔑 화면의 쿠키는 버리고 관문이 든 포털 세션을 붙인다
			pr.Out.Header.Del("Cookie")
			for _, c := range g.box.list() {
				pr.Out.AddCookie(c)
			}
			pr.Out.Header.Del("X-Forwarded-For")
			//  ⚠ 로그인 화면은 관문이 글을 고쳐야 한다 → 압축 없이 받는다
			if pr.In.URL.Path == "/" {
				pr.Out.Header.Del("Accept-Encoding")
			}
		},
		ModifyResponse: func(res *http.Response) error { return g.fixResponse(res, up) },
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			logf("포털 연결 끊김 %s %s: %v", r.Method, r.URL.Path, err)
			g.mu.Lock()
			g.upstream = nil
			g.tried = []string{up.String() + "  →  연결이 끊겼습니다"}
			g.mu.Unlock()
			if strings.HasPrefix(r.URL.Path, "/api/") {
				jsonErr(w, http.StatusBadGateway, map[string]any{"ok": false, "offline": true, "error": "회사 포털에 연결되지 않았습니다"})
				return
			}
			http.Redirect(w, r, startPath, http.StatusFound)
		},
	}
}

func isLoginLoc(lu *url.URL) bool {
	return lu.Path == "/" || lu.Path == "" || lu.Path == "/login" || strings.HasPrefix(lu.Path, "/kiosk/login")
}

func (g *gateway) fixResponse(res *http.Response, up *url.URL) error {
	req := res.Request
	//  ① 쿠키 — 포털 세션은 **관문의 상자**에만 둔다(화면에는 주지 않는다)
	if cs := res.Cookies(); len(cs) > 0 {
		g.box.set(cs)
		res.Header.Del("Set-Cookie")
	}
	isAPI := strings.HasPrefix(req.URL.Path, "/api/")
	//  ② 로그인이 풀렸다(401 · 로그인 화면으로 보냄) → API 는 «로그인 필요» 로 고쳐 준다(화면이 로그인 단추를 띄운다)
	loc := res.Header.Get("Location")
	lu, _ := url.Parse(loc)
	if isAPI && (res.StatusCode == http.StatusUnauthorized || (loc != "" && lu != nil && isLoginLoc(lu))) {
		return replaceJSON(res, http.StatusUnauthorized, `{"ok":false,"login":true,"error":"로그인이 필요합니다"}`)
	}
	//  ③ 옮겨 가는 주소 — 포털 주소를 관문 주소로, 달력이 못 여는 곳은 달력으로
	if loc != "" && lu != nil {
		res.Header.Set("Location", fixLocation(lu, up))
	}
	//  ④ 결재 문서 종이(인쇄 화면)는 달력 안의 틀(iframe)에 띄운다 — 틀에 못 넣게 막는 머리말을 뗀다(같은 출처라 안전)
	if reApprPrint.MatchString(req.URL.Path) {
		res.Header.Del("X-Frame-Options")
		res.Header.Del("Content-Security-Policy")
	}
	//  ⑤ «/» — 로그인 화면이면 들어온 뒤 달력으로 오게 next 를 심고, 이미 로그인돼 포털 첫 화면이 오면 달력으로 돌린다
	if req.URL.Path == "/" && req.Method == http.MethodGet && res.StatusCode == http.StatusOK {
		body, err := io.ReadAll(io.LimitReader(res.Body, 4<<20))
		res.Body.Close()
		if err != nil {
			return err
		}
		html := string(body)
		if strings.Contains(html, `action="/login"`) || strings.Contains(html, `action="/2fa`) {
			if !strings.Contains(html, `name="next"`) {
				html = strings.Replace(html, `action="/login">`,
					`action="/login"><input type="hidden" name="next" value="`+startPath+`">`, 1)
			}
			html = strings.Replace(html, "</body>", loginNote+"</body>", 1)
		} else {
			res.StatusCode = http.StatusFound
			res.Status = "302 Found"
			res.Header.Set("Location", startPath)
			html = ""
		}
		setBody(res, html)
	}
	return nil
}

func replaceJSON(res *http.Response, code int, body string) error {
	res.Body.Close()
	res.StatusCode = code
	res.Status = fmt.Sprintf("%d %s", code, http.StatusText(code))
	res.Header = http.Header{"Content-Type": {"application/json; charset=utf-8"}, "Cache-Control": {"no-store"}}
	setBody(res, body)
	return nil
}

func setBody(res *http.Response, s string) {
	res.Header.Del("Content-Length")
	res.Header.Del("Content-Encoding")
	res.Body = io.NopCloser(strings.NewReader(s))
	res.ContentLength = int64(len(s))
}

func fixLocation(u *url.URL, up *url.URL) string {
	if u.IsAbs() {
		if u.Host != up.Host {
			return startPath //  ⚠ 다른 곳으로는 보내지 않는다
		}
		u.Scheme, u.Host = "", ""
	}
	p := u.Path
	//  로그인 화면 · 로그인 실패(`/?err=…` — 사유를 보여 줘야 한다) · 2단계 인증은 그대로
	if p == "/" || p == "" {
		if u.RawQuery != "" {
			return u.RequestURI()
		}
		return "/"
	}
	if strings.HasPrefix(p, "/2fa") || p == startPath {
		return u.RequestURI()
	}
	if strings.HasPrefix(p, "/kiosk/login") || p == "/login" {
		return "/"
	}
	if allowed(http.MethodGet, p) {
		return u.RequestURI()
	}
	return startPath
}

// 로그인 화면 아래에 붙이는 한 줄
const loginNote = `<div style="position:fixed;left:0;right:0;bottom:0;background:#1b2a4a;color:#fff;` +
	`font:14px/1.6 'Malgun Gothic',sans-serif;text-align:center;padding:9px">` +
	`📅 <b>한일 바탕화면 달력 v` + VERSION + `</b> · 로그인하면 달력에 결재·알림이 나옵니다 · 「로그인 유지」를 켜 두세요` +
	` · <a href="/cal" style="color:#9cc3f0">달력으로 돌아가기</a></div>`
