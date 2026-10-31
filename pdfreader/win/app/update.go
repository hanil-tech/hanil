//go:build windows

package main

// 🔄 자동 업데이트 — 저장소(release/hanil-pdf.json)에 더 새 판이 올라오면 뒤에서 받아 깔아 둔다
//
//	1. 켜고 20초 뒤, 그 뒤로 6시간마다 판 정보(json)를 읽는다(저장소 두 곳 중 더 새것)
//	2. 새 판이면 exe 를 받아 크기·SHA-256 을 맞춰 보고 「hanil-pdf-v….exe --update」로 조용히 깐다
//	   (떠 있는 exe 는 이름만 비켜 두고 새것을 넣는다 — copyFile)
//	3. 창에 「새 판을 받았습니다 — 다시 시작」을 띄운다. 그냥 두어도 다음에 켤 때 새 판으로 뜬다
//	끄기: 환경 설정 → 정보 → 자동 업데이트(HKCU\Software\HanilPDF AutoUpdate=0)

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"golang.org/x/sys/windows/registry"
)

// 판 정보를 읽는 곳 — 앞의 것부터(둘 다 읽어 더 새 판을 고른다). HKCU\Software\HanilPDF UpdateURL 로 바꿀 수 있다
var updateBases = []string{
	"https://raw.githubusercontent.com/hanil-tech/hanil/claude/magical-pascal-b2ksp0/release/",
	"https://raw.githubusercontent.com/hanil-tech/hanil/HEAD/release/",
}

type updInfo struct {
	Version string `json:"version"`
	File    string `json:"file"`
	Size    int64  `json:"size"`
	SHA256  string `json:"sha256"`
	Notes   string `json:"notes"`
	base    string
}

var (
	updMu    sync.Mutex
	updReady string //  받아 깐 새 판(없으면 "")
	updNotes string
)

func regStr(name string) string {
	k, err := registry.OpenKey(registry.CURRENT_USER, `Software\HanilPDF`, registry.QUERY_VALUE)
	if err != nil {
		return ""
	}
	defer k.Close()
	v, _, _ := k.GetStringValue(name)
	return v
}

func autoUpdateOn() bool { return regStr("AutoUpdate") != "0" }

func setAutoUpdate(on bool) {
	v := "1"
	if !on {
		v = "0"
	}
	_ = setStr(registry.CURRENT_USER, `Software\HanilPDF`, "AutoUpdate", v)
}

func portBusy() bool {
	c, err := net.DialTimeout("tcp", "127.0.0.1:"+strconv.Itoa(PORT), 300*time.Millisecond)
	if err != nil {
		return false
	}
	c.Close()
	return true
}

// 옛 판 exe(이름만 비켜 둔 것)와 받은 설치 파일 치우기
func cleanOld() {
	if m, _ := filepath.Glob(appExe() + ".old-*"); m != nil {
		for _, f := range m {
			_ = os.Remove(f)
		}
	}
	if ents, err := os.ReadDir(updDir()); err == nil {
		for _, e := range ents {
			if !strings.Contains(e.Name(), "v"+VERSION+".") || strings.HasSuffix(e.Name(), ".part") {
				_ = os.Remove(filepath.Join(updDir(), e.Name()))
			}
		}
	}
}

func updDir() string { return filepath.Join(installDir(), "update") }

func autoUpdateLoop() {
	time.Sleep(20 * time.Second)
	for {
		if autoUpdateOn() {
			if msg, err := checkUpdate(false); err != nil {
				logf("업데이트 확인: %v", err)
			} else if msg != "" {
				logf("업데이트: %s", msg)
			}
		}
		time.Sleep(6 * time.Hour)
	}
}

func fetchInfo(cl *http.Client) (*updInfo, error) {
	bases := updateBases
	if u := regStr("UpdateURL"); u != "" {
		bases = []string{strings.TrimRight(u, "/") + "/"}
	}
	var best *updInfo
	var lastErr error
	for _, b := range bases {
		r, err := cl.Get(b + "hanil-pdf.json?t=" + strconv.FormatInt(time.Now().Unix(), 10))
		if err != nil {
			lastErr = err
			continue
		}
		var in updInfo
		err = json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&in)
		r.Body.Close()
		if r.StatusCode != 200 || err != nil || in.Version == "" || in.File == "" {
			if lastErr == nil {
				lastErr = fmt.Errorf("%s: %d", b, r.StatusCode)
			}
			continue
		}
		in.base = b
		if best == nil || newer(in.Version, best.Version) {
			x := in
			best = &x
		}
	}
	if best == nil {
		return nil, lastErr
	}
	return best, nil
}

