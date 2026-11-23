//go:build windows

package main

// ── 바탕화면에 까는 창(WebView2) ─────────────────────────────
//
//	DesktopCal 처럼 **바탕화면 위·다른 창 아래**에 달력을 깐다.
//	  · 제목줄·테두리가 없고, 작업 표시줄·Alt+Tab 에 안 나온다(WS_EX_TOOLWINDOW).
//	  · 바탕화면(아이콘 층을 쥔 창)을 «주인»으로 삼고, 누가 위로 올리려 해도 늘 맨 아래로 돌려놓는다
//	    (WM_WINDOWPOSCHANGING 에서 hwndInsertAfter = HWND_BOTTOM).
//	  · 「바탕화면 보기(Win+D)」로 숨겨지면 2초 안에 다시 편다.
//	  · 위치·크기를 바꿀 때만 잠시 보통 창(테두리 있음)으로 바꾸고, 「고정」을 누르면 그 자리에 다시 깐다.
//	  · 알림 영역(시계 옆) 아이콘: 왼쪽 누르기 = 달력을 잠시 앞으로, 오른쪽 = 메뉴, 풍선 알림 누르기 = 포털의 그 화면.
//
//	⚠ 창 메시지는 창을 만든 실(스레드)에서만 다룬다 — 다른 곳(관문)에서 부를 때는 Dispatch 로 넘긴다.

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"unsafe"

	webview "github.com/jchv/go-webview2"
	"golang.org/x/sys/windows"
)

var (
	user32                 = windows.NewLazySystemDLL("user32.dll")
	shell32                = windows.NewLazySystemDLL("shell32.dll")
	pShowWindow            = user32.NewProc("ShowWindow")
	pSetForeground         = user32.NewProc("SetForegroundWindow")
	pSetWindowLongPtr      = user32.NewProc("SetWindowLongPtrW")
	pGetWindowLongPtr      = user32.NewProc("GetWindowLongPtrW")
	pCallWindowProc        = user32.NewProc("CallWindowProcW")
	pSetWindowPos          = user32.NewProc("SetWindowPos")
	pGetClientRect         = user32.NewProc("GetClientRect")
	pClientToScreen        = user32.NewProc("ClientToScreen")
	pAdjustWindowRectEx    = user32.NewProc("AdjustWindowRectEx")
	pSystemParametersInfo  = user32.NewProc("SystemParametersInfoW")
	pFindWindow            = user32.NewProc("FindWindowW")
	pFindWindowEx          = user32.NewProc("FindWindowExW")
	pIsIconic              = user32.NewProc("IsIconic")
	pIsWindowVisible       = user32.NewProc("IsWindowVisible")
	pSetTimer              = user32.NewProc("SetTimer")
	pCreatePopupMenu       = user32.NewProc("CreatePopupMenu")
	pAppendMenu            = user32.NewProc("AppendMenuW")
	pTrackPopupMenu        = user32.NewProc("TrackPopupMenu")
	pDestroyMenu           = user32.NewProc("DestroyMenu")
	pGetCursorPos          = user32.NewProc("GetCursorPos")
	pPostMessage           = user32.NewProc("PostMessageW")
	pLoadImage             = user32.NewProc("LoadImageW")
	pGetSystemMetrics      = user32.NewProc("GetSystemMetrics")
	pRegisterWindowMessage = user32.NewProc("RegisterWindowMessageW")
	pShellNotifyIcon       = shell32.NewProc("Shell_NotifyIconW")
	pSetLayeredAttr        = user32.NewProc("SetLayeredWindowAttributes")
	pReleaseCapture        = user32.NewProc("ReleaseCapture")
)

const (
	wsOverlappedWindow = 0x00CF0000
	wsPopup            = 0x80000000
	wsVisible          = 0x10000000
	wsClipChildren     = 0x02000000
	wsExToolWindow     = 0x00000080
	wsExLayered        = 0x00080000

	swpNoSize        = 0x0001
	swpNoMove        = 0x0002
	swpNoZOrder      = 0x0004
	swpNoActivate    = 0x0010
	swpFrameChanged  = 0x0020
	swpShowWindow    = 0x0040
	hwndBottom       = 1
	hwndTop          = 0
	hwndTopmost      = ^uintptr(0) // -1
	hwndNoTopmost    = ^uintptr(1) // -2
	wmClose          = 0x0010
	wmActivate       = 0x0006
	wmWindowPosChang = 0x0046
	wmTimer          = 0x0113
	wmExitSizeMove   = 0x0232
	wmNcLButtonDown  = 0x00A1
	wmNull           = 0x0000
	wmLButtonUp      = 0x0202
	wmRButtonUp      = 0x0205
	wmTray           = 0x8002 //  WM_APP+2 — 알림 영역 아이콘이 보내는 소식(WM_APP 는 라이브러리가 쓴다)
	ninBalloonClick  = 0x0405
	timerKeep        = 7
)

