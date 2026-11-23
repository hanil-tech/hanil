# 📠 CimFAX 수신팩스 포털 연동 (fax/portal)

받은 팩스를 포털 **「팩스함」**(`/fax`)에서 보고, 거래처·담당자에 자동으로 이어 주는 **포털 드롭인 조각**입니다.
`viewer3d/portal`, `deskcal/portal` 과 같은 방식으로 포털(Node/Express)에 붙입니다.

> 포털 원본은 이 저장소에 없습니다 — 여기서 **부품**을 만들고, 포털 담당 쪽이 적용합니다.
> 설계서: 「CimFAX 수신팩스 포털 연동」 (4·5·7장).

## 파일
| 파일 | 하는 일 |
|------|---------|
| `fax-route.js` | 엔드포인트(에이전트 업로드·보고, 팩스함 API). `require('./fax-route')(app, ctx)` |
| `fax-page.html` | 팩스함 화면 (`/fax`) — 목록·검색·PDF 보기·거래처/담당자/상태 편집·미저장 경고 |
| `fax-schema.sql` | DB 표 5개 (MSSQL): fax_inbox · fax_sender_map · fax_link · fax_event · fax_agent_status |
| `설치안내.txt` | **자세한 설치·토큰·DB 어댑터·거래처매칭·도구 안내 (먼저 읽으세요)** |

## 빠른 요약
1. `fax-schema.sql` 을 포털 DB 에 적용.
2. `fax-route.js`·`fax-page.html` 을 포털 폴더에 두고, `server.js` 에 한 줄:
   `require('./fax-route')(app, { db: faxDb, agentToken: process.env.FAX_AGENT_TOKEN });`
   (`db` 는 `async (sql, params[]) => rows`. MSSQL 은 `?`→`@p` 어댑터 — 설치안내 2번 ★)
3. 포털 환경변수 `FAX_AGENT_TOKEN` 설정, 사내 PC 에이전트에도 같은 토큰 + `-ApiBase` 포털주소.
4. 포털 메뉴에 `/fax` 링크.

## 엔드포인트
- **에이전트(토큰·사내망):** `POST /api/fax/inbound` (multipart → 201/409) · `POST /api/fax/agent-report` (200)
- **사람(로그인):** `GET /api/fax` · `GET /api/fax/{id}` · `GET /api/fax/{id}/file`(공유불가) · `/thumb` · `PATCH /api/fax/{id}` · `POST /api/fax/{id}/links` · `GET /api/fax/stats` · `GET /api/fax/agent-status`(관리자)

## 거래처 자동매칭 (설계서 5.2)
숫자만 → 학습표(`fax_sender_map`) → 거래처 팩스/전화 완전일치 → 뒤 8자리 후보 제안.
인터넷팩스 이름(SmartWorks·ACEFAX·KODIT EFAX·SENDLABS FAX1/2)·의미없는 번호는 미매칭.
③④(거래처표 대조)는 `ctx.matchPartner(digits)` 로 넘기면 됩니다(설치안내 4번). 손으로 바꾸면 학습표에 저장.

## 보안
파일은 **로그인 다운로드로만**(공개 주소 없음) — 팩스엔 주민번호·계좌·계약서가 있을 수 있음.
에이전트 토큰은 업로드·보고 전용, 사내망 IP 에서만. 열람·배정은 `fax_event` 에 기록.
