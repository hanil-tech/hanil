//go:build windows

package main

// ── 양식별 프린터 ───────────────────────────────────────────
//
//	사용자 「양식별로 프린터를 지정할 수 있게」
//	⭐ 양식(거래처 라벨 모양)마다 프린터를 정해 두면 그 양식은 인쇄 창 없이 그 프린터로 바로 나간다.
//	  정해 두지 않은 양식은 예전 그대로(PRINT=dialog → 인쇄 창 · silent → 기본 프린터).
//	⭐ 정한 것은 이 PC 에만 남는다: %LOCALAPPDATA%\HanilLabel\printers.json  ({"양식":"프린터 이름"})
//
//	인쇄는 WebView2 의 PrintAsync(ICoreWebView2_16::Print) 로 한다 — 프린터 이름을 지정할 수 있는 유일한 길.
//	go-webview2 에는 이 함수가 없어 COM 표(vtable)를 직접 부른다. 순번은 WebView2.h 의 상속 사슬을 센 것:
//	  ICoreWebView2(3+58) → _2(7) _3(5) _4(4) _5(2) _6(1) _7(1) _8(7) _9(9) _10(2) _11(3) _12(3) _13(1) _14(3) _15(4)
//	  → ICoreWebView2_16::Print = 113
//	  ICoreWebView2Environment(3+5) → 2(1) 3(2) 4(1) 5(2) → Environment6::CreatePrintSettings = 14
//	  ICoreWebView2PrintSettings(3+26) → PrintSettings2: … PutPrinterName = 44
//	⚠ WebView2 런타임 1.0.1518(2023) 보다 옛것이면 QueryInterface 가 실패한다 → 화면이 예전 인쇄로 물러선다.

import (
	"encoding/json"
	"errors"
	"math"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"sync"
	"syscall"
	"unsafe"

	webview "github.com/jchv/go-webview2"
	"github.com/jchv/go-webview2/pkg/edge"
	"golang.org/x/sys/windows"
)

var (
	winspool          = windows.NewLazySystemDLL("winspool.drv")
	pEnumPrinters     = winspool.NewProc("EnumPrintersW")
	pGetDefaultPrintr = winspool.NewProc("GetDefaultPrinterW")
)

// ── 프린터 목록 ──
func listPrinters() []string {
	const flags = 0x2 | 0x4 // PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
	var need, n uint32
	pEnumPrinters.Call(flags, 0, 4, 0, 0, uintptr(unsafe.Pointer(&need)), uintptr(unsafe.Pointer(&n)))
	if need == 0 {
		return nil
	}
	buf := make([]byte, need)
	r, _, _ := pEnumPrinters.Call(flags, 0, 4, uintptr(unsafe.Pointer(&buf[0])), uintptr(need),
		uintptr(unsafe.Pointer(&need)), uintptr(unsafe.Pointer(&n)))
	if r == 0 {
		return nil
	}
	type printerInfo4 struct {
		name   *uint16
		server *uint16
		attr   uint32
	}
	out := []string{}
	sz := unsafe.Sizeof(printerInfo4{})
	for i := uint32(0); i < n; i++ {
		p := (*printerInfo4)(unsafe.Pointer(&buf[uintptr(i)*sz]))
		if p.name != nil {
			out = append(out, windows.UTF16PtrToString(p.name))
		}
	}
	sort.Strings(out)
	return out
}

func defaultPrinter() string {
	var n uint32
	pGetDefaultPrintr.Call(0, uintptr(unsafe.Pointer(&n)))
	if n == 0 {
		return ""
	}
	b := make([]uint16, n)
	if r, _, _ := pGetDefaultPrintr.Call(uintptr(unsafe.Pointer(&b[0])), uintptr(unsafe.Pointer(&n))); r == 0 {
		return ""
	}
	return windows.UTF16ToString(b)
}

// ── 양식 → 프린터 (이 PC 에만) ──
var prMu sync.Mutex

func printerMapPath() string { return filepath.Join(profileDir(), "printers.json") }