// 음수 번호(GWL_*)를 uintptr 로
var (
	gwlpWndProc    = ^uintptr(3)  // -4
	gwlpHwndParent = ^uintptr(7)  // -8
	gwlStyle       = ^uintptr(15) // -16
	gwlExStyle     = ^uintptr(19) // -20
)

type rect struct{ Left, Top, Right, Bottom int32 }
type point struct{ X, Y int32 }

type windowPos struct {
	Hwnd            uintptr
	HwndInsertAfter uintptr
	X, Y, Cx, Cy    int32
	Flags           uint32
}

// 저장해 두는 자리 — **안쪽(그림이 그려지는 칸)** 의 화면 좌표. 테두리를 붙였다 뗐다 해도 달력이 안 움직이게.
type winRect struct{ X, Y, W, H int32 }

var (
	winMu      sync.Mutex
	winWV      webview.WebView
	hwndMain   uintptr
	oldProc    uintptr
	pinned     bool
	peek       bool //  잠시 앞으로 불러낸 상태(다른 창을 누르면 다시 바탕화면으로)
	alerting   bool //  🔔 결재 차례 알림을 띄운 상태 — 사람이 「확인」할 때까지 맨 위에 둔다
	quitting   bool
	place      winRect
	taskbarMsg uintptr
	trayMu     sync.Mutex
	trayOn     bool
	noticeURL  string
	alpha      = 100 //  🌫 투명도(불투명 %) — 30~100. 100 이면 겹창(layered)을 쓰지 않는다
)

func winFile() string { return filepath.Join(profileDir(), "window.json") }

func loadPlace() winRect {
	var r winRect
	if b, err := os.ReadFile(winFile()); err == nil && json.Unmarshal(b, &r) == nil && r.W >= 320 && r.H >= 240 {
		return r
	}
	//  처음 — 작업 영역 오른쪽에 큼직하게(아이콘이 보통 왼쪽에 있다)
	var wa rect
	pSystemParametersInfo.Call(0x0030, 0, uintptr(unsafe.Pointer(&wa)), 0) // SPI_GETWORKAREA
	ww, wh := wa.Right-wa.Left, wa.Bottom-wa.Top
	if ww < 800 || wh < 600 {
		ww, wh = 1280, 720
	}
	r.W, r.H = ww*60/100, wh*82/100
	r.X, r.Y = wa.Right-r.W-24, wa.Top+24
	return r
}

func savePlace() {
	b, _ := json.Marshal(place)
	_ = os.WriteFile(winFile(), b, 0o644)
}

// 지금 창 안쪽 칸의 화면 좌표
func clientPlace(h uintptr) winRect {
	var rc rect
	pGetClientRect.Call(h, uintptr(unsafe.Pointer(&rc)))
	p := point{}
	pClientToScreen.Call(h, uintptr(unsafe.Pointer(&p)))
	return winRect{X: p.X, Y: p.Y, W: rc.Right - rc.Left, H: rc.Bottom - rc.Top}
}

// 바탕화면 아이콘 층(SHELLDLL_DefView)을 쥔 맨 위 창 — Progman 이거나 WorkerW
func desktopHost() uintptr {
	cls := func(s string) uintptr { p, _ := windows.UTF16PtrFromString(s); return uintptr(unsafe.Pointer(p)) }
	pm, _, _ := pFindWindow.Call(cls("Progman"), 0)
	if pm != 0 {
		if dv, _, _ := pFindWindowEx.Call(pm, 0, cls("SHELLDLL_DefView"), 0); dv != 0 {
			return pm
		}
	}
	var w uintptr
	for {
		w, _, _ = pFindWindowEx.Call(0, w, cls("WorkerW"), 0)
		if w == 0 {
			break
		}
		if dv, _, _ := pFindWindowEx.Call(w, 0, cls("SHELLDLL_DefView"), 0); dv != 0 {
			return w
		}
	}
	return pm
}

