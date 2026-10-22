# 한일 판금 전개

3D 판금 도면(STEP)을 열면 **펼친 모양(전개도)** 을 계산해 **레이저 가공용 DXF** 로 저장하는 Windows 프로그램입니다.

- 두께는 자동으로 잽니다.
- K 계수를 회사 기준값으로 바꾸면 바로 다시 계산합니다.
- 절곡 목록(번호, 위/아래 방향, 각도, 안쪽 R, 펼친 길이)을 보여 주고 DXF 에도 적습니다.
- 여러 파일을 한꺼번에 DXF 로 바꿀 수 있습니다.

![화면](docs/screenshot.png)

## 어떤 파일을 열 수 있나

| 파일 | 열 수 있나 | 방법 |
|---|---|---|
| STEP (`.stp`, `.step`) | **바로 열림** | — |
| IGES (`.igs`, `.iges`) | 바로 열림 | — |
| 솔리드웍스 (`.sldprt`) | STEP 으로 저장 후 | 파일 → 다른 이름으로 저장 → **STEP AP214** |
| NX (`.prt`) | STEP 으로 저장 후 | 파일 → 내보내기 → **STEP** |
| CATIA (`.CATPart`) | STEP 으로 저장 후 | File → Save As → **stp** |
| AutoCAD 3D (`.dwg`) | STEP 으로 저장 후 | 3D 솔리드를 STEP 으로 내보내기 |

솔리드웍스·NX·CATIA·DWG 파일은 각 회사 고유 형식이라, 무료로 쓸 수 있는 3D 엔진(OpenCASCADE)으로는
직접 읽을 수 없습니다. 이런 파일을 열면 프로그램이 **어디서 어떻게 STEP 으로 저장하는지** 안내합니다.
STEP 은 세 CAD 모두 기본으로 지원하고, 판금 형상이 그대로 담깁니다.

> 고유 형식을 바로 열려면 CAD Exchanger, HOOPS Exchange 같은 **유료 변환 라이브러리**를 사야 합니다.
> 필요하시면 붙일 수 있는 구조로 만들어 두었습니다 (`hanil_unfold/loader.py`).

## 사용법

1. **[열기]** 또는 STEP 파일을 창에 끌어다 놓기
2. 왼쪽에 3D 형상, 오른쪽에 전개도, 아래에 절곡 목록이 나옵니다.
3. **K 계수**를 회사 기준값으로 맞춥니다 (기본 0.44).
4. **[DXF 저장]**

### DXF 레이어

| 레이어 | 내용 | 색 |
|---|---|---|
| `CUT` | 외곽선, 구멍 (절단) | 흰색 실선 |
| `BEND` | 절곡선 (절곡부 가운데) | 노란색 점선 |
| `NOTE` | `B1 UP 90.0° R2.00` 같은 절곡 글씨, 두께·크기 | 초록색 |

가공기로 보낼 때는 `NOTE` 레이어를 끄거나, 툴바의 **[DXF 에 절곡 글씨 넣기]** 를 끄고 저장하세요.
구멍과 라운드는 원·호로, 직선은 선으로 정확히 나옵니다.

### 방향 (UP / DOWN)

DXF 를 화면에 놓고 위에서 본다고 할 때

- **UP** : 플랜지가 보는 사람 쪽으로 올라옴
- **DOWN** : 반대쪽으로 내려감

## 계산 방법

```
펼친 길이 = 플랜지 직선 길이의 합 + Σ 절곡각(라디안) × (안쪽 R + K × 두께)
```

솔리드웍스·NX 의 **K 계수 방식**과 같은 식입니다. 같은 K 를 넣으면 같은 전개 길이가 나옵니다.
회사에서 굽힘 공제(BD) 표를 쓰신다면 K 계수로 환산해 넣으시면 됩니다.

## 전개할 수 있는 형상

- 두께가 일정한 판금 부품 (솔리드)
- 절곡부가 **원통(R)** 인 것 — ㄱ·ㄷ·Z 자, 상자·트레이, 헤밍(거의 180°), 둥글게 만 관
- 플랜지나 절곡부에 뚫린 구멍

지원하지 않는 것: 원뿔 절곡(깔때기), 프레스 성형(엠보·루버 같은 자유곡면), 용접으로 붙인 조립품.
이런 면이 있으면 전개도 아래에 경고가 뜹니다.

## 설치 파일 만들기 (개발자용)

`unfold/` 를 고쳐서 GitHub 에 올리면 **GitHub Actions** 가 Windows 에서 자동으로

1. 전개 시험(`tests/`)을 돌리고
2. 실행 파일을 만들어 견본 STEP 을 실제로 전개해 본 뒤
3. 설치 파일 `HanilUnfold-Setup.exe` 를 만듭니다.

결과는 저장소 **Actions** 탭 → 해당 실행 → 아래 **Artifacts** 의 `HanilUnfold-Setup` 에서 받습니다.

직접 만들려면 Windows 에서 (Python 3.12):

```bat
cd unfold
pip install -r requirements.txt pyinstaller pytest
python -m pytest tests
pyinstaller packaging\HanilUnfold.spec --noconfirm
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\setup.iss
```

화면 없이 변환만 할 때:

```bat
python -m hanil_unfold convert 부품.step -k 0.44 -o 결과폴더
HanilUnfold.exe convert 부품.step -k 0.44 -o 결과폴더
```

### 폴더 구성

| 경로 | 내용 |
|---|---|
| `hanil_unfold/loader.py` | STEP·IGES 읽기, 고유 형식 안내 |
| `hanil_unfold/unfolder.py` | 전개 계산 |
| `hanil_unfold/dxf_export.py` | DXF 저장 |
| `hanil_unfold/app.py` | 화면 |
| `samples/` | 시험용 STEP (브래킷, 트레이, 파이프) |
| `tests/` | 손 계산 값과 비교하는 시험 |
| `packaging/` | 실행 파일·설치 파일 설정 |
