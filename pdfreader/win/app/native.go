//go:build windows

package main

// 🛡 바깥 프로그램(PowerShell·cmd·regsvr32·rundll32)을 숨겨 띄우지 않고 윈도우 함수로 직접 한다
//
//	⚠ 「숨긴 PowerShell -ExecutionPolicy Bypass -EncodedCommand」, 「cmd /c ping … & rmdir」,
//	  「숨긴 regsvr32」은 악성 코드가 흔히 쓰는 모양이라 윈도우 디펜더가 바이러스로 오진한다(1.6.0 까지).
//	  바로가기는 COM(IShellLinkW), 미리 보기 DLL 등록은 DllRegisterServer 를 직접 부르고, 링크 열기는 ShellExecute.

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	pCoInit     = ole32.NewProc("CoInitializeEx")
	pCoUninit   = ole32.NewProc("CoUninitialize")
	pCoCreate   = ole32.NewProc("CoCreateInstance")
	pShellExecW = shell32.NewProc("ShellExecuteW")
)

var (
	clsidShellLink = windows.GUID{Data1: 0x00021401, Data2: 0, Data3: 0, Data4: [8]byte{0xC0, 0, 0, 0, 0, 0, 0, 0x46}}
	iidShellLinkW  = windows.GUID{Data1: 0x000214F9, Data2: 0, Data3: 0, Data4: [8]byte{0xC0, 0, 0, 0, 0, 0, 0, 0x46}}
	iidPersistFile = windows.GUID{Data1: 0x0000010b, Data2: 0, Data3: 0, Data4: [8]byte{0xC0, 0, 0, 0, 0, 0, 0, 0x46}}
)

// COM 객체의 n 번째 함수 부르기
func comCall(obj unsafe.Pointer, n int, args ...uintptr) uintptr {
	vtbl := *(**[64]uintptr)(obj)
	r, _, _ := syscall.SyscallN(vtbl[n], append([]uintptr{uintptr(obj)}, args...)...)
	return r
}

// 바로가기(.lnk) 만들기
func makeShortcut(lnk, target, desc string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	if r, _, _ := pCoInit.Call(0, 2); r == 0 || r == 1 { //  S_OK · S_FALSE
		defer pCoUninit.Call()
	}
	var sl unsafe.Pointer
	if r, _, _ := pCoCreate.Call(uintptr(unsafe.Pointer(&clsidShellLink)), 0, 1, uintptr(unsafe.Pointer(&iidShellLinkW)), uintptr(unsafe.Pointer(&sl))); r != 0 || sl == nil {
		return fmt.Errorf("CoCreateInstance %#x", r)
	}
	defer comCall(sl, 2)                                               //  Release
	comCall(sl, 20, uintptr(unsafe.Pointer(u16(target))))              //  SetPath
	comCall(sl, 9, uintptr(unsafe.Pointer(u16(filepath.Dir(target))))) //  SetWorkingDirectory
	comCall(sl, 7, uintptr(unsafe.Pointer(u16(desc))))                 //  SetDescription
	comCall(sl, 17, uintptr(unsafe.Pointer(u16(target))), 0)           //  SetIconLocation
	var pf unsafe.Pointer
	if r := comCall(sl, 0, uintptr(unsafe.Pointer(&iidPersistFile)), uintptr(unsafe.Pointer(&pf))); r != 0 || pf == nil {
		return fmt.Errorf("IPersistFile %#x", r)
	}
	defer comCall(pf, 2)
	if r := comCall(pf, 6, uintptr(unsafe.Pointer(u16(lnk))), 1); r != 0 { //  Save
		return fmt.Errorf("Save %#x", r)
	}
	return nil
}

const lnkName = "한일 PDF 리더.lnk"

func shortcutDirs() []string {
	var out []string
	for _, id := range []*windows.KNOWNFOLDERID{windows.FOLDERID_Desktop, windows.FOLDERID_Programs} {
		if p, err := windows.KnownFolderPath(id, 0); err == nil && p != "" {
			out = append(out, p)
		}
	}
	return out
}

func ensureShortcuts(exe string) {
	for _, d := range shortcutDirs() {
		if err := makeShortcut(filepath.Join(d, lnkName), exe, "PDF 보기·찾기·고치기 — "+MAKER); err != nil {
			logf("바로가기 %s: %v", d, err)
		}
	}
}

func removeShortcuts() {
	for _, d := range shortcutDirs() {
		_ = os.Remove(filepath.Join(d, lnkName))
	}
}

// 미리 보기 DLL 등록·해제 — regsvr32 대신 DllRegisterServer 를 이 프로그램이 직접 부른다
func dllRegister(dll string, on bool) error {
	d, err := windows.LoadDLL(dll)
	if err != nil {
		return err
	}
	defer d.Release()
	name := "DllRegisterServer"
	if !on {
		name = "DllUnregisterServer"
	}
	p, err := d.FindProc(name)
	if err != nil {
		return err
	}
	if r, _, _ := p.Call(); r != 0 {
		return fmt.Errorf("%s %#x", name, r)
	}
	return nil
}

// 웹 주소·파일·설정 화면 열기(rundll32·explorer 대신)
func shellOpen(target string) error {
	if r, _, _ := pShellExecW.Call(0, uintptr(unsafe.Pointer(u16("open"))), uintptr(unsafe.Pointer(u16(target))), 0, 0, 1); r <= 32 {
		return fmt.Errorf("ShellExecute %d", r)
	}
	return nil
}
