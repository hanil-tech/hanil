#!/bin/bash
#  포털에 넣을 묶음 → ../release/hanil-bigfile-portal.zip
#  ⚠ zip 명령은 한글 이름에 UTF-8 표시를 안 해 윈도 탐색기에서 이름이 깨진다 — 파이썬 zipfile 로 만든다
set -e
cd "$(dirname "$0")"
python3 - <<'PY'
import zipfile
out = '../release/hanil-bigfile-portal.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    #  메모장에서 줄이 안 붙게 CRLF 로
    for t in ('설치안내.txt', '주의사항.txt'):
        z.writestr(t, open(t, encoding='utf-8').read().replace('\n', '\r\n').encode('utf-8-sig'))
    for src, name in [('portal/bigfile-route.js', 'bigfile-route.js'), ('portal/bigfile.html', 'bigfile.html'), ('README.md', 'README.md')]:
        z.write(src, name)
for i in zipfile.ZipFile(out).infolist(): print(i.filename, i.file_size, 'utf8' if i.flag_bits & 0x800 else '')
PY
