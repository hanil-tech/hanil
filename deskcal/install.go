package main

// ── 스스로 설치(판 바꾸기) ──────────────────────────────────
//
//	⚠ 새 판 exe 는 보통 «다운로드» 폴더에 들어간다. 그런데 시작프로그램·바탕화면 아이콘은
//	  **처음 둔 자리의 예전 exe** 를 가리키므로, 그대로 두면 계속 예전 판이 뜬다.
//	⭐ 그래서 판을 한 자리에 모은다: %LOCALAPPDATA%\HanilCal\app\hanil-cal.exe (라벨 발행기와 같은 방식)
//	  어디에 있는 exe 를 누르든 → 그 자리의 판보다 새것이면 그 자리에 덮어 설치하고 그것을 띄운다.

import (
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

func appDir() string { return filepath.Join(profileDir(), "app") }

// "1.10.0" > "1.9.3" 처럼 숫자로 견준다
func newer(a, b string) bool {
	pa, pb := strings.Split(a, "."), strings.Split(b, ".")
	for i := 0; i < len(pa) || i < len(pb); i++ {
		var x, y int
		if i < len(pa) {
			x, _ = strconv.Atoi(pa[i])
		}
		if i < len(pb) {
			y, _ = strconv.Atoi(pb[i])
		}
		if x != y {
			return x > y
		}
	}
	return false
}

// 참이면 이 프로세스는 할 일을 넘겼으니 끝내면 된다
func selfInstall(exePath string) bool {
	if runtime.GOOS != "windows" || exePath == "" {
		return false
	}
	target := filepath.Join(appDir(), "hanil-cal.exe")
	if strings.EqualFold(filepath.Clean(exePath), filepath.Clean(target)) {
		return false
	}
	vfile := filepath.Join(appDir(), "version.txt")
	inst := ""
	if b, err := os.ReadFile(vfile); err == nil {
		inst = strings.TrimSpace(string(b))
	}
	if _, err := os.Stat(target); err == nil && inst != "" && !newer(VERSION, inst) {
		logf("설치된 판(%s)을 띄웁니다 — 누른 exe: %s (%s)", inst, exePath, VERSION)
		return startExe(target)
	}
	logf("설치: %s (%s) → %s (설치돼 있던 판: %s)", exePath, VERSION, target, inst)
	//  ① 떠 있는 예전 판을 내린다(파일이 잡혀 있으면 못 덮는다)
	if _, ok := runningVersion(conf.Port); ok {
		askQuit(conf.Port)
		time.Sleep(1500 * time.Millisecond)
	}
	if err := os.MkdirAll(appDir(), 0o755); err != nil {
		logf("설치 폴더를 못 만듦: %v", err)
		return false
	}
	//  ② 복사 → 바꿔치기(도중에 끊겨도 반쪽 exe 가 남지 않게)
	tmp := target + ".new"
	if err := copyFile(exePath, tmp); err != nil {
		logf("복사 실패: %v", err)
		return false
	}
	var err error
	for i := 0; i < 20; i++ {
		_ = os.Remove(target)
		if err = os.Rename(tmp, target); err == nil {
			break
		}
		time.Sleep(300 * time.Millisecond)
	}
	if err != nil {
		logf("바꿔치기 실패: %v", err)
		_ = os.Remove(tmp)
		return false
	}
	_ = os.WriteFile(vfile, []byte(VERSION), 0o644)
	//  ③ 누른 exe 옆에 설정 파일이 있으면 옮겨 온다(설치된 자리에 아직 없을 때만)
	ini := filepath.Join(appDir(), iniName)
	if _, err := os.Stat(ini); os.IsNotExist(err) {
		if copyFile(filepath.Join(filepath.Dir(exePath), iniName), ini) == nil {
			logf("설정 파일을 옮겨 옴")
		}
	}
	return startExe(target)
}

func startExe(p string) bool {
	c := exec.Command(p, os.Args[1:]...)
	c.Dir = filepath.Dir(p)
	if err := c.Start(); err != nil {
		logf("설치된 exe 를 못 띄움: %v", err)
		return false
	}
	return true
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}
