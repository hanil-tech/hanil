# 📦 한일 포털 대용량 파일 (bigfile)

포털에서 **큰 파일(수 GB ~ 50GB)** 을 올리고 받는 화면입니다.
**설치할 것이 없습니다** — ActiveX·플러그인·별도 프로그램 없이 크롬·엣지·웨일·사파리, 폰 브라우저와 한일 포털 앱에서 그대로 됩니다
(HTML5 파일 읽기 + 보통 HTTP 만 씀).

| 할 수 있는 것 | 어떻게 |
|---|---|
| 큰 파일 올리기 | 끌어다 놓기 또는 눌러서 고르기 · 여러 개 한꺼번에 · 진행률·속도·남은 시간 |
| **그림으로 보기** | 💻 내 PC ⇄ 🗄 포털 서버 사이로 조각이 흘러가는 모습(올리기는 → , 받기는 ←) + **조각 지도**(칸마다 기다림·보내는 중·보냄·다시·검사 통과·틀림) |
| **끝난 뒤 검사** | 다 올리면 저절로: 서버가 디스크에서 다시 읽어 **파일 이름·크기·조각 수·조각별 CRC32·전체 CRC32·SHA-256** 을 내 PC 값과 하나하나 맞춰 보고 ✅/❌ 표로 보여 줌 |
| **받으면서 검사** | ⬇ 받기는 화면 안에서 조각마다 받아 서버의 조각 CRC32 와 맞춰 봄(틀리면 그 조각만 다시) → 끝나면 같은 검사표 |
| 🔍 서버 검사 | 목록의 🔍 — 서버의 파일이 올릴 때 그대로인지 언제든 다시 확인(디스크 고장 찾기). 결과는 목록에 「검사 ✓ / ✕」 |
| **끊겨도 이어 올리기** | 망이 끊기거나 창을 닫거나 서버를 다시 켜도, 같은 파일을 다시 고르면 **받아 둔 곳 다음부터** |
| 깨짐 막기 | 파일을 8MB 조각으로 잘라 3개씩 함께 보내고, 조각마다 CRC32 를 맞춰 봄 — 틀리면 그 조각만 다시 |
| 멈춤·다시·그만두기 | ⏸ · ▶ · ✕ |
| **이어 받기** | 받는 것도 끊기면 브라우저·폰 앱이 이어 받음(Range) · 서버 메모리에 올리지 않고 흘려 보냄 |
| 사내 공개 | 🏢 — 로그인한 직원 누구나 「사내 공개」 칸에서 받음 |
| 바깥 사람에게 링크 | 🔗 — 로그인 없이 받는 링크 · 기한(1~30일) · 받는 횟수 제한 · 언제든 끊기 |
| 관리자 | 「전체(관리자)」 칸에서 모든 사람의 파일을 보고 지움 |

시험(600MB, 실제 크로미움): 올리다 멈춤 → 서버 다시 켬 → 다시 로그인 → 같은 파일 고름 → 62% 부터 이어 올라감 → 받은 파일의 SHA-256 이 원본과 같음.
시험(검사): 300MB·123KB 올리기 → 자동 검사 ✅ · 받기(고른 자리 / 브라우저 내려받기) → 검사 ✅, 저장된 파일 SHA-256 = 원본 ·
서버 디스크의 2바이트를 일부러 바꿈 → 🔍 가 「❌ 틀린 조각 1개: 20」 으로 찾아냄.

### 받기 — 그림·검사가 되는 곳

| 어디서 | 받는 법 |
|---|---|
| 크롬·엣지를 **https**(또는 localhost)로 | 저장할 곳을 고르면 거기에 바로 써 감 — **크기 제한 없음** |
| 그 밖의 브라우저, 또는 http 주소 | 받은 조각을 브라우저가 모았다가 한 번에 저장 — **2GB 까지** |
| 한일 포털 앱 | 50MB 까지 |
| 위보다 큰 파일 | 저절로 보통 내려받기(그림·검사 없이, 이어 받기는 됨) |

목록의 「브라우저로 바로 받기」는 언제든 보통 내려받기입니다.

## 포털에 넣기 (포털 담당)

