//go:build !windows

package main

// 윈도우가 아니면 바로가기를 만들 곳이 없다(여기서는 시험만 한다)
func ensureShortcuts(exe string, autostart bool) {}

func cleanupStale(prof string, pid int, killOld bool) string { return "" }
