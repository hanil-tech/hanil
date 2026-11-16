//go:build windows

package main

import (
	"os/exec"
	"syscall"
	"unsafe"
)

// ⚠ 창 없이 띄운다 — 검은 명령창이 같이 뜨면 현장에서 실수로 닫는다.
const createNoWindow = 0x08000000

func hideWindow(c *exec.Cmd) {
	c.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
}

// 브라우저를 못 찾았을 때처럼 **화면에 띄울 곳이 없는** 오류는 윈도우 알림창으로 알린다.
func msgBox(title, text string) {
	u := syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
	t, _ := syscall.UTF16PtrFromString(text)
	c, _ := syscall.UTF16PtrFromString(title)
	const mbIconWarning = 0x30
	_, _, _ = u.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), mbIconWarning)
}
