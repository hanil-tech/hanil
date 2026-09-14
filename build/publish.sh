#!/usr/bin/env bash
#
# Windows(x64)용 배포 파일을 만든다.
#
#   ./build/publish.sh                기본 배포본 (세 프로그램이 .NET 런타임을 공유)
#   ./build/publish.sh --single-file  단독 실행 파일 (각 exe 하나로 완결)
#   ./build/publish.sh --all          둘 다 만들고 zip 으로 묶는다
#
# 어느 쪽이든 대상 PC 에 .NET 을 따로 설치할 필요가 없다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(grep -oP '(?<=<Version>)[^<]+' "$ROOT/Directory.Build.props" | head -1)"
PROJECTS=(TimeGuard.Service TimeGuard.Agent TimeGuard.Admin)

MODE="shared"
case "${1:-}" in
  --single-file) MODE="single" ;;
  --all)         MODE="all" ;;
  --help|-h)     sed -n '3,10p' "$0"; exit 0 ;;
  "")            ;;
  *)             echo "알 수 없는 옵션: $1"; exit 1 ;;
esac

# 배포 폴더에 함께 넣을 파일들
copy_extras() {
  local out="$1"
  cp "$ROOT/build/install.ps1"   "$out/"
  cp "$ROOT/build/uninstall.ps1" "$out/"
  cp "$ROOT/docs/설치안내.txt"    "$out/"
}

publish_shared() {
  local out="$ROOT/dist/TimeGuard"
  echo "=== 기본 배포본 (런타임 공유) ==="
  rm -rf "$out"; mkdir -p "$out"

  for project in "${PROJECTS[@]}"; do
    echo "--> $project"
    dotnet publish "$ROOT/src/$project/$project.csproj" \
      -c Release -r win-x64 --self-contained true \
      -p:EnableWindowsTargeting=true \
      -p:PublishSingleFile=false \
      -p:DebugType=none \
      -o "$out" --nologo -v quiet
  done

  copy_extras "$out"
  echo "완료: $out  ($(du -sh "$out" | cut -f1))"
}

publish_single() {
  local out="$ROOT/dist/TimeGuard-단독실행"
  echo "=== 단독 실행 파일 ==="
  rm -rf "$out"; mkdir -p "$out"

  for project in "${PROJECTS[@]}"; do
    echo "--> $project"
    # 프로젝트마다 따로 내보낸 뒤 exe 만 모은다.
    # 한 폴더에 바로 내보내면 서로의 부속 파일을 덮어써 버린다.
    local stage="$ROOT/dist/.stage-$project"
    rm -rf "$stage"

    dotnet publish "$ROOT/src/$project/$project.csproj" \
      -c Release -r win-x64 --self-contained true \
      -p:EnableWindowsTargeting=true \
      -p:PublishSingleFile=true \
      -p:EnableCompressionInSingleFile=true \
      -p:IncludeNativeLibrariesForSelfExtract=true \
      -p:DebugType=none \
      -o "$stage" --nologo -v quiet

    cp "$stage/$project.exe" "$out/"
    rm -rf "$stage"
  done

  copy_extras "$out"
  echo "완료: $out  ($(du -sh "$out" | cut -f1))"
}

make_zip() {
  local folder="$1" name="$2"
  local zip="$ROOT/dist/$name"

  rm -f "$zip"
  (cd "$ROOT/dist" && zip -qr9 "$zip" "$(basename "$folder")")
  echo "압축 완료: $zip  ($(du -h "$zip" | cut -f1))"
}

case "$MODE" in
  shared) publish_shared ;;
  single) publish_single ;;
  all)
    publish_shared
    echo
    publish_single
    echo
    make_zip "$ROOT/dist/TimeGuard"          "HanilTimeGuard-$VERSION-win-x64.zip"
    make_zip "$ROOT/dist/TimeGuard-단독실행"  "HanilTimeGuard-$VERSION-단독실행-win-x64.zip"
    ;;
esac

echo
echo "== 만들어진 실행 파일 =="
find "$ROOT/dist" -maxdepth 2 -name 'TimeGuard.*.exe' -printf '%-52p  %8s bytes\n' | sort
