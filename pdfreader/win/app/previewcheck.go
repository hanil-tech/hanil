//go:build windows

package main

// 🔍 탐색기 미리 보기 점검 — 그 PC 에서 어디가 막혔는지 글로 보여 준다
//
//	① 윈도우가 .pdf(그리고 기본 앱의 ProgID)에 쓰는 그림·미리 보기 처리기가 우리 것인가(AssocQueryString)
//	② 우리 DLL·pdfium 이 제자리에 있나(백신이 지웠나)
//	③ 우리 처리기를 이 프로그램 안에서 직접 불러 그 PDF 의 그림을 실제로 만들어 본다(탐색기가 하는 그대로)
//	④ 파일 속성(온라인 전용 등)

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	shlwapi       = windows.NewLazySystemDLL("shlwapi.dll")
	pAssocQuery   = shlwapi.NewProc("AssocQueryStringW")
	pStreamOnFile = shlwapi.NewProc("SHCreateStreamOnFileEx")
	gdi32         = windows.NewLazySystemDLL("gdi32.dll")
	pDeleteObj    = gdi32.NewProc("DeleteObject")

	iidClassFactory    = windows.GUID{Data1: 0x00000001, Data4: [8]byte{0xC0, 0, 0, 0, 0, 0, 0, 0x46}}
	iidThumbProvider   = windows.GUID{Data1: 0xe357fccd, Data2: 0xa995, Data3: 0x4576, Data4: [8]byte{0xb0, 0x1f, 0x23, 0x46, 0x30, 0x15, 0x4e, 0x96}}
	iidInitWithStream  = windows.GUID{Data1: 0xb824b49d, Data2: 0x22ac, Data3: 0x4161, Data4: [8]byte{0xac, 0x8a, 0x99, 0x16, 0xe8, 0xfa, 0x3f, 0x7f}}
	clsidHanilThumb, _ = windows.GUIDFromString(clsThumb)
)

// 윈도우가 assoc(.pdf 또는 ProgID)에 쓰는 셸 확장(iid) — 없으면 ""
func assocExt(assoc, iid string) string {
	buf := make([]uint16, 260)
	n := uint32(len(buf))
	r, _, _ := pAssocQuery.Call(0, 16 /* ASSOCSTR_SHELLEXTENSION */, uintptr(unsafe.Pointer(u16(assoc))), uintptr(unsafe.Pointer(u16(iid))), uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&n)))
	if r != 0 {
		return ""
	}
	return windows.UTF16ToString(buf)
}

