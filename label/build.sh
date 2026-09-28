#!/usr/bin/env bash
# Windows(x64)용 라벨 발행기를 만든다.
#
#   ./label/build.sh
#
# 결과: release/hanil-label.exe  (파일 하나 — 설치 없이 두 번 눌러 실행)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/../release/hanil-label.exe"
cd "$HERE"
#  아이콘·버전 정보(winres/) → rsrc_windows_amd64.syso. go-winres 가 없으면 저장소에 있는 것을 그대로 쓴다.
#   (go install github.com/tc-hib/go-winres@latest)
if command -v go-winres >/dev/null 2>&1; then go-winres make --arch amd64; fi
#  -H windowsgui : 검은 명령창 없이 뜬다
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o "$OUT" .
ls -l "$OUT"
