//go:build windows

// 📕 한일 PDF 리더 — 윈도우 프로그램(hanil-pdf.exe)
//
//	브라우저용 리더(pdfreader/src)를 독자 창(WebView2)에 띄우고, 윈도우에서만 되는 것을 붙인다.
//	  · PDF 를 두 번 누르면 이 프로그램으로(「연결 프로그램」 등록 — 기본 앱 지정은 윈도우 설정에서 사용자가)
//	  · 저장하면 그 파일에 바로(대화상자 없이) · 다른 이름으로는 윈도우 저장 창
//	  · 탐색기 미리 보기 창·큰 아이콘 그림(hanil-pdf-preview.dll + pdfium.dll)
//	  · 이미 떠 있으면 새 PDF 는 그 창의 새 탭으로
//	설치: 어디서 누르든 %LOCALAPPDATA%\Programs\HanilPDF 에 스스로 깔린다(관리자 권한 없이 · 사용자 단위).
//	지우기: 설정 → 앱 → 「한일 PDF 리더」 제거(= hanil-pdf.exe --uninstall)
package main

import (
	_ "embed"
	"bytes"
	"crypto/rand"
	b64 "encoding/base64"
	"encoding/hex"
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
	"syscall"
	"time"
	"unsafe"

	webview "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/registry"
)

const (
	VERSION = "1.1.0"
	PORT    = 47321 //  ⚠ 늘 같은 자리 — 리더의 설정·최근 파일(브라우저 저장소)이 주소마다 따로라서
	APPNAME = "한일 PDF 리더"
	MAKER   = "한일특장(주)"
	PROGID  = "HanilPDF.Document"
)

//go:embed assets/reader.html
var readerHTML []byte

//go:embed assets/hanil-pdf-preview.dll
var previewDLL []byte

//go:embed assets/pdfium.dll
var pdfiumDLL []byte

//go:embed host.js
var hostJS string

var (
	user32     = windows.NewLazySystemDLL("user32.dll")
	comdlg32   = windows.NewLazySystemDLL("comdlg32.dll")
	shell32    = windows.NewLazySystemDLL("shell32.dll")
	ole32      = windows.NewLazySystemDLL("ole32.dll")
	pMsgBox    = user32.NewProc("MessageBoxW")
	pShowWin   = user32.NewProc("ShowWindow")
	pSetFg     = user32.NewProc("SetForegroundWindow")
	pIsIconic  = user32.NewProc("IsIconic")
	pSetWLP    = user32.NewProc("SetWindowLongPtrW")
	pCallWP    = user32.NewProc("CallWindowProcW")
	pPostMsg   = user32.NewProc("PostMessageW")
	pGetOFN    = comdlg32.NewProc("GetOpenFileNameW")
	pGetSFN    = comdlg32.NewProc("GetSaveFileNameW")
	pBrowse    = shell32.NewProc("SHBrowseForFolderW")
	pPathIDL   = shell32.NewProc("SHGetPathFromIDListW")
	pChangeNfy = shell32.NewProc("SHChangeNotify")
	pTaskFree  = ole32.NewProc("CoTaskMemFree")
)

func baseDir() string    { return filepath.Join(os.Getenv("LOCALAPPDATA"), "HanilPDF") }
func installDir() string { return filepath.Join(os.Getenv("LOCALAPPDATA"), "Programs", "HanilPDF") }
func appExe() string     { return filepath.Join(installDir(), "hanil-pdf.exe") }
func engineDir() string  { return filepath.Join(installDir(), "engine-"+VERSION) }

var logMu sync.Mutex

func logf(f string, a ...interface{}) {
	logMu.Lock()
	defer logMu.Unlock()
	_ = os.MkdirAll(baseDir(), 0o755)
	p := filepath.Join(baseDir(), "log.txt")
	if st, err := os.Stat(p); err == nil && st.Size() > 1<<20 {
		_ = os.Rename(p, p+".old")
	}
	fh, err := os.OpenFile(p, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return
	}
	defer fh.Close()
	fmt.Fprintf(fh, "%s %s\r\n", time.Now().Format("2006-01-02 15:04:05"), fmt.Sprintf(f, a...))
}

