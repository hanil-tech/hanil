# 🧊 한일특장 도면 보기 (viewer3d)

STEP·IGES(3D)와 DWG·DXF(2D) 도면을 **설치 없이 브라우저에서** 봅니다. 파일은 그 기기 밖으로 나가지 않습니다.

| 형식 | 보기 | 엔진 |
|---|---|---|
| `.stp` `.step` `.igs` `.iges` | 3D — 돌리기·맞춤·정면/윗면/옆면·크기(mm)·📏 두 점 거리·부품 켜고 끄기·투명·📷 그림 | OpenCASCADE (`occt-import-js`, WASM) + three.js |
| `.dwg` `.dxf` | 2D — 끌기·확대(손가락 두 개·바퀴)·맞춤·📏 거리·검은/흰 바탕·📷 그림 | LibreDWG (`@mlightcad/libredwg-web`, WASM) → SVG |

⚠ **CATIA 원본(.CATPart·.CATProduct)은 열 수 없습니다**(다쏘 독점 형식). CATIA 에서 STEP 으로 내보내 여세요.
⚠ DWG 는 AutoCAD 전용 형식이라 특수 객체(표 등)는 일부 안 그려질 수 있습니다 — 그 수를 화면에 「그리지 못한 것 n개」로 알려 줍니다.

## 세 군데에서 같은 뷰어를 씁니다

1. **폰 앱** — 포털에서 도면 파일을 누르면 내려받는 대신 앱 안 도면 보기로 열립니다(`Viewer3dActivity`, `assets/viewer3d`).
2. **포털** — `hanil-viewer3d-portal.zip` (아래 「포털에 넣기」).
3. **PC 단독 한 장** — `hanil-drawing-viewer.html` 하나를 더블클릭 → 파일을 끌어다 놓기. 인터넷·서버 없이 열립니다(엔진을 품고 있어 약 23MB).

GitHub 가 APK 를 만들 때 함께 만들어 **Releases** 에 올립니다(`hanil-viewer3d-portal.zip`, `hanil-drawing-viewer.html`).

## 포털에 넣기 (포털 담당)

이 포털은 `express.static` 이 없어 파일마다 길을 내줘야 합니다. 그 길을 `portal/viewer3d-route.js` 로 만들어 두었습니다.

1. `hanil-viewer3d-portal.zip` 을 포털의 `public/` 에 풉니다 → `public/viewer3d/` (index.html · viewer.js · dwg.js · 엔진 2개 · 라이선스)
2. `portal/viewer3d-route.js` 를 포털 폴더(`server.js` 옆)에 둡니다.
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
  - 화면에 단추를 달 때(예): 파일 이름이 `.stp/.step/.igs/.iges/.dwg/.dxf` 이면 옆에 `🧊 미리보기` 링크를
    `'/viewer3d/view?src=' + encodeURIComponent(파일주소) + '&name=' + encodeURIComponent(파일이름)` 로.

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
