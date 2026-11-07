"""
AquaNet ASV Signal Extractor & Neural Classification Pipeline.

End-to-End Electrochemical Inference:
1. Ingests raw Anodic Stripping Voltammetry (ASV) sweeps (CSV with potential_mV, current_uA).
2. Applies 5-point Savitzky-Golay filtering and robust linear baseline subtraction (105 mV exclusion window).
3. Extracts net Faradaic stripping peak current (Ip) in the analytical window [-860 mV, -740 mV] (-800 mV +/- 60 mV, same as app/standards.py).
4. Maps peak current to Arsenic concentration using voltammetric calibration (slope/intercept).
5. Passes estimated Arsenic along with auxiliary geochemical sensors (pH, EC, Turbidity, Temp)
   directly into AquaNet-V1 for real-time edge water safety classification.
"""

from __future__ import annotations
import csv
import json
import os
import sys
import argparse
from typing import Dict, List, Tuple, Any, Optional

try:
    from aquanet_classifier import forward_pass, AquaNetV1, POTABILITY_LIMITS
except ImportError:
    try:
        from app.neural_classifier import forward_pass, AquaNetV1, POTABILITY_LIMITS
    except ImportError:
        from neural_classifier import forward_pass, AquaNetV1, POTABILITY_LIMITS


def savitzky_golay_5pt(y: List[float]) -> List[float]:
    """5-point quadratic Savitzky-Golay smoothing filter."""
    n = len(y)
    if n < 5:
        return list(y)
    smoothed = [0.0] * n
    smoothed[0] = (31.0 * y[0] + 9.0 * y[1] - 3.0 * y[2] - 5.0 * y[3] + 3.0 * y[4]) / 35.0
    smoothed[1] = (9.0 * y[0] + 13.0 * y[1] + 12.0 * y[2] + 6.0 * y[3] - 5.0 * y[4]) / 35.0
    for i in range(2, n - 2):
        smoothed[i] = (-3.0 * y[i - 2] + 12.0 * y[i - 1] + 17.0 * y[i] + 12.0 * y[i + 1] - 3.0 * y[i + 2]) / 35.0
    smoothed[n - 2] = (-5.0 * y[n - 5] + 6.0 * y[n - 4] + 12.0 * y[n - 3] + 13.0 * y[n - 2] + 9.0 * y[n - 1]) / 35.0
    smoothed[n - 1] = (3.0 * y[n - 5] - 5.0 * y[n - 4] - 3.0 * y[n - 3] + 9.0 * y[n - 2] + 31.0 * y[n - 1]) / 35.0
    return smoothed


def fit_linear_baseline(
    potentials: List[float],
    currents: List[float],
    peak_potential_mv: float = -800.0,
    exclusion_half_width_mv: float = 105.0,
) -> Tuple[float, float]:
    """Fit a linear baseline outside the 3-sigma peak exclusion window."""
    p_fit = []
    c_fit = []
    for p, c in zip(potentials, currents):
        if abs(p - peak_potential_mv) > exclusion_half_width_mv:
            p_fit.append(p)
            c_fit.append(c)

    if len(p_fit) < 2:
        return 0.0, sum(currents) / len(currents)

    n = len(p_fit)
    x_bar = sum(p_fit) / n
    y_bar = sum(c_fit) / n
    s_xx = sum((x - x_bar) ** 2 for x in p_fit)
    s_xy = sum((x - x_bar) * (y - y_bar) for x, y in zip(p_fit, c_fit))
    slope = s_xy / s_xx if s_xx != 0.0 else 0.0
    intercept = y_bar - slope * x_bar
    return slope, intercept


def calculate_standard_addition(
    ip_sample: float,
    ip_spiked: float,
    c_spike: float
) -> Dict[str, Any]:
    """
    Standard addition matrix inversion method.
    Given:
        ip_sample: Peak current of unknown water sample (uA)
        ip_spiked: Peak current after adding known standard concentration c_spike (uA)
        c_spike:   Concentration of added standard (mg/L)
    Returns:
        Concentration of unknown sample, calibration slope, and validity status.
    """
    delta_i = ip_spiked - ip_sample
    if delta_i <= 1e-6 or c_spike <= 0.0 or ip_sample <= 0.0:
        return {
            "valid": False,
            "reason": "Invalid standard addition parameters (delta_current <= 0 or non-positive inputs)",
            "estimated_concentration_mg_l": 0.0,
            "slope": 0.0,
            "delta_current_ua": delta_i,
        }

    slope = delta_i / c_spike
    c_sample = ip_sample / slope
    return {
        "valid": True,
        "estimated_concentration_mg_l": round(c_sample, 4),
        "estimated_concentration_ug_l": round(c_sample * 1000.0, 1),
        "calibration_slope_ua_per_mg_l": round(slope, 4),
        "delta_current_ua": round(delta_i, 4),
        "ip_sample_ua": round(ip_sample, 4),
        "ip_spiked_ua": round(ip_spiked, 4),
        "c_spike_mg_l": round(c_spike, 4),
    }