// 🔔 결재할 문서가 왔다 — 달력을 **모든 창 위로** 올려 알림 카드를 보인다(「확인」을 누를 때까지).
//
//	⚠ 윈도우는 뒤에 있던 프로그램이 스스로 앞으로 나오는 것(포커스 뺏기)을 막는다 → 「맨 위(TOPMOST)」로 올려 보이게만 한다.
func doAlert() {
	h := hwndMain
	alerting, peek = true, pinned
	if r, _, _ := pIsIconic.Call(h); r != 0 {
		pShowWindow.Call(h, 9)
	}
	pSetWindowPos.Call(h, hwndTopmost, 0, 0, 0, 0, swpNoMove|swpNoSize|swpShowWindow)
	pSetForeground.Call(h)
}

func doBack() {
	h := hwndMain
	alerting, peek = false, false
	pSetWindowPos.Call(h, hwndNoTopmost, 0, 0, 0, 0, swpNoMove|swpNoSize|swpNoActivate)
	if pinned {
		pSetWindowPos.Call(h, hwndBottom, 0, 0, 0, 0, swpNoMove|swpNoSize|swpNoActivate)
	}
}

// 🌫 투명도 — 창 전체(글자 포함)를 비치게 한다(DesktopCal 의 「투명도」). 100 이면 겹창을 끈다.
//
//	⚠ 겹창(WS_EX_LAYERED)과 WebView2 가 맞지 않는 PC(오래된 그래픽 드라이버)에서는 화면이 검게 나올 수 있다 →
//	  알림 영역 메뉴의 「투명도 원래대로」로 언제든 되돌린다.
func layeredBit() uintptr {
	if alpha < 100 {
		return wsExLayered
	}
	return 0
}

func applyAlpha() { applyAlphaValue(alpha) }

// 정해 둔 투명도(alpha)는 그대로 두고 화면에만 잠시 a% 로 — 결재 문서를 볼 때는 비치면 안 된다(talpha)
func applyAlphaValue(a int) {
	h := hwndMain
	ex, _, _ := pGetWindowLongPtr.Call(h, gwlExStyle)
	if a < 100 {
		pSetWindowLongPtr.Call(h, gwlExStyle, ex|wsExLayered)
		pSetLayeredAttr.Call(h, 0, uintptr(a*255/100), 2) // LWA_ALPHA
	} else if ex&wsExLayered != 0 {
		pSetWindowLongPtr.Call(h, gwlExStyle, ex&^wsExLayered)
	}
	pSetWindowPos.Call(h, 0, 0, 0, 0, 0, swpNoMove|swpNoSize|swpNoZOrder|swpNoActivate|swpFrameChanged)
}

func saveAlpha() {
	_ = os.WriteFile(filepath.Join(profileDir(), "alpha.txt"), []byte(strconv.Itoa(alpha)), 0o644)
}

func loadAlpha() {
	if b, err := os.ReadFile(filepath.Join(profileDir(), "alpha.txt")); err == nil {
		if n, err := strconv.Atoi(strings.TrimSpace(string(b))); err == nil && n >= 30 && n <= 100 {
			alpha = n
		}
	}
}

const minW, minH = 420, 300

// ↔ 크기 고르기 — 작업 영역(작업 표시줄 뺀 화면)의 몇 % · 어느 쪽
//
//	v = "60,right" · "40,left" · "80,center" · "100,full"
func doSize(v string) {
	pct, pos := 60, "right"
	if i := strings.Index(v, ","); i >= 0 {
		pct, _ = strconv.Atoi(v[:i])
		pos = v[i+1:]
	}
	if pct < 25 || pct > 100 {
		pct = 60
	}
	var wa rect
	pSystemParametersInfo.Call(0x0030, 0, uintptr(unsafe.Pointer(&wa)), 0)
	ww, wh := wa.Right-wa.Left, wa.Bottom-wa.Top
	if pos == "full" || pct == 100 {
		place = winRect{X: wa.Left, Y: wa.Top, W: ww, H: wh}
	} else {
		hp := int32(pct + 25)
		if hp > 94 {
			hp = 94
		}
		if hp < 50 {
			hp = 50
		}
		place.W, place.H = ww*int32(pct)/100, wh*hp/100
		if place.W < minW {
			place.W = minW
		}
		place.Y = wa.Top + 24
		switch pos {
		case "left":
			place.X = wa.Left + 24
		case "center":
			place.X, place.Y = wa.Left+(ww-place.W)/2, wa.Top+(wh-place.H)/2
		default:
			place.X = wa.Right - place.W - 24
		}
	}
	savePlace()
	if pinned {
		pSetWindowPos.Call(hwndMain, hwndBottom, uintptr(place.X), uintptr(place.Y), uintptr(place.W), uintptr(place.H), swpNoActivate|swpShowWindow)
	} else {
		rc := rect{place.X, place.Y, place.X + place.W, place.Y + place.H}
		pAdjustWindowRectEx.Call(uintptr(unsafe.Pointer(&rc)), wsOverlappedWindow, 0, 0)
		pSetWindowPos.Call(hwndMain, 0, uintptr(rc.Left), uintptr(rc.Top), uintptr(rc.Right-rc.Left), uintptr(rc.Bottom-rc.Top), swpNoZOrder)
	}
}

