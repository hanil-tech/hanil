//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
	"syscall"
)

// 리눅스·맥에서는 창이 없다(여기서는 시험만 한다)
func hideWindow(c *exec.Cmd) {
	if c.SysProcAttr == nil {
		c.SysProcAttr = &syscall.SysProcAttr{}
	}
	c.SysProcAttr.Setpgid = true
}

func msgBox(title, text string) {
	fmt.Fprintln(os.Stderr, title+": "+text)
}
