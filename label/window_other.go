//go:build !windows

package main

import "errors"

// 윈도우가 아니면 독자 창이 없다 — 시험에서는 브라우저 창으로 띄운다
func runWindow(url string) error { return errors.New("독자 창은 윈도우에서만") }

func focusWindow() bool { return false }
