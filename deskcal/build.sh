#!/usr/bin/env bash
# Windows(x64)용 바탕화면 달력과 포털에 넣을 일정 조각을 만든다.
#
#   ./deskcal/build.sh
#
# 결과: release/hanil-cal-v<판>.exe          (직원 PC — 두 번 누르면 설치·실행)
#       release/hanil-cal-portal.zip         (포털 서버 — calendar-route.js · calendar-page.html · 설치안내)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VER="$(grep -oP '(?<=const VERSION = ")[^"]+' "$HERE/main.go")"
REL="$HERE/../release"
OUT="$REL/hanil-cal-v$VER.exe"
rm -f "$REL"/hanil-cal-v*.exe
cd "$HERE"
#  아이콘·버전 정보(winres/) → rsrc_windows_amd64.syso  (go install github.com/tc-hib/go-winres@latest)
if command -v go-winres >/dev/null 2>&1; then go-winres make --arch amd64; fi
#  -H windowsgui : 검은 명령창 없이 뜬다
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o "$OUT" .
#  ✍ 코드 서명(인증서가 있을 때만):  SIGN_PFX=인증서.pfx SIGN_PASS=암호 ./deskcal/build.sh
if [ -n "${SIGN_PFX:-}" ]; then
  osslsigncode sign -pkcs12 "$SIGN_PFX" ${SIGN_PASS:+-pass "$SIGN_PASS"} \
    -n "한일 바탕화면 달력" -h sha256 -t http://timestamp.digicert.com \
    -in "$OUT" -out "$OUT.signed" && mv "$OUT.signed" "$OUT"
fi
#  포털 조각 — ⚠ zip 명령은 한글 이름이 윈도에서 깨진다 → 파이썬 zipfile
python3 - "$REL/hanil-cal-portal.zip" <<'PY'
import sys, zipfile
out = sys.argv[1]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('설치안내.txt', open('portal/설치안내.txt', encoding='utf-8').read().replace('\n', '\r\n').encode('utf-8-sig'))
    z.write('portal/calendar-route.js', 'calendar-route.js')
    z.write('page.html', 'calendar-page.html')   #  폰·브라우저 /calendar — 바탕화면 달력과 같은 화면
PY
#  안내 글의 내려받기 링크도 새 이름으로
sed -i -E "s#hanil-cal-v[0-9.]+\.exe#hanil-cal-v$VER.exe#g" "$REL/README.md" "$HERE/README.md"
ls -l "$OUT" "$REL/hanil-cal-portal.zip"
