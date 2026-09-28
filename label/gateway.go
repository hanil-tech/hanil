package main

// ── 관문(127.0.0.1) ─────────────────────────────────────────
//
//	브라우저는 이 관문에만 붙고, 관문이 포털에 대신 묻는다.
//
//	⭐ 왜 관문을 두나
//	  ① **라벨 길만 연다.** 사무직 계정으로 로그인해도 이 창에서는 라벨 화면 밖으로 못 나간다.
//	     (주소창이 없어도 링크 하나로 다른 메뉴가 열릴 수 있다 — 그 길을 여기서 끊는다.)
//	  ② 로그인하면 포털 첫 화면이 아니라 **곧장 라벨 화면**으로 온다.
//	  ③ 포털이 멎거나 선이 빠지면 브라우저 오류 대신 **우리말 안내**와 다시 시도 단추를 보인다.
//	     다시 붙을 때 사내 주소 ↔ 도메인을 새로 고른다.
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
	"strings"
	"sync"
	"time"
)

//go:embed page.html
var pageHTML []byte

const pingPath = "/__label/ping"
const retryPath = "/__label/retry"

type gateway struct {
	mu       sync.Mutex
	upstream *url.URL
	tried    []string
	seen     time.Time
	tr       map[string]*http.Transport
}

func newGateway() *gateway {
	return &gateway{seen: time.Now(), tr: map[string]*http.Transport{}}
}

func (g *gateway) lastSeen() time.Time {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.seen
}

func (g *gateway) pickUpstream() bool {
	u, tried := pick(conf.URLs)
	g.mu.Lock()
	defer g.mu.Unlock()
	g.tried = tried
	if u == "" {
		g.upstream = nil
		return false
	}
	g.upstream, _ = url.Parse(u)
	return true
}

func (g *gateway) current() *url.URL {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.seen = time.Now()
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
	t.ResponseHeaderTimeout = 60 * time.Second
	g.tr[k] = t
	return t
}

// ── 어느 길을 통과시키나 ─────────────────────────────────────
type verdict int

const (
	pass verdict = iota
	home         //  화면 요청 → 라벨 화면으로 돌려보낸다
	deny         //  API 요청 → 403
	gone         //  스크립트·그림 같은 조각 → 404 (라벨 화면 HTML 을 대신 주면 «스크립트가 아니다» 오류가 난다)
)

var staticOK = map[string]bool{
	"/menulog.js": true, "/itempeek.js": true, "/hanil-logo.png": true,
	"/favicon.ico": true, "/manifest.json": true,
}
var staticPrefix = []string{"/css/", "/js/", "/fonts/", "/img/", "/app-icons/"}

func rule(method, p string) verdict {
	get := method == http.MethodGet || method == http.MethodHead
	isAPI := strings.HasPrefix(p, "/api/")
	no := home
	if isAPI || !get {
		no = deny
	}
	//  ⚠ 조각(스크립트·그림·글꼴)은 돌려보내지 않고 «없음» 으로 답한다
	if no == home && path.Ext(p) != "" {
		no = gone
	}
	switch {
	//  ⚠⚠ 포털의 앱 설치용 서비스 워커는 막는다. 이 창에 한 번 깔리면 요청을 가로채고
	//    알림 권한을 물어 «Permissions check failed» 오류가 난다.
	//    404 를 주면 브라우저가 이미 깔린 워커도 스스로 지운다.
	case strings.HasSuffix(p, "/sw.js"):
		return gone
	//  라벨 화면
	case p == portalLabel && get:
		return pass
	//  로그인 · 2단계 인증 · 나가기
	case p == "/" && get:
		return pass //  ⚠ 로그인 뒤의 «포털 첫 화면»은 ServeHTTP 가 따로 막는다
	case p == "/login" && method == http.MethodPost:
		return pass
	case p == "/2fa" || p == "/2fa/resend" || p == "/2fa/cancel":
		return pass
	case p == "/logout":
		return pass
	//  라벨 API — 읽기는 모두, 쓰기는 «라벨 만들기» 하나만.
	//  ⚠ 양식·라벨지 이름 바꾸기, 미세조정 저장, 출고 표시는 사무실에서 한다
	//    (현장에서 건드려 라벨지가 어긋나면 그 종이는 통째로 못 쓴다).
	case strings.HasPrefix(p, "/api/labels/") && get:
		return pass
	case p == "/api/labels/make" && method == http.MethodPost:
		return pass
	case p == "/api/pv/label-forms" && get:
		return pass
	//  품목 사진 · 품번 미리보기(읽기만)
	case (strings.HasPrefix(p, "/api/items/img/") || strings.HasPrefix(p, "/api/items/by-no/")) && get:
		return pass
	//  메뉴 사용 기록(포털 공통 스크립트)
	case p == "/api/menulog" || p == "/api/menulog/can":
		return pass
	case staticOK[p] && get:
		return pass
	}
	if get {
		for _, x := range staticPrefix {
			if strings.HasPrefix(p, x) {
				return pass
			}
		}
	}
	return no
}

