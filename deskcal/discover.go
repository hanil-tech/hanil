package main

// ── 포털에 이미 있는 달력(일정) 찾기 ────────────────────────
//
//	사용자 「포털의 달력 자료가 안 나오네?」 — 포털에는 원래 달력 메뉴가 있다.
//	⚠ 포털 원본이 이 저장소에 없어 그 API 주소를 모른다 → 로그인한 세션으로 **포털 화면을 읽어 스스로 찾는다.**
//	  ① 달력일 만한 화면(/calendar · /schedule · /m …)의 HTML 에서 '/api/…(cal|sched|event|plan|agenda)…' 주소를 뽑고
//	  ② 흔한 이름(/api/calendar · /api/schedule …)도 함께 GET 으로 물어
//	  ③ JSON 으로 «날짜가 든 줄 목록» 을 돌려주는 첫 주소를 고른다(읽기만 — GET).
//	찾은 주소는 discovered.json 에 적어 두고, 관문은 그 주소(GET)만 더 통과시킨다.
//	달력 화면이 그 주소의 JSON 을 일정 모양으로 바꿔 「포털 달력」 으로 보인다.
//	⚠ 못 찾으면 무엇을 물어봤는지(주소·답 코드·앞부분)를 보여 준다 — 그것을 보내 주면 맞춘다.

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

type probeRow struct {
	Path   string `json:"path"`
	Status int    `json:"status"`
	Rows   int    `json:"rows"`
	Note   string `json:"note"`
}

type discovered struct {
	API  string     `json:"api"`  //  찾은 일정 API (예: /api/schedule/list)
	Page string     `json:"page"` //  그 일정이 보이는 포털 화면(「포털에서 열기」)
	At   int64      `json:"at"`
	Log  []probeRow `json:"log"`
}

var (
	discMu   sync.Mutex
	discNow  discovered
	discBusy bool
)

func discFile() string { return filepath.Join(profileDir(), "discovered.json") }

func loadDiscovered() {
	if b, err := os.ReadFile(discFile()); err == nil {
		discMu.Lock()
		_ = json.Unmarshal(b, &discNow)
		discMu.Unlock()
	}
}

func discoveredAPI() string {
	discMu.Lock()
	defer discMu.Unlock()
	return discNow.API
}

var (
	reAPIRef  = regexp.MustCompile(`["'\x60](/api/[A-Za-z0-9_\-/.]*(?:[Cc]al|[Ss]ched|[Ee]vent|[Pp]lan|[Aa]genda|[Dd]iary|[Hh]oliday)[A-Za-z0-9_\-/.]*)`)
	reCalPage = regexp.MustCompile(`href=["'](/[A-Za-z0-9_\-/]*(?:cal|sched|event|plan|agenda|diary)[A-Za-z0-9_\-/]*)["']`)
)

// 흔한 이름들 — 화면에서 못 뽑았을 때도 물어본다
var guessAPIs = []string{
	"/api/calendar", "/api/calendar/events", "/api/calendar/list", "/api/calendars",
	"/api/schedule", "/api/schedules", "/api/schedule/list", "/api/schedule/month", "/api/schedules/list",
	"/api/events", "/api/event/list", "/api/plan", "/api/plans", "/api/agenda", "/api/company/schedule",
}
var guessPages = []string{"/calendar", "/schedule", "/schedules", "/cal", "/plan", "/agenda", "/m", "/mywork", "/dashboard", "/"}

// 일정 같은 줄이 몇 개인가 — 배열이거나 {items|events|list|rows|data|schedules|result}
func countRows(b []byte) (int, string) {
	var v any
	if json.Unmarshal(b, &v) != nil {
		return -1, "JSON 아님"
	}
	arr := findArray(v, 0)
	if arr == nil {
		return 0, "목록 없음"
	}
	dated := 0
	reDate := regexp.MustCompile(`^\d{4}[-./]\d{1,2}[-./]\d{1,2}|^\d{8}$`)
	for _, it := range arr {
		m, ok := it.(map[string]any)
		if !ok {
			continue
		}
		for _, x := range m {
			if s, ok := x.(string); ok && reDate.MatchString(s) {
				dated++
				break
			}
		}
	}
	if len(arr) > 0 && dated == 0 {
		return 0, "날짜가 든 줄이 없음"
	}
	return dated, ""
}

func findArray(v any, depth int) []any {
	if depth > 3 {
		return nil
	}
	switch t := v.(type) {
	case []any:
		return t
	case map[string]any:
		for _, k := range []string{"events", "items", "list", "rows", "data", "schedules", "schedule", "result", "results", "calendar"} {
			if x, ok := t[k]; ok {
				if a := findArray(x, depth+1); a != nil {
					return a
				}
			}
		}
	}
	return nil
}

