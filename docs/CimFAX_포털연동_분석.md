# CimFAX 팩스 서버 → 사내 포털 연동 분석서

> 목적: CimFAX 로 **들어오는 팩스를 사내 포털로 자동 전송**하기 위해 CimFAX 의 동작 방식을 분석하고 연동 방법을 정한다.
> 분석일: 2026-11-12 ~ 13 · 분석 도구: REA(역분석 도구) + Ghidra 12.1.4 디컴파일러 + 디스어셈블러(capstone)로 정적 분석 · 실행은 하지 않음

---

## 1. 결론 먼저

| 방법 | 내용 | 난이도 | 추천 |
|---|---|---|---|
| **A. 팩스 → 메일 전달 (공식 기능)** | CimFAX 가 받은 팩스를 메일로 보내고, 포털이 그 메일함을 읽어 등록 | 쉬움 · 1~2일 | ★ **지금 바로** |
| **B. 클라이언트 PC 의 저장 파일 읽기** | CimFAX 클라이언트가 내려받아 둔 TIF 파일과 목록 DB 를 포털 에이전트가 읽어 업로드 | 보통 · 1주 | 메일을 쓰기 싫을 때 |
| **C. CimFAX 서버와 직접 통신** | 포털 서버가 CimFAX 클라이언트처럼 접속해 팩스를 직접 내려받음 | 어려움 · 2~3주 + 현장 확인 | 실시간·완전 자동이 꼭 필요할 때 |

**추천 순서:** A 로 먼저 운영을 시작한다 → 부족하면 C 를 개발한다.
**보내기**는 C 방식(장비와 직접 통신)으로 만들었다. CimFAX 공식 앱 FaxGo 를 디컴파일해서 로그인 계산, 작업 머리, 전송 순서를 모두 확인했다 (10장). 구현은 `fax/portal/cimfax-client.js`.

메일을 쓰기 어렵다면 B 도 좋다. FaxBox 에 **"자동 내보내기 → PDF → 공유 폴더"** 기능이 있다는 것을 디컴파일로 확인했기 때문에 (5.1.1), 포털은 폴더만 지켜보면 된다.
C 는 이번 분석으로 통신 방식의 뼈대를 거의 다 알아냈지만, 실제 장비에서 통신 내용을 한 번 기록해 맞춰 봐야 한다 (6장).

---

## 2. 분석한 자료

CimFAX 공식 홈페이지(www.cimfax.com)에서 누구나 받을 수 있는 파일만 분석했다. 회사 장비나 데이터에는 접근하지 않았다.

| 파일 | 버전 | 내용 |
|---|---|---|
| `CimFAX_Setup_All_5022E.exe` | 클라이언트 5022E | Windows 클라이언트 설치 파일 (NSIS) |
| `SwUpdate_5060.zip` | 서버 5060 | 장비 펌웨어 업데이트 (암호화·압축되어 있어 내부 분석은 하지 않음) |
| `CimFAX Easy User Manual2025.pdf` | 2025 | 사용자 설명서 |

설치 파일을 풀면 이런 프로그램이 나온다.

| 파일 | 역할 |
|---|---|
| **`FaxBox.exe`** | 메인 클라이언트. 서버 접속, 팩스 보내기·받기, 목록 관리 → **이번 분석의 핵심** |
| `CFXFinder.exe` | 사내망에서 CimFAX 장비를 자동으로 찾는 프로그램 |
| `FaxViewer.exe` | 팩스 이미지 보기 |
| `Printer\*` | "CimFAX 프린터" 가상 프린터 드라이버 (인쇄하면 팩스로 보냄) |
| `Templates\Fax.fdb` | 팩스 목록을 담는 로컬 DB (Microsoft Access 형식) |
| `tools\tiff2pdf.dll` 등 | TIF → PDF 변환 |

---

## 3. CimFAX 구조

```
                    전화선
                      │
   ┌──────────────────▼──────────────────┐
   │  CimFAX 장비 (사내망)                 │
   │  · 팩스 수신·발신, 대기열, 사용자 계정 │
   │  · 받은 팩스를 장비 안에 보관          │
   │  · (설정 시) 받은 팩스를 메일로 전달   │ ──── 방법 A ───▶ 메일함 ──▶ 포털
   └──────────────────┬──────────────────┘
                      │ TCP 3001~3007, UDP 5076~5077
         ┌────────────┴────────────┐
         ▼                         ▼
   ┌──────────────┐        ┌──────────────┐
   │ 직원 PC        │        │ 포털 서버      │
   │ FaxBox.exe    │        │ (방법 C:       │
   │ · 팩스를 내려받아│        │  FaxBox 대신   │
   │   TIF 로 저장   │        │  직접 접속)    │
   │ · Fax.fdb 기록 │        └──────────────┘
   └──────┬───────┘
          └──── 방법 B: 저장된 파일을 읽어 포털로 업로드
```

