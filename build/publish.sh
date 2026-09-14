#!/usr/bin/env bash
# Windows(x64)용 배포 파일을 만든다.
# 세 프로그램을 같은 폴더에 내보내 .NET 런타임 파일을 공유하게 한다.
# 결과물은 dist/TimeGuard 이며, 대상 PC 에 .NET 설치가 필요 없다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/dist/TimeGuard"

rm -rf "$OUT"
mkdir -p "$OUT"

COMMON=(
  -c Release
  -r win-x64
  --self-contained true
  -p:EnableWindowsTargeting=true
  -p:PublishSingleFile=false
  -p:DebugType=none
  -p:GenerateDocumentationFile=false
  -o "$OUT"
)

for project in TimeGuard.Service TimeGuard.Agent TimeGuard.Admin; do
  echo "==> $project 빌드 중"
  dotnet publish "$ROOT/src/$project/$project.csproj" "${COMMON[@]}" --nologo -v minimal
done

cp "$ROOT/build/install.ps1"   "$OUT/"
cp "$ROOT/build/uninstall.ps1" "$OUT/"
cp "$ROOT/docs/설치안내.txt"    "$OUT/" 2>/dev/null || true

echo
echo "완료: $OUT"
ls -la "$OUT" | grep -E '\.exe$|\.ps1$' || true
