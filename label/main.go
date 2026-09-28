// ════════════════════════════════════════════════════════════════════
//
//	🏷 한일특장 라벨 발행기 (Windows) — hanil-label.exe
//
// ════════════════════════════════════════════════════════════════════
//
//	현장 키오스크(바코드 리더기 달린 PC)에서 **라벨만** 뽑는 프로그램.
//	작업이 끝나면 품번을 리더기로 찍거나 찾아서 담고, 바코드 프린터나 레이저 프린터로 뽑는다.
//
//	⭐ 라벨을 그리는 코드는 **포털의 것(/kiosk/label)을 그대로** 쓴다.
//	  이 프로그램이 라벨을 따로 그리면 사무실 라벨과 현장 라벨이 곧 달라진다.
//	  로트·고유번호·QR 도 포털이 매기므로 사무실에서 뽑은 것과 한 줄로 이어진다.
//
//	⭐ 이 프로그램이 하는 일
//	  ① 포털 주소를 스스로 고른다(사내 주소 먼저, 안 되면 도메인)
//	  ② 이 PC 안에 작은 **관문**(127.0.0.1)을 열고, 그 관문으로 포털에 붙는다.
//	     관문은 **라벨 화면과 로그인에 필요한 길만** 통과시킨다 — 누가 어느 계정으로
//	     로그인하든 이 창에서는 급여·회계 같은 다른 메뉴로 갈 수 없다.
//	  ③ Edge(없으면 Chrome)를 주소창 없는 창으로 띄운다.
//	     인쇄는 «인쇄 창에서 프린터 고르기» 또는 «기본 프린터로 바로» 중 하나(설정 파일).
//
//	⚠ 바깥 꾸러미를 하나도 안 쓴다(go 표준 것만).
package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
)

const VERSION = "1.4.1"

// 바탕화면·시작 메뉴 아이콘 이름
const shortcutName = "한일 라벨 발행기"

// 가장 먼저 열 화면 — 가운데 검색창 하나인 «간편 발행» 화면(page.html)
const startPath = "/label"

// 포털의 키오스크 라벨 화면 — 라벨을 그리고 인쇄하는 곳(간편 화면이 숨겨 두고 쓴다)
const portalLabel = "/kiosk/label"

// ⚠ 차례가 뜻이 있다: 사내 주소를 먼저 본다(더 빠르고, 바깥 인터넷이 끊겨도 된다).
var defaultURLs = []string{
	"http://192.168.1.30:8820",
	"https://work.hanil-steel.com",
}

type Conf struct {
	URLs       []string
	Browser    string
	Print      string //  "dialog"(인쇄 창) · "silent"(기본 프린터로 바로)
	Fullscreen bool
	Port       int
	Width      int
	Height     int
	Probe      int
	Shortcut   bool //  바탕화면·시작 메뉴 아이콘을 만들까(기본 켜짐)
	Autostart  bool //  윈도우가 켜지면 저절로 띄울까(기본 꺼짐)
}

var conf = Conf{Print: "dialog", Port: 18830, Width: 1280, Height: 900, Probe: 3, Shortcut: true}

const iniName = "hanil-label.ini"

