"""Regenerate frontend/device3d-data.js (the 3D device view) from the STL files in models_3d/.

Run from AquaSentry_Platform/:  python scripts/stl_to_js.py
Binary STL only. Positions are stored as Int16 in 0.01 mm units (enough for parts up to +-327 mm).
"""
import base64
import json
import os
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = os.path.join(ROOT, "models_3d")
OUT = os.path.join(ROOT, "AquaSentry_Platform", "frontend", "device3d-data.js")
PARTS = [  # (name used by device3d.js, file)
    ("base", "aquasentry_shell_base_full_120mm.stl"),
    ("lid", "aquasentry_shell_lid_full_120mm.stl"),
    ("well", "aquasentry_sample_well_15ml.stl"),
    ("strainer", "aquasentry_suction_strainer.stl"),
]


def read_stl(path):
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[80:84])[0]
    verts = []
    for i in range(n):
        off = 84 + i * 50 + 12  # skip the stored normal
        verts.extend(struct.unpack("<9f", data[off:off + 36]))
    return verts


def main():
    out = {"scale": 0.01, "parts": []}
    for name, fname in PARTS:
        v = read_stl(os.path.join(MODELS, fname))
        q = [int(round(x / 0.01)) for x in v]
        if max(abs(x) for x in q) >= 32767:
            raise SystemExit(f"{fname}: part too large for Int16 at 0.01 mm")
        raw = struct.pack("<%dh" % len(q), *q)
        out["parts"].append({"name": name, "tris": len(v) // 9, "data": base64.b64encode(raw).decode()})
        print(f"{name}: {len(v) // 9} triangles")
    js = ("/* Generated from models_3d/*.stl by scripts/stl_to_js.py — AquaSentry shell, sample well and strainer.\n"
          "   Int16 vertex positions in 0.01 mm units, 3 vertices per triangle. */\n"
          "window.AQUASENTRY_MODEL=" + json.dumps(out, separators=(",", ":")) + ";\n")
    open(OUT, "w").write(js)
    print("wrote", OUT, f"({len(js) // 1024} KB)")


if __name__ == "__main__":
    main()