func u16(s string) *uint16 { p, _ := windows.UTF16PtrFromString(s); return p }
func msgBox(title, text string, flags uintptr) int {
	r, _, _ := pMsgBox.Call(0, uintptr(unsafe.Pointer(u16(text))), uintptr(unsafe.Pointer(u16(title))), flags)
	return int(r)
}
func hideWindow(c *exec.Cmd) {
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
}

// ───────────────────────── 시작 ─────────────────────────
func main() {
	exe, _ := os.Executable()
	if r, err := filepath.EvalSymlinks(exe); err == nil {
		exe = r
	}
	var files []string
	flags := map[string]bool{}
	for _, a := range os.Args[1:] {
		if strings.HasPrefix(a, "--") {
			flags[a] = true
			continue
		}
		if p, err := filepath.Abs(a); err == nil {
			files = append(files, p)
		}
	}
	logf("시작 v%s %s 파일 %d개 %v", VERSION, exe, len(files), flags)
	if flags["--uninstall"] {
		uninstall()
		return
	}
	//  📦 설치 자리가 아니면 스스로 깔고 그것을 띄운다(이미 깔린 판이 더 새것이면 그것을)
	if !strings.EqualFold(filepath.Clean(exe), filepath.Clean(appExe())) && !flags["--portable"] {
		if installed := installedVersion(); installed == "" || newer(VERSION, installed) || flags["--register"] {
			if err := install(exe); err != nil {
				logf("설치 실패: %v", err)
				msgBox(APPNAME, "설치하지 못했습니다:\n"+err.Error()+"\n\n설치 없이 이 자리에서 띄웁니다.", 0x30)
			} else {
				args := append([]string{"--installed"}, files...)
				if startDetached(appExe(), args...) {
					return
				}
			}
		} else if startDetached(appExe(), files...) {
			return
		}
	} else if flags["--register"] {
		_ = register(exe)
	}
	token := loadToken()
	//  🪟 이미 떠 있으면 그 창에 파일을 넘기고 끝
	if forward(token, files) {
		logf("떠 있는 창에 넘김")
		return
	}
	ensureEngine(false)
	run(token, files, flags["--installed"])
}

func startDetached(exe string, args ...string) bool {
	c := exec.Command(exe, args...)
	c.Dir = filepath.Dir(exe)
	if err := c.Start(); err != nil {
		logf("띄우기 실패 %s: %v", exe, err)
		return false
	}
	return true
}

func loadToken() string {
	p := filepath.Join(baseDir(), "token.txt")
	if b, err := os.ReadFile(p); err == nil && len(bytes.TrimSpace(b)) >= 32 {
		return strings.TrimSpace(string(b))
	}
	r := make([]byte, 24)
	_, _ = rand.Read(r)
	t := hex.EncodeToString(r)
	_ = os.MkdirAll(baseDir(), 0o755)
	_ = os.WriteFile(p, []byte(t), 0o600)
	return t
}

func forward(token string, files []string) bool {
	b, _ := json.Marshal(files)
	cl := http.Client{Timeout: 3 * time.Second}
	r, err := cl.Post("http://127.0.0.1:"+strconv.Itoa(PORT)+"/open?t="+token, "application/json", bytes.NewReader(b))
	if err != nil {
		return false
	}
	defer r.Body.Close()
	return r.StatusCode == 200
}

// ───────────────────────── 창 ─────────────────────────
var (
	wv         webview.WebView
	wvMu       sync.Mutex
	pending    []string
	allowClose bool
	oldProc    uintptr
	firstRun   bool
)