func main() {
	exeDir, exePath := ".", ""
	if p, err := os.Executable(); err == nil {
		if r, err2 := filepath.EvalSymlinks(p); err2 == nil {
			p = r
		}
		exeDir, exePath = filepath.Dir(p), p
	}
	openLog()
	//  📦 어디서 누르든 한 자리(%LOCALAPPDATA%\HanilLabel\app)의 판으로 모은다 — 새 판이면 설치까지
	if selfInstall(exePath) {
		return
	}
	conf.URLs = append([]string{}, defaultURLs...)
	ini := filepath.Join(exeDir, iniName)
	if _, err := os.Stat(ini); os.IsNotExist(err) {
		_ = os.WriteFile(ini, []byte(strings.ReplaceAll(SAMPLE_INI, "\n", "\r\n")), 0o644)
	}
	readIni(ini)
	readArgs()

	//  🖥 바탕화면 아이콘 — 창을 띄우는 것과 따로 돈다(늦어도 창이 먼저 뜬다)
	iconDone := make(chan struct{})
	go func() {
		defer close(iconDone)
		if conf.Shortcut && exePath != "" {
			ensureShortcuts(exePath, conf.Autostart)
		}
	}()
	defer func() {
		select {
		case <-iconDone:
		case <-time.After(15 * time.Second):
		}
	}()

	logf("시작 v%s · %s · %s", VERSION, exePath, runtime.GOOS)

	//  ⚠ 이미 켜져 있으면(관문이 살아 있으면) 창만 하나 더 띄우고 끝낸다.
	//    ⚠ 단 **예전 판**이 떠 있으면 그것을 내리고 새 판으로 연다(안 그러면 고친 것이 안 먹는다).
	killOld := false
	if v, ok := runningVersion(conf.Port); ok {
		if v == VERSION {
			logf("이미 켜져 있음 — 창만 띄움")
			if err := openApp(local(conf.Port) + startPath); err != nil {
				msgBox("한일 라벨 발행기", "Edge 나 Chrome 을 찾지 못했습니다.\n"+err.Error())
			}
			return
		}
		logf("예전 판(%s)이 떠 있음 — 내리고 새로 연다", v)
		killOld = true
	}
	//  🧹 빈 창의 원인들을 치운다 — 남은 Edge, 예전 판, 창 자리 기억(전체 화면으로 굳은 것)
	logf("치우기: %s", cleanupStale(profileDir(), os.Getpid(), killOld))
	fixPrefs()
	for i := 0; i < 20 && killOld; i++ {
		if _, ok := runningVersion(conf.Port); !ok {
			break
		}
		time.Sleep(250 * time.Millisecond)
	}

	ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(conf.Port))
	if err != nil {
		msgBox("한일 라벨 발행기", "이 PC 의 "+strconv.Itoa(conf.Port)+" 번 문을 다른 프로그램이 쓰고 있습니다.\n"+
			iniName+" 의 PORT 를 다른 숫자로 바꿔 주세요.")
		return
	}
	gw := newGateway()
	gw.pickUpstream()
	gw.mu.Lock()
	logf("포털 주소: %v", gw.tried)
	gw.mu.Unlock()
	go func() { _ = (&http.Server{Handler: gw}).Serve(ln) }()

	cmd, err := launch(local(conf.Port) + startPath)
	if err != nil {
		logf("브라우저 못 띄움: %v", err)
		msgBox("한일 라벨 발행기", "Edge 나 Chrome 을 찾지 못했습니다.\n"+
			"Microsoft Edge 또는 Google Chrome 을 설치한 뒤 다시 실행해 주세요.")
		return
	}
	//  ⭐ 창이 닫히면 관문도 닫는다(이 PC 에 쓸데없이 남지 않게)
	started := time.Now()
	_ = cmd.Wait()
	logf("브라우저 끝남 (%s)", time.Since(started).Round(time.Second))
	if time.Since(started) < 5*time.Second {
		//  ⚠ 브라우저가 곧바로 끝났다 = 이미 떠 있던 같은 자리(프로필)의 창에 일을 넘긴 것이다.
		//    그 창은 여전히 이 관문을 쓴다 → 창을 쓰는 동안(마지막 요청 뒤 10분) 더 버틴다.
		for time.Since(gw.lastSeen()) < 10*time.Minute {
			time.Sleep(30 * time.Second)
		}
	}
}

func local(port int) string { return "http://127.0.0.1:" + strconv.Itoa(port) }

// 떠 있는 관문의 판 번호("hanil-label 1.2.2" 의 뒤)
func runningVersion(port int) (string, bool) {
	cl := &http.Client{Timeout: 800 * time.Millisecond}
	r, err := cl.Get(local(port) + pingPath)
	if err != nil {
		return "", false
	}
	defer r.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(r.Body, 64))
	s := string(b)
	if !strings.HasPrefix(s, "hanil-label") {
		return "", false
	}
	return strings.TrimSpace(strings.TrimPrefix(s, "hanil-label")), true
}

// ── 창 자리 기억 지우기 ─────────────────────────────────────
//
//	⚠⚠ 예전 판은 포털 라벨 화면을 창 전체로 열었고, 그 화면은 처음 누를 때 **전체 화면**을 켠다.
//	  Edge 는 앱 창의 자리·크기를 기억해 두었다가 다음에 그대로 여는데, 전체 화면으로 굳은 자리를
//	  되살리면 **제목줄 없는 빈 창**이 뜬다. 켤 때마다 그 기억을 지운다(창은 늘 최대화로 열린다).
func fixPrefs() {
	p := filepath.Join(profileDir(), "Default", "Preferences")
	b, err := os.ReadFile(p)
	if err != nil {
		return
	}
	var m map[string]any
	if json.Unmarshal(b, &m) != nil {
		return
	}
	br, _ := m["browser"].(map[string]any)
	if br == nil {
		return
	}
	changed := false
	for _, k := range []string{"app_window_placement", "window_placement"} {
		if _, ok := br[k]; ok {
			delete(br, k)
			changed = true
		}
	}
	if !changed {
		return
	}
	if nb, err := json.Marshal(m); err == nil {
		if os.WriteFile(p, nb, 0o644) == nil {
			logf("창 자리 기억을 지웠습니다")
		}
	}
}

