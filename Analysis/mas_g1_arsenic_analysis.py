# MAS-G1 Arsenic Ion Quantification Pipeline
#
# Background (from AccuSensing product data, As-M003050 sensor + MAS-G1 reader):
# - Technique: electrochemical stripping voltammetry with a 3-electrode system.
# - Target species: arsenic(III) ions.
# - Diagnostic peak: approximately -800 mV versus the strip's internal reference.
# - Quantification range: 0.03-0.50 mg/L As(III).
# - Limit of detection (LOD): 0.02 mg/L.
# - Peak current versus concentration is linear, with R^2 > 0.99.
# - Analysis time: approximately 180 seconds per strip.
#
# The script analyzes a raw voltammogram exported by the MAS-G1 hardware or
# potentiostat as paired potential (mV) and current (uA) arrays. It does not
# communicate with the hardware.
#
# Pipeline:
# 1. Load a raw voltammogram from CSV.
# 2. Smooth the current using Savitzky-Golay filtering, when SciPy is available.
# 3. Fit and subtract a sloped baseline using the scan shoulders.
# 4. Find the arsenic peak near -800 mV and measure its net current.
# 5. Convert peak current to concentration using a linear calibration.
# 6. Flag results against the validated LOD and quantification range.
#
# Usage:
#   python mas_g1_arsenic_analysis.py calibrate standards.csv calibration.json
#   python mas_g1_arsenic_analysis.py quantify sample.csv calibration.json
#   python mas_g1_arsenic_analysis.py demo
#
# Voltammogram CSV columns: potential_mV,current_uA
# Standards CSV columns: concentration_mgL,file

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import List, Tuple, cast

import numpy as np
from numpy.typing import NDArray

try:
    # SciPy is optional; import it dynamically so environments without SciPy
    # can use the moving-average fallback below.
    savgol_filter = import_module("scipy.signal").savgol_filter
    _scipy_available = True
except ImportError:  # graceful fallback if scipy isn't installed
    _scipy_available = False


# ----------------------------------------------------------------------
# Sensor / instrument constants (As-M003050 strip on MAS-G1)
# ----------------------------------------------------------------------
PEAK_POTENTIAL_MV = -800        # nominal As(III) stripping peak location
PEAK_SEARCH_WINDOW_MV = 60      # search +/- this many mV around the nominal peak
BASELINE_SHOULDER_MV = 40       # width of flat shoulders used to fit baseline
LOD_MGL = 0.02                  # limit of detection
QUANT_RANGE_MGL = (0.03, 0.50)  # validated quantification range


# ----------------------------------------------------------------------
# Data containers
# ----------------------------------------------------------------------
@dataclass
class Voltammogram:
    potential_mV: NDArray[np.float64]
    current_uA: NDArray[np.float64]

    @classmethod
    def from_csv(cls, path: str) -> "Voltammogram":
        potential_values: List[float] = []
        current_values: List[float] = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                potential_values.append(float(row["potential_mV"]))
                current_values.append(float(row["current_uA"]))
        potential_array: np.ndarray = np.asarray(potential_values, dtype=float)
        current_array: np.ndarray = np.asarray(current_values, dtype=float)
        order = np.argsort(potential_array)
        return cls(potential_array[order], current_array[order])


@dataclass
class PeakResult:
    peak_potential_mV: float
    raw_current_uA: float
    baseline_current_uA: float
    net_current_uA: float  # baseline-corrected -> the analytical signal


