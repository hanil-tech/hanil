#!/usr/bin/env bash
#
# Windows(x64)용 배포 파일을 만든다.
#
#   ./build/publish.sh
#
# 결과는 파일 두 개다.
#
#   dist/TimeGuard-Setup.exe          직원 PC 에 설치
#   dist/TimeGuard-Server-Setup.exe   관리 서버에 설치
#
# 설치에 필요한 모든 것이 이 안에 들어 있다.
# 받는 사람은 이 파일 하나만 있으면 되고, .NET 을 따로 깔 필요도 없다.
#
# 파일 이름을 영문으로 두는 이유:
#   한글 이름은 메신저나 압축 프로그램을 거치면서 깨진다.
#   압축을 풀 때 그 파일을 아예 건너뛰어서, 받는 쪽에서는 사라진 것처럼 보인다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
WORK="$DIST/.work"

VERSION="$(grep -oP '(?<=<Version>)[^<]+' "$ROOT/Directory.Build.props" | head -1)"

case "${1:-}" in
  --help|-h) sed -n '3,18p' "$0"; exit 0 ;;
  "")        ;;
  *)         echo "알 수 없는 옵션: $1"; exit 1 ;;
esac

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

# 설치될 프로그램들을 한 폴더에 모은다. 런타임을 함께 쓰므로 용량이 줄어든다.
stage() {
  local name="$1"; shift
  local out="$WORK/$name"

  mkdir -p "$out"

  for project in "$@"; do
    dotnet publish "$ROOT/src/$project/$project.csproj" \
      -c Release -r win-x64 --self-contained true \
      -p:EnableWindowsTargeting=true \
      -p:PublishSingleFile=false \
      -p:DebugType=none \
      -o "$out" --nologo -v quiet
  done
}

# 모아 둔 폴더를 설치 프로그램 안에 넣을 묶음으로 만든다.
pack() {
  local name="$1"
  local zip="$WORK/$name.zip"

  # -j: 폴더 이름 없이 파일만 담는다. 푸는 쪽에서 그대로 설치 폴더가 된다.
  # -UN=UTF8: 이름을 UTF-8 로 못박는다.
  (cd "$WORK/$name" && zip -qr9 -UN=UTF8 "$zip" .)

  echo "$zip"
}

# 설치 프로그램을 파일 하나로 만든다.
build_setup() {
  local project="$1" exe="$2" payload="$3"
  local stage_dir="$WORK/setup-$project"

  dotnet publish "$ROOT/src/$project/$project.csproj" \
    -c Release -r win-x64 --self-contained true \
    -p:EnableWindowsTargeting=true \
    -p:PublishSingleFile=true \
    -p:EnableCompressionInSingleFile=true \
    -p:IncludeNativeLibrariesForSelfExtract=true \
    -p:DebugType=none \
    -p:PayloadZip="$payload" \
    -o "$stage_dir" --nologo -v quiet

  mv "$stage_dir/$exe" "$DIST/$exe"
}

# 메신저가 exe 첨부를 막는 경우를 대비해 zip 도 하나 만들어 둔다.
wrap_zip() {
  local exe="$1" zip="$2"

  rm -f "$DIST/$zip"
  (cd "$DIST" && zip -q9 -UN=UTF8 "$zip" "$exe")

  echo "        $zip  ($(du -h "$DIST/$zip" | cut -f1))"
}

# ✍ 사내 인증서(공개용)를 설치 파일 안에 함께 담는다.
#
# 담아 두면 설치할 때 이 PC 가 우리 인증서를 믿도록 등록해 둔다.
# 그러면 다음부터 "확인되지 않은 게시자" 경고가 뜨지 않는다(자동 업데이트도 조용하다).
#
# 없으면 그냥 넘어간다 - 예전과 똑같이 동작하고, 첫 설치 때 경고가 한 번 뜰 뿐이다.
# 만드는 법: build/인증서-만들기.ps1 (윈도우에서 한 번)
CERT="$ROOT/cert/hanil-code-signing.cer"

add_cert() {
  [ -f "$CERT" ] || return 0
  cp "$CERT" "$WORK/$1/hanil-code-signing.cer"
}

echo "=== 직원 PC 설치 파일 ==="
stage client TimeGuard.Service TimeGuard.Agent TimeGuard.Admin
add_cert client
cp "$ROOT/docs/설치안내.txt"          "$WORK/client/Install-Guide.txt"
cp "$ROOT/docs/직원계정_권한낮추기.md" "$WORK/client/Employee-Account-Guide.md"
build_setup TimeGuard.Setup "TimeGuard-Setup.exe" "$(pack client)"
echo "완료: dist/TimeGuard-Setup.exe  ($(du -h "$DIST/TimeGuard-Setup.exe" | cut -f1))"

echo
echo "=== 관리 서버 설치 파일 ==="
stage server TimeGuard.Server
cp "$ROOT/docs/서버설치안내.txt"       "$WORK/server/Server-Install-Guide.txt"
cp "$ROOT/docs/직원계정_권한낮추기.md" "$WORK/server/Employee-Account-Guide.md"

# 💿 직원 PC 설치 파일을 서버 설치 파일 안에 함께 넣는다.
#
# 이 한 줄이 "PC 열 대를 도는 일"을 없앤다.
# 서버를 새로 설치하면 설치 프로그램이 이 파일을 '나눠 주는 자리'에 놓고,
# 직원 PC 들이 서버에 물어보다가 그것을 보고 스스로 따라온다.
#
# 서버 설치 파일이 그만큼 커지지만(약 두 배), 서버는 한 대뿐이고 한 번만 받는다.
cp "$DIST/TimeGuard-Setup.exe" "$WORK/server/TimeGuard-Setup.exe"
add_cert server
build_setup TimeGuard.ServerSetup "TimeGuard-Server-Setup.exe" "$(pack server)"
echo "완료: dist/TimeGuard-Server-Setup.exe  ($(du -h "$DIST/TimeGuard-Server-Setup.exe" | cut -f1))"

echo
echo "=== exe 를 막는 메신저용 zip ==="
wrap_zip "TimeGuard-Setup.exe"        "HanilTimeGuard-$VERSION-Client.zip"
wrap_zip "TimeGuard-Server-Setup.exe" "HanilTimeGuard-$VERSION-Server.zip"

rm -rf "$WORK"

echo
echo "== 배포 파일 =="
for f in "$DIST"/*.exe "$DIST"/*.zip; do
  [ -e "$f" ] || continue
  printf '  %-44s %8s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
done
