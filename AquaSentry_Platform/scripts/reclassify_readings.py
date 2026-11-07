"""Re-run the current safety rules over every stored reading.

Verdicts are saved with each reading, so when a standard changes (v5.2: India's IS 10500 arsenic limit is
10 µg/L with no relaxation, not 50 µg/L) old rows keep their old verdict. This updates classification,
regulatory tier, analytical status, safe-to-drink flag and uncertainty from the stored measurements.
Measured values are never changed.

    python scripts/reclassify_readings.py            # preview: print what would change
    python scripts/reclassify_readings.py --apply    # write the changes (a .bak copy is made first)

Uses DATABASE_URL if set, otherwise AquaSentry_Platform/aquasentry.db.
"""
import argparse
import os
import shutil
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from app.database import SessionLocal, DATABASE_URL  # noqa: E402
from app import models  # noqa: E402
from app.classification import classify_arsenic_neural  # noqa: E402


def _v(x, d):
    return d if x is None else x


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the changes")
    args = ap.parse_args()

    if args.apply and DATABASE_URL.startswith("sqlite:///"):
        path = DATABASE_URL[len("sqlite:///"):]
        if os.path.exists(path):
            shutil.copy2(path, path + ".bak")
            print(f"Backup: {path}.bak")

    db = SessionLocal()
    changes = Counter()
    skipped = 0
    try:
        for r in db.query(models.Reading).all():
            try:
                res = classify_arsenic_neural(
                    r.arsenic_ppb, _v(r.ph, 7.2), _v(r.conductivity_us_cm, 400.0),
                    _v(r.turbidity_ntu, 2.0), _v(r.temperature_c, 24.0), r.source_type or "simulated")
            except ValueError:
                skipped += 1
                continue
            if res.label != r.classification or res.regulatory_tier != r.regulatory_tier:
                changes[(r.classification, res.label)] += 1
                if args.apply:
                    r.classification = res.label
                    r.regulatory_tier = res.regulatory_tier
                    r.analytical_status = res.analytical_status
                    r.is_safe_to_drink = res.is_safe_to_drink
                    r.uncertainty_ppb = res.uncertainty_ppb
        if args.apply:
            db.commit()
    finally:
        db.close()

    total = sum(changes.values())
    for (old, new), n in sorted(changes.items(), key=lambda kv: -kv[1]):
        print(f"  {old:18s} -> {new:18s} {n}")
    verb = "Updated" if args.apply else "Would update"
    print(f"{verb} {total} reading(s); {skipped} skipped (implausible stored values).")
    if not args.apply and total:
        print("Run again with --apply to write these changes.")


if __name__ == "__main__":
    main()