func loadPrinterMap() map[string]string {
	m := map[string]string{}
	if b, err := os.ReadFile(printerMapPath()); err == nil {
		_ = json.Unmarshal(b, &m)
	}
	return m
}

func setPrinterFor(form, printer string) error {
	prMu.Lock()
	defer prMu.Unlock()
	m := loadPrinterMap()
	if printer == "" {
		delete(m, form)
	} else {
		m[form] = printer
	}
	b, _ := json.MarshalIndent(m, "", "  ")
	_ = os.MkdirAll(profileDir(), 0o755)
	if err := os.WriteFile(printerMapPath(), b, 0o644); err != nil {
		return err
	}
	logf("양식 프린터: %q → %q", form, printer)
	return nil
}

// ── COM 부르기 ──
func comCall(obj uintptr, idx int, args ...uintptr) uintptr {
	vtbl := *(*uintptr)(unsafe.Pointer(obj))
	fn := *(*uintptr)(unsafe.Pointer(vtbl + uintptr(idx)*unsafe.Sizeof(uintptr(0))))
	r, _, _ := syscall.SyscallN(fn, append([]uintptr{obj}, args...)...)
	return r
}

func comQI(obj uintptr, iid string) uintptr {
	g, err := windows.GUIDFromString(iid)
	if err != nil || obj == 0 {
		return 0
	}
	var out uintptr
	if hr := comCall(obj, 0, uintptr(unsafe.Pointer(&g)), uintptr(unsafe.Pointer(&out))); hr != 0 {
		return 0
	}
	return out
}

func comRelease(obj uintptr) {
	if obj != 0 {
		comCall(obj, 2)
	}
}

// go-webview2 가 감춰 둔 칸을 꺼낸다(이름으로 — 라이브러리를 고치지 않으려고)
func hiddenField(v reflect.Value, name string) reflect.Value {
	for v.Kind() == reflect.Ptr || v.Kind() == reflect.Interface {
		if v.IsNil() {
			return reflect.Value{}
		}
		v = v.Elem()
	}
	if v.Kind() != reflect.Struct {
		return reflect.Value{}
	}
	f := v.FieldByName(name)
	if !f.IsValid() || !f.CanAddr() {
		return reflect.Value{}
	}
	return reflect.NewAt(f.Type(), unsafe.Pointer(f.UnsafeAddr())).Elem()
}

func webviewCOM(w webview.WebView) (core, env uintptr) {
	b := hiddenField(reflect.ValueOf(w), "browser")
	if !b.IsValid() {
		return 0, 0
	}
	c, ok := b.Interface().(*edge.Chromium)
	if !ok || c == nil {
		return 0, 0
	}
	if f := hiddenField(reflect.ValueOf(c), "webview"); f.IsValid() && f.Kind() == reflect.Ptr {
		core = f.Pointer()
	}
	env = uintptr(unsafe.Pointer(c.Environment()))
	return core, env
}

// ── 인쇄가 끝났다는 알림(ICoreWebView2PrintCompletedHandler) ──
type printDoneHandler struct {
	vtbl *[4]uintptr
}

var (
	pdVtbl    [4]uintptr
	pdHandler = &printDoneHandler{vtbl: &pdVtbl}
	pdOnce    sync.Once
	pdWV      webview.WebView
)

func initPrintHandler() {
	pdOnce.Do(func() {
		pdVtbl[0] = windows.NewCallback(func(this, riid, ppv uintptr) uintptr {
			*(*uintptr)(unsafe.Pointer(ppv)) = this
			return 0
		})
		pdVtbl[1] = windows.NewCallback(func(this uintptr) uintptr { return 1 })
		pdVtbl[2] = windows.NewCallback(func(this uintptr) uintptr { return 1 })
		pdVtbl[3] = windows.NewCallback(func(this, hr, status uintptr) uintptr {
			logf("양식 프린터 인쇄 끝: hr=%#x status=%d", uint32(hr), status)
			if w := pdWV; w != nil {
				js := "window.__hpDone&&window.__hpDone(" + itoa(int(int32(uint32(hr)))) + "," + itoa(int(status)) + ")"
				w.Dispatch(func() { w.Eval(js) })
			}
			return 0
		})
	})
}

