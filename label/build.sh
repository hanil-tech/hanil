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
#  -H windowsgui : 검은 명령창 없이 뜬다
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o "$OUT" .
ls -l "$OUT"
