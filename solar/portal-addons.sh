#!/bin/bash
#  🔁 포털이 켜질 때마다(systemd ExecStartPre) 우리 조각이 빠졌으면 다시 넣는다 — 포털 업그레이드로 server.js·faxbox.js 가 바뀌어도 유지
#   넣는 법 (한 번, sudo):  bash ~/solar/portal-addons.sh --install 알림받을포털아이디
#   빼는 법:               bash ~/solar/portal-addons.sh --uninstall
#   이 스크립트는 실패해도 포털 시작을 막지 않는다 (항상 0 으로 끝남)
PORTAL=${PORTAL_DIR:-/data/portal}
HERE="$(cd "$(dirname "$0")" && pwd)"
CONF="$HERE/addons.conf"
LOG="$HERE/addons.log"
NODE="$(command -v node || echo /usr/bin/node)"

if [ "$1" = "--install" ]; then
  [ -n "$2" ] && echo "NOTIFY=$2" > "$CONF"
  D=/etc/systemd/system/hanil-portal.service.d
  sudo mkdir -p "$D" && printf '[Service]\nExecStartPre=-/bin/bash %s/portal-addons.sh\n' "$HERE" | sudo tee "$D/hanil-addons.conf" >/dev/null && sudo systemctl daemon-reload && echo "✅ 등록 — 포털이 켜질 때마다 확인합니다 ($D/hanil-addons.conf)"
  exit 0
fi
if [ "$1" = "--uninstall" ]; then
  sudo rm -f /etc/systemd/system/hanil-portal.service.d/hanil-addons.conf && sudo systemctl daemon-reload
  "$NODE" "$HERE/patch-portal-solar.js" "$PORTAL/server.js" --undo
  echo "✅ 자동 확인 해제 + server.js 에서 뺌 (포털을 다시 켜면 적용)"; exit 0
fi

NOTIFY=""; [ -f "$CONF" ] && . "$CONF"
{
  echo "── $(date '+%F %T')"
  if [ -f "$HERE/patch-portal-solar.js" ]; then
    "$NODE" "$HERE/patch-portal-solar.js" "$PORTAL/server.js" ${NOTIFY:+--notify "$NOTIFY"}
  fi
  if [ -f "$HERE/patch-faxbox-autoread.js" ] && [ -f "$PORTAL/faxbox.js" ]; then
    "$NODE" "$HERE/patch-faxbox-autoread.js" "$PORTAL/faxbox.js"
  fi
} >> "$LOG" 2>&1
tail -n 400 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
exit 0
