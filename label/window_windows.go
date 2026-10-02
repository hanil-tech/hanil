//go:build windows

package main

// ── 독자 창(WebView2) ───────────────────────────────────────
//
//	사용자 「익스플로러(브라우저)를 이용한 화면이 아닌 독자적인 화면으로」
//	⭐ Edge 창을 빌려 쓰지 않고 **이 프로그램이 제 창**을 띄운다(제목·아이콘·작업 표시줄 모두 «한일 라벨 발행»).
//	  창 안의 그림은 윈도우에 들어 있는 WebView2(Edge 엔진)가 그린다 — 라벨 그리기·로트·고유번호는
//	  예전처럼 포털 것을 그대로 쓴다(사무실 라벨과 갈라지지 않게).
//	⭐ Edge 프로세스를 따로 띄우지 않으니 «껐다 켜면 빈 창» 같은 일이 생길 자리가 없다.
//	  창을 닫으면 이 프로그램도 끝난다.
//	⚠ WebView2 런타임이 없는 PC(오래된 윈도우 10)면 예전처럼 Edge 창으로 띄운다(main 이 받아서).

import (
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"

	webview "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
)

var (
	user32            = windows.NewLazySystemDLL("user32.dll")
	pShowWindow       = user32.NewProc("ShowWindow")
	pSetForeground    = user32.NewProc("SetForegroundWindow")
	pSetWindowLongPtr = user32.NewProc("SetWindowLongPtrW")
	pSetWindowPos     = user32.NewProc("SetWindowPos")
	pGetSystemMetrics = user32.NewProc("GetSystemMetrics")
	pIsIconic         = user32.NewProc("IsIconic")
)

var (
	winMu sync.Mutex
	winWV webview.WebView
)

// 다른 실행(바탕화면 아이콘을 또 누름)이 «창을 앞으로» 부탁할 때 — 관문이 부른다
func focusWindow() bool {
	winMu.Lock()
	w := winWV
	winMu.Unlock()
	if w == nil {
		return false
	}
	w.Dispatch(func() {
		h := uintptr(w.Window())
		if r, _, _ := pIsIconic.Call(h); r != 0 {
			pShowWindow.Call(h, 9) // SW_RESTORE
		}
		pSetForeground.Call(h)
	})
	return true
}

func runWindow(url string) error {
	//  ⚠ 창을 만든 실(스레드)에서 끝까지 돌아야 한다(윈도우 규칙)
	runtime.LockOSThread()

	//  🖨 «기본 프린터로 바로» — 엔진에 옵션을 넘긴다(브라우저 창 때와 같은 옵션)
	args := []string{"--disable-features=Translate"}
	if conf.Print == "silent" {
		args = append(args, "--kiosk-printing")
	}
	os.Setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", strings.Join(args, " "))

	w := webview.NewWithOptions(webview.WebViewOptions{
		//  ⚠ 로그인·언어 설정이 남는 자리 — 이 프로그램만의 것
		DataPath:  filepath.Join(profileDir(), "WebView2"),
		AutoFocus: true,
		WindowOptions: webview.WindowOptions{
			Title:  "한일 라벨 발행 · v" + VERSION,
			Width:  uint(conf.Width),
			Height: uint(conf.Height),
			IconId: 1, //  exe 안의 아이콘(winres #1)
			Center: true,
		},
	})
	if w == nil {
		return errors.New("WebView2 를 열지 못했습니다(런타임이 없을 수 있습니다)")
	}
	defer w.Destroy()
	winMu.Lock()
	winWV = w
	winMu.Unlock()

	h := uintptr(w.Window())
	if conf.Fullscreen {
		//  ⛶ 키오스크 — 제목줄 없이 화면 전체(끄기: Alt+F4)
		const gwlStyle = ^uintptr(15) // GWL_STYLE = -16
		const wsPopupVisible = 0x80000000 | 0x10000000
		pSetWindowLongPtr.Call(h, gwlStyle, wsPopupVisible)
		cx, _, _ := pGetSystemMetrics.Call(0) // SM_CXSCREEN
		cy, _, _ := pGetSystemMetrics.Call(1) // SM_CYSCREEN
		const hwndTop, swpFrameChanged, swpShow = 0, 0x0020, 0x0040
		pSetWindowPos.Call(h, hwndTop, 0, 0, cx, cy, swpFrameChanged|swpShow)
	} else {
		pShowWindow.Call(h, 3) // SW_MAXIMIZE — 현장 화면은 늘 크게
	}
	w.Navigate(url)
	logf("독자 창으로 띄웠습니다")
	w.Run()
	logf("창을 닫았습니다")
	winMu.Lock()
	winWV = nil
	winMu.Unlock()
	return nil
}
