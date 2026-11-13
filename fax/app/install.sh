#!/bin/bash
#  📠 한일 팩스 설치 — 이 폴더에서:  bash install.sh
#   1) Node.js · Ghostscript 확인   2) 처음 설정(장비)   3) 관리자 계정   4) 서비스 등록(부팅 때 자동 시작)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"
NODE="$(command -v node || true)"

echo "📠 한일 팩스 설치 — 폴더 $DIR · 실행 계정 $RUN_USER"

if [ -z "$NODE" ]; then echo "❌ Node.js 가 없습니다 (18 이상 필요)"; exit 1; fi
NODE_MAJOR="$("$NODE" -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 18 ]; then echo "❌ Node.js 18 이상이 필요합니다 (지금 $("$NODE" -v))"; exit 1; fi
echo "✅ Node.js $("$NODE" -v)"

if ! command -v gs >/dev/null 2>&1; then
  echo "▶ Ghostscript 설치 (팩스 보내기에 필요)"
  sudo apt-get install -y ghostscript
fi
echo "✅ Ghostscript $(gs --version)"

if [ ! -f "$DIR/hanil-fax.json" ]; then
  "$NODE" "$DIR/hanil-fax.js" setup
fi
"$NODE" "$DIR/hanil-fax.js" check || { echo "⚠ 장비 로그인이 안 됩니다 — node hanil-fax.js setup 으로 다시 설정하세요"; exit 1; }

if ! "$NODE" -e "process.exit(Object.values(require('$DIR/hanil-fax.json').users||{}).some(u=>u.admin)?0:1)"; then
  echo "▶ 관리자 계정을 하나 만듭니다"
  read -r -p "  아이디(영문): " AID
  read -r -p "  이름: " ANAME
  "$NODE" "$DIR/hanil-fax.js" adduser "$AID" "$ANAME" --admin
fi

PORT="$("$NODE" -p "require('$DIR/hanil-fax.json').port||3990")"
if ss -ltn 2>/dev/null | grep -q ":$PORT "; then
  if ! systemctl is-active --quiet hanil-fax; then echo "❌ 포트 $PORT 를 다른 프로그램이 쓰고 있습니다 — hanil-fax.json 의 port 를 바꾸세요"; exit 1; fi
fi

echo "▶ 서비스 등록 (sudo 비밀번호를 물을 수 있습니다)"
sudo tee /etc/systemd/system/hanil-fax.service >/dev/null <<EOF
[Unit]
Description=한일 팩스 (CimFAX 받기·보내기)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$DIR
ExecStart=$NODE $DIR/hanil-fax.js
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hanil-fax

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now hanil-fax
sleep 2
systemctl --no-pager --lines=5 status hanil-fax || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "✅ 설치 끝 —  http://${IP:-서버주소}:$PORT/fax"
echo "   직원 추가:  node $DIR/hanil-fax.js adduser 아이디 이름"
echo "   기록 보기:  journalctl -u hanil-fax -f"
if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  echo "   ⚠ 방화벽(ufw)이 켜져 있습니다. 사내에서 열려면:  sudo ufw allow from 192.168.0.0/16 to any port $PORT proto tcp"
fi