func dispatchOpen(files []string) {
	wvMu.Lock()
	w := wv
	if w == nil {
		pending = append(pending, files...)
		wvMu.Unlock()
		return
	}
	wvMu.Unlock()
	w.Dispatch(func() {
		h := uintptr(w.Window())
		if r, _, _ := pIsIconic.Call(h); r != 0 {
			pShowWin.Call(h, 9)
		}
		pSetFg.Call(h)
		for _, f := range files {
			b, _ := json.Marshal(f)
			w.Eval("window.HANIL_HOST && window.HANIL_HOST.openPath(" + string(b) + ")")
		}
	})
}

func run(token string, files []string, installed bool) {
	pending = files
	firstRun = installed
	ln, err := net.Listen("tcp", "127.0.0.1:"+strconv.Itoa(PORT))
	port := PORT
	if err != nil {
		//  자리를 다른 프로그램이 쓰면 아무 자리나(이때는 설정·최근 파일이 이번 실행에만 남는다)
		ln, err = net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			msgBox(APPNAME, "시작하지 못했습니다: "+err.Error(), 0x10)
			return
		}
		port = ln.Addr().(*net.TCPAddr).Port
	}
	go func() { _ = http.Serve(ln, server(token, port)) }()

	runtime.LockOSThread()
	w := webview.NewWithOptions(webview.WebViewOptions{
		DataPath:  filepath.Join(baseDir(), "WebView2"),
		AutoFocus: true,
		WindowOptions: webview.WindowOptions{
			Title: APPNAME, Width: 1400, Height: 900, IconId: 1, Center: true,
		},
	})
	if w == nil {
		//  WebView2 런타임이 없으면(오래된 윈도우 10) 기본 브라우저로
		p := filepath.Join(baseDir(), "hanil-pdf-reader.html")
		_ = os.WriteFile(p, readerHTML, 0o644)
		msgBox(APPNAME, "이 PC 에 Microsoft Edge WebView2 런타임이 없어 브라우저로 엽니다.\n(https://go.microsoft.com/fwlink/p/?LinkId=2124703 에서 받아 깔면 독자 창으로 열립니다)", 0x40)
		_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", p).Start()
		return
	}
	defer w.Destroy()
	bind(w)
	wvMu.Lock()
	wv = w
	wvMu.Unlock()
	h := uintptr(w.Window())
	pShowWin.Call(h, 3) //  크게
	//  ⚠ X 를 누르면 바로 닫지 않고 리더에게 묻는다(저장 안 한 문서가 있으면 확인)
	oldProc, _, _ = pSetWLP.Call(h, ^uintptr(3), windows.NewCallback(func(hwnd, msg, wp, lp uintptr) uintptr {
		const wmClose = 0x0010
		if msg == wmClose && !allowClose {
			w.Eval("(window.__hanilCanClose ? window.__hanilCanClose() : Promise.resolve(true)).then(function(ok){ if (ok) window.hostReallyClose(); })")
			return 0
		}
		r, _, _ := pCallWP.Call(oldProc, hwnd, msg, wp, lp)
		return r
	}))
	w.Navigate("http://127.0.0.1:" + strconv.Itoa(port) + "/?t=" + token)
	logf("창을 띄움 (자리 %d)", port)
	w.Run()
	logf("끝")
}