- 장비가 **서버**, 직원 PC 의 FaxBox 가 **클라이언트**다.
- 받은 팩스는 장비에 보관된다. 클라이언트가 접속하면 아직 안 받은 팩스를 내려받아 PC 에 TIF 파일로 저장한다.

---

## 4. 방법 A — 팩스 → 메일 전달 (공식 기능)

### 4.1 근거
- 공식 문제 해결 문서에 설정 방법이 있다 (서버 버전 5058 이상 필요).
- 클라이언트 코드에도 같은 설정을 장비로 보내는 명령이 들어 있다:
  `<USER_NAME>…<EMAIL_OPT>…<SMTP_ADDR>…<SMTP_USER>…<SMTP_PWD>…<EMAIL_FROM>…<EMAIL_TO>`

### 4.2 장비 설정 (FaxBox 에서 관리자로 로그인)
1. **서버 → 사용자 계정**: 해당 계정에 "Fax forward to email", "Distribute" 권한을 체크한다.
2. 같은 화면의 **"Fax forward to email options"** 에 다음을 넣는다.

   | 항목 | 값 |
   |---|---|
   | Fax forward to email | Always |
   | Email to receive | 포털 전용 수신 메일 (예: `fax-inbox@회사도메인`) |
   | SMTP setting | Private |
   | SMTP server | 회사 메일 서버 주소:포트 (예: `smtp.office365.com:587#TLS`) |
   | SMTP account / password | 보내는 데 쓸 메일 계정 (Gmail·Outlook 이면 "앱 비밀번호") |
   | Email for sending | SMTP 계정과 같은 주소 |

3. 공용 수신함(public) 팩스까지 받으려면 **공용 SMTP 설정**(`SET_PUB_SMTP_SETTING`)도 같은 방식으로 채운다.
4. 서버 버전이 5058 미만이면 홈페이지의 업데이트 파일로 먼저 올린다 (현재 최신 5060).

### 4.3 포털 쪽 개발
- 포털에 **메일 수집기**를 하나 만든다. 1분마다 `fax-inbox` 메일함을 IMAP 으로 읽는다.
- 첨부된 팩스 파일(TIF 또는 PDF)을 꺼내 PDF 로 통일하고, 포털 "받은 팩스" 게시판에 올린 뒤 담당자에게 알림을 보낸다.
- 처리한 메일은 "처리완료" 폴더로 옮긴다. 메일의 Message-ID 로 중복 등록을 막는다.
- 메일 제목과 본문에서 발신 번호, 수신 시각, 수신 계정을 읽어 낸다. 정확한 형식은 테스트 팩스를 한 장 받아 보고 맞춘다.

### 4.4 장단점
- 장점: CimFAX 를 건드리지 않는다. 장비가 업데이트되어도 깨지지 않는다. 하루 이틀이면 끝난다.
- 단점: 메일 서버를 한 번 거친다 (보통 수십 초 지연). 장비에 메일 비밀번호를 저장해야 한다.

---

## 5. 방법 B — 클라이언트 PC 저장 파일 읽기

FaxBox 를 켜 두는 PC 한 대(예: 총무 PC)에서, FaxBox 가 내려받은 파일을 포털 에이전트가 읽어 올린다.

### 5.1 분석으로 확인한 저장 방식
| 항목 | 값 (FaxBox.exe 안의 문자열) |
|---|---|
| 설정 위치 (레지스트리) | `HKCU\SOFTWARE\Cimsun\CimFAX\Settings` |
| 팩스 파일 경로 | `$STG_DIR$FaxFiles\%s\%s\%s\%s.tif` (서버·계정·함 구분 폴더 아래 TIF) |
| 내보내기 파일 이름 | `%s%04d%02d%02d%02d%02d%02d_From_%s_To_%s.tif` → 예: `20261112093015_From_0212345678_To_hanil.tif` |
| 목록 DB | `Fax.fdb` (Access), 테이블 `FAXLIST`, 받은편지함·보낸편지함은 `INBOX`·`OUTBOX` |
| 로그 | `$STG_DIR$log\YYYY-MM-DD.log` |
| **자동 내보내기** | ✔ 클라이언트 "Fax automatic export settings" 기능 (Ghidra 디컴파일로 동작 확인, 아래 5.1.1) |