func (g *gateway) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	p := r.URL.Path
	switch p {
	case pingPath:
		fmt.Fprint(w, "hanil-label "+VERSION)
		return
	case retryPath:
		ok := g.pickUpstream()
		g.mu.Lock()
		t := strings.Join(g.tried, " · ")
		g.mu.Unlock()
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": ok, "url": startPath, "tried": t})
		return
	}
	up := g.current()
	if up == nil {
		g.offline(w, r)
		return
	}
	//  🏷 간편 발행 화면 — 이 프로그램 안에 들어 있다(라벨 그리기·인쇄는 숨겨 둔 포털 라벨 화면이 한다)
	if p == startPath && (r.Method == http.MethodGet || r.Method == http.MethodHead) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(pageHTML)
		return
	}
	switch rule(r.Method, p) {
	case home:
		http.Redirect(w, r, startPath, http.StatusFound)
		return
	case gone:
		http.NotFound(w, r)
		return
	case deny:
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprint(w, `{"ok":false,"error":"라벨 발행기에서는 쓸 수 없는 기능입니다. 사무실 포털에서 해 주세요."}`)
		return
	}
	g.proxy(up).ServeHTTP(w, r)
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
			//  ⚠ X-Forwarded-For 를 붙이지 않는다 — 붙이면 포털 기록에 이 PC 가 아니라 127.0.0.1 이 남는다
			pr.Out.Header.Del("X-Forwarded-For")
			//  ⚠ 첫 화면(/)은 관문이 글을 읽어 고쳐야 한다 → 압축 없이 받는다(Go 가 알아서 풀어 준다)
			if pr.In.URL.Path == "/" || pr.In.URL.Path == portalLabel {
				pr.Out.Header.Del("Accept-Encoding")
			}
			//  ⭐ 라벨 화면은 «끼워 넣은 화면(embed=1)» 으로 받는다.
			//    그러면 포털이 사무실용 장치(통합검색·알림·쪽지·점검 안내·앱 설치·자동 로그아웃)를
			//    붙이지 않는다 — 그 장치들이 부르는 API 는 관문이 막으므로 붙어 있으면 오류만 난다.
			if pr.In.URL.Path == portalLabel {
				q := pr.Out.URL.Query()
				q.Set("embed", "1")
				pr.Out.URL.RawQuery = q.Encode()
			}
		},
		ModifyResponse: func(res *http.Response) error { return g.fixResponse(res, up) },
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			//  ⚠ 붙어 있던 주소가 끊겼다 — 다음 «다시 시도»에서 새로 고르게 비운다
			g.mu.Lock()
			g.upstream = nil
			g.tried = []string{up.String() + "  →  " + shortErr(err)}
			g.mu.Unlock()
			g.offline(w, r)
		},
	}
}

func shortErr(err error) string {
	s := err.Error()
	if strings.Contains(s, "timeout") || strings.Contains(s, "deadline") {
		return "답이 너무 늦습니다"
	}
	return "연결이 끊겼습니다"
}

func (g *gateway) fixResponse(res *http.Response, up *url.URL) error {
	req := res.Request
	//  ① 쿠키 — 관문(127.0.0.1)에 붙도록 Domain·Secure 를 뗀다.
	//     ⚠ 관문 ↔ 브라우저 사이는 이 PC 안이라 밖으로 나가지 않는다. 포털까지는 원래대로 https 다.
	if cs := res.Header.Values("Set-Cookie"); len(cs) > 0 {
		res.Header.Del("Set-Cookie")
		for _, c := range cs {
			res.Header.Add("Set-Cookie", localCookie(c))
		}
	}
	//  ② 옮겨 가는 주소 — 포털 주소를 관문 주소로, 라벨 밖으로 가는 곳은 라벨 화면으로
	if loc := res.Header.Get("Location"); loc != "" {
		res.Header.Set("Location", g.fixLocation(loc, up))
	}
	//  ③ 라벨 화면 — 예전 판이 깔아 둔 서비스 워커를 지운다(한 번 지우면 다시 안 깔린다)
	if req.URL.Path == portalLabel && req.Method == http.MethodGet && res.StatusCode == http.StatusOK {
		body, err := io.ReadAll(io.LimitReader(res.Body, 16<<20))
		res.Body.Close()
		if err != nil {
			return err
		}
		html := string(body)
		if i := strings.Index(strings.ToLower(html), "</head>"); i >= 0 {
			html = html[:i] + swKill + html[i:]
		} else {
			html = swKill + html
		}
		res.Header.Del("Content-Length")
		res.Header.Del("Content-Encoding")
		res.Body = io.NopCloser(strings.NewReader(html))
		res.ContentLength = int64(len(html))
	}
	//  ④ 로그인한 채로 «/» 를 열면 포털 첫 화면이 나온다 → 라벨 화면으로 돌린다.
	//     로그인 화면(아직 안 들어옴)일 때만 그대로 보여 주고, 들어오면 라벨 화면으로 오게 `next` 를 심는다.
	if req.URL.Path == "/" && req.Method == http.MethodGet && res.StatusCode == http.StatusOK {
		body, err := io.ReadAll(io.LimitReader(res.Body, 4<<20))
		res.Body.Close()
		if err != nil {
			return err
		}
		html := string(body)
		if strings.Contains(html, `action="/login"`) || strings.Contains(html, `action="/setup"`) {
			if !strings.Contains(html, `name="next"`) {
				html = strings.Replace(html, `<form method="post" action="/login">`,
					`<form method="post" action="/login"><input type="hidden" name="next" value="`+startPath+`">`, 1)
			}
			html = strings.Replace(html, "</body>", loginNote+"</body>", 1)
		} else {
			res.StatusCode = http.StatusFound
			res.Status = "302 Found"
			res.Header.Set("Location", startPath)
			html = ""
		}
		res.Header.Del("Content-Length")
		res.Header.Del("Content-Encoding")
		res.Body = io.NopCloser(strings.NewReader(html))
		res.ContentLength = int64(len(html))
	}
	return nil
}

