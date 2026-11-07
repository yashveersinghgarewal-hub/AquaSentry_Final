"""
Generate a synthetic square-wave voltammetry dataset for an arsenic
water-testing example file (potential_mV, current_uA).

Mimics the shape of real stripping-voltammetry data: a noisy baseline
current with a Gaussian-shaped stripping peak near -800 mV (typical
region for As stripping peaks vs Ag/AgCl reference).
"""

import csv
import random

def generate_arsenic_csv(
    filename="arsenic_voltammetry_example.csv",
    v_start=-1000.0,
    v_end=-600.0,
    v_step=5.0,
    baseline_min=0.02,
    baseline_max=0.09,
    peak_center=-800.0,
    peak_height=0.22,
    peak_width=15.0,
    noise_sd=0.015,
    seed=None,
):
    """
    v_start/v_end/v_step: sweep range and step, in mV
    baseline_min/max: random baseline current range, in uA
    peak_center: mV location of the arsenic stripping peak
    peak_height: extra current (uA) added at the peak center
    peak_width: std-dev (mV) controlling how broad the peak is
    noise_sd: random Gaussian noise added on top of everything, in uA
    seed: set for reproducible output, leave None for fresh random data
    """
    rng = random.Random(seed)

    n_steps = int(round((v_end - v_start) / v_step)) + 1
    rows = []

    for i in range(n_steps):
        v = v_start + i * v_step

        # slowly wandering baseline so it doesn't look perfectly flat
        baseline = rng.uniform(baseline_min, baseline_max)

        # Gaussian-shaped stripping peak
        peak = peak_height * pow(2.718281828, -((v - peak_center) ** 2) / (2 * peak_width ** 2))

        noise = rng.gauss(0, noise_sd)

        current = max(0.0, baseline + peak + noise)
        rows.append((round(v, 1), current))

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["potential_mV", "current_uA"])
        writer.writerows(rows)

    return filename


if __name__ == "__main__":
    generate_arsenic_csv()
