package main

// 🔄 자동 업데이트 — 저장소(release/hanil-label.json)에 더 새 판이 올라오면 뒤에서 받아 바꾼다(PDF 리더와 같은 방식)
//
//	사용자 「다시 다운 안 받고 업그레이드되면 자동으로 확인해서 업그레이드되게」 (바탕화면 달력 deskcal/update.go 와 같은 것)
//	1. 켤 때 한 번 — 30초 뒤(안 되면 1분 간격으로 두 번 더) 판 정보(json)를 읽는다(저장소 두 곳 중 더 새 판)
//	2. 새 판이면 exe 를 %LOCALAPPDATA%\HanilLabel\update\ 로 받아 크기·SHA-256 을 맞춰 본다
//	3. 키오스크가 「한가할 때」 — 3분 동안 아무도 안 써서 언어 고르기 화면으로 돌아갈 때(page.html) — 받은 exe 를 띄운다 →
//	   그 exe 가 스스로 설치(install.go: 떠 있는 예전 판을 내리고 app\ 에 덮어쓰기)하고 새 판으로 다시 뜬다.
//	   ⚠ 라벨을 찾거나 뽑는 중에는 절대 안 바꾼다. 계정·설정·프린터 고른 것은 그대로.
//	끄기: hanil-label.ini 에 AUTOUPDATE=0

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"
)

// 판 정보를 읽는 곳 — 둘 다 읽어 더 새 판을 고른다. hanil-label.ini 의 UPDATEURL 로 바꿀 수 있다
var updateBases = []string{
	"https://raw.githubusercontent.com/hanil-tech/hanil/claude/magical-pascal-b2ksp0/release/",
	"https://raw.githubusercontent.com/hanil-tech/hanil/HEAD/release/",
}

const updateManifest = "hanil-label.json"

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
	updReady string //  받아 둔 새 판 판 번호
	updExe   string //  받아 둔 새 판 exe
	updNotes string
	updRun   sync.Mutex
)

func updReadyVer() string  { v, _ := updateState(); return v }
func updNotesText() string { _, n := updateState(); return n }

func updDir() string { return filepath.Join(profileDir(), "update") }

func updateState() (string, string) {
	updMu.Lock()
	defer updMu.Unlock()
	return updReady, updNotes
}

func autoUpdateLoop() {
	//  ⚠ 윈도우에서만 — 시험(HANILLABEL_UPDATE_TEST=1)은 리눅스에서도 바로
	test := os.Getenv("HANILLABEL_UPDATE_TEST") == "1"
	if (runtime.GOOS != "windows" && !test) || !conf.AutoUpdate {
		return
	}
	cleanUpdates()
	//  ⭐ 켤 때 한 번만 확인한다(사용자 「실행할 때만 체크하면 되지」).
	//    윈도우가 막 켜졌을 때는 인터넷이 아직 안 붙어 있을 수 있다 → 30초 뒤, 안 되면 1분 간격으로 두 번 더.
	wait, again := 30*time.Second, time.Minute
	if test {
		wait, again = time.Second, time.Second
	}
	time.Sleep(wait)
	for try := 1; try <= 3; try++ {
		msg, err := checkUpdate()
		if err == nil {
			if msg != "" {
				logf("업데이트: %s", msg)
			}
			return
		}
		logf("업데이트 확인(%d/3): %v", try, err)
		time.Sleep(again)
	}
}

// 지난번에 받아 쓴 설치 파일 치우기
func cleanUpdates() {
	ents, err := os.ReadDir(updDir())
	if err != nil {
		return
	}
	for _, e := range ents {
		_ = os.Remove(filepath.Join(updDir(), e.Name()))
	}
}

func fetchInfo(cl *http.Client) (*updInfo, error) {
	bases := updateBases
	if conf.UpdateURL != "" {
		bases = []string{strings.TrimRight(conf.UpdateURL, "/") + "/"}
	}
	var best *updInfo
	var lastErr error
	for _, b := range bases {
		r, err := cl.Get(b + updateManifest + "?t=" + strconv.FormatInt(time.Now().Unix(), 10))
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

// 새 판이 있으면 받아 둔다(바꾸기는 키오스크가 한가할 때 applyUpdate 로)
func checkUpdate() (string, error) {
	if !updRun.TryLock() {
		return "", nil
	}
	defer updRun.Unlock()
	cl := &http.Client{Timeout: 10 * time.Minute, Transport: &http.Transport{Proxy: http.ProxyFromEnvironment, ResponseHeaderTimeout: 30 * time.Second}}
	in, err := fetchInfo(cl)
	if err != nil {
		return "", fmt.Errorf("판 정보를 읽지 못했습니다: %v", err)
	}
	ready, _ := updateState()
	if !newer(in.Version, VERSION) || (ready != "" && !newer(in.Version, ready)) {
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
	updMu.Lock()
	updReady, updExe, updNotes = in.Version, dst, in.Notes
	updMu.Unlock()
	return "새 판 v" + in.Version + " 을 받아 두었습니다(키오스크가 한가할 때 바꿉니다)", nil
}

// 받아 둔 새 판으로 바꾼다 — 새 exe 가 이 프로그램을 내리고(cleanupStale) 설치한 뒤 새 판으로 다시 띄운다
func applyUpdate() bool {
	updMu.Lock()
	exe, v := updExe, updReady
	updMu.Unlock()
	if exe == "" {
		return false
	}
	if _, err := os.Stat(exe); err != nil {
		return false
	}
	logf("새 판 v%s 으로 바꿉니다", v)
	c := exec.Command(exe, "--update")
	c.Dir = filepath.Dir(exe)
	if err := c.Start(); err != nil {
		logf("새 판을 못 띄움: %v", err)
		return false
	}
	go c.Wait()
	return true
}
