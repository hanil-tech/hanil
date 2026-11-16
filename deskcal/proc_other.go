//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
)

func hideWindow(c *exec.Cmd) {}

// 윈도우가 아니면(시험) 알림창 대신 오류 출력으로
func msgBox(title, text string) { fmt.Fprintln(os.Stderr, title+": "+text) }
