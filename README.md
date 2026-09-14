# 한일 TimeGuard

관리자가 지정한 허용 시간대를 벗어나면 사용자에게 단계별로 안내한 뒤 컴퓨터 전원을 차단하는 Windows 프로그램입니다.

## 무엇을 하는가

- 관리자가 **요일별 허용 시간대**를 정합니다 (예: 평일 09:00~18:00, 주말 사용 불가).
- 허용 시간이 끝나기 전에 **10분 / 5분 / 1분 전 알림**을 띄웁니다.
- 마지막 **60초 카운트다운 창**이 화면 최상위에 뜹니다. 사용자는 이 창을 닫을 수 없습니다.
- 시간이 다 되면 **전원 차단**(또는 로그오프 / 화면 잠금)을 실행합니다.
- 설정 변경에는 **관리자 비밀번호**가 필요합니다.
- 감시 본체는 **Windows 서비스(SYSTEM 권한)** 라 일반 사용자가 작업 관리자로 끌 수 없습니다.

## 구성

| 프로그램 | 실행 위치 | 역할 |
|---|---|---|
| `TimeGuard.Service.exe` | Windows 서비스 (SYSTEM) | 시간 감시, 전원 차단 실행, 설정 보관 |
| `TimeGuard.Agent.exe` | 사용자 세션 | 트레이 아이콘, 경고 알림, 카운트다운 창 |
| `TimeGuard.Admin.exe` | 관리자가 실행 | 비밀번호 인증 후 설정 변경 |

세 프로그램은 이름 있는 파이프(`HanilTimeGuard.Control`)로 통신합니다.

### 왜 이렇게 나누었나

Windows 서비스는 세션 0에 격리되어 있어 사용자 화면에 창을 띄울 수 없습니다. 그래서 **판정과 조치는 서비스**가, **화면 표시는 에이전트**가 맡습니다.

이 구조 덕분에 **사용자가 에이전트를 강제 종료해도 차단은 그대로 실행됩니다**. 경고만 못 볼 뿐입니다. 게다가 서비스가 30초마다 확인해 에이전트를 다시 띄웁니다.

## 설치

배포 폴더(`dist/TimeGuard`)를 대상 PC에 복사한 뒤, **관리자 권한 PowerShell**에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

설치 스크립트가 하는 일:

1. `C:\Program Files\HanilTimeGuard` 에 파일 복사
2. `C:\ProgramData\HanilTimeGuard` 생성 후 **일반 사용자는 읽기 전용**으로 권한 설정
3. `HanilTimeGuard` 서비스 등록 (자동 시작, 비정상 종료 시 자동 복구)
4. 에이전트를 시작 프로그램에 등록
5. 서비스 시작

> .NET 설치가 필요 없습니다. 런타임이 함께 들어 있습니다 (약 74MB).

### 설치 직후 반드시 할 일

설치 직후에는 **감시가 꺼져 있어 아무도 제한받지 않습니다.** 설정을 실수로 잘못 넣은 채 PC가 꺼지는 일을 막기 위한 의도된 동작입니다.

`TimeGuard.Admin.exe` 를 실행해 다음 순서로 진행하세요.

| 순서 | 메뉴 | 내용 |
|---|---|---|
| 1 | `10` 관리자 비밀번호 변경 | 비밀번호를 먼저 정합니다. 이게 없으면 감시를 켤 수 없습니다 |
| 2 | `2` 허용 시간대 설정 | 예: 평일 `09:00-18:00`, 주말 `없음` |
| 3 | `4` 시간 초과 시 조치 | 전원 차단 / 로그오프 / 화면 잠금 |
| 4 | `5` 경고 방식 설정 | 경고 단계와 카운트다운 시간 (기본값 그대로도 됩니다) |
| 5 | `3` 감시 켜기 | **이때부터 실제로 동작합니다** |

## 관리자 도구 사용법

### 대화형 메뉴

`TimeGuard.Admin.exe` 를 그냥 실행하면 메뉴가 열립니다.

```
  1. 현재 상태 자세히 보기      7. 일시 중지 / 해제
  2. 허용 시간대 설정           8. 휴일 관리
  3. 감시 켜기 / 끄기           9. 제한 제외 계정 관리
  4. 시간 초과 시 조치 변경    10. 관리자 비밀번호 변경
  5. 경고 방식 설정            11. 기록 보기
  6. 임시 연장 부여             0. 종료
```

### 명령줄 (여러 대를 한 번에 설정할 때)

```powershell
TimeGuard.Admin.exe status                                  # 현재 상태
TimeGuard.Admin.exe set-window 평일 09:00-18:00 -p 비밀번호
TimeGuard.Admin.exe set-window 주말 없음 -p 비밀번호
TimeGuard.Admin.exe extend 30 -p 비밀번호                    # 지금부터 30분 연장
TimeGuard.Admin.exe suspend 60 -p 비밀번호                   # 60분간 감시 중지
TimeGuard.Admin.exe enable -p 비밀번호
TimeGuard.Admin.exe log 50 -p 비밀번호
```

### 시간대 표기법

| 입력 | 뜻 |
|---|---|
| `09:00-18:00` | 하루 한 구간 |
| `09:00-12:00,13:00-18:00` | 점심시간 제외 (두 구간) |
| `22:00-06:00` | 자정을 넘기는 야간 구간 |
| `없음` | 그 요일은 사용 불가 |
| `종일` | 24시간 허용 |

## 현장에서 자주 쓰는 기능

