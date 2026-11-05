package main

// ── 이 PC 에 남기는 것 ──────────────────────────────────────
//
//	%LOCALAPPDATA%\HanilCal\
//	  data.json    — 날짜별 메모·색, 화면 설정(달력 화면이 통째로 읽고 쓴다)
//	  session.dat  — 포털 로그인 세션 쿠키(DPAPI 로 암호화 — 이 PC·이 윈도우 사용자만 풀린다)
//
//	⚠ 메모는 이 PC 에만 있다(포털에 올리지 않는다). 다른 PC 로 옮길 때는 data.json 을 복사한다.

import (
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

func dataFile() string    { return filepath.Join(profileDir(), "data.json") }
func sessionFile() string { return filepath.Join(profileDir(), "session.dat") }

var dataMu sync.Mutex

func loadData() []byte {
	dataMu.Lock()
	defer dataMu.Unlock()
	b, err := os.ReadFile(dataFile())
	if err != nil || !json.Valid(b) {
		//  ⚠ 깨졌으면 지난번 것으로
		if b2, err2 := os.ReadFile(dataFile() + ".bak"); err2 == nil && json.Valid(b2) {
			return b2
		}
		return []byte("{}")
	}
	return b
}

func saveData(b []byte) error {
	if !json.Valid(b) {
		return errors.New("올바른 JSON 이 아닙니다")
	}
	dataMu.Lock()
	defer dataMu.Unlock()
	_ = os.MkdirAll(profileDir(), 0o755)
	p := dataFile()
	//  ⭐ 바꿔치기로 쓴다 — 쓰다가 전원이 나가도 반쪽 파일이 남지 않게. 바로 앞 것은 .bak 로 남긴다.
	tmp := p + ".new"
	if err := os.WriteFile(tmp, b, 0o600); err != nil {
		return err
	}
	if _, err := os.Stat(p); err == nil {
		_ = os.Remove(p + ".bak")
		_ = os.Rename(p, p+".bak")
	}
	return os.Rename(tmp, p)
}

// ── 포털 세션 쿠키 ─────────────────────────────────────────
//
//	⭐ 표준 cookiejar 는 꺼낼 수가 없어 껐다 켜면 다시 로그인해야 한다 → 포털 하나만 상대하니 작은 상자를 따로 둔다.
//	⚠ 사내 주소·바깥 도메인 둘 다 같은 포털 서버라 한 상자를 같이 쓴다(안 맞으면 다시 로그인하면 된다).
type cookieBox struct {
	mu sync.Mutex
	m  map[string]savedCookie
}

type savedCookie struct {
	Name    string    `json:"n"`
	Value   string    `json:"v"`
	Path    string    `json:"p,omitempty"`
	Expires time.Time `json:"e,omitempty"`
}

func newCookieBox() *cookieBox {
	b := &cookieBox{m: map[string]savedCookie{}}
	if enc, err := os.ReadFile(sessionFile()); err == nil {
		if raw, err := unprotect(enc); err == nil {
			var list []savedCookie
			if json.Unmarshal(raw, &list) == nil {
				for _, c := range list {
					b.m[c.Name] = c
				}
			}
		}
	}
	return b
}

func (b *cookieBox) set(cs []*http.Cookie) {
	if len(cs) == 0 {
		return
	}
	b.mu.Lock()
	now := time.Now()
	for _, c := range cs {
		exp := c.Expires
		if c.MaxAge > 0 {
			exp = now.Add(time.Duration(c.MaxAge) * time.Second)
		}
		if c.MaxAge < 0 || (!exp.IsZero() && exp.Before(now)) || c.Value == "" {
			delete(b.m, c.Name)
			continue
		}
		b.m[c.Name] = savedCookie{Name: c.Name, Value: c.Value, Path: c.Path, Expires: exp}
	}
	b.mu.Unlock()
	b.save()
}

func (b *cookieBox) list() []*http.Cookie {
	b.mu.Lock()
	defer b.mu.Unlock()
	now := time.Now()
	out := []*http.Cookie{}
	for k, c := range b.m {
		if !c.Expires.IsZero() && c.Expires.Before(now) {
			delete(b.m, k)
			continue
		}
		out = append(out, &http.Cookie{Name: c.Name, Value: c.Value})
	}
	return out
}

func (b *cookieBox) empty() bool { return len(b.list()) == 0 }

func (b *cookieBox) clear() {
	b.mu.Lock()
	b.m = map[string]savedCookie{}
	b.mu.Unlock()
	_ = os.Remove(sessionFile())
}

func (b *cookieBox) save() {
	b.mu.Lock()
	list := make([]savedCookie, 0, len(b.m))
	for _, c := range b.m {
		list = append(list, c)
	}
	b.mu.Unlock()
	raw, _ := json.Marshal(list)
	enc, err := protect(raw)
	if err != nil {
		logf("세션 암호화 실패: %v", err)
		return
	}
	_ = os.MkdirAll(profileDir(), 0o755)
	_ = os.WriteFile(sessionFile(), enc, 0o600)
}
