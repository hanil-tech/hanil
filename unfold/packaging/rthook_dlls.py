# 묶인 실행 파일 안에서 OpenCASCADE·VTK DLL 폴더를 찾을 수 있게 한다.
import os
import sys

base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
for name in ("cadquery_ocp.libs", "vtk.libs"):
    path = os.path.join(base, name)
    if os.path.isdir(path):
        os.add_dll_directory(path)