var updRun sync.Mutex

// 새 판이 있으면 받아서 깐다. 돌려주는 글은 사람에게 보일 안내(새 판이 없으면 manual 일 때만)
func checkUpdate(manual bool) (string, error) {
	if !updRun.TryLock() {
		return "이미 확인하는 중입니다.", nil
	}
	defer updRun.Unlock()
	updMu.Lock()
	ready := updReady
	updMu.Unlock()
	cl := &http.Client{Timeout: 10 * time.Minute, Transport: &http.Transport{Proxy: http.ProxyFromEnvironment, ResponseHeaderTimeout: 30 * time.Second}}
	in, err := fetchInfo(cl)
	if err != nil {
		return "", fmt.Errorf("판 정보를 읽지 못했습니다(인터넷 연결을 확인하세요): %v", err)
	}
	if !newer(in.Version, VERSION) || (ready != "" && !newer(in.Version, ready)) {
		if ready != "" {
			return "새 판 v" + ready + " 을 이미 받아 두었습니다. 다시 시작하면 새 판으로 뜹니다.", nil
		}
		if manual {
			return "지금 판(v" + VERSION + ")이 가장 새 판입니다.", nil
		}
		return "", nil
	}
	if strings.ContainsAny(in.File, `/\:`) || !strings.HasSuffix(strings.ToLower(in.File), ".exe") {
		return "", fmt.Errorf("판 정보의 파일 이름이 이상합니다: %s", in.File)
	}
	if in.Size <= 0 || len(in.SHA256) != 64 {
		return "", fmt.Errorf("판 정보에 크기·검사값이 없습니다")
	}
	logf("새 판 v%s 받기 시작 %s", in.Version, in.base+in.File)
	if err := os.MkdirAll(updDir(), 0o755); err != nil {
		return "", err
	}
	dst := filepath.Join(updDir(), in.File)
	r, err := cl.Get(in.base + in.File)
	if err != nil {
		return "", fmt.Errorf("새 판을 받지 못했습니다: %v", err)
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return "", fmt.Errorf("새 판을 받지 못했습니다: HTTP %d", r.StatusCode)
	}
	f, err := os.Create(dst + ".part")
	if err != nil {
		return "", err
	}
	h := sha256.New()
	n, err := io.Copy(io.MultiWriter(f, h), io.LimitReader(r.Body, in.Size+1))
	f.Close()
	if err != nil || n != in.Size || !strings.EqualFold(hex.EncodeToString(h.Sum(nil)), in.SHA256) {
		_ = os.Remove(dst + ".part")
		if err == nil {
			err = fmt.Errorf("받은 파일이 맞지 않습니다(크기 %d / %d 또는 검사값 다름)", n, in.Size)
		}
		return "", err
	}
	_ = os.Remove(dst)
	if err := os.Rename(dst+".part", dst); err != nil {
		return "", err
	}
	c := exec.Command(dst, "--update")
	c.Dir = updDir()
	hideWindow(c)
	if err := c.Run(); err != nil {
		return "", fmt.Errorf("새 판을 깔지 못했습니다: %v", err)
	}
	if installedVersion() != in.Version {
		return "", fmt.Errorf("새 판을 깔지 못했습니다(설치 판 %s)", installedVersion())
	}
	updMu.Lock()
	updReady, updNotes = in.Version, in.Notes
	updMu.Unlock()
	logf("새 판 v%s 깔았음", in.Version)
	notifyUpdate()
	return "새 판 v" + in.Version + " 을 받아 깔았습니다. 다시 시작하면 새 판으로 뜹니다.", nil
}

// 창에 알리기 — 리더가 「다시 시작」 단추를 띄운다
func notifyUpdate() {
	updMu.Lock()
	v, notes := updReady, updNotes
	updMu.Unlock()
	if v == "" {
		return
	}
	wvMu.Lock()
	w := wv
	wvMu.Unlock()
	if w == nil {
		return
	}
	b, _ := json.Marshal(map[string]string{"version": v, "notes": notes})
	w.Dispatch(func() {
		w.Eval("window.HANIL_HOST && window.HANIL_HOST.updated && window.HANIL_HOST.updated(" + string(b) + ")")
	})
}

// 다시 시작 — 새 판을 「--restart」로 띄우고 이 창은 닫는다(저장 확인은 리더가 먼저 함)
func restartApp() {
	if startDetached(appExe(), "--restart") {
		allowClose = true
		wvMu.Lock()
		w := wv
		wvMu.Unlock()
		if w != nil {
			pPostMsg.Call(uintptr(w.Window()), 0x0010, 0, 0)
		}
	}
}