#### 5.1.1 자동 내보내기 동작 (Ghidra 디컴파일 `FUN_00440070`)
팩스 한 장을 다 받으면 FaxBox 가 다음을 한다.
1. 자동 내보내기가 켜져 있으면 지정한 **내보내기 폴더**에 파일을 쓴다.
2. 하위 폴더 옵션:
   - 사용 안 함 → 내보내기 폴더에 바로 저장
   - 방식 1 → 보낸 곳 번호별 하위 폴더 (번호가 없으면 `unknow`)
   - 방식 2 → 연락처에 등록된 **보낸 곳 이름**별 하위 폴더 (없으면 번호)
3. 형식 옵션: **TIF 그대로** 또는 **PDF 로 변환**. PDF 변환이 실패하면 `…_PdfErr.tif` 로 남긴다.
4. 별도로 "사본 저장" 옵션이 켜져 있으면 다른 위치에 한 부 더 쓴다.

**→ 방법 B 가 생각보다 훨씬 쉽다.** FaxBox 설정에서 자동 내보내기를 "PDF, 공유 폴더(예: `\\NAS\fax-inbox`)" 로 켜 두면, 포털 에이전트는 그 폴더에 새로 생기는 PDF 만 올리면 된다. 받은 시각·보낸 곳은 파일 이름(`YYYYMMDDhhmmss_From_번호_To_계정`)과 폴더 이름에서 읽는다.

`FAXLIST` 주요 칸: `ID, TASK_ID, SERVER_ID, STATUS, CID(발신자 ID), PHONE(상대 번호), PAGE_TOTAL, DATE_TIME, FILE_NAME, RECEIVER, SENDER, REMARK, IS_DEL`

### 5.2 포털 쪽 개발
- 작은 Windows 서비스(에이전트)가 `FaxFiles` 폴더를 지켜보다가 새 TIF 파일이 생기면 PDF 로 바꿔 포털에 올린다.
- 함께 `Fax.fdb` 의 `FAXLIST` 를 읽어 발신 번호·수신 시각·수신 계정을 붙인다. 읽기 전용으로만 연다.
- **먼저 확인할 것:** FaxBox 의 "자동 내보내기" 기능으로 특정 폴더에 PDF 를 떨궈 줄 수 있으면, 에이전트는 그 폴더만 보면 되므로 훨씬 단순해진다.

### 5.3 장단점
- 장점: 메일 서버가 필요 없다.
- 단점: 그 PC 와 FaxBox 가 항상 켜져 있어야 한다. 클라이언트가 업데이트되면 폴더나 DB 형식이 바뀔 수 있다.

---

## 6. 방법 C — CimFAX 서버와 직접 통신 (프로토콜 분석 결과)

포털 서버가 FaxBox 대신 장비에 직접 접속해 팩스를 받아 오는 방법이다. 아래는 `FaxBox.exe` 를 디스어셈블해서 확인한 내용이다.
**✔ = 코드에서 직접 확인 · △ = 추정, 현장 확인 필요**

### 6.1 장비 찾기 (UDP)
- ✔ `CFXFinder.exe` 와 `FaxBox.exe` 가 **UDP 5077** 포트로 장비의 브로드캐스트를 듣는다 (`htons(0x13D5)`).
- ✔ FaxBox 는 **UDP 5076** 도 연다 (`htons(0x13D4)`), `SO_BROADCAST` 사용.
- 장비 IP 를 고정해 두면 포털은 이 단계를 건너뛰고 IP 로 바로 접속하면 된다.

### 6.2 서비스별 TCP 포트
FaxBox 는 기능마다 다른 포트로 따로 접속한다. 기본 포트는 3001 이고, 사용자가 접속 주소를 `IP:포트` 로 바꾸면 모든 포트가 같은 만큼 밀린다 (✔ 코드: `포트 = 서비스 기본값 + (입력 포트 − 3001)`).

