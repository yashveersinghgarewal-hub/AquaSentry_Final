"""
Fill a SEPARATE database with a realistic, clearly labelled demo field programme, for presentations,
competition judging and screenshots. Never run it against a real deployment's database.

    cd AquaSentry_Platform
    python scripts/seed_field_demo.py --db demo_field.db
    DATABASE_URL=sqlite:///demo_field.db python -m uvicorn app.main:app --port 8000

Six nodes in the arsenic belt (Bihar, West Bengal, Uttar Pradesh, Assam, Punjab, Jharkhand), 30 days of
readings, lab confirmations (including one sample the sensor MISSED, so the validation panel shows the
honest picture), a standard-addition calibration, a low battery and a silent node. Every device code
starts with DEMO- and every reading is labelled "SIMULATED FIELD DEMO".
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

NODES = [
    # code, name, village, district, state, lat, lon, kind, profile
    ("DEMO-BHOJ-01", "Primary school handpump", "Simri", "Bhojpur", "Bihar", 25.556, 84.663, "handpump", "rising"),
    ("DEMO-NADIA-02", "Ward 4 deep tubewell", "Haringhata", "Nadia", "West Bengal", 22.950, 88.570, "tubewell", "clean"),
    ("DEMO-BALLIA-03", "Market handpump", "Bairia", "Ballia", "Uttar Pradesh", 25.760, 84.470, "handpump", "hazardous"),
    ("DEMO-JORHAT-04", "Tea estate well", "Titabor", "Jorhat", "Assam", 26.600, 94.200, "open_well", "copper"),
    ("DEMO-AMRIT-05", "Gurdwara borewell", "Ajnala", "Amritsar", "Punjab", 31.840, 74.760, "borewell", "lowlevel"),
    ("DEMO-SAHIB-06", "Anganwadi handpump", "Rajmahal", "Sahibganj", "Jharkhand", 25.050, 87.840, "handpump", "silent"),
]


def level(profile: str, day: float, rnd: random.Random) -> float:
    noise = rnd.gauss(0, 1.5)
    if profile == "rising":                       # monsoon recharge pulling arsenic up: ~5 µg/L a week
        return max(0.0, 24 + 0.75 * day + noise)
    if profile == "clean":
        return max(0.0, 6 + noise)
    if profile == "hazardous":
        return max(0.0, 185 + 18 * math.sin(day / 4) + rnd.gauss(0, 6))
    if profile == "copper":
        return max(0.0, 31 + noise)
    if profile == "lowlevel":                     # real 14 µg/L: below the sensor's 20 µg/L detection limit
        return max(0.0, 9 + noise)
    return max(0.0, 42 + noise)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="demo_field.db", help="SQLite file to create (default demo_field.db)")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    db = os.path.abspath(args.db)
    if os.path.basename(db) == "aquasentry.db":
        sys.exit("Refusing to seed aquasentry.db: use a separate demo database.")
    os.environ["DATABASE_URL"] = "sqlite:///" + db
    os.environ["RATE_LIMIT_READINGS_PER_MIN"] = "0"
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fastapi.testclient import TestClient
    from app.main import app

    rnd = random.Random(2026)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    with TestClient(app) as c:
        def post(path, body, method="post"):
            r = getattr(c, method)(path, json=body)
            if r.status_code >= 300:
                raise SystemExit(f"{path}: {r.status_code} {r.text[:200]}")
            return r.json()

        # v5.7: a node's LOW readings are only trusted with an electrode calibration and a passing check standard
        # in the last 7 days, so the demo programme has both, like a real one would (weekly 50 ug/L check).
        ext = post("/api/admin/calibrations/external", {
            "standards": [{"ug_l": c_, "peak_ua": round(0.0096 + 0.0008563 * c_ + e_, 5)}
                          for c_, e_ in ((0, 0.0003), (10, -0.0002), (20, 0.0002), (50, -0.0001), (100, 0.0002))],
            "electrode_lot": "MAS-G1-2611", "approved_by": "Demo lab lead", "notes": "SIMULATED FIELD DEMO"})
        for code, *_ in NODES:
            post("/api/qc/runs", {"device_code": code, "run_type": "blank", "measured_ug_l": round(abs(rnd.gauss(2, 1)), 1),
                                  "recorded_at": (now - timedelta(days=2, hours=1)).isoformat()})
            post("/api/qc/runs", {"device_code": code, "run_type": "check_standard", "expected_ug_l": 50,
                                  "measured_ug_l": round(50 * (1 + rnd.gauss(0, 0.04)), 1),
                                  "recorded_at": (now - timedelta(days=2)).isoformat()})

        for code, name, village, district, state, lat, lon, kind, profile in NODES:
            first = True
            cal_ref = ext["calibration_id"]          # v5.10: every reading names the calibration that produced it
            for h in range(args.days * 24, -1, -6):           # every 6 hours
                t = now - timedelta(hours=h)
                if profile == "silent" and h < 5 * 24:        # stopped reporting 5 days ago
                    continue
                v = level(profile, (args.days * 24 - h) / 24, rnd)
                body = {"device_code": code, "arsenic_ppb": round(v, 1), "source_type": "hardware",
                        "source_label": "SIMULATED FIELD DEMO", "recorded_at": t.isoformat(),
                        "idempotency_key": f"{code}-{h}", "firmware_version": "5.9.0",
                        "qc_status": "pass", "scans_averaged": 3,
                        "ph": round(7.4 + rnd.gauss(0, 0.15), 2), "temperature_c": round(26 + rnd.gauss(0, 1), 1),
                        "conductivity_us_cm": round(620 + rnd.gauss(0, 40)), "turbidity_ntu": round(abs(rnd.gauss(1.5, 0.6)), 1),
                        "battery_pct": 12 if code == "DEMO-JORHAT-04" and h < 24 else round(80 - h / 24),
                        "arsenic_species": "total" if profile in ("clean", "hazardous") else "as3_only",
                        "peak_current_ua": round(0.0096 + 0.0008563 * v, 4)}
                if profile == "copper":
                    body["cu_peak_ua"] = round(0.2 + abs(rnd.gauss(0, 0.05)), 3)
                body["calibration_ref"] = cal_ref
                post("/api/readings", body)
                if first:
                    post(f"/api/admin/devices/{code}/site", {"name": name, "village": village, "district": district,
                                                            "state": state, "latitude": lat, "longitude": lon,
                                                            "source_kind": kind}, method="put")
                    if code == "DEMO-BHOJ-01":
                        # a standard addition in this well's own water: its later readings use the matrix-matched slope
                        cal_ref = post("/api/admin/calibrations/standard-addition", {
                            "device_code": code, "electrode_lot": "MAS-G1-2611", "approved_by": "Demo lab lead",
                            "sample_peak_ua": 0.0405, "additions": [{"ug_l": 20, "peak_ua": 0.0577}, {"ug_l": 40, "peak_ua": 0.0748}],
                            "notes": "SIMULATED FIELD DEMO"})["calibration_id"]
                    first = False

        # lab confirmations: ICP-MS at a NABL lab, paired with the nearest node reading
        labs = [("DEMO-BHOJ-01", 20, 41, 17), ("DEMO-BHOJ-01", 6, 52, 21), ("DEMO-BALLIA-03", 12, 214, 70),
                ("DEMO-NADIA-02", 15, 5.5, None), ("DEMO-JORHAT-04", 9, 46, 19), ("DEMO-AMRIT-05", 8, 14.2, 6)]
        for code, days_ago, total, as3 in labs:
            post("/api/lab-results", {"device_code": code, "arsenic_ug_l": total, "as3_ug_l": as3, "lab_method": "ICP-MS",
                                      "lab_name": "PHED District Water Testing Laboratory (demo)", "nabl_accredited": True,
                                      "sampled_at": (now - timedelta(days=days_ago, hours=2)).isoformat()})
        v = c.get("/api/validation").json()
    print(f"Demo field programme written to {db}")
    print(f"  {len(NODES)} nodes, {v['n_pairs']} lab pairs, missed unsafe samples: {v['missed_unsafe']}")
    print(f"  Run:  DATABASE_URL=sqlite:///{db} python -m uvicorn app.main:app --port 8000")


if __name__ == "__main__":
    main()