// 화면(달력)에서 가장자리·머리줄을 누른 채 끌 때 — 윈도우의 «크기 바꾸기/옮기기»를 대신 시작한다
//
//	ht: 2 = 옮기기(제목줄), 10 왼쪽 11 오른쪽 12 위 13 왼위 14 오른위 15 아래 16 왼아래 17 오른아래
//	⚠ 단추를 누르고 있는 동안에 와야 한다(화면이 누르자마자 부른다). 놓으면 윈도우가 알아서 끝낸다.
func doDrag(ht int) {
	if ht != 2 && (ht < 10 || ht > 17) {
		return
	}
	pReleaseCapture.Call()
	pPostMessage.Call(hwndMain, wmNcLButtonDown, uintptr(ht), 0)
}

// ⭐ 바탕화면에 깐다(테두리 없음 · 작업 표시줄에 없음 · 늘 맨 아래)
func doPin() {
	h := hwndMain
	pinned, peek = true, false
	pSetWindowLongPtr.Call(h, gwlStyle, wsPopup|wsVisible|wsClipChildren)
	pSetWindowLongPtr.Call(h, gwlExStyle, wsExToolWindow|layeredBit())
	pSetWindowLongPtr.Call(h, gwlpHwndParent, desktopHost())
	pSetWindowPos.Call(h, hwndBottom, uintptr(place.X), uintptr(place.Y), uintptr(place.W), uintptr(place.H),
		swpFrameChanged|swpNoActivate|swpShowWindow)
}

// 위치·크기 조정 — 보통 창(테두리·제목줄)으로. 안쪽 칸은 그 자리에 그대로 둔다.
func doUnpin() {
	h := hwndMain
	pinned, peek = false, false
	pSetWindowLongPtr.Call(h, gwlpHwndParent, 0)
	pSetWindowLongPtr.Call(h, gwlExStyle, layeredBit())
	pSetWindowLongPtr.Call(h, gwlStyle, wsOverlappedWindow|wsVisible|wsClipChildren)
	rc := rect{place.X, place.Y, place.X + place.W, place.Y + place.H}
	pAdjustWindowRectEx.Call(uintptr(unsafe.Pointer(&rc)), wsOverlappedWindow, 0, 0)
	pSetWindowPos.Call(h, hwndTop, uintptr(rc.Left), uintptr(rc.Top), uintptr(rc.Right-rc.Left), uintptr(rc.Bottom-rc.Top),
		swpFrameChanged|swpShowWindow)
	pSetForeground.Call(h)
}

// 잠시 앞으로 — 다른 창을 누르면(비활성) 다시 바탕화면 층으로 내려간다
func doPeek() {
	h := hwndMain
	if r, _, _ := pIsIconic.Call(h); r != 0 {
		pShowWindow.Call(h, 9) // SW_RESTORE
	}
	if pinned {
		peek = true
	}
	pSetWindowPos.Call(h, hwndTop, 0, 0, 0, 0, swpNoMove|swpNoSize|swpShowWindow)
	pSetForeground.Call(h)
}