func itoa(i int) string { b, _ := json.Marshal(i); return string(b) }

// 지금 창의 문서를 printer 로 인쇄 창 없이 보낸다(끝나면 window.__hpDone(hr, status))
//
//	⚠ 창(UI) 실에서 불러야 한다 — 바인딩은 그 실에서 불린다.
func printTo(w webview.WebView, printer string) error {
	core, env := webviewCOM(w)
	if core == 0 || env == 0 {
		return errors.New("인쇄 엔진을 찾지 못했습니다")
	}
	wv16 := comQI(core, "{0EB34DC9-9F91-41E1-8639-95CD5943906B}")
	env6 := comQI(env, "{e59ee362-acbd-4857-9a8e-d3644d9459a9}")
	defer comRelease(wv16)
	defer comRelease(env6)
	if wv16 == 0 || env6 == 0 {
		return errors.New("WebView2 가 오래되어 프린터를 고를 수 없습니다(Edge 업데이트 필요)")
	}
	var ps uintptr
	if hr := comCall(env6, 14, uintptr(unsafe.Pointer(&ps))); hr != 0 || ps == 0 {
		return errors.New("인쇄 설정을 만들지 못했습니다")
	}
	defer comRelease(ps)
	//  여백 0 · 배율 100% · 머리글/바닥글 없음 · 배경(검은 칸·로고) 찍기 — 라벨 화면 인쇄 창에서 맞추던 그대로
	comCall(ps, 6, uintptr(math.Float64bits(1.0))) // PutScaleFactor
	comCall(ps, 12, uintptr(math.Float64bits(0)))  // PutMarginTop
	comCall(ps, 14, uintptr(math.Float64bits(0)))  // PutMarginBottom
	comCall(ps, 16, uintptr(math.Float64bits(0)))  // PutMarginLeft
	comCall(ps, 18, uintptr(math.Float64bits(0)))  // PutMarginRight
	comCall(ps, 20, 1)                             // PutShouldPrintBackgrounds
	comCall(ps, 24, 0)                             // PutShouldPrintHeaderAndFooter
	ps2 := comQI(ps, "{CA7F0E1F-3484-41D1-8C1A-65CD44A63F8D}")
	if ps2 == 0 {
		return errors.New("WebView2 가 오래되어 프린터를 고를 수 없습니다(Edge 업데이트 필요)")
	}
	defer comRelease(ps2)
	name, err := windows.UTF16PtrFromString(printer)
	if err != nil {
		return err
	}
	if hr := comCall(ps2, 44, uintptr(unsafe.Pointer(name))); hr != 0 { // PutPrinterName
		return errors.New("프린터 이름을 넣지 못했습니다")
	}
	initPrintHandler()
	pdWV = w
	if hr := comCall(wv16, 113, ps, uintptr(unsafe.Pointer(pdHandler))); hr != 0 { // Print
		return errors.New("인쇄를 시작하지 못했습니다")
	}
	logf("양식 프린터로 인쇄: %q", printer)
	return nil
}

// 화면(page.html)에 쓰는 함수들을 건넨다
func bindPrinters(w webview.WebView) {
	type info struct {
		Printers []string          `json:"printers"`
		Default  string            `json:"default"`
		Map      map[string]string `json:"map"`
		Mode     string            `json:"mode"`
	}
	_ = w.Bind("hanilPrinters", func() info {
		prMu.Lock()
		m := loadPrinterMap()
		prMu.Unlock()
		return info{Printers: listPrinters(), Default: defaultPrinter(), Map: m, Mode: conf.Print}
	})
	_ = w.Bind("hanilSetPrinter", func(form, printer string) error { return setPrinterFor(form, printer) })
	_ = w.Bind("hanilPrint", func(printer string) error { return printTo(w, printer) })
}