func bind(w webview.WebView) {
	_ = w.Bind("hostPending", func() []string {
		wvMu.Lock()
		defer wvMu.Unlock()
		p := pending
		pending = nil
		return p
	})
	_ = w.Bind("hostFirstRun", func() bool { r := firstRun; firstRun = false; return r })
	_ = w.Bind("hostOpenDialog", func() []string { return openDialog(uintptr(w.Window())) })
	_ = w.Bind("hostSaveDialog", func(name, cur string) string { return saveDialog(uintptr(w.Window()), name, cur) })
	_ = w.Bind("hostPickFolder", func() string { return pickFolder(uintptr(w.Window())) })
	_ = w.Bind("hostListDir", func(dir string) []map[string]interface{} { return listDir(dir) })
	_ = w.Bind("hostAssociate", func() string { return associate() })
	_ = w.Bind("hostPreview", func() string {
		if err := ensureEngine(true); err != nil {
			return "탐색기 미리 보기를 켜지 못했습니다: " + err.Error()
		}
		return "탐색기 미리 보기를 켰습니다. 탐색기를 다시 열면 PDF 미리 보기 창(Alt+P)·큰 아이콘에 보입니다."
	})
	_ = w.Bind("hostTitle", func(t string) { w.SetTitle(t) })
	_ = w.Bind("hostReallyClose", func() {
		allowClose = true
		pPostMsg.Call(uintptr(w.Window()), 0x0010, 0, 0)
	})
	_ = w.Bind("hostExit", func() {
		w.Eval("(window.__hanilCanClose ? window.__hanilCanClose() : Promise.resolve(true)).then(function(ok){ if (ok) window.hostReallyClose(); })")
	})
	_ = w.Bind("hostReveal", func(p string) { _ = exec.Command("explorer.exe", "/select,", p).Start() })
}

// ───────────────────────── 작은 웹 서버(이 PC 안에서만) ─────────────────────────
//
//	리더 화면 · 파일 읽기(/file) · 저장(/save) · 두 번째 실행이 넘긴 파일(/open).
//	⚠ 127.0.0.1 에만 열고, 실행마다 같은 비밀 표(token)를 요구한다 — 다른 웹사이트가 내 PC 파일을 못 읽게.
func server(token string, port int) http.Handler {
	host := "127.0.0.1:" + strconv.Itoa(port)
	mux := http.NewServeMux()
	ok := func(w http.ResponseWriter, r *http.Request) bool {
		if r.Host != host || r.URL.Query().Get("t") != token {
			http.Error(w, "forbidden", 403)
			return false
		}
		return true
	}
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" || !ok(w, r) {
			if r.URL.Path != "/" {
				http.NotFound(w, r)
			}
			return
		}
		js := strings.ReplaceAll(hostJS, "__TOKEN__", token)
		page := bytes.Replace(readerHTML, []byte("<head>"), []byte("<head><script>"+js+"</script>"), 1)
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(page)
	})
	mux.HandleFunc("/file", func(w http.ResponseWriter, r *http.Request) {
		if !ok(w, r) {
			return
		}
		p := r.URL.Query().Get("path")
		f, err := os.Open(p)
		if err != nil {
			http.Error(w, "열 수 없음: "+err.Error(), 404)
			return
		}
		defer f.Close()
		st, _ := f.Stat()
		w.Header().Set("Content-Type", "application/pdf")
		http.ServeContent(w, r, filepath.Base(p), st.ModTime(), f)
	})
	mux.HandleFunc("/save", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || !ok(w, r) {
			return
		}
		p := r.URL.Query().Get("path")
		if p == "" || !strings.EqualFold(filepath.Ext(p), ".pdf") {
			http.Error(w, "PDF 로만 저장합니다", 400)
			return
		}
		if err := writeAtomic(p, r.Body); err != nil {
			logf("저장 실패 %s: %v", p, err)
			http.Error(w, "저장하지 못했습니다: "+err.Error()+"\n(다른 프로그램이 그 파일을 열고 있으면 닫고 다시 하세요)", 500)
			return
		}
		logf("저장 %s", p)
		_, _ = w.Write([]byte("ok"))
	})
	mux.HandleFunc("/open", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Query().Get("t") != token {
			http.Error(w, "forbidden", 403)
			return
		}
		var files []string
		_ = json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&files)
		dispatchOpen(files)
		_, _ = w.Write([]byte("ok"))
	})
	return mux
}

// ⚠ 쓰다가 끊겨도 원본이 반쪽으로 남지 않게 — 옆에 쓰고 바꿔치기
func writeAtomic(p string, body io.Reader) error {
	tmp := p + ".hanil-saving"
	f, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err = io.Copy(f, io.LimitReader(body, 4<<30)); err == nil {
		err = f.Sync()
	}
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		_ = os.Remove(tmp)
		return err
	}
	for i := 0; i < 10; i++ {
		if err = os.Rename(tmp, p); err == nil {
			return nil
		}
		time.Sleep(200 * time.Millisecond)
	}
	_ = os.Remove(tmp)
	return err
}