// ── 기록 ────────────────────────────────────────────────────
//
//	%LOCALAPPDATA%\HanilLabel\hanil-label.log — 현장에서 «안 돼요» 할 때 이 파일을 받아 본다.
var logFile *os.File
var logMu sync.Mutex

func openLog() {
	_ = os.MkdirAll(profileDir(), 0o755)
	p := filepath.Join(profileDir(), "hanil-label.log")
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
	lanWait := time.Duration(sec) * time.Second
	if isLAN(u) && lanWait > time.Second {
		lanWait = time.Second
	}
	if h := hostPort(u); h != "" {
		c, err := net.DialTimeout("tcp", h, lanWait)
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
	r, err := cl.Get(u + "/")
	if err != nil {
		return false, "답이 없습니다"
	}
	defer r.Body.Close()
	io.Copy(io.Discard, io.LimitReader(r.Body, 4096))
	if r.StatusCode >= 500 {
		return false, "서버가 오류를 냅니다 (" + strconv.Itoa(r.StatusCode) + ")"
	}
	return true, "좋습니다 (" + strconv.Itoa(r.StatusCode) + ")"
}

func hostPort(u string) string {
	s := u
	https := strings.HasPrefix(s, "https://")
	s = strings.TrimPrefix(strings.TrimPrefix(s, "http://"), "https://")
	if i := strings.IndexAny(s, "/?"); i >= 0 {
		s = s[:i]
	}
	if s == "" {
		return ""
	}
	if !strings.Contains(s, ":") {
		if https {
			return s + ":443"
		}
		return s + ":80"
	}
	return s
}

func isLAN(u string) bool {
	h := hostPort(u)
	if i := strings.LastIndex(h, ":"); i > 0 {
		h = h[:i]
	}
	if strings.HasPrefix(h, "192.168.") || strings.HasPrefix(h, "10.") || strings.HasPrefix(h, "127.") {
		return true
	}
	if strings.HasPrefix(h, "172.") {
		if p := strings.Split(h, "."); len(p) > 1 {
			if n, err := strconv.Atoi(p[1]); err == nil && n >= 16 && n <= 31 {
				return true
			}
		}
	}
	return false
}

// ── 브라우저 띄우기 ────────────────────────────────────────
func browserArgs(url string) []string {
	args := []string{
		"--app=" + url,
		//  ⚠ 이 프로그램만의 자리 — 직원이 쓰는 Edge 와 로그인·설정이 섞이지 않는다
		"--user-data-dir=" + profileDir(),
		"--no-first-run", "--no-default-browser-check",
		"--disable-session-crashed-bubble", "--overscroll-history-navigation=0",
		"--disable-features=Translate",
	}
	if conf.Fullscreen {
		args = append(args, "--kiosk", "--start-fullscreen", "--disable-pinch")
	} else {
		args = append(args, "--window-size="+strconv.Itoa(conf.Width)+","+strconv.Itoa(conf.Height),
			"--start-maximized")
	}
	//  🖨 «기본 프린터로 바로» — 인쇄 창 없이 곧바로 나간다(바코드 프린터를 기본으로 두는 자리)
	if conf.Print == "silent" {
		args = append(args, "--kiosk-printing")
	}
	return args
}

func launch(url string) (*exec.Cmd, error) {
	exe := conf.Browser
	if exe == "" {
		exe = findBrowser()
	}
	if exe == "" {
		return nil, fmt.Errorf("브라우저를 못 찾았습니다")
	}
	c := exec.Command(exe, browserArgs(url)...)
	hideWindow(c)
	if err := c.Start(); err != nil {
		return nil, err
	}
	return c, nil
}

func openApp(url string) error {
	c, err := launch(url)
	if err != nil {
		return err
	}
	go c.Wait()
	time.Sleep(1500 * time.Millisecond)
	return nil
}

func profileDir() string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		base = os.TempDir()
	}
	return filepath.Join(base, "HanilLabel")
}

