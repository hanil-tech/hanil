"""빌드 번호·커밋·날짜를 hanil_unfold/_build.py 로, Windows 실행 파일 버전 정보를 version_info.txt 로 쓴다.

    python packaging/write_build_info.py <빌드 번호> <커밋>
"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

number = sys.argv[1] if len(sys.argv) > 1 else "0"
commit = (sys.argv[2] if len(sys.argv) > 2 else "")[:7]
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
      StringStruct('FileDescription', '한일 판금 전개'),
      StringStruct('FileVersion', '{version}.{four[3]}'),
      StringStruct('InternalName', 'HanilUnfold'),
      StringStruct('OriginalFilename', 'HanilUnfold.exe'),
      StringStruct('ProductName', '한일 판금 전개'),
      StringStruct('ProductVersion', '{version} (빌드 {number} · {commit})')])]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""
with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as f:
    f.write(info)
print(f"버전 {version}, 빌드 {number}, 커밋 {commit}")
