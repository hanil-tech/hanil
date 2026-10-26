"""빌드 번호·커밋·날짜를 hanil_unfold/_build.py 로, Windows 실행 파일 버전 정보를 version_info.txt 로 쓴다.

    python packaging/write_build_info.py <빌드 번호> <커밋> [--edition unfold]

--edition unfold: 전개 전용판 — hanil_unfold/_edition.py 에 판을 못 박는다 (없으면 그 파일을 지워 전체판).
"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

args = [a for a in sys.argv[1:]]
edition = "full"
if "--edition" in args:
    i = args.index("--edition")
    edition = args[i + 1]
    del args[i:i + 2]
number = args[0] if len(args) > 0 else "0"
commit = (args[1] if len(args) > 1 else "")[:7]
ed_path = os.path.join(ROOT, "hanil_unfold", "_edition.py")
if edition == "unfold":
    with open(ed_path, "w", encoding="utf-8") as f:
        f.write('EDITION = "unfold"\n')
elif os.path.exists(ed_path):
    os.remove(ed_path)
product = "한일 판금 전개 (전개 전용)" if edition == "unfold" else "한일 판금 전개"
exe = "HanilUnfoldLite" if edition == "unfold" else "HanilUnfold"
today = datetime.date.today().isoformat()

with open(os.path.join(ROOT, "hanil_unfold", "_build.py"), "w", encoding="utf-8") as f:
    f.write(f'BUILD_NUMBER = "{number}"\nBUILD_COMMIT = "{commit}"\nBUILD_DATE = "{today}"\n')

src = open(os.path.join(ROOT, "hanil_unfold", "__init__.py"), encoding="utf-8").read()
version = re.search(r'__version__ = "([^"]+)"', src).group(1)
nums = [int(x) for x in version.split(".")] + [0, 0, 0]
four = (nums[0], nums[1], nums[2], int(number) if number.isdigit() else 0)

# PyInstaller 가 실행 파일에 넣는 버전 정보 (파일 속성 → 자세히 에 보인다)
info = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={four}, prodvers={four}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041204b0', [
      StringStruct('CompanyName', '한일특장(주)'),
      StringStruct('LegalCopyright', 'Copyright © 2025-2026 한일특장(주). All rights reserved.'),
      StringStruct('FileDescription', '{product}'),
      StringStruct('FileVersion', '{version}.{four[3]}'),
      StringStruct('InternalName', '{exe}'),
      StringStruct('OriginalFilename', '{exe}.exe'),
      StringStruct('ProductName', '{product}'),
      StringStruct('ProductVersion', '{version} (빌드 {number} · {commit})')])]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""
with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as f:
    f.write(info)
print(f"{product}: 버전 {version}, 빌드 {number}, 커밋 {commit}")
