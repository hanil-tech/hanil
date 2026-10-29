"""배포 정보 hanil-unfold.json 을 쓴다 (자동 업데이트가 읽음).

    python packaging/write_release_manifest.py <버전> <빌드> <커밋> <전체판 exe> <전개 전용판 exe> <주소 머리> <출력 json>
"""
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

version, build, commit, full, lite, base, out = sys.argv[1:8]


def asset(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return {"name": os.path.basename(path), "url": f"{base.rstrip('/')}/{os.path.basename(path)}",
            "sha256": h.hexdigest(), "size": os.path.getsize(path)}


try:
    from hanil_unfold.changes import CHANGES
    notes = "\n".join(f"· {x}" for x in CHANGES[0][1]) if CHANGES and CHANGES[0][0] == version else ""
except Exception:  # noqa: BLE001
    notes = ""
info = {"version": version, "build": int(build) if str(build).isdigit() else 0, "commit": commit[:7],
        "date": datetime.date.today().isoformat(), "notes": notes,
        "assets": {"full": asset(full), "lite": asset(lite)}}
with open(out, "w", encoding="utf-8") as f:
    json.dump(info, f, ensure_ascii=False, indent=1)
print(out, info["version"], info["build"])