func subProc(hwnd, msg, wp, lp uintptr) uintptr {
	switch msg {
	case wmWindowPosChang:
		p := (*windowPos)(unsafe.Pointer(lp))
		//  ⭐ 늘 맨 아래 — 누가(누르기·다른 프로그램) 위로 올려도 바탕화면 바로 위로 돌려놓는다
		if pinned && !peek {
			if p.Flags&swpNoZOrder == 0 {
				p.HwndInsertAfter = hwndBottom
			}
		}
		//  너무 작게 줄이지 못하게(달력이 안 보이게 되면 다시 키울 곳이 없다)
		if pinned && p.Flags&swpNoSize == 0 {
			if p.Cx < minW {
				p.Cx = minW
			}
			if p.Cy < minH {
				p.Cy = minH
			}
		}
	case wmExitSizeMove:
		//  ↔ 바탕화면에 깔린 채로 끌어 옮기거나 크기를 바꿨다 — 그 자리를 기억한다
		if pinned {
			place = clientPlace(hwnd)
			savePlace()
		}
	case wmActivate:
		if wp&0xFFFF == 0 && peek && !alerting { // WA_INACTIVE
			peek = false
			pSetWindowPos.Call(hwnd, hwndBottom, 0, 0, 0, 0, swpNoMove|swpNoSize|swpNoActivate)
		}
	case wmClose:
		//  ⚠ 바탕화면 달력은 Alt+F4 한 번에 사라지면 안 된다 — 끄기는 알림 영역 메뉴의 「끄기」로
		if pinned && !quitting {
			return 0
		}
		if !pinned {
			//  보통 창으로 쓰다가 끄면 그 자리를 기억한다(창이 없어지기 전에)
			place = clientPlace(hwnd)
			savePlace()
		}
	case wmTimer:
		if wp == timerKeep && pinned {
			//  「바탕화면 보기」(Win+D)로 숨겨졌으면 다시 편다(앞으로 나오지는 않게)
			v, _, _ := pIsWindowVisible.Call(hwnd)
			ic, _, _ := pIsIconic.Call(hwnd)
			if v == 0 || ic != 0 {
				pShowWindow.Call(hwnd, 4) // SW_SHOWNOACTIVATE
				pSetWindowPos.Call(hwnd, hwndBottom, uintptr(place.X), uintptr(place.Y), uintptr(place.W), uintptr(place.H), swpNoActivate|swpShowWindow)
			}
			return 0
		}
	case wmTray:
		switch lp & 0xFFFF {
		case wmLButtonUp:
			doPeek()
		case wmRButtonUp:
			trayMenu(hwnd)
		case ninBalloonClick:
			trayMu.Lock()
			u := noticeURL
			trayMu.Unlock()
			if u != "" {
				openExternal(u)
			} else {
				doPeek()
			}
		}
		return 0
	}
	if taskbarMsg != 0 && msg == taskbarMsg {
		//  탐색기가 다시 켜졌다 — 알림 영역 아이콘을 다시 넣는다
		trayMu.Lock()
		trayOn = false
		trayMu.Unlock()
		trayAdd(hwnd)
	}
	r, _, _ := pCallWindowProc.Call(oldProc, hwnd, msg, wp, lp)
	return r
}

// ── 알림 영역 아이콘 ────────────────────────────────────────
type notifyIconData struct {
	CbSize           uint32
	HWnd             uintptr
	UID              uint32
	UFlags           uint32
	UCallbackMessage uint32
	HIcon            uintptr
	SzTip            [128]uint16
	DwState          uint32
	DwStateMask      uint32
	SzInfo           [256]uint16
	UVersion         uint32
	SzInfoTitle      [64]uint16
	DwInfoFlags      uint32
	GuidItem         windows.GUID
	HBalloonIcon     uintptr
}

const (
	nimAdd     = 0
	nimModify  = 1
	nimDelete  = 2
	nifMessage = 0x01
	nifIcon    = 0x02
	nifTip     = 0x04
	nifInfo    = 0x10
	niifInfo   = 0x01
)

func copyW(dst []uint16, s string) {
	u, _ := windows.UTF16FromString(s)
	if len(u) > len(dst) {
		u = u[:len(dst)]
		u[len(u)-1] = 0
	}
	copy(dst, u)
}

func baseNID(h uintptr) notifyIconData {
	var n notifyIconData
	n.CbSize = uint32(unsafe.Sizeof(n))
	n.HWnd = h
	n.UID = 1
	return n
}

