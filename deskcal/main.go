// ════════════════════════════════════════════════════════════════════
//
//	📅 한일 바탕화면 달력 (Windows) — hanil-cal.exe
//
// ════════════════════════════════════════════════════════════════════
//
//	바탕화면 자체가 달력이 되는 프로그램(DesktopCal 같은 것)에 **회사 포털을 붙였다.**
//	  · 바탕화면 아이콘들 사이에 달력이 깔려 있다 — 다른 창을 띄우면 그 뒤로 숨고, 「바탕화면 보기」에서도 남는다.
//	  · 날짜 칸을 두 번 누르면 그날의 메모를 적는다(이 PC 에만 남는다).
//	  · 포털의 **결재 문서**가 기안일 칸에, **결재할 문서·오늘 할 일·쪽지·알림**이 옆 칸에 나온다.
//	  · 새 결재 요청·쪽지가 오면 작업 표시줄 오른쪽 아래에 윈도 알림을 띄운다.
//
//	⭐ 이 프로그램이 하는 일
//	  ① 포털 주소를 스스로 고른다(사내 주소 먼저, 안 되면 바깥 도메인)
//	  ② 이 PC 안에 작은 **관문**(127.0.0.1)을 열고, 그 관문으로 포털에 붙는다.
//	     관문은 **로그인과 «읽기만 하는» 몇 길(결재함·할 일·쪽지)** 만 통과시킨다.
//	     승인·반려 같은 일은 「포털에서 열기」로 평소 쓰는 브라우저에서 한다.
//	  ③ WebView2 창을 바탕화면에 깐다(작업 표시줄에는 안 나오고, 알림 영역 아이콘으로 부른다).
//
//	⚠ 비밀번호를 이 프로그램이 들고 있지 않는다 — 포털의 로그인 화면(2단계 인증 포함)을 그대로 쓰고,
//	  받은 세션 쿠키만 이 PC·이 사용자만 풀 수 있게(DPAPI) 암호화해 둔다.
package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
)

const VERSION = "1.0.0"

// 바탕화면·시작 메뉴 아이콘 이름
const shortcutName = "한일 바탕화면 달력"

// 달력 화면(이 프로그램 안에 들어 있다)
const startPath = "/cal"

// ⚠ 차례가 뜻이 있다: 사내 주소를 먼저 본다(더 빠르고, 바깥 인터넷이 끊겨도 된다).
//
//	노트북을 회사 밖에서 켜면 바깥 도메인으로 붙는다(안드로이드 앱과 같은 두 주소).
var defaultURLs = []string{
	"http://192.168.1.30:8820",
	"https://work.hanil-steel.com",
}

type Conf struct {
	URLs      []string
	Port      int
	Probe     int
	Shortcut  bool //  바탕화면·시작 메뉴 아이콘을 (없으면) 만든다
	Autostart bool //  윈도우가 켜지면 저절로 띄운다 — 바탕화면 달력이니 기본으로 켠다
	Pin       bool //  바탕화면에 깔기(끄면 보통 창)
}

var conf = Conf{Port: 18850, Probe: 3, Shortcut: true, Autostart: true, Pin: true}

const iniName = "hanil-cal.ini"

const SAMPLE_INI = `; 한일 바탕화면 달력 설정 — 바꾼 뒤 프로그램을 껐다 켜면 적용됩니다
; URL 은 쉼표로 여러 개 — 앞의 것부터 붙어 봅니다
URL=http://192.168.1.30:8820,https://work.hanil-steel.com
PIN=1               ; 1 = 바탕화면에 깔기(아이콘 사이) / 0 = 보통 창
AUTOSTART=1         ; 1 = 윈도우가 켜지면 저절로 띄웁니다
SHORTCUT=1          ; 1 = 바탕화면·시작 메뉴 아이콘을 (없으면) 만듭니다
PORT=18850          ; 이 PC 안의 관문 번호(다른 프로그램과 겹칠 때만 바꿉니다)
`