func listDir(dir string) []map[string]interface{} {
	out := []map[string]interface{}{}
	ents, err := os.ReadDir(dir)
	if err != nil {
		return out
	}
	for _, e := range ents {
		n := e.Name()
		if strings.HasPrefix(n, ".") || strings.HasPrefix(n, "$") {
			continue
		}
		if e.IsDir() || strings.EqualFold(filepath.Ext(n), ".pdf") {
			out = append(out, map[string]interface{}{"name": n, "path": filepath.Join(dir, n), "dir": e.IsDir()})
		}
	}
	return out
}

// ───────────────────────── 윈도우 대화상자 ─────────────────────────
type openFileName struct {
	lStructSize       uint32
	hwndOwner         uintptr
	hInstance         uintptr
	lpstrFilter       *uint16
	lpstrCustomFilter *uint16
	nMaxCustFilter    uint32
	nFilterIndex      uint32
	lpstrFile         *uint16
	nMaxFile          uint32
	lpstrFileTitle    *uint16
	nMaxFileTitle     uint32
	lpstrInitialDir   *uint16
	lpstrTitle        *uint16
	flags             uint32
	nFileOffset       uint16
	nFileExtension    uint16
	lpstrDefExt       *uint16
	lCustData         uintptr
	lpfnHook          uintptr
	lpTemplateName    *uint16
	pvReserved        uintptr
	dwReserved        uint32
	flagsEx           uint32
}

func filter() []uint16 {
	var f []uint16
	for _, s := range []string{"PDF 문서 (*.pdf)", "*.pdf", "모든 파일 (*.*)", "*.*"} {
		f = append(f, windows.StringToUTF16(s)...)
	}
	return append(f, 0)
}

func openDialog(owner uintptr) []string {
	buf := make([]uint16, 65536)
	flt := filter()
	o := openFileName{hwndOwner: owner, lpstrFilter: &flt[0], nFilterIndex: 1, lpstrFile: &buf[0], nMaxFile: uint32(len(buf)),
		lpstrTitle: u16("PDF 열기"), flags: 0x80000 | 0x1000 | 0x800 | 0x200 | 0x8}
	o.lStructSize = uint32(unsafe.Sizeof(o))
	if r, _, _ := pGetOFN.Call(uintptr(unsafe.Pointer(&o))); r == 0 {
		return nil
	}
	//  여러 개면 「폴더\0파일1\0파일2\0\0」, 하나면 「전체 경로\0\0」
	var parts []string
	start := 0
	for i := 0; i < len(buf); i++ {
		if buf[i] == 0 {
			if i == start {
				break
			}
			parts = append(parts, windows.UTF16ToString(buf[start:i]))
			start = i + 1
		}
	}
	if len(parts) <= 1 {
		return parts
	}
	var out []string
	for _, n := range parts[1:] {
		out = append(out, filepath.Join(parts[0], n))
	}
	return out
}

func saveDialog(owner uintptr, name, cur string) string {
	buf := make([]uint16, 4096)
	copy(buf, windows.StringToUTF16(name))
	flt := filter()
	o := openFileName{hwndOwner: owner, lpstrFilter: &flt[0], nFilterIndex: 1, lpstrFile: &buf[0], nMaxFile: uint32(len(buf)),
		lpstrTitle: u16("다른 이름으로 저장"), lpstrDefExt: u16("pdf"), flags: 0x80000 | 0x2 | 0x800 | 0x8}
	if cur != "" && filepath.IsAbs(cur) {
		o.lpstrInitialDir = u16(filepath.Dir(cur))
	}
	o.lStructSize = uint32(unsafe.Sizeof(o))
	if r, _, _ := pGetSFN.Call(uintptr(unsafe.Pointer(&o))); r == 0 {
		return ""
	}
	return windows.UTF16ToString(buf)
}

