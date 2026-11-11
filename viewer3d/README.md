# 🧊 한일특장 도면 보기 (viewer3d)

STEP·IGES(3D)와 DWG·DXF(2D) 도면을 **설치 없이 브라우저에서** 봅니다. 파일은 그 기기 밖으로 나가지 않습니다.

| 형식 | 보기 | 엔진 |
|---|---|---|
| `.stp` `.step` `.igs` `.iges` | 3D — 돌리기·맞춤·정면/윗면/옆면·크기(mm)·📏 두 점 거리·부품 켜고 끄기·투명·📷 그림 | OpenCASCADE (`occt-import-js`, WASM) + three.js |
| `.dwg` `.dxf` | 2D — 끌기·확대(손가락 두 개·바퀴)·맞춤·📏 거리·검은/흰 바탕·📷 그림 | LibreDWG (`@mlightcad/libredwg-web`, WASM) → SVG |
| `.CATPart` `.CATProduct` `.CATDrawing` `.cgr` | **미리보기 그림**(v1.2.0 · 100MB 도 몇 초) — CATIA 가 저장할 때 파일 안에 넣어 두는 그림을 꺼내 보임 · 📷 그림 | 직접(JPEG·PNG·BMP 를 찾아 실제로 열리는 가장 큰 것) |

⚠ CATIA 원본은 다쏘 전용 형식이라 **3D 로 돌려 보지는 못합니다** — 들어 있는 미리보기 그림만 보입니다(CATIA 「열기」 창의 그 그림).
  미리보기 없이 저장된 파일은 「미리보기 그림이 없습니다」라고 알려 줍니다. 3D 로 보려면 CATIA 에서 STEP 으로 내보내 여세요.
⚠ DWG 는 AutoCAD 전용 형식이라 특수 객체(표 등)는 일부 안 그려질 수 있습니다 — 그 수를 화면에 「그리지 못한 것 n개」로 알려 줍니다.

## 🏭 큰 도면(100MB 급) — 포털 변환기 (v1.3.0)

브라우저 안 엔진(occt-import-js)은 **부품 수의 제곱으로 느려집니다**(조립품 나무를 읽는 OpenCASCADE XCAF 단계 탓).
시험: 4MB(부품 300) 10초 · 12MB(1,600) 60초 · 33MB(2,400) 3분 · 106MB(7,500) 30분 넘음 — 폰은 더 느리고 메모리가 모자랍니다.

그래서 포털에서는 **포털 서버가 한 번만 가볍게 바꿔 두고**(`.hm3` 묶음, viewer3d-cache/) 다음부터는 그것만 내줍니다.

| 서버에 | 106MB STEP(부품 7,500) 처음 | 다시 열 때 |
|---|---|---|
| **OpenCASCADE(occt-draw)** 깔림 | **약 1분 30초** | 몇 초(받은 미리보기 0.6MB) |
| 없음(설치 없는 엔진으로) | 30분 넘음 | 몇 초 |

- 서버 OpenCASCADE 는 조립품 나무(이름·색)를 안 읽고 모양만 읽어 빠릅니다 → 부품 이름은 「부품 n」, 색은 돌려 가며 칠합니다.
- **CATIA 원본**은 서버가 미리보기 그림만 꺼내 보냅니다(100MB 를 폰으로 받지 않음).
- 2MB 넘는 STEP·IGES 는 서버가, 그보다 작은 것과 DWG·DXF 는 브라우저가 직접 읽습니다(OpenCASCADE 가 없으면 15MB, 폰 4MB 부터 서버).
- 첨부는 **그 사람의 로그인(쿠키)을 붙여** 포털 자신에게 받아 옵니다 → 권한 없는 첨부는 변환도 안 되고, 첨부 길(메신저·결재·게시판)마다 손댈 것이 없습니다.
- 한 번에 하나씩 바꿉니다(나머지는 줄). 30분 넘으면 멈춥니다. 결과는 5GB·60일을 넘으면 오래 안 쓴 것부터 지웁니다.
- 직접 읽을 때도 엔진은 **일꾼(Web Worker)** 에서 돌아 화면이 멈추지 않고 「n초째」가 보입니다.
- **폰 앱**: 포털에 변환기가 있으면 포털의 도면 보기 화면을 엽니다(폰이 원본을 안 받음). 없으면 예전처럼 받아서 앱 안에서.

## 세 군데에서 같은 뷰어를 씁니다

1. **폰 앱** — 포털에서 도면 파일을 누르면 내려받는 대신 앱 안 도면 보기로 열립니다(`Viewer3dActivity`, `assets/viewer3d`).
2. **포털** — `hanil-viewer3d-portal.zip` (아래 「포털에 넣기」).
3. **PC 단독 한 장** — `hanil-drawing-viewer.html` 하나를 더블클릭 → 파일을 끌어다 놓기. 인터넷·서버 없이 열립니다(엔진을 품고 있어 약 23MB).

