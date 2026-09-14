# 배포 파일

Windows 64비트용입니다. **대상 PC 에 .NET 을 따로 설치할 필요가 없습니다.**

받는 방법: GitHub 저장소에서 파일을 클릭한 뒤 오른쪽 위 **Download** 버튼

| 파일 | 설치 대상 | 크기 |
|---|---|---|
| `HanilTimeGuard-1.0.0-관리서버-win-x64.zip` | 관리 서버로 쓸 PC **한 대** | 46MB |
| `HanilTimeGuard-1.0.0-직원PC-win-x64.zip` | 시간을 제한할 **직원 PC 들** | 33MB |

## 설치 순서

### 1단계 — 관리 서버 (먼저)

사무실 PC 한 대를 정해 관리서버 zip 을 풀고, **관리자 권한 PowerShell** 에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-server.ps1
```

끝나면 접속 주소와 임시 비밀번호가 나옵니다. 브라우저로 접속해:

1. `admin` 과 임시 비밀번호로 로그인
2. **[설정]** → 비밀번호 변경
3. **[기본 시간표]** → 허용 시간대 지정 (예: 월~금 `09:00-18:00`)
4. **[설정]** → **클라이언트 등록 키** 확인 (다음 단계에 필요)

자세한 내용은 zip 안의 `서버설치안내.txt` 를 보십시오.

### 2단계 — 직원 PC

직원PC zip 을 풀고, **관리자 권한 PowerShell** 에서:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

이어서 서버에 등록합니다. 주소와 등록 키는 1단계에서 확인한 값입니다.

```powershell
& "C:\Program Files\HanilTimeGuard\TimeGuard.Admin.exe" enroll `
    --server http://192.168.0.10:8080 `
    --key ABCDE-FGHIJ-KLMNO-PQRST

net stop HanilTimeGuard
net start HanilTimeGuard
```

등록되면 서버의 **PC 목록** 에 나타납니다.

## 들어 있는 것

**관리서버 zip**

| 파일 | 역할 |
|---|---|
| `TimeGuard.Server.exe` | 관리 서버 (웹 화면 + 시간표 배포) |
| `install-server.ps1` / `uninstall-server.ps1` | 설치 / 제거 |
| `서버설치안내.txt` | 한글 설치 안내 |

**직원PC zip**

| 파일 | 역할 |
|---|---|
| `TimeGuard.Service.exe` | 시간 감시와 전원 차단 (Windows 서비스) |
| `TimeGuard.Agent.exe` | 트레이 아이콘, 경고, 연장 요청 |
| `TimeGuard.Admin.exe` | 서버 등록, 상태 확인 |
| `install.ps1` / `uninstall.ps1` | 설치 / 제거 |
| `설치안내.txt` | 한글 설치 안내 |

## 단독 실행 파일이 필요하다면

직원 PC 용을 exe 하나로 완결된 형태(각 약 35MB)로 만들 수도 있습니다.
용량이 커서 저장소에는 넣지 않았으니 직접 빌드해 주십시오.

```bash
./build/publish.sh --single-file
```

세 exe 는 **반드시 같은 폴더**에 두어야 합니다. 서비스가 같은 폴더에서
`TimeGuard.Agent.exe` 를 찾아 실행하기 때문입니다.

## 설치 후 꼭 해야 할 한 가지

TimeGuard 의 보호는 **직원 계정이 일반 사용자일 때** 제대로 듣습니다.
직원 계정에 관리자 권한이 있으면 서비스를 멈춰 전부 무력화할 수 있습니다.

서버 **PC 목록** 화면이 어느 PC 가 아직 위험한지 빨갛게 알려 줍니다.
표시된 PC 들의 계정 권한을 낮춰 주십시오.

방법은 zip 안의 **`직원계정_권한낮추기.md`** 에 정리되어 있습니다.
PC 한 대에 10분이면 됩니다.

> 그 문서의 **2단계(관리자 계정 먼저 확보)** 를 건너뛰지 마십시오.
> 건너뛰면 그 PC 에서 아무것도 못 하게 됩니다.

## 서버 없이 쓰기

PC 한두 대만 관리한다면 직원PC zip 만 설치하고 서버 등록을 건너뛰면 됩니다.
그 경우 `TimeGuard.Admin.exe` 메뉴에서 직접 시간표를 설정합니다.