**임시 연장** (메뉴 `6`) — 야근 등으로 오늘만 더 써야 할 때. 설정을 건드리지 않고 지금부터 N분만 늘려 줍니다. 다음 날부터는 원래 시간대로 돌아갑니다.

**일시 중지** (메뉴 `7`) — 점검이나 프로그램 설치 중에 PC가 꺼지면 곤란할 때. 지정한 시간 동안 감시 자체를 멈춥니다.

**제한 제외 계정** (메뉴 `9`) — 관리자 계정은 시간 제한을 받지 않게 등록해 둘 수 있습니다. 설치 직후 등록해 두기를 권합니다.

**휴일 관리** (메뉴 `8`) — 특정 날짜를 휴일로 지정합니다. 기본은 휴일에 사용 불가이며, 반대로 휴일에만 제한을 풀 수도 있습니다.

## 안전장치

시간 제한 프로그램이 오작동해 업무 PC가 꺼지면 피해가 큽니다. 다음과 같이 **의심스러우면 차단하지 않는 쪽**으로 만들었습니다.

| 상황 | 동작 |
|---|---|
| 설정 파일이 없음 | 감시 꺼짐 상태로 동작 |
| 설정 파일이 손상됨 | 감시 꺼짐 상태로 동작 (절대로 켜진 채 넘어가지 않음) |
| 비밀번호 미설정 | 감시를 켤 수 없음 |
| 감시 루프에서 오류 발생 | 오류를 기록하고 다음 초에 계속 (서비스는 죽지 않음) |
| 전원 차단 실패 | 기록 후 30초 뒤 재시도 |
| 조치 실행 직후 | 5분간 중복 실행 안 함 |

또한 **허용 시간대 밖에서 PC를 켠 경우**에는 곧바로 끄지 않고 기본 120초의 유예를 줍니다. 작업을 저장할 시간이 필요하기 때문입니다. 반대로 사용 중에 허용 시간이 끝난 경우에는 이미 10분 전부터 경고했으므로 유예 없이 바로 실행합니다.

## 파일 위치

```
C:\Program Files\HanilTimeGuard\      프로그램 파일
C:\ProgramData\HanilTimeGuard\
    config.json                        설정 (일반 사용자는 읽기 전용)
    timeguard.log                      조치·설정 변경 기록
```

설정 파일은 사람이 읽을 수 있는 JSON 이고 시간은 `"09:00"` 형태로 저장됩니다. 다만 직접 고치기보다 관리자 도구를 쓰기를 권합니다. 서비스는 설정 파일이 바뀌면 자동으로 다시 읽습니다.

## 제거

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1

# 설정과 기록을 남기려면
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1 -KeepSettings
```

## 개발자용

### 빌드

```bash
./build/publish.sh        # dist/TimeGuard 에 win-x64 자체 포함 배포본 생성
```

Windows 에서는 다음과 같이 합니다.

```powershell
dotnet publish src\TimeGuard.Service\TimeGuard.Service.csproj -c Release -r win-x64 --self-contained true -o dist\TimeGuard
dotnet publish src\TimeGuard.Agent\TimeGuard.Agent.csproj     -c Release -r win-x64 --self-contained true -o dist\TimeGuard
dotnet publish src\TimeGuard.Admin\TimeGuard.Admin.csproj     -c Release -r win-x64 --self-contained true -o dist\TimeGuard
```

세 프로젝트를 **같은 폴더**로 내보내야 합니다. 서비스가 같은 폴더에서 `TimeGuard.Agent.exe` 를 찾아 실행하고, .NET 런타임 파일도 공유합니다.

### 테스트

```bash
dotnet test
```

스케줄 판정 로직은 부작용 없는 순수 계산으로 분리해 두어 Windows 없이도 전부 검증됩니다 (58개 테스트).

### 서비스를 콘솔에서 직접 실행 (동작 확인용)

```powershell
# 관리자 권한 명령 프롬프트에서
"C:\Program Files\HanilTimeGuard\TimeGuard.Service.exe"
```

서비스로 등록하지 않아도 앞단에서 실행되어 로그를 바로 볼 수 있습니다. Ctrl+C 로 종료합니다.

### UI 구현에 관하여

경고 창과 트레이 아이콘은 WinForms/WPF 없이 **Win32 API 직접 호출**로 만들었습니다. 배포본에 Windows Desktop 런타임이 필요 없어 용량이 줄고, Linux/CI 환경에서도 Windows용 바이너리를 빌드할 수 있습니다.

## 프로젝트 구조

```
src/
  TimeGuard.Core/        설정 모델, 스케줄 판정 엔진, 비밀번호 해시, IPC 계약  (플랫폼 무관)
    Config/              GuardConfig, WeeklySchedule, TimeWindow, ConfigStore, PasswordHasher
    Schedule/            ScheduleEvaluator — "지금 써도 되는가" 판정
    Ipc/                 IpcContracts, ControlClient
  TimeGuard.Service/     Windows 서비스
    GuardWorker.cs       1초 주기 감시 루프
    ControlServer.cs     이름 있는 파이프 서버
    Interop/             전원 제어, 사용자 세션 프로세스 실행
  TimeGuard.Agent/       사용자 세션 알림 프로그램
    AgentWindow.cs       트레이 아이콘 + 카운트다운 창 (Win32)
  TimeGuard.Admin/       관리자 설정 도구
tests/
  TimeGuard.Core.Tests/  판정 엔진 단위 테스트
build/
  publish.sh             배포본 생성
  install.ps1            설치
  uninstall.ps1          제거
```