| 서비스 이름 | 기본 포트 | 용도 | 근거 |
|---|---|---|---|
| `CIMFAX_LOGIN` | **3001** | 로그인, 서버 정보 | ✔ |
| `CIMFAX_SEND_FAX` | 3002 | 팩스 보내기 (파일 업로드) | ✔ |
| `CIMFAX_VOICE` | 3003 | 음성 안내 파일 | ✔ |
| **`CIMFAX_RECV_FAX`** | **3005** | **받은 팩스 내려받기 ← 포털 연동 핵심** | ✔ |
| `CIMFAX_ADMIN` | 3006 | 사용자·SMTP·회선 설정 (관리자) | ✔ |
| `CIMFAX_CMD` | 3007 | 목록 조회, 삭제, 상태 조회 등 명령 | ✔ |

### 6.3 메시지 형식
- ✔ 메시지는 **XML 비슷한 태그 문자열**이다. 예: `<ACTION>RECVFAX</ACTION><LAST_RECV_ID>120</LAST_RECV_ID>`
- ✔ 문자열은 **UTF-16LE**(Windows 유니코드) 그대로 전송된다. 길이 헤더 없이 보내고, 끝에 연결별 설정에 따라 `\0`, `\r\n`, `\n` 중 하나를 붙인다 (`0x406430` 함수).
- ✔ 파일은 문자열 메시지 다음에 바이너리로 이어서 보낸다. 크기는 `<FILELEN>`, `<HEADERSIZE>`, `<BUFSIZE>` 로 미리 알려 준다.
- △ 서버 응답은 `<FEEDBACK>…</FEEDBACK>` 형태로 오는 것으로 보인다 (예: `RECV_OK`, `FAILED`, `ERROR`).

### 6.4 로그인
✔ 로그인 메시지 형식 (3가지 변형):
```
<ACTION>LOGIN</ACTION><USERNAME>사용자</USERNAME><PASSWORD>비밀번호</PASSWORD>
<ACTION>LOGIN</ACTION><USERNAME>…</USERNAME><PASSWORD>…</PASSWORD><SERVICE>CIMFAX_RECV_FAX</SERVICE>
<ACTION>LOGIN</ACTION><USERNAME>…</USERNAME><PASSWORD>…</PASSWORD><UDP_PORT>5076</UDP_PORT><SERVICE>…</SERVICE>
```
- ✔ 각 서비스 연결은 접속 직후 `<SERVICE>` 를 붙여 로그인한다.
- ✔ **비밀번호는 그대로 보내지 않는다 — 챌린지·응답 방식** (Ghidra 디컴파일 `FUN_00433ff0`, `FUN_00433820`):
  1. 접속하면 장비가 먼저 `<SERVICE_NAME>CIMFAX_LOGIN</SERVICE_NAME><SWVER>…</SWVER><SERVER_ID>16진수</SERVER_ID><VERIFY_STRING>임의 문자열</VERIFY_STRING>` 을 보낸다.
  2. 클라이언트는 `(저장된 비밀번호 값 + VERIFY_STRING)` 을 ANSI 로 바꿔 **16바이트 해시**를 계산하고, 소문자 16진수 32자로 만들어 로그인 메시지에 넣는다. 해시 초기값이 MD5 의 `0x67452301` 이라 **MD5 로 추정**한다.
  3. 장비는 `<LOGIN_STATE>` (거부 시 `DENY`), `<PERMISSION>`, `<EXT_NUM>`(내선), `<BIND>` 를 돌려준다.
  - △ "저장된 비밀번호 값" 이 평문 비밀번호인지, 한 번 더 가공한 값인지와 문자열을 붙이는 순서는 현장 기록으로 확정한다.
- ✔ 로그인 응답의 서버 고유 번호(`SERVER_ID`, 16진수)와 `TASK_ID` 를 묶으면 팩스 한 건을 겹치지 않게 구분할 수 있다.

