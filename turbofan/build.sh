#!/usr/bin/env bash
#
# Turbo Fan Design 윈도우 프로그램(exe)을 만든다. 리눅스·윈도우(Git Bash) 어디서나.
#
#   ./turbofan/build.sh            exe 만들기 → release/hanil-turbofan-v<버전>.exe
#   ./turbofan/build.sh --test     만들기 전에 시험(가짜 AutoCAD 로 모든 기능 실행)도 돌린다
#
# 필요한 것: .NET SDK 8 (빌드만 함. 만들어진 exe 는 윈도우 10/11 기본 .NET Framework 4.8 로 돈다)
#
# 원본 VBA(.dvb)를 다시 옮기려면(변환기를 고쳤을 때):
#   python3 turbofan/tools/vba2vb.py
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
VERSION="$(grep -oP '(?<=<Version>)[^<]+' "$HERE/src/TurboFan.vbproj" | head -1)"

if [[ "${1:-}" == "--test" ]]; then
  out="$(mktemp -d)"
  dotnet run --project "$HERE/tests/Runner" -- "$out"
  echo "시험 도면(SVG): $out"
fi

dotnet build "$HERE/src/TurboFan.vbproj" -c Release -nologo -v quiet
mkdir -p "$ROOT/release"
cp "$HERE/src/bin/Release/TurboFanDesign.exe" "$ROOT/release/hanil-turbofan-v$VERSION.exe"
echo "만듦: release/hanil-turbofan-v$VERSION.exe"
