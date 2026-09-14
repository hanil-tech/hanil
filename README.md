# 한일 TimeGuard

관리자가 정한 시간대를 벗어나면 직원 PC 를 안내 후 종료하는 Windows 프로그램입니다.
**중앙 관리 서버**에서 PC 별 시간표를 정하고, 직원이 올린 연장 요청을 승인합니다.

## 왜 서버가 필요한가

직원 PC 에만 설치하는 방식은 한 가지 약점이 있습니다. **직원이 관리자 비밀번호를 알아내면
자기 PC 에서 감시를 꺼 버릴 수 있습니다.** 비밀번호가 그 PC 에 저장되어 있고, 판단도 그 PC 가
하기 때문입니다.

서버를 두면 권한이 직원 PC 에서 사라집니다. 비밀번호를 알아내도 그 PC 에서는 바꿀 수 있는 게
없습니다. 그리고 누군가 서비스를 멈추거나 랜선을 뽑으면 **서버 화면에 "연결 끊김" 으로 남아
관리자가 알 수 있습니다.**

> 다만 직원 계정이 Windows 관리자 권한을 갖고 있으면 서비스를 멈출 방법은 여전히 있습니다.
> **직원 계정은 일반 사용자로 낮추는 것**을 함께 하셔야 효과가 제대로 납니다.

## 전체 구조

```
   ┌─────────────────────────────────────────┐
   │  관리 서버 (사무실 PC 한 대)              │
   │  TimeGuard.Server.exe                    │
   │                                          │
   │  · 웹 브라우저로 관리                     │
   │  · PC 별 시간표 지정                      │
   │  · 연장 요청 승인 / 거절                  │
   │  · 각 PC 상태와 기록 확인                 │
   └────────────────┬────────────────────────┘
                    │  사내망 (기본 60초마다)
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ 직원PC 1 │ │ 직원PC 2 │ │ 직원PC 3 │
   │          │ │          │ │          │
   │ 서비스   │ │ 서비스   │ │ 서비스   │  ← 감시·전원 차단 (SYSTEM 권한)
   │ 에이전트 │ │ 에이전트 │ │ 에이전트 │  ← 경고·카운트다운·연장 요청
   └─────────┘ └─────────┘ └─────────┘
```

**연결이 끊겨도 제한은 유지됩니다.** 각 PC 는 마지막으로 받은 시간표를 파일로 보관해 두고
그대로 적용합니다. 랜선을 뽑거나 서버를 꺼서 제한을 피할 수 없습니다.

## 구성 프로그램

| 프로그램 | 설치 위치 | 역할 |
|---|---|---|
| `TimeGuard.Server.exe` | 관리 서버 PC | 웹 관리 화면, 시간표 배포, 연장 승인 |
| `TimeGuard.Service.exe` | 직원 PC (서비스) | 시간 감시, 전원 차단, 서버와 통신 |
| `TimeGuard.Agent.exe` | 직원 PC (사용자 세션) | 트레이 아이콘, 경고, 카운트다운, 연장 요청 |
| `TimeGuard.Admin.exe` | 직원 PC | 서버 등록, 상태 확인, 단독 모드 설정 |

### 왜 서비스와 에이전트로 나누었나

Windows 서비스는 세션 0 에 격리되어 있어 사용자 화면에 창을 띄울 수 없습니다.
그래서 **판정과 조치는 서비스**가, **화면 표시는 에이전트**가 맡습니다.

이 구조 덕분에 **사용자가 에이전트를 강제 종료해도 차단은 그대로 실행됩니다.** 경고만 못 볼
뿐입니다. 서비스가 30초마다 확인해 에이전트를 다시 띄우기도 합니다.

## 설치

### 1단계 — 관리 서버

사무실 PC 한 대를 정해 `dist/TimeGuard-서버` 폴더를 복사한 뒤, **관리자 권한 PowerShell**에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-server.ps1
```

설치 스크립트가 서비스 등록, 방화벽 개방(사내망만), 자료 폴더 권한 설정까지 처리합니다.
끝나면 접속 주소와 임시 비밀번호를 알려 줍니다.

브라우저로 접속해 다음 순서로 진행하세요.

| 순서 | 화면 | 내용 |
|---|---|---|
| 1 | 로그인 | 아이디 `admin`, 임시 비밀번호 |
| 2 | 설정 | 관리자 비밀번호 변경 |
| 3 | 기본 시간표 | 예: 월~금 `09:00-18:00`, 토·일 `없음` |
| 4 | 설정 | **클라이언트 등록 키** 확인 (직원 PC 설치에 필요) |

### 2단계 — 직원 PC

`dist/TimeGuard` 폴더를 복사한 뒤, **관리자 권한 PowerShell**에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

이어서 서버에 등록합니다.

```powershell
& "C:\Program Files\HanilTimeGuard\TimeGuard.Admin.exe" enroll `
    --server http://192.168.0.10:8080 `
    --key ABCDE-FGHIJ-KLMNO-PQRST