### 6.5 받은 팩스 내려받기 (`CIMFAX_RECV_FAX`, 포트 3005)
✔ 코드에서 확인한 흐름:
```
포털 → 장비 : TCP 3005 접속
포털 → 장비 : <ACTION>LOGIN</ACTION><USERNAME>…</USERNAME><PASSWORD>…</PASSWORD><SERVICE>CIMFAX_RECV_FAX</SERVICE>
포털 → 장비 : <ACTION>RECVFAX</ACTION><LAST_RECV_ID>마지막으로 받은 번호</LAST_RECV_ID>
               (공용 수신함도 받을 때) <LAST_PUB_ID>마지막 공용 번호</LAST_PUB_ID>
장비 → 포털 : 새 팩스 개수 NEWFAX_AMOUNT, 상태 RECV_STAT / FAX_STATUS
장비 → 포털 : 팩스 정보 (TASK_ID, SERVER_ID, PHONE, CID, PAGE_TOTAL, DATE_TIME, RECEIVER, FILE_LEN …)
장비 → 포털 : 팩스 파일 데이터 (TIF, FILE_LEN 바이트)
포털 → 장비 : <FEEDBACK>RECV_OK</FEEDBACK><FILELEN>받은 바이트 수</FILELEN>
(다음 팩스 반복)
```
- ✔ FaxBox 는 받은 팩스를 `ADD_RECV_FAX` 로 자기 `Fax.fdb` 에 기록하고, 다음 접속 때 **가장 큰 TASK_ID** 를 `LAST_RECV_ID` 로 보낸다. 포털도 똑같이 마지막 번호만 기억하면 된다.

**파일 전송 세부 규칙 (Ghidra 디컴파일 `FUN_00440070` 으로 확인 ✔)**
| 단계 | 내용 |
|---|---|
| 알림 | 장비가 `<NEWFAX_AMOUNT>`, `<FAX_STATUS>`, `<CID>`, `<PHONE_REC>`, `<CHECKED_ID>` 등을 보낸다. `CHECKED_ID` 는 장비가 확인한 마지막 번호 |
| 전송 예고 | 장비가 `<FILELEN>파일 크기</FILELEN><HEADERSIZE>1024</HEADERSIZE><BUFSIZE>조각 크기</BUFSIZE>` 를 보낸다 |
| 검사 | 클라이언트는 `FILELEN` 이 1 ~ 10,799,999 바이트, `BUFSIZE` 가 1024 ~ 65536, `HEADERSIZE` 가 정확히 **1024** 인지 확인한다. 맞으면 **`R`**(준비됨), 틀리면 **`F`**(실패) 한 글자를 보낸다 |
| 헤더 | 먼저 **1024 바이트 고정 헤더**가 온다. 팩스 정보가 들어 있다 (헤더 +0x18: 상태 코드, +0x20: 보낸 곳 번호(UTF-16), +0x1D4: 보낸 곳 팩스 ID(CSID) 등). 클라이언트는 이것을 따로 파일로 저장한다 |
| 본문 | 이어서 TIF 데이터가 `BUFSIZE` 단위로 온다. 클라이언트는 **조각 하나를 받을 때마다 `R`** 을 보내 다음 조각을 요청한다 |
| 완료 | 전체 크기를 다 받으면 TIF 파일을 저장하고, 자동 내보내기(5.1.1)를 실행한다 |
- ✔ 새 팩스 도착 알림 메시지(`CIMFAX_UI_GOT_RECV_NEW_FAX`)가 있어, 접속을 유지하면 장비가 새 팩스를 바로 밀어 주는 구조로 보인다 (△ 확인 필요).

### 6.6 기타 명령 (`CIMFAX_CMD`, 포트 3007) — 포털에서 쓸 만한 것
| 명령 | 형식 | 용도 |
|---|---|---|
| `GET_SVR_INFO` | `<ACTION>GET_SVR_INFO</ACTION>` | 장비 버전, 상태 |
| `GET_SEND_FAX_STATUS` | `<TASK_ID_LIST>…` | 보낸 팩스 결과 조회 |
| `GET_FAX_LIST_BY_IDX` | `<IDX_LIST>…` | 번호로 팩스 목록 조회 |
| `DELETE_FAX` / `DELETE_FAX_BY_ID` | `<TASKID>…<DELETE>…<REMOVE>…` | 처리한 팩스 정리 |
| `DISTRIBUTE_FAX` | `<TASKID>…<RECV_LIST>…` | 팩스를 다른 사용자에게 배분 |
| `DOWN_FILE` / `UP_FILE` | `<FILE>…<BUFSIZE>…<FILELEN>…` | 파일 내려받기·올리기 |
| (조회) | `<TASK_ID_LIST>…<QY_USER>…<QY_DTBGN>…<QY_DTEND>…<QY_TYPE>…` | 사용자·기간으로 팩스 검색 |

