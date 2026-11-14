#!/bin/bash
#  📠 장비 → ~/fax-archive (PDF) → NAS 받는 폴더(연도별 폴더)  — 포털 faxbox 가 NAS 를 읽어 간다
#   예약 작업(2분마다):
#   */2 * * * * /usr/bin/flock -n /tmp/cimfax-export.lock /bin/bash /home/gaos/fax-setup/fax-sync.sh >> /home/gaos/fax-export.log 2>&1
#   설정은 아래 네 줄만 고친다 (또는 같은 이름의 환경 변수)
HOST="${CIMFAX_HOST:-192.168.1.156}"
USER_ID="${CIMFAX_USER:-admin}"
NAS_DIR="${FAX_NAS_DIR:-/mnt/nas/80_받은팩스/admin}"
ARCHIVE="${FAX_ARCHIVE:-$HOME/fax-archive}"

HERE="$(cd "$(dirname "$0")" && pwd)"
NODE="$(command -v node || echo /usr/bin/node)"
cd "$HERE" || exit 1

#  1) 장비에서 새 팩스를 PDF 로 꺼낸다 (이어 받기 — 새 것이 없으면 조용히 끝남)
"$NODE" cimfax-check.js --host "$HOST" --user "$USER_ID" --pass-file "$HOME/.cimfax-pass" --export "$ARCHIVE" --pdf-only --quiet

#  2) NAS 가 붙어 있을 때만 넣는다 (부팅 직후 아직이면 다음 차례에)
ls "$NAS_DIR" >/dev/null 2>&1 || exit 0
LIST="$ARCHIVE/.nas-copied"
touch "$LIST"

for f in "$ARCHIVE"/*.pdf; do
  [ -e "$f" ] || continue
  b="$(basename "$f")"
  #  한 번 넣은 것은 다시 안 넣는다 (포털이 원본을 옮기거나 지워도)
  if grep -qxF "$b" "$LIST"; then continue; fi
  y="${b:0:4}"
  dest="$NAS_DIR/${y}년"
  mkdir -p "$dest" || continue
  #  다 쓴 뒤에 이름을 바꿔서, 포털이 반쯤 쓴 파일을 읽지 않게
  if cp "$f" "$dest/$b.part"; then
    if mv "$dest/$b.part" "$dest/$b"; then
      echo "$b" >> "$LIST"
      echo "$(date '+%F %T') NAS ← ${y}년/$b"
    fi
  fi
done