net stop HanilTimeGuard
net start HanilTimeGuard
```

등록되면 서버의 **PC 목록**에 나타납니다.

> .NET 설치가 필요 없습니다. 런타임이 함께 들어 있습니다.

## 관리 화면

| 화면 | 하는 일 |
|---|---|
| **PC 목록** | 각 PC 의 현재 상태, 접속 여부, 마지막 연결 시각 |
| **PC 상세** | 그 PC 전용 시간표, 즉시 연장·중지, 최근 기록 |
| **연장 요청** | 직원 요청 승인·거절. 요청보다 적게 줄 수도 있음 |
| **기본 시간표** | 전용 시간표를 쓰지 않는 모든 PC 에 적용 |
| **기록** | 언제 어느 PC 가 꺼졌는지 전체 조회 |
| **설정** | 등록 키, 연결 끊김 판단 기준, 비밀번호 |

화면 모습은 `docs/` 폴더의 캡처 이미지를 보십시오.

## 직원이 보는 모습

작업 표시줄에 TimeGuard 아이콘이 생깁니다. 마우스를 올리면 남은 시간이 보이고,
클릭하면 자세한 안내가 뜹니다.

- 종료 **10분 / 5분 / 1분 전** 알림
- 마지막 **60초 카운트다운 창** (화면 최상위, 닫을 수 없음)
- 시간이 다 되면 전원 차단

카운트다운 창은 **포커스를 뺏지 않으므로** 그 동안에도 작업을 저장할 수 있습니다.

### 연장 요청

트레이 아이콘 오른쪽 클릭 → **사용 시간 연장 요청**

필요한 시간(30분~4시간)과 사유를 적어 보내면 관리자 화면에 뜹니다.
승인되면 직원 화면에 알림이 뜨고 곧바로 반영됩니다.

## 시간대 표기법

| 입력 | 뜻 |
|---|---|
| `09:00-18:00` | 하루 한 구간 |
| `09:00-12:00, 13:00-18:00` | 점심시간 제외 |
| `22:00-06:00` | 자정을 넘기는 야간 근무 |
| `없음` | 그 요일은 사용 불가 |
| `종일` | 24시간 허용 |

## 안전장치

시간 제한 프로그램이 오작동해 업무 PC 가 꺼지면 피해가 큽니다.
**의심스러우면 차단하지 않는 쪽**으로 만들었습니다.

| 상황 | 동작 |
|---|---|
| 설정 파일이 없거나 손상됨 | 감시 꺼짐 상태로 동작 (절대 켜진 채 넘어가지 않음) |
| 서버 정책을 한 번도 못 받음 | 제한하지 않음 |
| 서버 연결 끊김 | **마지막으로 받은 시간표를 계속 적용** |
| 감시 루프 오류 | 기록 후 다음 초에 계속 (서비스는 죽지 않음) |
| 전원 차단 실패 | 기록 후 30초 뒤 재시도 |
| 조치 실행 직후 | 5분간 중복 실행 안 함 |

**허용 시간대 밖에서 PC 를 켠 경우**에는 곧바로 끄지 않고 기본 120초의 유예를 줍니다.
반대로 사용 중에 시간이 끝난 경우에는 이미 10분 전부터 경고했으므로 유예 없이 실행합니다.

## 파일 위치

**관리 서버**
```
C:\Program Files\HanilTimeGuardServer\    프로그램
C:\ProgramData\HanilTimeGuardServer\
    timeguard.db                           모든 설정과 기록 (이 파일만 백업하면 됩니다)
    최초설정정보.txt                        첫 로그인 정보 (확인 후 삭제)
```

**직원 PC**
```
C:\Program Files\HanilTimeGuard\          프로그램
C:\ProgramData\HanilTimeGuard\
    config.json                            현재 적용 중인 설정 (일반 사용자는 읽기 전용)
    server.json                            서버 주소와 장비 토큰
    policy-cache.json                      마지막으로 받은 시간표 (연결이 끊겨도 이걸 씁니다)
    timeguard.log                          기록