### 6.7 현장에서 확인해야 할 것 (개발 전 반나절)
사내망 PC 에서 아래를 한 번만 하면 △ 항목을 모두 확정할 수 있다.
1. FaxBox 가 설치된 PC 에 **Wireshark** 를 설치한다.
2. 필터 `tcp.port >= 3001 && tcp.port <= 3007 || udp.port == 5076 || udp.port == 5077` 로 기록을 시작한다.
3. FaxBox 로그인 → 테스트 팩스 1장 받기 → FaxBox 종료.
4. 기록 파일(.pcapng)을 저장한다. 이 파일을 다시 분석하면 다음이 확정된다.
   - 로그인 해시에 넣는 값과 순서 (6.4 △)
   - 각 연결의 문자열 끝 표시 (`\0` / `\r\n` / `\n`)
   - 1024 바이트 헤더의 나머지 칸 (쪽수, 수신 시각, 수신 계정 위치)

> 주의: 기록 파일에 CimFAX 계정 비밀번호와 팩스 내용이 들어 있을 수 있다. 공개 저장소에 올리지 말 것.

---

## 7. 포털 쪽 설계 (A·B·C 공통)

### 7.1 데이터 (받은 팩스 표)
| 칸 | 설명 | CimFAX 출처 |
|---|---|---|
| id | 포털 고유 번호 | — |
| source_key | 중복 방지 키 | `SERVER_ID` + `TASK_ID` (C) / 메일 Message-ID (A) / 파일 경로 (B) |
| received_at | 수신 시각 | `DATE_TIME` |
| from_number | 보낸 곳 번호 | `PHONE`, `CID` |
| cimfax_user | 수신 계정 | `RECEIVER` (공용함이면 public) |
| pages | 쪽수 | `PAGE_TOTAL` |
| pdf_file | 변환된 PDF | TIF → PDF |
| status | 신규 / 확인 / 처리완료 | 포털 자체 |
| assignee | 담당자 | 수신 계정 → 포털 사용자 매핑 |

### 7.2 처리 흐름
1. 수집 (A 메일 / B 폴더 / C 직접 통신)
2. TIF → PDF 변환, 첫 쪽 썸네일 생성
3. `source_key` 로 중복 확인 후 저장
4. 수신 계정 → 담당자 매핑, 포털 알림
5. 실패하면 3회 재시도, 계속 실패하면 관리자 알림

### 7.3 포털 API (예시)
```
POST /api/fax/inbound        (수집기 → 포털, 사내 인증 토큰 필요)
  multipart: file=<pdf>, meta={"source_key":"…","received_at":"…","from_number":"…","cimfax_user":"…","pages":2}
GET  /api/fax?status=new     (포털 화면)
```

---

## 8. 법적·보안 메모
- 이번 분석은 **회사가 구입한 장비를 회사 포털과 연동하기 위한 것**이다. 저작권법 제101조의4(프로그램코드 역분석)가 허용하는 "호환에 필요한 정보 획득" 범위 안에서 진행한다. CimFAX 의 코드나 화면을 복제하지 않고, 통신 방식만 참고해 연동 코드를 새로 작성한다.
- 가능하면 먼저 제조사(us@cimfax.com)에 **공식 연동 API·SDK** 가 있는지 문의한다. 있으면 그것을 쓰는 것이 가장 안전하다.
- 이 저장소는 공개되어 있다. 계정·비밀번호·통신 기록·실제 팩스 파일은 올리지 않는다.
- 방법 C 는 장비 펌웨어가 업데이트되면 동작이 바뀔 수 있다. 업데이트 전에 테스트 장비나 테스트 계정으로 먼저 확인한다.

---

## 9. 다음 할 일
1. [ ] FaxBox 관리자 화면에서 **팩스 → 메일 전달**이 켜지는지 확인 (서버 버전 5058 이상인지 확인)
2. [ ] 포털 전용 수신 메일함 만들기, 테스트 팩스 1장으로 메일 형식 확인
3. [ ] 포털 개발 환경 확인 (언어, 저장소, 로그인 방식)
4. [ ] 메일 수집기 + 받은 팩스 화면 개발 (방법 A)
5. [ ] (필요하면) Wireshark 기록 1회 → 방법 C 프로토콜 확정 → 직접 수신 모듈 개발

---

## 10. 팩스 보내기 — FaxGo 앱 분석 (2026-11-13)