type browseInfo struct {
	hwndOwner      uintptr
	pidlRoot       uintptr
	pszDisplayName *uint16
	lpszTitle      *uint16
	ulFlags        uint32
	lpfn           uintptr
	lParam         uintptr
	iImage         int32
}

func pickFolder(owner uintptr) string {
	name := make([]uint16, 260)
	bi := browseInfo{hwndOwner: owner, pszDisplayName: &name[0], lpszTitle: u16("자주 여는 폴더를 고르세요"), ulFlags: 0x1 | 0x40}
	pidl, _, _ := pBrowse.Call(uintptr(unsafe.Pointer(&bi)))
	if pidl == 0 {
		return ""
	}
	defer pTaskFree.Call(pidl)
	path := make([]uint16, 1024)
	if r, _, _ := pPathIDL.Call(pidl, uintptr(unsafe.Pointer(&path[0]))); r == 0 {
		return ""
	}
	return windows.UTF16ToString(path)
}

// ───────────────────────── 설치 · 등록 ─────────────────────────
func installedVersion() string {
	k, err := registry.OpenKey(registry.CURRENT_USER, `Software\HanilPDF`, registry.QUERY_VALUE)
	if err != nil {
		return ""
	}
	defer k.Close()
	v, _, _ := k.GetStringValue("Version")
	if _, err := os.Stat(appExe()); err != nil {
		return ""
	}
	return v
}

func newer(a, b string) bool {
	pa, pb := strings.Split(a, "."), strings.Split(b, ".")
	for i := 0; i < len(pa) || i < len(pb); i++ {
		var x, y int
		if i < len(pa) {
			x, _ = strconv.Atoi(pa[i])
		}
		if i < len(pb) {
			y, _ = strconv.Atoi(pb[i])
		}
		if x != y {
			return x > y
		}
	}
	return false
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := dst + ".new"
	out, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err = io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	if err = out.Close(); err != nil {
		return err
	}
	for i := 0; i < 25; i++ {
		_ = os.Remove(dst)
		if err = os.Rename(tmp, dst); err == nil {
			return nil
		}
		time.Sleep(200 * time.Millisecond)
	}
	return err
}

func install(src string) error {
	if err := os.MkdirAll(installDir(), 0o755); err != nil {
		return err
	}
	//  ⚠ 떠 있는 옛 판이 exe 를 잡고 있으면 덮지 못한다 → 내려 달라고 부탁(창이 떠 있으면 그대로 두고 다시 시도)
	if err := copyFile(src, appExe()); err != nil {
		return fmt.Errorf("%v (한일 PDF 리더 창을 모두 닫고 다시 하세요)", err)
	}
	if err := register(appExe()); err != nil {
		return err
	}
	if err := ensureEngine(true); err != nil {
		logf("미리 보기 등록 실패: %v", err)
	}
	ensureShortcuts(appExe())
	logf("설치 끝 v%s", VERSION)
	return nil
}

func setStr(root registry.Key, path, name, val string) error {
	k, _, err := registry.CreateKey(root, path, registry.SET_VALUE)
	if err != nil {
		return err
	}
	defer k.Close()
	return k.SetStringValue(name, val)
}

