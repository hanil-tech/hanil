"""자동 업데이트: 서버 json 읽기 · 새 버전 판정 · 설치 파일 받기 (sha256) · 설치 명령."""
import hashlib
import json

import pytest

from hanil_unfold import updater


def _manifest(tmp_path, version="9.9.9", build=999, exe_bytes=b"MZ-fake-installer"):
    exe = tmp_path / "HanilUnfold-Setup.exe"
    exe.write_bytes(exe_bytes)
    info = {"version": version, "build": build, "date": "2026-10-29", "commit": "abc1234", "notes": "시험",
            "assets": {"full": {"name": exe.name, "url": exe.as_uri(), "sha256": hashlib.sha256(exe_bytes).hexdigest(),
                                "size": len(exe_bytes)},
                       "lite": {"name": "HanilUnfoldLite-Setup.exe", "url": exe.as_uri(), "sha256": "", "size": 0}}}
    p = tmp_path / "hanil-unfold.json"
    p.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return p.as_uri(), info


def test_fetch_and_is_newer(tmp_path):
    url, info = _manifest(tmp_path)
    got = updater.fetch(url)
    assert got["version"] == "9.9.9" and got["assets"]["full"]["sha256"]
    assert updater.is_newer(got)                                           # 9.9.9 > 지금
    assert updater.is_newer({"version": "1.56.0", "build": 90}, ((1, 56, 0), 86))
    assert not updater.is_newer({"version": "1.56.0", "build": 86}, ((1, 56, 0), 86))
    assert not updater.is_newer({"version": "1.55.9", "build": 999}, ((1, 56, 0), 1))
    assert updater.is_newer({"version": "1.57.0", "build": 1}, ((1, 56, 0), 999))
    assert updater.label(got) == "9.9.9 (빌드 999)"
    (tmp_path / "x.json").write_text("{}")
    with pytest.raises(ValueError):
        updater.fetch((tmp_path / "x.json").as_uri())


def test_download_verifies_sha256(tmp_path):
    url, info = _manifest(tmp_path)
    a = updater.asset(info)
    seen = []
    dest = updater.download(a["url"], str(tmp_path / "dl" / "setup.exe") if (tmp_path / "dl").mkdir() is None else "",
                            a["sha256"], progress=lambda got, total: seen.append((got, total)))
    assert open(dest, "rb").read() == b"MZ-fake-installer" and seen and seen[-1][0] == len(b"MZ-fake-installer")
    with pytest.raises(ValueError):
        updater.download(a["url"], str(tmp_path / "bad.exe"), "00" * 32)
    assert not (tmp_path / "bad.exe").exists()


def test_install_command():
    cmd = updater.install_command(r"C:\Temp\HanilUnfold-Setup.exe", r"C:\Program Files\HanilUnfold\HanilUnfold.exe")
    assert cmd[:2] == ["cmd", "/c"] and "/SILENT" in cmd[2] and "/CLOSEAPPLICATIONS" in cmd[2]
    assert cmd[2].index("HanilUnfold-Setup.exe") < cmd[2].index("HanilUnfold.exe\"")
    assert updater.app_exe() == "" or updater.app_exe().endswith(".exe")


def test_app_check_update_and_install(tmp_path, monkeypatch):
    """창: 서버 json (file://) 으로 확인 → 새 버전이면 업데이트 창 (여기선 가로채기) → 설치: 받기 · sha256 · 설치 명령 · 끝내기."""
    from hanil_unfold.app import MainWindow
    from PySide6.QtWidgets import QApplication, QMessageBox
    url, info = _manifest(tmp_path)
    w = MainWindow()
    w.settings.setValue("update_url", url)
    w.settings.setValue("auto_update", "1")
    w.settings.setValue("update_skip", "")
    shown = []
    monkeypatch.setattr(w, "_update_dialog", lambda info_, newer: shown.append((info_["version"], newer)))
    w.check_update(manual=False)
    w._update_worker.wait(5000)
    QApplication.processEvents()
    assert shown == [("9.9.9", True)]
    # 건너뛴 버전은 자동 확인에서 안 보이고, 직접 확인하면 보임
    w.settings.setValue("update_skip", "9.9.9 (빌드 999)")
    shown.clear()
    w.check_update(manual=False)
    w._update_worker.wait(5000)
    QApplication.processEvents()
    assert shown == []
    w.check_update(manual=True)
    w._update_worker.wait(5000)
    QApplication.processEvents()
    assert shown == [("9.9.9", True)]
    # 설치
    from hanil_unfold import updater
    ran = {}
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(updater, "install", lambda setup, relaunch="": ran.update(setup=setup, relaunch=relaunch))
    quit_ = []
    monkeypatch.setattr(QApplication.instance(), "quit", lambda: quit_.append(True))
    w._install_update(info)
    assert ran["setup"].endswith("HanilUnfold-Setup.exe") and open(ran["setup"], "rb").read() == b"MZ-fake-installer"
    assert quit_ == [True]
    w.close()