포털에서 팩스를 보내려면 장비와 직접 통신해야 한다. FaxBox 의 `/send` 옵션은 FaxViewer 의 보내기 창을 띄울 뿐이라 자동화할 수 없다 (Ghidra `FUN_00417ba0`). 그래서 CimFAX 공식 안드로이드 앱 **FaxGo** (`download.cimfax.com/android/faxgo.apk`, SHA-256 `d67e5201…a7a698`) 를 androguard 로 디컴파일했다. 이 앱도 같은 사내망 프로토콜로 팩스를 보내고, Java 라서 FaxBox 보다 훨씬 정확하게 읽힌다.

### 10.1 공통
- ✔ 글자는 **UTF-16LE**, 끝 표시 없음. 응답은 최대 1024 바이트씩 읽는다 (`SocketBase`)
- ✔ 태그 값 읽기는 대소문자를 가리지 않는다 (`ConvertUtil.getValue`)
- ✔ 장비 찾기: UDP 255.255.255.255:**5076** 으로 `CimFAX/FaxGo where are you?(ID:장비ID)` 를 보내면, **5077** 로 `NAME:… ID: …)` 답이 온다

### 10.2 로그인 (6.4 의 △ 확정)
```
장비 → <SERVER_ID>…</SERVER_ID><SERVER_NAME>…</SERVER_NAME><VERIFY_STRING>임의값</VERIFY_STRING>   (접속하자마자)
포털 → <ACTION>LOGIN</ACTION><USERNAME>계정</USERNAME><PASSWORD>md5hex(VERIFY_STRING + cal128MD5(비밀번호))</PASSWORD>
장비 → <LOGIN_STATE>OK</LOGIN_STATE><PERMISSION>…</PERMISSION><EXT_NUM>…</EXT_NUM>
```
- `md5hex` = 표준 MD5, 소문자 16진수 (`ConvertUtil.getMD5`, 바이트코드로 확인)
- `cal128MD5(pw)` = `MD5Code(k).getMD5ofStr(pw)` 를 k = 0,1,2,3 으로 네 번 구해 이어 붙인 128자 (`ConvertUtil.cal128MD5`)
- `MD5Code(k)` = 표준 MD5 와 같고 **시작값만** `A+11k, B+71k, C+37k, D+97k` 로 바뀐다 (`md5Init`). 회전은 부호 없는 시프트(`ushr-int`)로 표준과 같다. k=0 이면 표준 MD5 와 결과가 같은 것을 확인했다.

### 10.3 보내기 (TCP 3002)
```
포털 → (로그인)
포털 → <ACTION>SENDFAX</ACTION><FILELEN>머리+TIFF 바이트</FILELEN><HEADERSIZE>1088</HEADERSIZE><BUFSIZE>1200</BUFSIZE>
장비 → R            포털 → 1200 바이트 (머리 1088 바이트 다음 TIFF)
장비 → R            포털 → 다음 1200 바이트 …  (끝까지)
장비 → <FEEDBACK>RECV_OK</FEEDBACK><TASKID>작업번호</TASKID><INTER_FORWARD>…</INTER_FORWARD>
```
**작업 머리 1088 바이트** (`CFaxItem` → `mergeArrays`, 정수는 리틀엔디언 4바이트, 글자칸은 2바이트씩):

| 위치 | 크기 | 칸 | FaxGo 가 넣는 값 |
|---|---|---|---|
| 0 | 4×6 | remove, taskId, fileId, isDel, ID, serverId | 0 |
| 24 | 4 | status | **5** |
| 28 | 4 | priority | 2 (기본) |
| 32 | 64 | cid | 비움 |
| 96 | 64 | **phone** (받는 번호, 글자마다 2바이트) | `--` 는 `,,,,,,,,` (쉼) 로 |
| 160 | 4 | **pageTotal** | 쪽수 |
| 164·168·172 | 4×3 | pageSended, dialTotal(5), dialAlready | |
| 176 | 16 | dateTime (SYSTEMTIME, UTC) | 지금 |
| 192 | 16 | dateTimePlan | 예약이면 그 시각 |
| 208 | 4 | remarkId | 0 |
| 212·340·404·532·596·660 | 128·64·128·64·64·256 | issue, fileName, receiver, sender, reviewer, remark | 비움 |
| 916 | 4×3 | sending % / state / baud | 0 |
| 928·944·960 | 16×3 | dateTimeStop, timeLimitStart, timeLimitEnd | 비움 |
| 976·980·984 | 4×3 | dialRetryTime, **faxQuality**(1), spendTime | |
| 988·992·996·1000·1004 | 4×5 | disableSvrHeader, taskGroup, disableDialPrefix, lineNum, isPublicFax | 0 |
| 1008 | 80 | resv | 0 |