func trayAdd(h uintptr) {
	trayMu.Lock()
	defer trayMu.Unlock()
	if trayOn {
		return
	}
	n := baseNID(h)
	n.UFlags = nifMessage | nifIcon | nifTip
	n.UCallbackMessage = wmTray
	var hinst windows.Handle
	_ = windows.GetModuleHandleEx(0, nil, &hinst)
	cx, _, _ := pGetSystemMetrics.Call(49) // SM_CXSMICON
	cy, _, _ := pGetSystemMetrics.Call(50)
	n.HIcon, _, _ = pLoadImage.Call(uintptr(hinst), 1, 1, cx, cy, 0x8000) // IMAGE_ICON · LR_SHARED
	copyW(n.SzTip[:], "한일 바탕화면 달력 v"+VERSION)
	r, _, _ := pShellNotifyIcon.Call(nimAdd, uintptr(unsafe.Pointer(&n)))
	trayOn = r != 0
}

func trayDel(h uintptr) {
	trayMu.Lock()
	defer trayMu.Unlock()
	n := baseNID(h)
	pShellNotifyIcon.Call(nimDelete, uintptr(unsafe.Pointer(&n)))
	trayOn = false
}

// 풍선 알림(윈도 10·11 에서는 오른쪽 아래 알림으로 뜬다)
func showNotice(title, text, u string) {
	winMu.Lock()
	h := hwndMain
	winMu.Unlock()
	if h == 0 {
		return
	}
	trayMu.Lock()
	defer trayMu.Unlock()
	if !trayOn {
		return
	}
	noticeURL = ""
	if u != "" {
		if up := currentPortal(); up != "" {
			noticeURL = up + u
		}
	}
	n := baseNID(h)
	n.UFlags = nifInfo
	n.DwInfoFlags = niifInfo
	copyW(n.SzInfoTitle[:], title)
	copyW(n.SzInfo[:], text)
	pShellNotifyIcon.Call(nimModify, uintptr(unsafe.Pointer(&n)))
}

const (
	cmdShow = 1 + iota
	cmdEdit
	cmdPin
	cmdPortal
	cmdReload
	cmdAlpha
	cmdA90
	cmdA80
	cmdA70
	cmdA60
	cmdA50
	cmdQuit
)

func trayMenu(h uintptr) {
	m, _, _ := pCreatePopupMenu.Call()
	if m == 0 {
		return
	}
	defer pDestroyMenu.Call(m)
	add := func(id int, s string) {
		p, _ := windows.UTF16PtrFromString(s)
		pAppendMenu.Call(m, 0, uintptr(id), uintptr(unsafe.Pointer(p)))
	}
	add(cmdShow, "📅 달력 앞으로 보기")
	if pinned {
		add(cmdEdit, "↔ 위치·크기 조정")
	} else {
		add(cmdPin, "📌 바탕화면에 고정")
	}
	add(cmdReload, "🔄 새로 고침")
	add(cmdPortal, "🌐 포털 열기")
	//  🌫 투명도 — 하위 메뉴 대신 한 줄씩(고르기 쉽게)
	pAppendMenu.Call(m, 0x800, 0, 0)
	if alpha < 100 {
		add(cmdAlpha, "🌫 투명도 원래대로 (100%)")
	}
	for i, a := range []int{90, 80, 70, 60, 50} {
		mark := "   "
		if alpha == a {
			mark = "✓ "
		}
		add(cmdA90+i, mark+"🌫 "+strconv.Itoa(a)+"%")
	}
	pAppendMenu.Call(m, 0x800, 0, 0) // MF_SEPARATOR
	add(cmdQuit, "끄기")
	var pt point
	pGetCursorPos.Call(uintptr(unsafe.Pointer(&pt)))
	pSetForeground.Call(h)                                                                    //  ⚠ 이것이 없으면 메뉴 밖을 눌러도 메뉴가 안 닫힌다(윈도우 규칙)
	id, _, _ := pTrackPopupMenu.Call(m, 0x0100|0x0002, uintptr(pt.X), uintptr(pt.Y), 0, h, 0) // TPM_RETURNCMD|TPM_RIGHTBUTTON
	pPostMessage.Call(h, wmNull, 0, 0)
	switch int(id) {
	case cmdShow:
		doPeek()
	case cmdEdit:
		doUnpin()
	case cmdPin:
		place = clientPlace(h)
		savePlace()
		doPin()
	case cmdReload:
		if winWV != nil {
			winWV.Eval("location.reload()")
		}
	case cmdPortal:
		if up := currentPortal(); up != "" {
			openExternal(up + "/")
		}
	case cmdAlpha:
		alpha = 100
		saveAlpha()
		applyAlpha()
	case cmdA90, cmdA80, cmdA70, cmdA60, cmdA50:
		alpha = []int{90, 80, 70, 60, 50}[int(id)-cmdA90]
		saveAlpha()
		applyAlpha()
	case cmdQuit:
		quitting = true
		trayDel(h)
		pPostMessage.Call(h, wmClose, 0, 0)
	}
}