@dataclass
class Calibration:
    slope: float        # uA per (mg/L)
    intercept: float     # uA
    r_squared: float
    n_points: int
    concentrations: List[float] = field(default_factory=lambda: [])
    peak_currents: List[float] = field(default_factory=lambda: [])

    def to_json(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def from_json(cls, path: str) -> "Calibration":
        data = json.loads(Path(path).read_text())
        return cls(**data)

    def concentration_from_current(self, net_current_uA: float) -> float:
        if self.slope == 0:
            raise ValueError("Calibration slope is zero; cannot invert.")
        return (net_current_uA - self.intercept) / self.slope


# ----------------------------------------------------------------------
# Signal processing
# ----------------------------------------------------------------------
def smooth(current: np.ndarray, window: int = 9, polyorder: int = 3) -> np.ndarray:
    """Savitzky-Golay smoothing; falls back to a moving average if scipy
    is unavailable."""
    n = len(current)
    if n < 5:
        return current.copy()

    if _scipy_available:
        w = min(window, n - (1 - n % 2))  # keep window odd and <= n
        if w % 2 == 0:
            w -= 1
        w = max(w, polyorder + 2 if (polyorder + 2) % 2 == 1 else polyorder + 3)
        w = min(w, n if n % 2 == 1 else n - 1)
        w = max(w, 5)
        return savgol_filter(current, window_length=w, polyorder=min(polyorder, w - 1))
    else:
        kernel = np.ones(5) / 5
        return np.convolve(current, kernel, mode="same")


def fit_baseline(volt: Voltammogram, peak_center_mV: float = PEAK_POTENTIAL_MV,
                  search_window_mV: float = PEAK_SEARCH_WINDOW_MV,
                  shoulder_mV: float = BASELINE_SHOULDER_MV) -> np.ndarray:
    """
    Fit a straight-line baseline under the As stripping peak using the
    flat shoulders just outside the peak search window (standard
    linear/tangent baseline subtraction used for stripping voltammetry).
    Returns the baseline current evaluated at every point in `volt`.
    """
    lo_peak = peak_center_mV - search_window_mV
    hi_peak = peak_center_mV + search_window_mV

    left_mask = (volt.potential_mV >= lo_peak - shoulder_mV) & (volt.potential_mV < lo_peak)
    right_mask = (volt.potential_mV > hi_peak) & (volt.potential_mV <= hi_peak + shoulder_mV)

    shoulder_mask = left_mask | right_mask
    if shoulder_mask.sum() < 2:
        # Not enough shoulder data -> fall back to a flat baseline at the
        # minimum current in the whole scan (conservative).
        return np.full_like(volt.current_uA, volt.current_uA.min())

    x = volt.potential_mV[shoulder_mask]
    y = volt.current_uA[shoulder_mask]
    coeffs = np.polyfit(x, y, deg=1)  # linear baseline: y = a*x + b
    baseline = np.polyval(coeffs, volt.potential_mV)
    return baseline


def find_peak(volt: Voltammogram, smoothed_current: np.ndarray, baseline: np.ndarray,
              peak_center_mV: float = PEAK_POTENTIAL_MV,
              search_window_mV: float = PEAK_SEARCH_WINDOW_MV) -> PeakResult:
    """Find the max baseline-corrected current within the expected As
    peak window and report it as the analytical signal."""
    lo, hi = peak_center_mV - search_window_mV, peak_center_mV + search_window_mV
    mask = (volt.potential_mV >= lo) & (volt.potential_mV <= hi)
    if not np.any(mask):
        raise ValueError(
            f"No data points found in the expected As(III) peak window "
            f"[{lo}, {hi}] mV. Check the scan range / potential units."
        )

    net = smoothed_current[mask] - baseline[mask]
    idx_local = int(np.argmax(net))
    idx_global = np.where(mask)[0][idx_local]

    return PeakResult(
        peak_potential_mV=float(volt.potential_mV[idx_global]),
        raw_current_uA=float(smoothed_current[idx_global]),
        baseline_current_uA=float(baseline[idx_global]),
        net_current_uA=float(net[idx_local]),
    )


def process_voltammogram(volt: Voltammogram) -> PeakResult:
    """Full preprocessing + peak extraction for one voltammogram."""
    smoothed = smooth(volt.current_uA)
    baseline = fit_baseline(volt)
    return find_peak(volt, smoothed, baseline)


# ----------------------------------------------------------------------
# Calibration
# ----------------------------------------------------------------------
def build_calibration(standards: List[Tuple[float, str]]) -> Calibration:
    """
    standards: list of (concentration_mg_per_L, path_to_voltammogram_csv)
    Fits I_peak = m*C + b by linear regression, as validated on the
    datasheet (R^2 > 0.99 over 0.03-0.50 mg/L).
    """
    concs: List[float] = []
    currents: List[float] = []
    for conc, path in standards:
        volt = Voltammogram.from_csv(path)
        peak = process_voltammogram(volt)
        concs.append(conc)
        currents.append(peak.net_current_uA)

    concs_arr = np.asarray(concs, dtype=float)
    currents_arr = np.asarray(currents, dtype=float)

    slope, intercept = np.polyfit(concs_arr, currents_arr, deg=1)
    predicted = slope * concs_arr + intercept
    ss_res = cast(float, np.sum((currents_arr - predicted) ** 2))
    ss_tot = cast(float, np.sum((currents_arr - currents_arr.mean()) ** 2))
    r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    return Calibration(
        slope=float(slope),
        intercept=float(intercept),
        r_squared=float(r_squared),
        n_points=len(concs),
        concentrations=concs_arr.tolist(),
        peak_currents=currents_arr.tolist(),
    )


# ----------------------------------------------------------------------
# Quantification (the main "answer" step)
# ----------------------------------------------------------------------
@dataclass
class ArsenicResult:
    peak: PeakResult
    concentration_mgL: float
    below_lod: bool
    within_quant_range: bool
    flag: str


def quantify_arsenic(volt: Voltammogram, calibration: Calibration) -> ArsenicResult:
    peak = process_voltammogram(volt)
    conc = calibration.concentration_from_current(peak.net_current_uA)

    below_lod = conc < LOD_MGL
    within_range = QUANT_RANGE_MGL[0] <= conc <= QUANT_RANGE_MGL[1]

    if below_lod:
        flag = f"< LOD ({LOD_MGL} mg/L) — report as 'not detected'"
    elif conc < QUANT_RANGE_MGL[0]:
        flag = "Above LOD but below validated quantification range — treat as estimate"
    elif conc > QUANT_RANGE_MGL[1]:
        flag = "Above validated quantification range (0.50 mg/L) — dilute sample and re-run"
    else:
        flag = "Within validated quantification range"

    return ArsenicResult(
        peak=peak,
        concentration_mgL=float(conc),
        below_lod=below_lod,
        within_quant_range=within_range,
        flag=flag,
    )


def report(result: ArsenicResult) -> str:
    p = result.peak
    lines = [
        "=== MAS-G1 / As-M003050 Arsenic(III) Quantification ===",
        f"Peak location        : {p.peak_potential_mV:.1f} mV (expected ~{PEAK_POTENTIAL_MV} mV)",
        f"Raw peak current      : {p.raw_current_uA:.4f} uA",
        f"Baseline current      : {p.baseline_current_uA:.4f} uA",
        f"Net (analytical) signal: {p.net_current_uA:.4f} uA",
        f"Arsenic concentration  : {result.concentration_mgL:.4f} mg/L",
        f"Status                : {result.flag}",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Synthetic-data demo (so the pipeline is runnable with no real hardware)
# ----------------------------------------------------------------------
def _synthetic_voltammogram(conc_mgL: float, noise: float = 0.02, seed: int | None = None) -> Voltammogram:
    """
    Generates a plausible stripping voltammogram: sloped baseline +
    a Gaussian-ish peak at -800 mV whose height scales linearly with
    concentration, matching the datasheet's described behavior.
    """
    rng = np.random.default_rng(seed)
    potentials = np.arange(-1000, -600 + 1, 5, dtype=float)  # mV
    baseline_true = 0.05 + 0.00015 * (potentials + 1000)     # gentle slope
    true_slope_uA_per_mgL = 0.9   # arbitrary but realistic-scale sensitivity
    peak_height = true_slope_uA_per_mgL * conc_mgL
    peak = peak_height * np.exp(-0.5 * ((potentials - PEAK_POTENTIAL_MV) / 15.0) ** 2)
    current = baseline_true + peak + rng.normal(0, noise, size=potentials.shape)
    return Voltammogram(potentials, current)


def run_demo() -> None:
    print("Generating synthetic calibration standards (0.03-0.50 mg/L)...")
    standards_dir = Path(tempfile.gettempdir()) / "mas_g1_demo"
    standards_dir.mkdir(exist_ok=True)

    std_concs = [0.03, 0.10, 0.25, 0.50]
    standards: List[Tuple[float, str]] = []
    for i, c in enumerate(std_concs):
        v = _synthetic_voltammogram(c, seed=100 + i)
        path = standards_dir / f"std_{c:.2f}.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["potential_mV", "current_uA"])
            w.writerows(zip(v.potential_mV, v.current_uA))
        standards.append((c, str(path)))

    calibration = build_calibration(standards)
    print(f"Calibration: I = {calibration.slope:.4f} * C + {calibration.intercept:.4f}"
          f"  (R^2 = {calibration.r_squared:.4f}, n={calibration.n_points})\n")

    print("Generating an 'unknown' sample at a hidden concentration...")
    true_unknown_conc = 0.18  # mg/L, pretend we don't know this
    unknown = _synthetic_voltammogram(true_unknown_conc, seed=7)

    result = quantify_arsenic(unknown, calibration)
    print(report(result))
    print(f"\n(For demo purposes only — the synthetic sample was actually "
          f"{true_unknown_conc} mg/L; estimated {result.concentration_mgL:.4f} mg/L.)")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="MAS-G1 arsenic voltammogram analyzer")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cal = sub.add_parser("calibrate", help="Build a calibration from known standards")
    p_cal.add_argument("standards_csv", help="CSV with columns concentration_mgL,file")
    p_cal.add_argument("output_json", help="Where to save the calibration")

    p_quant = sub.add_parser("quantify", help="Quantify arsenic in a sample voltammogram")
    p_quant.add_argument("sample_csv", help="CSV with columns potential_mV,current_uA")
    p_quant.add_argument("calibration_json", help="Calibration file produced by 'calibrate'")

    sub.add_parser("demo", help="Run an end-to-end demo with synthetic data")

    args = parser.parse_args()

    if args.command == "calibrate":
        standards: List[Tuple[float, str]] = []
        with open(args.standards_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                standards.append((float(row["concentration_mgL"]), row["file"]))
        calibration = build_calibration(standards)
        calibration.to_json(args.output_json)
        print(f"Saved calibration to {args.output_json}")
        print(f"I = {calibration.slope:.4f} * C + {calibration.intercept:.4f}  "
              f"(R^2 = {calibration.r_squared:.4f})")

    elif args.command == "quantify":
        volt = Voltammogram.from_csv(args.sample_csv)
        calibration = Calibration.from_json(args.calibration_json)
        result = quantify_arsenic(volt, calibration)
        print(report(result))

    elif args.command == "demo":
        run_demo()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No args given -> just run the demo so it's easy to try.
        run_demo()
    else:
        main()
