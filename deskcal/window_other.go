//go:build !windows

package main

// 윈도우가 아닌 곳(개발 PC·시험) — 창 없이 관문만 띄워 둔다. 브라우저로 http://127.0.0.1:18850/cal 을 열어 본다.

import (
	"fmt"
	"os"
	"os/signal"
)

func runWindow(url string, gw *gateway) error {
	fmt.Println("한일 바탕화면 달력 v" + VERSION + " — 창 없이 관문만: " + url)
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	select {
	case <-c:
	case <-quitCh:
	}
	return nil
}

var quitCh = make(chan struct{})

func focusWindow() bool                { return true }
func isPinned() bool                   { return false }
func hasDesktop() bool                 { return false }
func windowCmd(m, v string)            { fmt.Println("창 명령:", m, v) }
func quitApp()                         { close(quitCh) }
func openExternal(u string)            { fmt.Println("열기:", u) }
func showNotice(title, text, u string) { fmt.Println("알림:", title, "·", text, "·", u) }