// ── 관문이 부르는 것들 ─────────────────────────────────────
var gwRef *gateway

func currentPortal() string {
	if gwRef == nil {
		return ""
	}
	if u := gwRef.current(); u != nil {
		return u.String()
	}
	if len(conf.URLs) > 0 {
		return conf.URLs[0]
	}
	return ""
}

func dispatch(f func()) bool {
	winMu.Lock()
	w := winWV
	winMu.Unlock()
	if w == nil {
		return false
	}
	w.Dispatch(f)
	return true
}

func focusWindow() bool { return dispatch(doPeek) }

func isPinned() bool { return pinned }

func currentAlpha() int { return alpha }

func hasDesktop() bool { return true }

func windowCmd(m, v string) {
	dispatch(func() {
		switch m {
		case "size":
			doSize(v)
		case "drag":
			n, _ := strconv.Atoi(v)
			doDrag(n)
		case "talpha":
			//  v 가 비면 정해 둔 투명도로 되돌린다
			if n, err := strconv.Atoi(v); err == nil && n >= 30 && n <= 100 {
				applyAlphaValue(n)
			} else {
				applyAlpha()
			}
		case "alpha":
			if n, err := strconv.Atoi(v); err == nil && n >= 30 && n <= 100 && n != alpha {
				alpha = n
				saveAlpha()
				applyAlpha()
			}
		case "edit":
			doUnpin()
		case "pin":
			if !pinned {
				place = clientPlace(hwndMain)
				savePlace()
			}
			doPin()
		case "front":
			doPeek()
		case "alert":
			doAlert()
		case "back":
			doBack()
		}
	})
}

func quitApp() {
	dispatch(func() {
		quitting = true
		trayDel(hwndMain)
		pPostMessage.Call(hwndMain, wmClose, 0, 0)
	})
}

func openExternal(u string) {
	verb, _ := windows.UTF16PtrFromString("open")
	file, _ := windows.UTF16PtrFromString(u)
	if err := windows.ShellExecute(0, verb, file, nil, nil, 1); err != nil {
		logf("브라우저로 못 엶 %s: %v", u, err)
	}
}

func runWindow(url string, gw *gateway) error {
	//  ⚠ 창을 만든 실(스레드)에서 끝까지 돌아야 한다(윈도우 규칙)
	runtime.LockOSThread()
	gwRef = gw
	place = loadPlace()
	loadAlpha()
	w := webview.NewWithOptions(webview.WebViewOptions{
		DataPath:  filepath.Join(profileDir(), "WebView2"),
		AutoFocus: true,
		WindowOptions: webview.WindowOptions{
			Title:  "한일 바탕화면 달력",
			Width:  uint(place.W),
			Height: uint(place.H),
			IconId: 1,
		},
	})
	if w == nil {
		return errors.New("WebView2 를 열지 못했습니다(런타임이 없을 수 있습니다)")
	}
	defer w.Destroy()
	h := uintptr(w.Window())
	winMu.Lock()
	winWV, hwndMain = w, h
	winMu.Unlock()

	oldProc, _, _ = pGetWindowLongPtr.Call(h, gwlpWndProc)
	pSetWindowLongPtr.Call(h, gwlpWndProc, windows.NewCallback(subProc))
	tb, _ := windows.UTF16PtrFromString("TaskbarCreated")
	taskbarMsg, _, _ = pRegisterWindowMessage.Call(uintptr(unsafe.Pointer(tb)))
	trayAdd(h)
	pSetTimer.Call(h, timerKeep, 2000, 0)

	if conf.Pin {
		doPin()
	} else {
		doUnpin()
	}
	applyAlpha()
	w.Navigate(url)
	logf("창을 띄웠습니다 (바탕화면 고정=%v · %+v)", conf.Pin, place)
	w.Run()
	trayDel(h)
	winMu.Lock()
	winWV, hwndMain = nil, 0
	winMu.Unlock()
	return nil
}