func main() {
	exeDir, exePath := ".", ""
	if p, err := os.Executable(); err == nil {
		if r, err2 := filepath.EvalSymlinks(p); err2 == nil {
			p = r
		}
		exeDir, exePath = filepath.Dir(p), p
	}
	openLog()
	//  📦 어디서 누르든 한 자리(%LOCALAPPDATA%\HanilCal\app)의 판으로 모은다 — 새 판이면 설치까지
	if selfInstall(exePath) {
		return
	}
	conf.URLs = append([]string{}, defaultURLs...)
	ini := filepath.Join(exeDir, iniName)
	if _, err := os.Stat(ini); os.IsNotExist(err) && runtime.GOOS == "windows" {
		_ = os.WriteFile(ini, []byte(strings.ReplaceAll(SAMPLE_INI, "\n", "\r\n")), 0o644)
	}
	readIni(ini)
	readArgs()
	logf("시작 v%s · %s · %s", VERSION, exePath, runtime.GOOS)

	//  ⚠ 이미 켜져 있으면 떠 있는 달력을 앞으로 부르고 끝낸다(달력이 두 장 깔리지 않게)
	if v, ok := runningVersion(conf.Port); ok {
		if v == VERSION || !newer(VERSION, v) {
			askFocus(conf.Port)
			logf("이미 켜져 있음(v%s) — 앞으로 불렀습니다", v)
			return
		}
		logf("예전 판(%s)이 떠 있음 — 내리고 새로 연다", v)
		askQuit(conf.Port)
		for i := 0; i < 20; i++ {
			if _, ok := runningVersion(conf.Port); !ok {
				break
			}
			time.Sleep(250 * time.Millisecond)
		}
	}

	//  🖥 바탕화면·시작 메뉴·시작프로그램 아이콘 — 창을 띄우는 것과 따로 돈다
	go func() {
		if conf.Shortcut && exePath != "" {
			ensureShortcuts(exePath, conf.Autostart)
		}
	}()

	ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(conf.Port))
	if err != nil {
		msgBox("한일 바탕화면 달력", "이 PC 의 "+strconv.Itoa(conf.Port)+" 번 문을 다른 프로그램이 쓰고 있습니다.\n"+
			iniName+" 의 PORT 를 다른 숫자로 바꿔 주세요.")
		return
	}
	gw := newGateway()
	gw.pickUpstream()
	go func() {
		//  ⚠ 회사 밖에서 켰다가 사내망에 붙는 노트북 — 끊겨 있으면 1분마다 다시 고른다
		for {
			time.Sleep(time.Minute)
			if gw.current() == nil {
				gw.pickUpstream()
			}
		}
	}()
	go func() { _ = (&http.Server{Handler: gw}).Serve(ln) }()

	if err := runWindow(local(conf.Port)+startPath, gw); err != nil {
		logf("창을 못 띄움: %v", err)
		msgBox("한일 바탕화면 달력", "달력 창을 띄우지 못했습니다.\n"+err.Error()+
			"\n\nMicrosoft Edge WebView2 런타임을 설치한 뒤 다시 실행해 주세요.\n(https://go.microsoft.com/fwlink/p/?LinkId=2124703)")
	}
	logf("끝")
}

func local(port int) string { return "http://127.0.0.1:" + strconv.Itoa(port) }

func localGet(port int, p string, wait time.Duration) (string, bool) {
	cl := &http.Client{Timeout: wait}
	r, err := cl.Get(local(port) + p)
	if err != nil {
		return "", false
	}
	defer r.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(r.Body, 64))
	return strings.TrimSpace(string(b)), r.StatusCode == http.StatusOK
}

func askFocus(port int) bool {
	s, ok := localGet(port, focusPath, 1500*time.Millisecond)
	return ok && s == "ok"
}

func askQuit(port int) { localGet(port, quitPath, 1500*time.Millisecond) }

// 떠 있는 관문의 판 번호("hanil-cal 1.0.0" 의 뒤)
func runningVersion(port int) (string, bool) {
	s, ok := localGet(port, pingPath, 800*time.Millisecond)
	if !ok || !strings.HasPrefix(s, "hanil-cal") {
		return "", false
	}
	return strings.TrimSpace(strings.TrimPrefix(s, "hanil-cal")), true
}

func profileDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "HanilCal")
}

// ── 기록 ────────────────────────────────────────────────────
//
//	%LOCALAPPDATA%\HanilCal\hanil-cal.log — «안 돼요» 할 때 이 파일을 받아 본다.
var logFile *os.File
var logMu sync.Mutex