func register(exe string) error {
	cu := registry.CURRENT_USER
	q := `"` + exe + `"`
	steps := [][3]string{
		{`Software\Classes\` + PROGID, "", "PDF 문서"},
		{`Software\Classes\` + PROGID, "FriendlyTypeName", "PDF 문서 (한일 PDF 리더)"},
		{`Software\Classes\` + PROGID + `\DefaultIcon`, "", q + ",0"},
		{`Software\Classes\` + PROGID + `\shell\open`, "FriendlyAppName", APPNAME},
		{`Software\Classes\` + PROGID + `\shell\open\command`, "", q + ` "%1"`},
		{`Software\Classes\.pdf\OpenWithProgids`, PROGID, ""},
		{`Software\Classes\Applications\hanil-pdf.exe`, "FriendlyAppName", APPNAME},
		{`Software\Classes\Applications\hanil-pdf.exe\SupportedTypes`, ".pdf", ""},
		{`Software\Classes\Applications\hanil-pdf.exe\shell\open\command`, "", q + ` "%1"`},
		{`Software\HanilPDF`, "Version", VERSION},
		{`Software\HanilPDF`, "Path", exe},
		{`Software\HanilPDF\Capabilities`, "ApplicationName", APPNAME},
		{`Software\HanilPDF\Capabilities`, "ApplicationDescription", "PDF 보기·찾기·주석·페이지 구성 — " + MAKER},
		{`Software\HanilPDF\Capabilities`, "ApplicationIcon", q + ",0"},
		{`Software\HanilPDF\Capabilities\FileAssociations`, ".pdf", PROGID},
		{`Software\RegisteredApplications`, "HanilPDF", `Software\HanilPDF\Capabilities`},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "DisplayName", APPNAME},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "DisplayVersion", VERSION},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "Publisher", MAKER},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "DisplayIcon", exe},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "InstallLocation", filepath.Dir(exe)},
		{`Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, "UninstallString", q + " --uninstall"},
	}
	for _, s := range steps {
		if err := setStr(cu, s[0], s[1], s[2]); err != nil {
			return fmt.Errorf("등록 %s: %v", s[0], err)
		}
	}
	if k, _, err := registry.CreateKey(cu, `Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`, registry.SET_VALUE); err == nil {
		_ = k.SetDWordValue("NoModify", 1)
		_ = k.SetDWordValue("NoRepair", 1)
		_ = k.SetDWordValue("EstimatedSize", uint32((len(readerHTML)+len(pdfiumDLL)+len(previewDLL))/1024+12000))
		k.Close()
	}
	pChangeNfy.Call(0x08000000, 0, 0, 0) //  SHCNE_ASSOCCHANGED
	return nil
}

// 미리 보기 확장 — 판마다 따로 폴더(탐색기가 옛 DLL 을 잡고 있어도 새 판을 깔 수 있게)
func ensureEngine(reg bool) error {
	dir := engineDir()
	dll := filepath.Join(dir, "hanil-pdf-preview.dll")
	need := false
	if st, err := os.Stat(dll); err != nil || st.Size() != int64(len(previewDLL)) {
		need = true
	}
	if st, err := os.Stat(filepath.Join(dir, "pdfium.dll")); err != nil || st.Size() != int64(len(pdfiumDLL)) {
		need = true
	}
	if need {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "pdfium.dll"), pdfiumDLL, 0o644); err != nil {
			return err
		}
		if err := os.WriteFile(dll, previewDLL, 0o644); err != nil {
			return err
		}
		reg = true
	}
	if !reg {
		return nil
	}
	c := exec.Command(filepath.Join(os.Getenv("SystemRoot"), "System32", "regsvr32.exe"), "/s", dll)
	hideWindow(c)
	if err := c.Run(); err != nil {
		return fmt.Errorf("regsvr32: %v", err)
	}
	//  옛 판 폴더는 지워 본다(탐색기가 잡고 있으면 다음에)
	if ents, err := os.ReadDir(installDir()); err == nil {
		for _, e := range ents {
			if e.IsDir() && strings.HasPrefix(e.Name(), "engine-") && e.Name() != "engine-"+VERSION {
				_ = os.RemoveAll(filepath.Join(installDir(), e.Name()))
			}
		}
	}
	logf("미리 보기 등록 %s", dll)
	return nil
}