func clsName(c string) string {
	switch {
	case c == "":
		return "없음"
	case strings.EqualFold(c, clsThumb):
		return "✅ 한일 PDF 리더(그림)"
	case strings.EqualFold(c, clsPreview):
		return "✅ 한일 PDF 리더(미리 보기 창)"
	}
	if k := regDefault(`CLSID\` + c); k != "" {
		return "❌ 다른 프로그램: " + k + " " + c
	}
	return "❌ 다른 프로그램 " + c
}

// 우리 처리기로 그 파일의 그림을 직접 만들어 본다
func tryThumb(dll, pdf string) (string, error) {
	d, err := windows.LoadDLL(dll)
	if err != nil {
		return "", fmt.Errorf("DLL 을 읽지 못함(백신이 막았거나 지움?): %v", err)
	}
	defer d.Release()
	gco, err := d.FindProc("DllGetClassObject")
	if err != nil {
		return "", err
	}
	var cf unsafe.Pointer
	if r, _, _ := gco.Call(uintptr(unsafe.Pointer(&clsidHanilThumb)), uintptr(unsafe.Pointer(&iidClassFactory)), uintptr(unsafe.Pointer(&cf))); r != 0 || cf == nil {
		return "", fmt.Errorf("DllGetClassObject %#x", r)
	}
	defer comCall(cf, 2)
	var tp unsafe.Pointer
	if r := comCall(cf, 3, 0, uintptr(unsafe.Pointer(&iidThumbProvider)), uintptr(unsafe.Pointer(&tp))); r != 0 || tp == nil {
		return "", fmt.Errorf("CreateInstance %#x", r)
	}
	defer comCall(tp, 2)
	var ini unsafe.Pointer
	if r := comCall(tp, 0, uintptr(unsafe.Pointer(&iidInitWithStream)), uintptr(unsafe.Pointer(&ini))); r != 0 || ini == nil {
		return "", fmt.Errorf("IInitializeWithStream %#x", r)
	}
	defer comCall(ini, 2)
	var stm unsafe.Pointer
	if r, _, _ := pStreamOnFile.Call(uintptr(unsafe.Pointer(u16(pdf))), 0x40 /* STGM_READ|SHARE_DENY_NONE */, 0, 0, 0, uintptr(unsafe.Pointer(&stm))); r != 0 || stm == nil {
		return "", fmt.Errorf("파일을 열지 못함 %#x", r)
	}
	defer comCall(stm, 2)
	t0 := time.Now()
	if r := comCall(ini, 3, uintptr(stm), 0); r != 0 {
		return "", fmt.Errorf("Initialize %#x", r)
	}
	var hbmp, alpha uintptr
	if r := comCall(tp, 3, 256, uintptr(unsafe.Pointer(&hbmp)), uintptr(unsafe.Pointer(&alpha))); r != 0 || hbmp == 0 {
		return "", fmt.Errorf("GetThumbnail %#x (pdfium.dll 을 못 읽었거나 PDF 를 못 그림)", uint32(r))
	}
	pDeleteObj.Call(hbmp)
	return fmt.Sprintf("✅ 그림 만들기 성공 (%.1f초)", time.Since(t0).Seconds()), nil
}

func previewCheck(pdf string) string {
	var b strings.Builder
	line := func(f string, a ...interface{}) { fmt.Fprintf(&b, f+"\n", a...) }
	line("한일 PDF 리더 v%s · 탐색기 미리 보기 점검", VERSION)
	line("")
	pids := pdfUserProgIDs()
	line("① 윈도우가 쓰는 처리기")
	if len(pids) > 0 {
		line("  · PDF 기본 앱: %s", strings.Join(pids, ", "))
	} else {
		line("  · PDF 기본 앱: 한일 PDF 리더(또는 지정 안 됨)")
	}
	for _, a := range append([]string{".pdf"}, pids...) {
		line("  · %s 큰 아이콘 그림: %s", a, clsName(assocExt(a, "{"+strings.Trim(iidThumb, "{}")+"}")))
		line("  · %s 미리 보기 창: %s", a, clsName(assocExt(a, "{"+strings.Trim(iidPreview, "{}")+"}")))
		//  레지스트리에 적힌 그대로(위가 「없음」인데 여기 있으면 윈도우가 다른 것을 먼저 고른 것)
		line("      레지스트리 %s\\shellex 그림=%s", a, clsName(regDefault(a+`\shellex\`+iidThumb)))
	}
	line("  · SystemFileAssociations\\.pdf 그림=%s", clsName(regDefault(`SystemFileAssociations\.pdf\shellex\`+iidThumb)))
	line("")
	line("② 미리 보기 파일")
	dll := filepath.Join(engineDir(), "hanil-pdf-preview.dll")
	for _, f := range []string{dll, filepath.Join(engineDir(), "pdfium.dll")} {
		if st, err := os.Stat(f); err == nil {
			line("  ✅ %s (%d KB)", f, st.Size()/1024)
		} else {
			line("  ❌ %s 없음 — 백신이 지웠을 수 있습니다(Windows 보안 → 보호 기록)", f)
		}
	}
	line("  · 등록된 DLL: %s", regDefault(`CLSID\`+clsThumb+`\InprocServer32`))
	line("")
	line("③ 실제로 그림 만들기")
	if pdf == "" {
		line("  · 시험할 PDF 가 없습니다 — PDF 를 하나 연 뒤 다시 누르세요")
	} else {
		line("  · %s", pdf)
		if p, err := windows.UTF16PtrFromString(pdf); err == nil {
			if a, err := windows.GetFileAttributes(p); err == nil {
				if a&0x00400000 != 0 || a&0x00001000 != 0 || a&0x00040000 != 0 {
					line("  ⚠ 이 파일은 「온라인 전용」(Synology Drive·OneDrive)입니다 — 탐색기가 그림을 만들 때 내려받아야 합니다")
				}
			}
		}
		if m, err := tryThumb(dll, pdf); err != nil {
			line("  ❌ %v", err)
		} else {
			line("  %s", m)
		}
	}
	return b.String()
}

// HKCR 의 기본값(HKCU 가 앞) — 처리기 이름 보기용
func regDefault(sub string) string {
	for _, root := range []windows.Handle{windows.HKEY_CURRENT_USER, windows.HKEY_LOCAL_MACHINE} {
		var k windows.Handle
		if windows.RegOpenKeyEx(root, u16(`Software\Classes\`+sub), 0, windows.KEY_READ, &k) != nil {
			continue
		}
		buf := make([]uint16, 512)
		n := uint32(len(buf) * 2)
		var typ uint32
		err := windows.RegQueryValueEx(k, nil, nil, &typ, (*byte)(unsafe.Pointer(&buf[0])), &n)
		windows.RegCloseKey(k)
		if err == nil {
			return windows.UTF16ToString(buf)
		}
	}
	return ""
}

var _ = syscall.SyscallN
