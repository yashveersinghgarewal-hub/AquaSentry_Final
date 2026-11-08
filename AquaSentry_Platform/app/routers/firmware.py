"""Firmware builds for nodes to pull (v5.6).

An admin uploads a compiled .bin for one board (POST /api/admin/firmware?board=esp32&version=5.6.1 with
the file as the request body; arduino-cli / PlatformIO produce it). Nodes built with PULL_OTA ask
/api/firmware/latest once a day and download newer builds; the download carries an x-MD5 header,
which the ESP32's HTTPUpdate checks before it installs anything.
"""
import hashlib
import json
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from ..deps import now_utc, require_admin

router = APIRouter()
BOARDS = ("esp32", "esp32s3", "esp32c3")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
MAX_BYTES = 4 * 1024 * 1024


def firmware_dir() -> str:
    from ..database import DATABASE_URL, _PLATFORM_DIR
    base = os.getenv("AQUASENTRY_DATA_DIR")
    if not base and DATABASE_URL.startswith("sqlite:///"):
        base = os.path.dirname(DATABASE_URL[len("sqlite:///"):])
    d = os.path.join(base or _PLATFORM_DIR, "firmware")
    os.makedirs(d, exist_ok=True)
    return d


def _vt(v: str):
    return tuple(int(x) for x in v.split("."))


def _manifest() -> dict:
    p = os.path.join(firmware_dir(), "manifest.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(m: dict):
    p = os.path.join(firmware_dir(), "manifest.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1)
    os.replace(tmp, p)


@router.post("/api/admin/firmware", tags=["Firmware"], dependencies=[Depends(require_admin)])
async def upload_firmware(request: Request, board: str = Query(...), version: str = Query(...),
                          notes: Optional[str] = Query(None, max_length=500)):
    if board not in BOARDS:
        raise HTTPException(status_code=422, detail=f"board must be one of {', '.join(BOARDS)}")
    if not VERSION_RE.match(version):
        raise HTTPException(status_code=422, detail="version must look like 5.6.1")
    data = await request.body()
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(status_code=422, detail="Send the .bin file (up to 4 MB) as the request body.")
    if data[0] != 0xE9:                      # every ESP32 app image starts with the 0xE9 magic byte
        raise HTTPException(status_code=422, detail="That is not an ESP32 app image (.bin from the build).")
    name = f"{board}-{version}.bin"
    with open(os.path.join(firmware_dir(), name), "wb") as f:
        f.write(data)
    m = _manifest()
    m.setdefault(board, {})[version] = {"file": name, "size": len(data), "md5": hashlib.md5(data).hexdigest(),
                                        "sha256": hashlib.sha256(data).hexdigest(), "notes": notes,
                                        "uploaded_at": now_utc().isoformat()}
    _save_manifest(m)
    return {"board": board, "version": version, **m[board][version]}


@router.get("/api/firmware/latest", tags=["Firmware"])
def latest(board: str, current: Optional[str] = None):
    """The newest build for this board, or 204 if the node is already up to date."""
    builds = _manifest().get(board, {})
    if not builds:
        return Response(status_code=204)
    newest = max(builds, key=_vt)
    if current and VERSION_RE.match(current) and _vt(newest) <= _vt(current):
        return Response(status_code=204)
    b = builds[newest]
    return {"version": newest, "url": f"/api/firmware/download/{board}/{newest}", "size": b["size"],
            "md5": b["md5"], "sha256": b["sha256"], "notes": b.get("notes")}


@router.get("/api/firmware/download/{board}/{version}", tags=["Firmware"])
def download(board: str, version: str):
    b = _manifest().get(board, {}).get(version)
    if b is None:
        raise HTTPException(status_code=404, detail="No such build.")
    return FileResponse(os.path.join(firmware_dir(), b["file"]), media_type="application/octet-stream",
                        headers={"x-MD5": b["md5"]}, filename=b["file"])


@router.get("/api/firmware", tags=["Firmware"])
def list_builds():
    return _manifest()