MULTI_ANALYTE_WINDOWS = {
    "arsenic": {
        "symbol": "As",
        "name": "Arsenic",
        "window_mv": (-860.0, -740.0),
        "nominal_peak_mv": -800.0,
        "default_slope": 0.8563,
        "default_intercept": 0.0096,
        "lod_mg_l": 0.020,
    },
    "cadmium": {
        "symbol": "Cd",
        "name": "Cadmium",
        "window_mv": (-700.0, -600.0),
        "nominal_peak_mv": -650.0,
        "default_slope": 1.1200,
        "default_intercept": 0.0050,
        "lod_mg_l": 0.003,
    },
    "lead": {
        "symbol": "Pb",
        "name": "Lead",
        "window_mv": (-500.0, -400.0),
        "nominal_peak_mv": -450.0,
        "default_slope": 1.3400,
        "default_intercept": 0.0080,
        "lod_mg_l": 0.010,
    },
    "copper": {
        "symbol": "Cu",
        "name": "Copper",
        "window_mv": (0.0, 150.0),
        "nominal_peak_mv": 50.0,
        "default_slope": 0.9500,
        "default_intercept": 0.0100,
        "lod_mg_l": 0.050,
    },
}


def deconvolve_multi_analyte_trace(
    potentials: List[float],
    currents: List[float],
    custom_slopes: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Deconvolves multi-element anodic stripping peaks across Arsenic (As), Cadmium (Cd), Lead (Pb), and Copper (Cu).
    """
    smoothed = savitzky_golay_5pt(currents)
    m_base, c_base = fit_linear_baseline(potentials, smoothed, peak_potential_mv=-800.0, exclusion_half_width_mv=105.0)

    analyte_results = {}
    for key, info in MULTI_ANALYTE_WINDOWS.items():
        w_min, w_max = info["window_mv"]
        slope = custom_slopes.get(key, info["default_slope"]) if custom_slopes else info["default_slope"]
        intercept = info["default_intercept"]

        max_net = -1e9
        best_p = info["nominal_peak_mv"]

        for p, c in zip(potentials, smoothed):
            if w_min <= p <= w_max:
                b = m_base * p + c_base
                net = c - b
                if net > max_net:
                    max_net = net
                    best_p = p

        detected = max_net > 0.05
        conc_mg_l = max(0.0, (max_net - intercept) / slope) if detected else 0.0

        analyte_results[key] = {
            "symbol": info["symbol"],
            "name": info["name"],
            "detected": detected,
            "peak_potential_mv": round(best_p, 1),
            "net_peak_current_ua": round(max(0.0, max_net), 4) if detected else 0.0,
            "estimated_concentration_mg_l": round(conc_mg_l, 4),
            "estimated_concentration_ug_l": round(conc_mg_l * 1000.0, 1),
            "lod_mg_l": info["lod_mg_l"],
        }

    return analyte_results


def process_asv_trace(
    csv_path: str,
    calibration_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Process a voltammetry CSV trace and calculate calibrated Arsenic concentration."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"ASV data file not found: {csv_path}")

    potentials: List[float] = []
    currents: List[float] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_key = "potential_mV" if "potential_mV" in row else ("potential" if "potential" in row else list(row.keys())[0])
            c_key = "current_uA" if "current_uA" in row else ("current" if "current" in row else list(row.keys())[1])
            potentials.append(float(row[p_key]))
            currents.append(float(row[c_key]))

    # Calibration parameters
    slope = 0.8563
    intercept = 0.0096
    if calibration_path and os.path.exists(calibration_path):
        with open(calibration_path, "r", encoding="utf-8") as f:
            cal = json.load(f)
            slope = float(cal.get("slope", slope))
            intercept = float(cal.get("intercept", intercept))

    # Signal Denoising
    smoothed = savitzky_golay_5pt(currents)

    # Baseline Subtraction
    m_base, c_base = fit_linear_baseline(potentials, smoothed, peak_potential_mv=-800.0, exclusion_half_width_mv=105.0)

    # Net Peak Current Extraction in analytical window [-860, -740] mV (-800 +/- 60, as in app/standards.py)
    peak_potential = -800.0
    max_net_current = -1e9
    raw_peak_current = 0.0
    baseline_at_peak = 0.0

    for p, c in zip(potentials, smoothed):
        if -860.0 <= p <= -740.0:
            b = m_base * p + c_base
            net = c - b
            if net > max_net_current:
                max_net_current = net
                peak_potential = p
                raw_peak_current = c
                baseline_at_peak = b

    # Calibrated Arsenic Inversion: [As] = (Ip - intercept) / slope
    estimated_as_mg_l = max(0.0, (max_net_current - intercept) / slope)
    estimated_as_ug_l = estimated_as_mg_l * 1000.0

    multi_analytes = deconvolve_multi_analyte_trace(potentials, smoothed, {"arsenic": slope})

    return {
        "file_name": os.path.basename(csv_path),
        "total_sweep_points": len(potentials),
        "peak_potential_mv": peak_potential,
        "net_peak_current_ua": round(max_net_current, 6),
        "raw_current_at_peak_ua": round(raw_peak_current, 6),
        "baseline_at_peak_ua": round(baseline_at_peak, 6),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "estimated_arsenic_mg_l": round(estimated_as_mg_l, 4),
        "estimated_arsenic_ug_l": round(estimated_as_ug_l, 1),
        "multi_analyte_deconvolution": multi_analytes,
        "standard_addition_supported": True,
    }


def analyze_water_sample(
    csv_path: str,
    calibration_path: Optional[str] = None,
    ph: float = 7.2,
    conductivity_us_cm: float = 400.0,
    turbidity_ntu: float = 2.0,
    temperature_c: float = 24.0,
) -> Dict[str, Any]:
    """Execute end-to-end ASV extraction and AquaNet neural safety classification."""
    asv_res = process_asv_trace(csv_path, calibration_path)
    as_mg = asv_res["estimated_arsenic_mg_l"]

    nn_res = forward_pass(
        arsenic_mg_l=as_mg,
        ph=ph,
        conductivity_us_cm=conductivity_us_cm,
        turbidity_ntu=turbidity_ntu,
        temperature_c=temperature_c,
    )

    return {
        "asv_signal_processing": asv_res,
        "geochemical_parameters": {
            "arsenic_mg_l": as_mg,
            "ph": ph,
            "conductivity_us_cm": conductivity_us_cm,
            "turbidity_ntu": turbidity_ntu,
            "temperature_c": temperature_c,
        },
        "neural_safety_classification": nn_res,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-End ASV Stripping & AquaNet Neural Surveillance")
    parser.add_argument("--csv", default="example_data.csv", help="Path to raw voltammetry CSV trace")
    parser.add_argument("--cal", default="calibration.json", help="Path to voltammetric calibration JSON")
    parser.add_argument("--ph", type=float, default=7.2, help="Water pH")
    parser.add_argument("--ec", type=float, default=400.0, help="Electrical conductivity in uS/cm")
    parser.add_argument("--turb", type=float, default=2.0, help="Turbidity in NTU")
    parser.add_argument("--temp", type=float, default=24.0, help="Water temperature in °C")

    args = parser.parse_args()

    print("=" * 75)
    print("AquaNet ASV Stripping Voltammetry -> Neural Risk Pipeline")
    print("=" * 75)

    result = analyze_water_sample(
        csv_path=args.csv,
        calibration_path=args.cal if os.path.exists(args.cal) else None,
        ph=args.ph,
        conductivity_us_cm=args.ec,
        turbidity_ntu=args.turb,
        temperature_c=args.temp,
    )

    asv = result["asv_signal_processing"]
    nn = result["neural_safety_classification"]

    print(f"\n[1] Voltammetric Stripping Signal Analysis ({asv['file_name']}):")
    print(f"    Sweep Points: {asv['total_sweep_points']} (-1000 mV to -600 mV)")
    print(f"    Peak Potential: {asv['peak_potential_mv']} mV (Arsenic oxidation)")
    print(f"    Net Peak Current (Ip): {asv['net_peak_current_ua']} uA")
    print(f"    Inverted Arsenic: {asv['estimated_arsenic_mg_l']} mg/L ({asv['estimated_arsenic_ug_l']} ug/L)")

    print(f"\n[2] AquaNet-V1 Neural Safety Verdict:")
    print(f"    Final Classification: [{nn['predicted_class'].upper()}] (Confidence: {nn['confidence_pct']}%)")
    print(f"    Class Probabilities: {nn['probabilities']}")
    print(f"    Execution Latency: {nn['latency_ms']} ms")
    if nn["reason_codes"]:
        print(f"    Policy Advisories:")
        for r in nn["reason_codes"]:
            print(f"      - {r}")

    print("\n" + "=" * 75)