// 기본 앱으로 — 윈도우 10·11 은 프로그램이 마음대로 기본 앱을 못 바꾼다 → 설정 화면을 열어 준다
func associate() string {
	_ = register(appExe())
	uri := "ms-settings:defaultapps?registeredAppUser=HanilPDF"
	if err := exec.Command("explorer.exe", uri).Start(); err != nil {
		return "설정 화면을 열지 못했습니다: " + err.Error()
	}
	return "윈도우 설정이 열립니다. 「.pdf」 옆의 앱을 눌러 「한일 PDF 리더」를 고르세요.\n(윈도우 10 은 「앱별 기본값 선택」 → .pdf)"
}

func q(s string) string { return "'" + strings.ReplaceAll(s, "'", "''") + "'" }

func ensureShortcuts(exe string) {
	ps := `$ErrorActionPreference='SilentlyContinue'
$W=New-Object -ComObject WScript.Shell
$exe=` + q(exe) + `
function Put($folder){
  if(-not $folder){ return }
  $p=Join-Path $folder '한일 PDF 리더.lnk'
  $s=$W.CreateShortcut($p); $s.TargetPath=$exe; $s.WorkingDirectory=(Split-Path $exe)
  $s.IconLocation="$exe,0"; $s.Description='PDF 보기·찾기·고치기 — 한일특장(주)'; $s.Save()
}
Put ([Environment]::GetFolderPath('Desktop'))
Put ([Environment]::GetFolderPath('Programs'))
`
	runPS(ps)
}

func runPS(ps string) {
	u := windows.StringToUTF16(ps)
	b := make([]byte, (len(u)-1)*2)
	for i, r := range u[:len(u)-1] {
		b[i*2], b[i*2+1] = byte(r), byte(r>>8)
	}
	c := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", b64.StdEncoding.EncodeToString(b))
	hideWindow(c)
	_ = c.Run()
}

func uninstall() {
	if msgBox(APPNAME, "한일 PDF 리더를 지울까요?\n(PDF 파일은 그대로 남습니다)", 0x24) != 6 {
		return
	}
	dll := filepath.Join(engineDir(), "hanil-pdf-preview.dll")
	c := exec.Command(filepath.Join(os.Getenv("SystemRoot"), "System32", "regsvr32.exe"), "/u", "/s", dll)
	hideWindow(c)
	_ = c.Run()
	cu := registry.CURRENT_USER
	for _, k := range []string{`Software\Classes\` + PROGID, `Software\Classes\Applications\hanil-pdf.exe`, `Software\HanilPDF`, `Software\Microsoft\Windows\CurrentVersion\Uninstall\HanilPDF`} {
		deleteTree(cu, k)
	}
	if k, err := registry.OpenKey(cu, `Software\Classes\.pdf\OpenWithProgids`, registry.SET_VALUE); err == nil {
		_ = k.DeleteValue(PROGID)
		k.Close()
	}
	if k, err := registry.OpenKey(cu, `Software\RegisteredApplications`, registry.SET_VALUE); err == nil {
		_ = k.DeleteValue("HanilPDF")
		k.Close()
	}
	pChangeNfy.Call(0x08000000, 0, 0, 0)
	runPS(`$ErrorActionPreference='SilentlyContinue'
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) '한일 PDF 리더.lnk')
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) '한일 PDF 리더.lnk')`)
	//  ⚠ 지금 도는 exe 는 스스로 못 지운다 → 잠시 뒤 지우는 명령을 남긴다
	c = exec.Command("cmd.exe", "/c", "ping -n 3 127.0.0.1 >nul & rmdir /s /q \""+installDir()+"\"")
	hideWindow(c)
	_ = c.Start()
	msgBox(APPNAME, "지웠습니다. (설정·최근 파일은 "+baseDir()+" 에 남아 있습니다 — 필요 없으면 지우세요)", 0x40)
}

func deleteTree(root registry.Key, path string) {
	k, err := registry.OpenKey(root, path, registry.ENUMERATE_SUB_KEYS)
	if err == nil {
		names, _ := k.ReadSubKeyNames(-1)
		k.Close()
		for _, n := range names {
			deleteTree(root, path+`\`+n)
		}
	}
	_ = registry.DeleteKey(root, path)
}

