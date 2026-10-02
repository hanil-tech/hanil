#!/usr/bin/env bash
# Windows(x64)용 라벨 발행기를 만든다.
#
#   ./label/build.sh
#
# 결과: release/hanil-label.exe  (파일 하나 — 설치 없이 두 번 눌러 실행)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#  📛 파일 이름은 늘 같게(사용자 「쉽게, 간단하게」) — 판 번호는 창 제목·파일 속성에서 본다
REL="$HERE/../release"
OUT="$REL/hanil-label.exe"
rm -f "$REL"/hanil-label*.exe
cd "$HERE"
#  아이콘·버전 정보(winres/) → rsrc_windows_amd64.syso. go-winres 가 없으면 저장소에 있는 것을 그대로 쓴다.
#   (go install github.com/tc-hib/go-winres@latest)
if command -v go-winres >/dev/null 2>&1; then go-winres make --arch amd64; fi
#  -H windowsgui : 검은 명령창 없이 뜬다
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o "$OUT" .
#  ✍ 코드 서명 — SmartScreen 「게시자」 칸에 회사 이름이 나오게 하는 유일한 방법.
#   인증서(.pfx)가 있을 때만 한다:  SIGN_PFX=인증서.pfx SIGN_PASS=암호 ./label/build.sh
#   ⚠ 요즘 인증서는 USB 토큰·클라우드에 들어 있어 .pfx 로 못 꺼내는 경우가 많다 →
#     그때는 윈도우에서: signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a hanil-label.exe
if [ -n "${SIGN_PFX:-}" ]; then
  osslsigncode sign -pkcs12 "$SIGN_PFX" ${SIGN_PASS:+-pass "$SIGN_PASS"} \
    -n "한일 라벨 발행기" -h sha256 -t http://timestamp.digicert.com \
    -in "$OUT" -out "$OUT.signed" && mv "$OUT.signed" "$OUT"
  echo "서명했습니다"
fi
sed -i -E "s#hanil-label(-v[0-9.]+)?\.exe\)#hanil-label.exe)#g" "$REL/README.md" "$HERE/README.md"
ls -l "$OUT"