func openLog() {
	_ = os.MkdirAll(profileDir(), 0o755)
	p := filepath.Join(profileDir(), "hanil-cal.log")
	if fi, err := os.Stat(p); err == nil && fi.Size() > 1<<20 {
		_ = os.Rename(p, p+".old")
	}
	f, err := os.OpenFile(p, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err == nil {
		logFile = f
	}
}

func logf(format string, a ...any) {
	logMu.Lock()
	defer logMu.Unlock()
	if logFile == nil {
		return
	}
	fmt.Fprintf(logFile, "%s  %s\r\n", time.Now().Format("2006-01-02 15:04:05"), fmt.Sprintf(format, a...))
}

// ── 주소 고르기 ────────────────────────────────────────────
//
//	⚠ «포트가 열렸나» 만 보면 안 된다 — 실제로 HTTP 로 물어보고 **답이 오는지**까지 본다.
func pick(urls []string) (string, []string) {
	tried := []string{}
	for _, u := range urls {
		u = strings.TrimRight(strings.TrimSpace(u), "/")
		if u == "" {
			continue
		}
		ok, why := probe(u, conf.Probe)
		tried = append(tried, u+"  →  "+why)
		if ok {
			return u, tried
		}
	}
	return "", tried
}

func probe(u string, sec int) (bool, string) {
	//  ⭐ 사내 주소는 1초면 넉넉하다 — 회사 밖에서 켤 때마다 몇 초씩 헛기다리지 않게
	wait := time.Duration(sec) * time.Second
	if isLAN(u) && wait > time.Second {
		wait = time.Second
	}
	if h := hostPort(u); h != "" {
		c, err := net.DialTimeout("tcp", h, wait)
		if err != nil {
			return false, "닿지 않습니다"
		}
		c.Close()
	}
	cl := &http.Client{
		Timeout:       time.Duration(sec+2) * time.Second,
		Transport:     &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: isLAN(u)}},
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	r, err := cl.Get(u + "/api/version")
	if err != nil {
		return false, "답이 없습니다"
	}
	r.Body.Close()
	if r.StatusCode >= 500 {
		return false, "서버 오류 " + r.Status
	}
	return true, "연결됨"
}

func hostPort(u string) string {
	s := u
	port := "80"
	if strings.HasPrefix(s, "https://") {
		s, port = s[8:], "443"
	} else if strings.HasPrefix(s, "http://") {
		s = s[7:]
	}
	if i := strings.IndexAny(s, "/?#"); i >= 0 {
		s = s[:i]
	}
	if s == "" {
		return ""
	}
	if _, _, err := net.SplitHostPort(s); err == nil {
		return s
	}
	return net.JoinHostPort(s, port)
}

// 사내망 주소(192.168.x · 10.x · 172.16~31.x · localhost)
func isLAN(u string) bool {
	h := hostPort(u)
	host, _, err := net.SplitHostPort(h)
	if err != nil {
		return false
	}
	if host == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && (ip.IsPrivate() || ip.IsLoopback())
}

// ── 설정 ───────────────────────────────────────────────────
func readIni(p string) {
	b, err := os.ReadFile(p)
	if err != nil {
		return
	}
	s := strings.TrimPrefix(string(b), "\uFEFF") //  메모장이 붙이는 BOM
	first := true
	for _, ln := range strings.Split(s, "\n") {
		if i := strings.Index(ln, ";"); i >= 0 {
			ln = ln[:i]
		}
		ln = strings.TrimSpace(ln)
		if ln == "" || strings.HasPrefix(ln, "#") {
			continue
		}
		i := strings.Index(ln, "=")
		if i < 0 {
			continue
		}
		k := strings.ToUpper(strings.TrimSpace(ln[:i]))
		v := strings.TrimSpace(ln[i+1:])
		if k == "URL" || k == "URLS" {
			if first {
				conf.URLs = nil
				first = false
			}
			addURLs(v)
			continue
		}
		setConf(k, v)
	}
}

func readArgs() {
	for _, a := range os.Args[1:] {
		a = strings.TrimPrefix(a, "--")
		i := strings.Index(a, "=")
		if i < 0 {
			continue
		}
		k := strings.ToUpper(strings.ReplaceAll(a[:i], "-", "_"))
		v := a[i+1:]
		if k == "URL" || k == "URLS" {
			conf.URLs = nil
			addURLs(v)
			continue
		}
		setConf(k, v)
	}
}

func addURLs(v string) {
	for _, one := range strings.Split(v, ",") {
		if s := strings.TrimSpace(one); s != "" {
			conf.URLs = append(conf.URLs, s)
		}
	}
}

func yes(v string) bool {
	v = strings.ToLower(strings.TrimSpace(v))
	return v == "1" || v == "y" || v == "yes" || v == "true" || v == "on"
}

func setConf(k, v string) {
	switch k {
	case "PORT":
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n < 65536 {
			conf.Port = n
		}
	case "PROBE":
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			conf.Probe = n
		}
	case "SHORTCUT":
		conf.Shortcut = yes(v)
	case "AUTOSTART":
		conf.Autostart = yes(v)
	case "PIN":
		conf.Pin = yes(v)
	}
}