func findBrowser() string {
	if runtime.GOOS == "windows" {
		cands := []string{
			`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`,
			`C:\Program Files\Microsoft\Edge\Application\msedge.exe`,
			`C:\Program Files\Google\Chrome\Application\chrome.exe`,
			`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`,
		}
		if la := os.Getenv("LOCALAPPDATA"); la != "" {
			cands = append(cands, filepath.Join(la, `Google\Chrome\Application\chrome.exe`))
		}
		for _, p := range cands {
			if fi, err := os.Stat(p); err == nil && !fi.IsDir() {
				return p
			}
		}
		for _, n := range []string{"msedge.exe", "chrome.exe"} {
			if p, err := exec.LookPath(n); err == nil {
				return p
			}
		}
		return ""
	}
	//  여기(리눅스)에서는 시험용으로 크로미움을 쓴다
	for _, n := range []string{"chromium", "google-chrome", "chromium-browser"} {
		if p, err := exec.LookPath(n); err == nil {
			return p
		}
	}
	if fi, err := os.Stat("/opt/pw-browsers/chromium"); err == nil && !fi.IsDir() {
		return "/opt/pw-browsers/chromium"
	}
	return ""
}

// ── 설정 ───────────────────────────────────────────────────
func readIni(p string) {
	b, err := os.ReadFile(p)
	if err != nil {
		return
	}
	s := strings.TrimPrefix(string(b), "\ufeff") //  메모장이 붙이는 BOM
	first := true
	for _, ln := range strings.Split(s, "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" || strings.HasPrefix(ln, "#") || strings.HasPrefix(ln, ";") {
			continue
		}
		i := strings.Index(ln, "=")
		if i < 0 {
			continue
		}
		k := strings.ToUpper(strings.TrimSpace(ln[:i]))
		v := strings.TrimSpace(ln[i+1:])
		if k == "URL" || k == "URLS" {
			//  ⚠ 적어 주셨으면 **그것이 먼저**다(기본 주소를 덮는다)
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
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "y", "yes", "on", "true", "예":
		return true
	}
	return false
}

func setConf(k, v string) {
	switch k {
	case "BROWSER":
		conf.Browser = v
	case "PRINT":
		switch strings.ToLower(v) {
		case "silent", "바로":
			conf.Print = "silent"
		default:
			conf.Print = "dialog"
		}
	case "SHORTCUT", "DESKTOP_ICON":
		conf.Shortcut = yes(v)
	case "AUTOSTART":
		conf.Autostart = yes(v)
	case "FULLSCREEN", "KIOSK":
		conf.Fullscreen = yes(v)
	case "PORT":
		if n, err := strconv.Atoi(v); err == nil && n > 1024 && n < 65536 {
			conf.Port = n
		}
	case "WIDTH":
		if n, err := strconv.Atoi(v); err == nil && n > 300 {
			conf.Width = n
		}
	case "HEIGHT":
		if n, err := strconv.Atoi(v); err == nil && n > 300 {
			conf.Height = n
		}
	case "PROBE", "TIMEOUT":
		if n, err := strconv.Atoi(v); err == nil && n > 0 && n < 60 {
			conf.Probe = n
		}
	}
}

// 처음 실행하면 이 프로그램 옆에 만들어 두는 설정 파일
const SAMPLE_INI = `# 한일 라벨 발행기 설정
# 고친 뒤에는 프로그램을 껐다 켜 주세요.

# 포털 주소 — 앞의 것부터 붙어 봅니다(사내 주소 먼저, 안 되면 도메인).
URL=http://192.168.1.30:8820, https://work.hanil-steel.com

# 인쇄 방식
#   dialog = 인쇄 창이 뜹니다. 바코드 프린터 / 레이저 프린터를 그때그때 고릅니다.
#   silent = 인쇄 창 없이 이 PC 의 «기본 프린터»로 바로 나갑니다.
#            (라벨 프린터를 기본 프린터로 지정해 두세요)
PRINT=dialog

# 전체 화면(키오스크) — 1 이면 화면 전체를 씁니다. 끄기: Alt+F4
FULLSCREEN=0

# 바탕화면·시작 메뉴 아이콘 — 1 이면 켤 때마다 확인해 없으면 만듭니다
SHORTCUT=1

# 윈도우가 켜지면 저절로 띄우기 — 1 이면 켭니다
AUTOSTART=0
`