```

서버 모드에서는 `config.json` 을 손으로 고쳐도 **서비스가 서버 정책으로 되돌립니다.**

## 서버 없이 쓰기

PC 한두 대만 관리한다면 서버 없이도 씁니다. 이 경우 `TimeGuard.Admin.exe` 를 실행해
메뉴에서 직접 시간표를 설정합니다. 서버에 등록하지 않으면 자동으로 이 모드입니다.

이미 등록한 PC 를 떼어 내려면:

```powershell
TimeGuard.Admin.exe unenroll
```

## 명령줄

```powershell
TimeGuard.Admin.exe status                                   # 현재 상태
TimeGuard.Admin.exe enroll --server <주소> --key <등록키>      # 서버에 등록
TimeGuard.Admin.exe unenroll                                 # 단독 모드로
TimeGuard.Admin.exe log 50                                   # 기록 보기

# 단독 모드에서만 동작합니다 (서버 모드에서는 서버가 관리)
TimeGuard.Admin.exe set-window 평일 09:00-18:00 -p 비밀번호
TimeGuard.Admin.exe extend 30 -p 비밀번호
TimeGuard.Admin.exe enable -p 비밀번호
```

## 개발자용

### 빌드

```bash
./build/publish.sh          # 직원 PC 용 + 관리 서버 배포본
./build/publish.sh --all    # 단독 실행 파일까지 만들고 zip 으로 묶음
```

### 테스트

```bash
dotnet test
```

- **Core 58개** — 스케줄 판정, 설정 저장, 비밀번호 해시
- **서버 55개** — 실제 HTTP 파이프라인을 통과시키는 통합 테스트.
  등록·인증·정책 배포·연장 승인·쿼리 번역·클라이언트 연동까지 포함

스케줄 판정은 부작용 없는 순수 계산으로 분리해 두어 Windows 없이도 전부 검증됩니다.
서버는 Linux 에서 그대로 띄워 확인할 수 있습니다.

```bash
dotnet run --project src/TimeGuard.Server    # http://localhost:8080
```

### 서버를 콘솔에서 직접 실행 (동작 확인용)

```powershell
"C:\Program Files\HanilTimeGuardServer\TimeGuard.Server.exe"
```

### UI 구현에 관하여

직원 PC 쪽 경고 창과 트레이 아이콘은 WinForms/WPF 없이 **Win32 API 직접 호출**로
만들었습니다. 배포본에 Windows Desktop 런타임이 필요 없어 용량이 줄고,
Linux/CI 환경에서도 Windows 용 바이너리를 빌드할 수 있습니다.

## 프로젝트 구조

```
src/
  TimeGuard.Core/        양쪽이 공유하는 부분 (플랫폼 무관)
    Config/              설정 모델, 시간표, 저장소, 비밀번호 해시
    Schedule/            ScheduleEvaluator — "지금 써도 되는가" 판정
    Ipc/                 서비스 ↔ 에이전트 ↔ 관리도구 통신
    Server/              서버 API 계약, 통신 클라이언트, 정책 보관
  TimeGuard.Server/      관리 서버 (ASP.NET Core + SQLite)
    Data/                데이터 모델, 정책 조합, 설정
    Api/                 클라이언트용 REST API
    Pages/               관리자 웹 화면
  TimeGuard.Service/     직원 PC 의 Windows 서비스
    GuardWorker.cs       1초 주기 감시 루프
    ServerSync.cs        서버와 정책 동기화
    ControlServer.cs     이름 있는 파이프 서버
    Interop/             전원 제어, 사용자 세션 프로세스 실행
  TimeGuard.Agent/       직원 PC 의 알림 프로그램
    AgentWindow.cs       트레이 아이콘 + 카운트다운 창 (Win32)
    ExtensionRequestDialog.cs   연장 요청 창 (Win32)
  TimeGuard.Admin/       직원 PC 의 설정 도구
tests/
  TimeGuard.Core.Tests/      판정 엔진 단위 테스트
  TimeGuard.Server.Tests/    서버 통합 테스트 + 클라이언트 연동 테스트
build/
  publish.sh                 배포본 생성
  install.ps1                직원 PC 설치
  install-server.ps1         관리 서버 설치
docs/
  설치안내.txt                직원 PC 설치 안내
  서버설치안내.txt            관리 서버 설치 안내
  동작확인_체크리스트.md       실제 Windows 에서 확인할 항목
```