**받기: [hanil-bigfile-portal.zip](https://github.com/hanil-tech/hanil/raw/HEAD/release/hanil-bigfile-portal.zip)** (안에 `설치안내.txt` · `주의사항.txt` · 두 파일 · 이 README). 고친 뒤 다시 묶기: `bigfile/build.sh`

1. `portal/bigfile-route.js` 와 `portal/bigfile.html` 을 포털 폴더(`server.js` 옆)에 둡니다.
2. `server.js` 에서 세션(express-session)이 붙은 뒤(다른 `require('./…')(app, …)` 들 사이) **한 줄**:
   ```js
   require('./bigfile-route')(app);
   ```
3. 포털을 다시 띄웁니다. 메뉴에 `/bigfile` 링크를 달면 됩니다(→ `/bigfile/view`, 공통 조각이 안 끼는 주소).

더 깔 것(npm 꾸러미)이 없습니다 — Node 기본 기능만 씁니다.

### ⚠ 앞에 nginx(또는 다른 프록시)가 있으면

조각(8MB)이 통과하게 늘려 주세요. 기본값(1MB)이면 화면에 「서버(nginx 등)가 조각을 너무 크다고 막았습니다」가 나옵니다.

```nginx
client_max_body_size 16m;
proxy_request_buffering off;   # 조각을 디스크에 한 번 더 쓰지 않게
proxy_buffering off;           # 받을 때 큰 파일을 nginx 가 쌓아 두지 않게
proxy_read_timeout 600s;
```

### 로그인한 사람을 알아보는 법

`req.session.user` 의 `id`(없으면 `user_id`·`username`·`name`)로 주인을 정하고,
`is_admin`·`isAdmin`·`admin`·`role === 'admin'` 중 하나라도 있으면 관리자로 봅니다.
포털 세션 모양이 다르면 직접 넘깁니다:

```js
require('./bigfile-route')(app, {
  user: (req) => req.session.user && { id: String(req.session.user.no), name: req.session.user.nm, admin: req.session.user.lv >= 9 },
});
```

### 설정 (모두 고를 수 있음)

```js
require('./bigfile-route')(app, {
  dir: 'D:/portal-files',   // 파일 둘 곳 (기본: server.js 옆 bigfile-store/, 또는 환경 변수 BIGFILE_DIR)
  maxGB: 50,                // 파일 하나 최대
  quotaGB: 0,               // 한 사람 합계(0 = 제한 없음)
  keepFreeGB: 5,            // 서버 디스크를 이만큼은 남겨 둠 — 모자라면 올리기를 시작하지 않음
  partialDays: 7,           // 다 못 올린 것은 마지막 조각 뒤 7일에 지움
  keepDays: 0,              // 다 올린 것을 n일 뒤 지움(0 = 안 지움)
  shareDaysMax: 30,         // 링크 기한 최대
  chunkMB: 8,               // 조각 크기(nginx client_max_body_size 보다 작게)
  parallel: 3,              // 한 파일을 몇 조각씩 함께 보내나
});
```

## ⚠ 주의사항

전체는 [주의사항.txt](주의사항.txt)(묶음에도 들어 있음 — Ⅰ부는 직원에게 그대로 전달). 꼭 지킬 것만:

- **포털을 하나만 띄웁니다** — 올리는 중인 파일 정보를 메모리에 들고 있어 pm2 cluster·여러 대로 나누면 조각이 엇갈립니다.
- **Node.js 18.15 이상** — 낮으면 디스크 남은 자리를 못 읽어 가득 찰 때까지 막지 못합니다.
- **nginx 가 있으면 `client_max_body_size 16m`** — 없으면 큰 파일이 안 올라갑니다.
- **처음 켜고 확인** — 오른쪽 위에 자기 이름, 관리자에게 「전체(관리자)」 칸. 아니면 `user` 설정을 넣습니다.
- **🔗 링크는 가진 사람 누구나 받습니다** — 기한·횟수를 정하고, 다 받으면 끊습니다. 바깥에 열 때는 https 로.
- **`bigfile-store/` 를 손으로 고치지 않습니다** — 지우기는 화면의 🗑, 백업은 폴더째 복사.
- 바이러스 검사는 하지 않습니다 · 보관 창고가 아니라 주고받는 곳입니다(원본은 따로).

## 저장 모양

```
bigfile-store/
  data/<열쇠>.bin    파일 내용 (디스크에는 원래 이름을 쓰지 않음 — 이상한 이름으로 폴더를 벗어날 수 없음)
  meta/<열쇠>.json   이름·크기·주인·받은 조각·공유 링크·받은 횟수
```

- DB 를 쓰지 않습니다. 백업은 이 폴더를 통째로 복사하면 됩니다.
- 받을 때는 늘 「내려받기」로 내줍니다(`application/octet-stream` + `nosniff`) — 올린 HTML 이 포털 안에서 열려 로그인을 훔치는 일이 없게.
- 남의 비공개 파일 주소를 알아도 404 입니다(주인·관리자·사내 공개만).

## 주소

| 주소 | 하는 일 |
|---|---|
| `GET /bigfile` · `/bigfile/view` | 화면 |
| `GET /bigfile/api/info` · `/list[?all=1]` | 내 정보·한도 · 목록 |
| `POST /bigfile/api/init?name=&size=&lm=` | 올리기 시작(같은 파일을 올리다 말았으면 그것을 이어 감) |
| `PUT /bigfile/api/chunk/<열쇠>/<번호>` | 조각 하나 (머리 `X-Crc32`) |
| `POST /bigfile/api/done/<열쇠>` | 다 보냄 — 빠진 조각·크기 확인 |
| `GET /bigfile/api/file/<열쇠>/dl` | 받기 (Range 됨) |
| `POST /bigfile/api/verify/<열쇠>[?again=1]` · `GET …/verify/<열쇠>` | 서버 검사 시작 · 진행(읽은 바이트)·결과 |
| `GET /bigfile/api/crcs/<열쇠>` | 조각별 CRC32 (받는 쪽이 맞춰 봄) |
| `POST /bigfile/api/pub/<열쇠>?on=1` · `DELETE /bigfile/api/file/<열쇠>` | 사내 공개 · 지우기 |
| `POST /bigfile/api/share/<열쇠>?days=&max=` · `DELETE …/share/<열쇠>/<링크>` | 링크 만들기 · 끊기 |
| `GET /bigfile/s/<링크>` · `/bigfile/s/<링크>/dl` | 바깥 사람 받기 화면 · 받기 (로그인 없음) |

## 점검

```
cd bigfile/test
npm i
node api-check.js     # 가짜 포털을 띄워 38가지(조각 깨짐·이어 올리기·이어 받기·권한·링크 횟수·서버 검사·디스크 고장 찾기 …) → ✅ 38 · ❌ 0
```