GitHub 가 APK 를 만들 때 함께 만들어 **Releases** 에 올립니다(`hanil-viewer3d-portal.zip`, `hanil-drawing-viewer.html`).

## 포털에 넣기 (포털 담당)

이 포털은 `express.static` 이 없어 파일마다 길을 내줘야 합니다. 그 길을 `portal/viewer3d-route.js` 로 만들어 두었습니다.

1. `hanil-viewer3d-portal.zip` 을 포털의 `public/` 에 풉니다 → `public/viewer3d/` (index.html · viewer.js · occt-worker.js · dwg.js · 엔진 2개 · 라이선스)
2. `portal/viewer3d-route.js` 와 `portal/viewer3d-convert.js` 를 포털 폴더(`server.js` 옆)에 둡니다.
   - **큰 도면을 빠르게**(권장, 우분투): `sudo apt install -y occt-draw libocct-draw-dev`
     (`libocct-draw-dev` 를 빼면 「libTKTopTest.so 를 못 찾는다」로 안 돕니다 — 점검 화면에 ⚠️ 로 나옵니다)
3. `server.js` 에서 세션이 붙은 뒤(다른 `require('./…')(app, …)` 들 사이) **한 줄**:
   ```js
   require('./viewer3d-route')(app);
   ```
4. 포털을 다시 띄웁니다.

**여는 주소**

- 파일 고르기 화면: `/viewer3d`
- 첨부를 바로 열기: `/viewer3d/view?src=<파일 주소(인코딩)>&name=<파일 이름(인코딩)>`
  - 메신저 첨부: `/viewer3d/view?src=%2Fapi%2Fchat%2Ffile%2F123&name=bracket.stp`
  - 결재 첨부: `/viewer3d/view?src=%2Fapi%2Fappr%2Ffile%2Fabc.dwg&name=%EB%8F%84%EB%A9%B4.dwg`
  - 화면에 단추를 달 때(예): 파일 이름이 `.stp/.step/.igs/.iges/.dwg/.dxf/.catpart/.catproduct` 이면 옆에 `🧊 미리보기` 링크를
    `'/viewer3d/view?src=' + encodeURIComponent(파일주소) + '&name=' + encodeURIComponent(파일이름)` 로.

**안 보일 때 — 먼저 점검 화면**: `/viewer3d/view?check=1`
그래픽 가속·WebAssembly·3D 엔진·2D 엔진·예시 STEP 읽기·**포털 변환기(서버 OpenCASCADE 있는지)** 를 한 화면에 ✅/⚠️/❌ 로 보여 줍니다.

- **그래픽 가속(WebGL)이 꺼진 PC**(원격 데스크톱·옛 드라이버·막아 둔 브라우저)도 **간이 미리보기**로 보입니다(돌려 보기·크기·그림 저장은 됨).
  ⚠ v1.0.0 은 이때 스크립트 전체가 멈춰 3D·DWG 모두 빈 화면이었습니다 → v1.1.0 에서 고침.
- 못 열면 **까닭을 화면 가운데** 적습니다: 서버 답(401/403/404), 「파일 대신 화면(HTML)이 왔습니다」(로그인 화면이거나
  내려받기 주소가 아닌 다른 화면 주소를 src 에 준 것), 빈 파일 등. **src 에는 첨부를 「내려받는」 주소**를 주세요.

**확인한 것**(포털 v13.41.0 을 띄워 시험)

- 로그인 안 했으면 로그인 화면 → 로그인하면 그 도면으로 돌아옵니다.
- 메신저에 올린 STEP·DWG 를 실제 첨부 주소(`/api/chat/file/…`)로 열어 3D·2D 로 그려짐.
- 화면 주소가 `/view` 로 끝나 포털 공통 조각(쪽지함·동그란 단추·화면 줄이기)이 **안 끼고**, `data-notheme="1"` 로 테마도 안 덮입니다.
  (`/viewer3d/index.html` 로 바로 열면 `/view` 로 돌려보냅니다.)
- 정해 둔 파일 이름 말고는 내주지 않습니다(`/viewer3d/../server.js` → 404).
- 포털 CSP(`script-src 'unsafe-eval'`)에서 WASM 엔진이 돕니다. 엔진은 브라우저가 7일 받아 둡니다.

## 만들기

```
cd viewer3d
npm ci
npm run build      # → out/portal/viewer3d · out/hanil-3d-viewer.html · ../android/app/src/main/assets/viewer3d
```

## 라이선스

- three.js — MIT · occt-import-js / OpenCASCADE — LGPL-2.1 · LibreDWG / libredwg-web — GPL-3.0
- 라이선스 글은 `public/viewer3d/license.*.txt` 에 함께 들어갑니다(사내에서 쓰는 것).