- **FaxGo 는 TIFF 를 암호화하지 않고 그대로 보낸다.** FaxBox 는 RC4 로 암호화하지만 (8장 아래 메모) 포털은 FaxGo 와 같이 한다.
- **TIFF 형식**: CimFAX 클라이언트가 만든 `TransReport.tif` 와 같게 한다. 폭 **1728**, 204×196 dpi, 흑백, **CCITT G3 2D**, 여러 쪽. 포털은 Ghostscript `tiffg32d -r204x196` 로 만든다. FaxGo 도 1728 폭으로 그린다 (`convertPDF2TIF`).

### 10.4 보낸 팩스 상태 (TCP 3007)
```
포털 → <ACTION>GET_SEND_FAX_STATUS</ACTION><TASK_ID_LIST>101,102</TASK_ID_LIST>   ('all in queue' 면 대기 중 전부)
장비 → <FEEDBACK>OK</FEEDBACK><AMOUNT>n</AMOUNT>
(n 번)  포털 → R    장비 → 1024 바이트 기록 (위 머리와 같은 배치: +4 작업번호, +24 상태, +164 보낸 쪽, +172 다이얼 횟수)
```
- △ **상태 코드 값의 뜻**(대기 / 보내는 중 / 성공 / 실패)은 아직 모른다. 포털은 코드 숫자, 보낸 쪽 수, 다이얼 횟수를 그대로 보여 준다. 현장 시험 팩스 몇 장으로 코드표를 채운다.

### 10.5 FaxBox 쪽 메모 — RC4 암호화
- FaxBox 는 받은 팩스와 올리는 팩스를 **RC4(40비트)** 로 암호화해서 주고받는다. 키는 `MD5( UTF-16LE( md5hex(ANSI(사용자 이름)) ) )` 로 만든다 (Ghidra `FUN_00407950`, `FUN_00407b40`, Windows `CryptDeriveKey(CALG_RC4)`). 받은 팩스는 수신자 이름이 로그인 사용자와 같을 때 이 키를 쓴다 (`FUN_00440070`).
- 키가 사용자 이름에서 나오므로 보안 효과는 거의 없다. 사내망 밖으로 장비 포트(3001~3007)를 열지 않는다.

### 10.6 현장 확인 (보내기)
`cimfax-check.js` 로 아래 순서대로 확인한다 (설치안내 3단계).
1. 로그인 → 2. 시험 팩스 한 장 → 3. 받은 쪽 종이 확인 → 4. `--status` 로 상태 코드 확인
- 확인할 것:
  - 1088 바이트 머리를 장비가 받는지 (FaxBox 는 1024 바이트 머리를 쓰지만, FaxGo 가 1088 로 보내므로 장비가 둘 다 받을 것으로 본다)
  - G3 TIFF 화질
  - 상태 코드표

---

### 부록: 분석 근거 위치 (FaxBox.exe 5022E, SHA-256 `7e6492d2…3f641`)
| 항목 | 주소 |
|---|---|
| 서비스 이름 문자열 → 포트 설정 | `CIMFAX_RECV_FAX` 참조 `0x43F97B`, 포트 `0xBBD`(3005) 설정 `0x43F99E` |
| 로그인 포트 3001 | `0x435D4C` |
| 포트 보정 (입력 포트 − 3001) | `0x433531` 부근 `add eax, 0xFFFFF447` |
| 연결 함수 | `0x4061C0` (주소, 포트) |
| 문자열 전송 (UTF-16LE + 끝 표시) | `0x406430` → 소켓 쓰기 `0x4064E0` |
| `RECVFAX` 요청 생성 | `0x43FF9E` (`<LAST_PUB_ID>` 추가: 플래그 bit 2) |
| `RECV_OK` 응답 생성 | `0x44188C` |
| UDP 5077 대기 | `CFXFinder.exe` `0x401067` |
| 받은 팩스 처리·자동 내보내기 (Ghidra) | `FUN_00440070` |
| 로그인 응답 처리 (Ghidra) | `FUN_00433ff0` |
| 로그인 해시 계산 (Ghidra) | `FUN_00433820` → 해시 `FUN_0043bcd0` (초기화 `0x43B170`, `0x67452301`) |
