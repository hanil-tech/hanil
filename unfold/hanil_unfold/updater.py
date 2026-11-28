"""자동 업데이트 — 서버 (기본: GitHub Release `unfold-latest`) 의 hanil-unfold.json 을 읽어 새 버전이 있으면 설치 파일을
받아 조용히 설치한다. 회사 서버를 쓰려면 같은 꼴의 json 과 설치 파일을 HTTP 로 두고 [업데이트 확인] 창에서 주소만 바꾼다.

hanil-unfold.json 꼴:
  {"version": "1.57.0", "build": 90, "date": "2026-10-29", "commit": "abc1234", "notes": "…",
   "assets": {"full": {"name": "HanilUnfold-Setup.exe", "url": "https://…/HanilUnfold-Setup.exe", "sha256": "…", "size": 1234},
              "lite": {…}}}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from . import BUILD_NUMBER, __version__, edition

DEFAULT_URL = "https://github.com/hanil-tech/hanil/releases/download/unfold-latest/hanil-unfold.json"
TIMEOUT = 8.0


def current() -> tuple[tuple[int, ...], int]:
    """(버전 숫자 묶음, 빌드 번호) — 개발판은 빌드 0."""
    return _vtuple(__version__), int(BUILD_NUMBER) if str(BUILD_NUMBER).isdigit() else 0


def _vtuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def fetch(url: str = DEFAULT_URL, timeout: float = TIMEOUT) -> dict:
    """서버의 hanil-unfold.json. 실패하면 예외 (URLError · ValueError)."""
    req = urllib.request.Request(url, headers={"User-Agent": f"HanilUnfold/{__version__}", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    info = json.loads(data.decode("utf-8"))
    if not isinstance(info, dict) or "version" not in info or "assets" not in info:
        raise ValueError("업데이트 정보 (hanil-unfold.json) 꼴이 다릅니다")
    return info


def is_newer(info: dict, cur=None) -> bool:
    """서버 버전이 지금 것보다 새것인지 — 버전 숫자, 같으면 빌드 번호."""
    v_cur, b_cur = cur or current()
    v_new = _vtuple(info.get("version", "0"))
    try:
        b_new = int(info.get("build", 0) or 0)
    except (TypeError, ValueError):
        b_new = 0
    if v_new != v_cur:
        return v_new > v_cur
    return b_new > b_cur


def asset(info: dict) -> dict:
    """이 판 (전체 · 전개 전용) 에 맞는 설치 파일 정보."""
    key = "lite" if edition.unfold_only() else "full"
    a = (info.get("assets") or {}).get(key) or {}
    if not a.get("url"):
        raise ValueError(f"설치 파일 ({key}) 주소가 없습니다")
    return a


def label(info: dict) -> str:
    b = info.get("build")
    return f"{info.get('version', '?')}" + (f" (빌드 {b})" if b else "")


def download(url: str, dest: str | None = None, sha256: str = "", progress=None, timeout: float = 60.0) -> str:
    """설치 파일 받기 (조각으로, progress(받은 바이트, 전체 바이트) 가 False 면 그만). sha256 이 있으면 맞는지 본다."""
    dest = dest or os.path.join(tempfile.gettempdir(), os.path.basename(url.split("?")[0]) or "HanilUnfold-Setup.exe")
    req = urllib.request.Request(url, headers={"User-Agent": f"HanilUnfold/{__version__}"})
    h = hashlib.sha256()
    tmp = dest + ".part"
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 18)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress is not None and progress(got, total) is False:
                f.close()
                os.remove(tmp)
                raise InterruptedError("그만둠")
    if sha256 and h.hexdigest().lower() != sha256.lower():
        os.remove(tmp)
        raise ValueError("받은 설치 파일이 서버 것과 다릅니다 (sha256) — 다시 받아 주세요")
    if os.path.exists(dest):
        os.remove(dest)
    os.replace(tmp, dest)
    return dest


def app_exe() -> str:
    """지금 실행 중인 프로그램 (설치한 exe). 개발판이면 ''."""
    return sys.executable if getattr(sys, "frozen", False) else ""


def install_command(setup_exe: str, relaunch: str = "") -> list[str]:
    """Inno Setup 설치 파일을 조용히 (/SILENT) 돌리고 끝나면 프로그램을 다시 켜는 명령 (cmd 한 줄)."""
    cmd = f'start "" /wait "{setup_exe}" /SILENT /SP- /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS'
    if relaunch:
        cmd += f' & start "" "{relaunch}"'
    return ["cmd", "/c", cmd]


def install(setup_exe: str, relaunch: str = "") -> None:
    """설치를 따로 띄운다 (이 프로그램은 바로 끝내야 파일을 바꿀 수 있음). 윈도우에서만."""
    if not sys.platform.startswith("win"):
        raise OSError("자동 설치는 윈도우에서만 됩니다 — 받은 파일을 직접 실행해 주세요: " + setup_exe)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(install_command(setup_exe, relaunch), creationflags=flags, close_fds=True)