func (g *gateway) portalGet(up *url.URL, p string) (int, []byte, string) {
	cl := &http.Client{Transport: g.transport(up), Timeout: 8 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	req, err := http.NewRequest(http.MethodGet, up.String()+p, nil)
	if err != nil {
		return 0, nil, ""
	}
	for _, c := range g.box.list() {
		req.AddCookie(c)
	}
	req.Header.Set("Accept", "application/json, text/html;q=0.9")
	res, err := cl.Do(req)
	if err != nil {
		return 0, nil, ""
	}
	defer res.Body.Close()
	b, _ := io.ReadAll(io.LimitReader(res.Body, 4<<20))
	return res.StatusCode, b, res.Header.Get("Content-Type")
}

// 포털 달력 찾기 — 로그인돼 있어야 한다. 몇 초 걸린다.
func (g *gateway) discover() discovered {
	discMu.Lock()
	if discBusy {
		d := discNow
		discMu.Unlock()
		return d
	}
	discBusy = true
	discMu.Unlock()
	defer func() { discMu.Lock(); discBusy = false; discMu.Unlock() }()

	out := discovered{At: time.Now().UnixMilli()}
	up := g.current()
	if up == nil {
		out.Log = append(out.Log, probeRow{Note: "포털에 연결되지 않음"})
		return out
	}
	now := time.Now()
	from := now.AddDate(0, -1, 0).Format("2006-01-02")
	to := now.AddDate(0, 2, 0).Format("2006-01-02")
	q := "?from=" + from + "&to=" + to + "&start=" + from + "&end=" + to + "&year=" + now.Format("2006") + "&month=" + now.Format("1") + "&ym=" + now.Format("2006-01")

	//  ① 화면에서 주소 뽑기
	apis := map[string]string{} //  API → 그것이 나온 화면
	pages := append([]string{}, guessPages...)
	seenPage := map[string]bool{}
	for i := 0; i < len(pages) && i < 24; i++ {
		pg := pages[i]
		if seenPage[pg] {
			continue
		}
		seenPage[pg] = true
		st, b, ct := g.portalGet(up, pg)
		if st != 200 || !strings.Contains(ct, "html") {
			continue
		}
		html := string(b)
		for _, m := range reAPIRef.FindAllStringSubmatch(html, -1) {
			a := strings.TrimRight(m[1], "/.")
			if strings.HasPrefix(a, "/api/cal/") { //  우리 조각(calendar-route.js)은 따로 쓴다
				continue
			}
			if _, ok := apis[a]; !ok {
				apis[a] = pg
			}
		}
		//  첫 화면·메뉴에서 달력 화면 링크를 더 찾는다
		for _, m := range reCalPage.FindAllStringSubmatch(html, -1) {
			if !seenPage[m[1]] {
				pages = append(pages, m[1])
			}
		}
	}
	for _, a := range guessAPIs {
		if _, ok := apis[a]; !ok {
			apis[a] = ""
		}
	}
	keys := make([]string, 0, len(apis))
	for k := range apis {
		keys = append(keys, k)
	}
	//  화면에서 뽑은 것을 먼저
	sort.SliceStable(keys, func(i, j int) bool { return apis[keys[i]] != "" && apis[keys[j]] == "" })

	//  ② 물어보기
	best, bestRows := "", 0
	for _, a := range keys {
		if strings.ContainsAny(a, "{}:") || strings.Count(a, "/") > 6 {
			continue
		}
		st, b, _ := g.portalGet(up, a+q)
		row := probeRow{Path: a, Status: st}
		if st == 200 {
			row.Rows, row.Note = countRows(b)
			if row.Rows <= 0 && len(b) > 0 {
				s := string(b)
				if len(s) > 120 {
					s = s[:120]
				}
				row.Note += " · " + s
			}
		}
		out.Log = append(out.Log, row)
		if row.Rows > bestRows {
			best, bestRows = a, row.Rows
		}
	}
	if best != "" {
		out.API = best
		out.Page = apis[best]
		if out.Page == "" || out.Page == "/" || out.Page == "/m" {
			out.Page = "/calendar"
		}
	}
	discMu.Lock()
	discNow = out
	discMu.Unlock()
	if b, err := json.MarshalIndent(out, "", " "); err == nil {
		_ = os.WriteFile(discFile(), b, 0o644)
	}
	logf("포털 달력 찾기: %q (%d줄) · 물어본 것 %d개", out.API, bestRows, len(out.Log))
	return out
}
