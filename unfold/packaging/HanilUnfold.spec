# -*- mode: python -*-
# Windows 실행 파일 만들기:  pyinstaller packaging/HanilUnfold.spec   (unfold 폴더에서)
import glob
import os
import sysconfig

from PyInstaller.utils.hooks import collect_submodules

SITE = sysconfig.get_paths()["purelib"]
HERE = os.path.abspath(SPECPATH)
ROOT = os.path.dirname(HERE)

def _imports(path):
    """DLL 이 불러 쓰는 다른 DLL 이름들 (소문자)."""
    import pefile
    pe = pefile.PE(path, fast_load=True)
    pe.parse_data_directories(directories=[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]])
    names = set()
    for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for entry in getattr(pe, attr, []):
            names.add(entry.dll.decode().lower())
    pe.close()
    return names


# OCP 가 쓰는 DLL 은 site-packages 와 같은 폴더 구조로 옮긴다 (OCP/__init__.py 가 그 경로를 찾는다).
ocp_libs = glob.glob(os.path.join(SITE, "cadquery_ocp.libs", "*.dll"))
binaries = [(dll, "cadquery_ocp.libs") for dll in ocp_libs]

# VTK 는 DLL 이 270MB 가 넘는다. OCP 가 실제로 부르는 것만 따라가며 골라 담는다.
vtk_dir = os.path.join(SITE, "vtk.libs")
vtk_all = {os.path.basename(p).lower(): p for p in glob.glob(os.path.join(vtk_dir, "*.dll"))}
todo = list(ocp_libs) + glob.glob(os.path.join(SITE, "OCP", "OCP*.pyd"))
picked = {}
while todo:
    for name in _imports(todo.pop()):
        if name in vtk_all and name not in picked:
            picked[name] = vtk_all[name]
            todo.append(vtk_all[name])
if not picked and vtk_all:
    # 이름으로 못 찾으면 용량이 크더라도 전부 담는다 (실행이 우선).
    picked = vtk_all
binaries += [(dll, "vtk.libs") for dll in picked.values()]
print(f"VTK DLL {len(picked)}개 / 전체 {len(vtk_all)}개를 담습니다")

a = Analysis(
    [os.path.join(HERE, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=[(os.path.join(ROOT, "hanil_unfold", "icon.ico"), "hanil_unfold"),
           # OCP 는 시작할 때 vtk.libs 폴더를 DLL 경로에 넣는데, 폴더가 없으면 오류가 난다.
           (os.path.join(HERE, "vtk.libs.txt"), "vtk.libs")],
    hiddenimports=collect_submodules("OCP") + ["ezdxf", "numpy", "openpyxl", "PIL",
                                               "scipy.sparse.linalg", "scipy.spatial"],
    runtime_hooks=[os.path.join(HERE, "rthook_dlls.py")],
    excludes=["tkinter", "matplotlib", "vtk", "vtkmodules", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="HanilUnfold",
    icon=os.path.join(ROOT, "hanil_unfold", "icon.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="HanilUnfold")
