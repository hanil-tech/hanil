#!/usr/bin/env bash
# 📕 한일 PDF 리더 — 모두 만들기
#   ./pdfreader/build-all.sh
# 결과(release/): hanil-pdf-v<판>.exe — 프로그램 하나가 세 가지를 한다
#   ① PDF 보기·찾기·고치기 창  ② 크롬·엣지에서 연 PDF 도 이 프로그램으로  ③ 탐색기 미리 보기
#   (설치가 안 되는 PC 용 브라우저 한 장은 프로그램 안 「내보내기 → 브라우저용 파일」로 만든다)
#   out/ 에는 브라우저 한 장(hanil-pdf-reader.html)·크롬 확장(chrome/)도 남는다 — 시험·포털용
# 필요한 것: node 20+, go 1.24+, python3. zig(C 컴파일러)·PDFium 은 처음 한 번 받아 ~/.cache/hanil-pdf 에 둔다.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REL="$HERE/../release"
CACHE="${HANIL_CACHE:-$HOME/.cache/hanil-pdf}"
mkdir -p "$CACHE"
VER="$(node -p "require('$HERE/package.json').version")"

echo "① 리더(브라우저 · 크롬 확장)"
cd "$HERE"
[ -d node_modules ] || npm ci --no-audit --no-fund
node build.mjs
rm -f out/hanil-pdf-chrome.zip
(cd out/chrome && zip -qr ../hanil-pdf-chrome.zip .)

echo "② 탐색기 미리 보기 DLL (C · zig cc · PDFium)"
ZIG="$CACHE/zig/ziglang/zig"
if [ ! -x "$ZIG" ]; then
  python3 -m pip download ziglang==0.13.0 --no-deps -d "$CACHE/zigdl" -q
  python3 -m pip install --target "$CACHE/zig" "$CACHE"/zigdl/ziglang-0.13.0-*.whl -q
fi
if [ ! -f "$CACHE/pdfium/bin/pdfium.dll" ]; then
  mkdir -p "$CACHE/pdfium"
  curl -sSL -o "$CACHE/pdfium/pdfium.tgz" https://github.com/bblanchon/pdfium-binaries/releases/latest/download/pdfium-win-x64.tgz
  tar xzf "$CACHE/pdfium/pdfium.tgz" -C "$CACHE/pdfium"
fi
A="$HERE/win/app/assets"
mkdir -p "$A"
"$ZIG" cc -target x86_64-windows-gnu -shared -O2 -o "$A/hanil-pdf-preview.dll" \
  "$HERE/win/preview/preview.c" "$HERE/win/preview/preview.def" -lole32 -luuid -lshlwapi -lgdi32 -luser32 -ladvapi32 -lshell32
cp "$CACHE/pdfium/bin/pdfium.dll" "$A/pdfium.dll"
cp "$HERE/out/hanil-pdf-reader.html" "$A/reader.html"

echo "③ 윈도우 프로그램 (Go · WebView2)"
cd "$HERE/win/app"
sed -i "s/const VERSION = \"[^\"]*\"/const VERSION = \"$VER\"/; s/^\tVERSION = \"[^\"]*\"/\tVERSION = \"$VER\"/" main.go
sed -i "s/\"[0-9.]*\.0\"/\"$VER.0\"/g; s/\"FileVersion\": \"[^\"]*\"/\"FileVersion\": \"$VER\"/; s/\"ProductVersion\": \"[^\"]*\"/\"ProductVersion\": \"$VER\"/" winres/winres.json
if command -v go-winres >/dev/null 2>&1 || [ -x "$(go env GOPATH)/bin/go-winres" ]; then
  PATH="$PATH:$(go env GOPATH)/bin" go-winres make --arch amd64
fi
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-H windowsgui" -o "$HERE/out/hanil-pdf-v$VER.exe" .

echo "④ release/ 에 넣기"
rm -f "$REL"/hanil-pdf-v*.exe "$REL"/hanil-pdf-reader.html "$REL"/hanil-pdf-chrome.zip
cp "$HERE/out/hanil-pdf-v$VER.exe" "$REL/"
#  🔄 자동 업데이트용 판 정보 — 깔린 프로그램이 이것을 읽고 새 판이면 받아 깐다(크기·SHA-256 확인)
#     ⚠ exe 와 같은 커밋에 올려야 한다(json 만 먼저 올라가면 받다가 크기가 안 맞아 다음 확인 때 다시 받음)
node -e '
const fs = require("fs"), c = require("crypto"), [f, out, ver, notes] = process.argv.slice(1);
const b = fs.readFileSync(f);
fs.writeFileSync(out, JSON.stringify({ version: ver, file: require("path").basename(f), size: b.length, sha256: c.createHash("sha256").update(b).digest("hex"), notes }, null, 1) + "\n");
' "$REL/hanil-pdf-v$VER.exe" "$REL/hanil-pdf.json" "$VER" "$(node -p "require('$HERE/package.json').updateNotes || ''")"
cat "$REL/hanil-pdf.json"
ls -la "$REL"/hanil-pdf*