// 이 창(127.0.0.1)에 깔린 서비스 워커를 모두 지운다
const swKill = `<script>try{navigator.serviceWorker&&navigator.serviceWorker.getRegistrations()` +
	`.then(function(rs){rs.forEach(function(r){r.unregister();});}).catch(function(){});}catch(e){}</script>`

// 로그인 화면 아래에 붙이는 한 줄 — 이 창이 라벨 전용임을 알린다
const loginNote = `<div style="position:fixed;left:0;right:0;bottom:0;background:#1b2a4a;color:#fff;` +
	`font:15px/1.6 'Malgun Gothic',sans-serif;text-align:center;padding:10px">` +
	`🏷 <b>한일 라벨 발행기</b> · 로그인하면 라벨 화면이 바로 열립니다 · 「로그인 유지」를 켜 두세요</div>`

func localCookie(c string) string {
	parts := strings.Split(c, ";")
	out := []string{strings.TrimSpace(parts[0])}
	for _, a := range parts[1:] {
		a = strings.TrimSpace(a)
		l := strings.ToLower(a)
		if strings.HasPrefix(l, "domain=") || l == "secure" {
			continue
		}
		//  ⚠ SameSite=None 은 Secure 가 없으면 버려진다 → Lax 로
		if l == "samesite=none" {
			a = "SameSite=Lax"
		}
		out = append(out, a)
	}
	return strings.Join(out, "; ")
}

func (g *gateway) fixLocation(loc string, up *url.URL) string {
	u, err := url.Parse(loc)
	if err != nil {
		return startPath
	}
	if u.IsAbs() {
		if u.Host != up.Host {
			return startPath //  ⚠ 다른 곳으로는 보내지 않는다
		}
		u.Scheme, u.Host = "", ""
	}
	p := u.Path
	//  키오스크 로그인 화면은 키오스크 계정만 받는다 → 포털 로그인으로(들어오면 라벨 화면으로)
	if strings.HasPrefix(p, "/kiosk/login") || strings.HasPrefix(p, "/kiosk/blocked") {
		return "/?next=" + url.QueryEscape(startPath)
	}
	//  로그인 실패(`/?err=…`)는 그대로 — 사유를 보여 줘야 한다
	if p == "/" || p == "" {
		if u.RawQuery != "" {
			return u.RequestURI()
		}
		return startPath
	}
	if rule(http.MethodGet, p) == pass {
		return u.RequestURI()
	}
	return startPath
}

// ── 못 붙었을 때 ────────────────────────────────────────────
func (g *gateway) offline(w http.ResponseWriter, r *http.Request) {
	if strings.HasPrefix(r.URL.Path, "/api/") || (r.Method != http.MethodGet && r.Method != http.MethodHead) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusBadGateway)
		fmt.Fprint(w, `{"ok":false,"error":"회사 포털에 연결되지 않았습니다. 잠시 뒤 다시 해 주세요."}`)
		return
	}
	g.mu.Lock()
	rows := ""
	for _, t := range g.tried {
		rows += "<li>" + htmlEsc(t) + "</li>"
	}
	g.mu.Unlock()
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusServiceUnavailable)
	fmt.Fprint(w, strings.NewReplacer("{{ROWS}}", rows, "{{VER}}", VERSION, "{{INI}}", iniName).Replace(HELP))
}

func htmlEsc(s string) string {
	return strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;", `"`, "&quot;").Replace(s)
}
