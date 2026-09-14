# 배포 파일

## HanilTimeGuard-1.0.0-win-x64.zip

Windows 64비트용 설치 파일입니다. **대상 PC 에 .NET 을 따로 설치할 필요가 없습니다.**

### 받는 방법

GitHub 저장소에서 이 파일을 클릭한 뒤 오른쪽 위의 **Download** 버튼을 누르면 내려받아집니다.

### 설치 순서

1. 압축을 풉니다.
2. 시작 메뉴에서 **PowerShell** 을 찾아 마우스 오른쪽 클릭 → **[관리자 권한으로 실행]**
3. 압축을 푼 폴더로 이동해 아래를 입력합니다.

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

4. 설치가 끝나면 `TimeGuard.Admin.exe` 를 실행해 비밀번호와 허용 시간대를 설정합니다.

자세한 내용은 압축 파일 안의 `설치안내.txt` 또는 저장소 최상위의 `README.md` 를 보십시오.

> **설치 직후에는 감시가 꺼져 있어 아무도 제한받지 않습니다.**
> 관리자 도구에서 비밀번호를 정하고 시간대를 넣은 뒤 감시를 켜야 동작합니다.

### 들어 있는 것

| 파일 | 역할 |
|---|---|
| `TimeGuard.Service.exe` | Windows 서비스. 시간 감시와 전원 차단 실행 |
| `TimeGuard.Agent.exe` | 사용자 화면의 트레이 아이콘과 경고 창 |
| `TimeGuard.Admin.exe` | 관리자 설정 도구 |
| `install.ps1` / `uninstall.ps1` | 설치 / 제거 스크립트 |
| `설치안내.txt` | 한글 설치 안내 |
| 그 외 | .NET 런타임 파일 (세 프로그램이 공유) |

## 단독 실행 파일이 필요하다면

각 프로그램을 exe 하나로 완결된 형태(각 약 35MB)로 만들 수도 있습니다.
용량이 커서 저장소에는 넣지 않았으니 직접 빌드해 주십시오.

```bash
./build/publish.sh --single-file    # dist/TimeGuard-단독실행/ 에 생성
```

다만 **세 exe 는 반드시 같은 폴더에 두어야 합니다.** 서비스가 같은 폴더에서
`TimeGuard.Agent.exe` 를 찾아 실행하기 때문입니다.

일반적인 설치에는 위의 zip 배포본을 쓰는 편이 용량도 작고 간편합니다.
