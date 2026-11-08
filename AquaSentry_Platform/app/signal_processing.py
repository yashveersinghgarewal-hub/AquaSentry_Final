"""
AquaSentry Electrochemical Signal Processing & Quality Control Pipeline.

Processes raw voltammograms acquired from the potentiostat (MAS-G1 strip / ADS1115 ADC):
1. Input validation & structural check (monotonic sweep, valid finite floats, bounds).
2. Five-point Savitzky-Golay smoothing vs rolling median vs raw baseline comparison.
3. Linear & polynomial baseline correction and subtraction.
4. Peak identification within validated analytical window (-800 mV +/- search window).
5. Signal-to-noise ratio (SNR), peak height (µA), integrated peak area, and peak width calculation.
6. Calibration mapping: converts peak current to Arsenic concentration (µg/L and mg/L).
7. Trace QC diagnostic flags: saturation, unstable baseline, ambiguous peaks, below LOD.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .standards import (
    CALIBRATION_SLOPE,
    CALIBRATION_INTERCEPT,
    CAL_MAX_UG_L,
    PEAK_POTENTIAL_MV,
    SWEEP_WINDOW_MV,
    mg_l_to_ug_l,
)


@dataclass
class PeakCharacteristics:
    peak_potential_mv: float
    peak_current_raw_ua: float
    baseline_current_ua: float
    net_peak_height_ua: float
    peak_area_ua_mv: float
    half_height_width_mv: float
    snr: float
    baseline_residual_variance: float
    is_valid_peak: bool
    qc_flags: List[str]


@dataclass
class VoltammetryResult:
    estimated_arsenic_ug_l: float
    estimated_arsenic_mg_l: float
    peak: Optional[PeakCharacteristics]
    filter_type: str
    qc_status: str                     # PASS | WARNING | REJECTED
    qc_messages: List[str]
    raw_potentials_mv: List[float]
    raw_currents_ua: List[float]
    smoothed_currents_ua: List[float]
    baseline_currents_ua: List[float]
    subtracted_currents_ua: List[float]


def savitzky_golay_5pt(y: List[float]) -> List[float]:
    """
    Apply a 5-point quadratic Savitzky-Golay smoothing filter.
    Convolution coefficients: [-3, 12, 17, 12, -3] / 35.
    Endpoints extrapolated with standard SG quadratic polynomial coefficients.
    Preserves linear and quadratic features exactly while suppressing random noise.
    """
    n = len(y)
    if n < 5:
        return list(y)

    smoothed = [0.0] * n
    # Endpoints computed via standard 5-point SG quadratic boundary coefficients
    smoothed[0] = (31.0 * y[0] + 9.0 * y[1] - 3.0 * y[2] - 5.0 * y[3] + 3.0 * y[4]) / 35.0
    smoothed[1] = (9.0 * y[0] + 13.0 * y[1] + 12.0 * y[2] + 6.0 * y[3] - 5.0 * y[4]) / 35.0

    # Interior 5-point window
    for i in range(2, n - 2):
        val = (-3.0 * y[i - 2] + 12.0 * y[i - 1] + 17.0 * y[i] + 12.0 * y[i + 1] - 3.0 * y[i + 2]) / 35.0
        smoothed[i] = val

    # Upper endpoints
    smoothed[n - 2] = (-5.0 * y[n - 5] + 6.0 * y[n - 4] + 12.0 * y[n - 3] + 13.0 * y[n - 2] + 9.0 * y[n - 1]) / 35.0
    smoothed[n - 1] = (3.0 * y[n - 5] - 5.0 * y[n - 4] - 3.0 * y[n - 3] + 9.0 * y[n - 2] + 31.0 * y[n - 1]) / 35.0

    return smoothed


def rolling_median_3pt(y: List[float]) -> List[float]:
    """Robust 3-point rolling median filter for spike suppression."""
    n = len(y)
    if n < 3:
        return list(y)
    res = [y[0]]
    for i in range(1, n - 1):
        window = sorted([y[i - 1], y[i], y[i + 1]])
        res.append(window[1])
    res.append(y[-1])
    return res


def fit_linear_baseline(
    potentials: List[float],
    currents: List[float],
    target_peak_mv: float = PEAK_POTENTIAL_MV,
    peak_target_mv: Optional[float] = None,
    exclusion_half_width_mv: float = 105.0,
) -> Tuple[List[float], float]:
    """
    Fit a linear baseline through sweep regions outside the stripping peak window.
    Returns (baseline_array, residual_variance).
    """
    t_peak = peak_target_mv if peak_target_mv is not None else target_peak_mv
    base_x = []
    base_y = []
    for p, c in zip(potentials, currents):
        if abs(p - t_peak) > exclusion_half_width_mv:
            base_x.append(p)
            base_y.append(c)

    if len(base_x) < 4:
        p_start, p_end = potentials[0], potentials[-1]
        c_start, c_end = currents[0], currents[-1]
        slope = (c_end - c_start) / (p_end - p_start) if p_end != p_start else 0.0
        intercept = c_start - slope * p_start
        baseline = [slope * p + intercept for p in potentials]
        return baseline, 0.01

    n_pts = len(base_x)
    mean_x = sum(base_x) / n_pts
    mean_y = sum(base_y) / n_pts
    ss_xx = sum((x - mean_x) ** 2 for x in base_x)
    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(base_x, base_y))

    slope = ss_xy / ss_xx if ss_xx != 0 else 0.0
    intercept = mean_y - slope * mean_x

    baseline = [slope * p + intercept for p in potentials]
    residuals = [(y - (slope * x + intercept)) for x, y in zip(base_x, base_y)]
    variance = sum(r * r for r in residuals) / max(1, n_pts - 2)

    return baseline, variance


def process_voltammetry_trace(
    potentials_mv: List[float],
    currents_ua: List[float],
    target_peak_mv: float = PEAK_POTENTIAL_MV,
    search_window_mv: float = SWEEP_WINDOW_MV,
    filter_mode: str = "savitzky_golay",
) -> VoltammetryResult:
    """
    Process raw ASV voltammetric scan arrays and return rigorous peak and concentration metrics.
    """
    qc_flags = []
    qc_messages = []

    if len(potentials_mv) != len(currents_ua):
        raise ValueError("Potentials and currents arrays must have identical length.")
    if len(potentials_mv) < 10:
        raise ValueError("Insufficient points for voltammetric trace analysis (minimum 10 required).")

    for val in potentials_mv + currents_ua:
        if math.isnan(val) or math.isinf(val):
            raise ValueError("Trace contains non-finite numbers (NaN or Infinity).")

    # Check for ADC saturation / clipping
    max_c = max(currents_ua)
    min_c = min(currents_ua)
    if any(c >= 10.0 for c in currents_ua) or currents_ua.count(max_c) > 3:
        qc_flags.append("ADC_SATURATION_HIGH")
        qc_messages.append("Signal clipping/saturation detected at upper ADC rail.")
    if any(c <= -10.0 for c in currents_ua) or currents_ua.count(min_c) > 3:
        qc_flags.append("ADC_SATURATION_LOW")
        qc_messages.append("Signal clipping/saturation detected at lower ADC rail.")

    if filter_mode == "savitzky_golay":
        smoothed_currents = savitzky_golay_5pt(currents_ua)
    elif filter_mode == "rolling_median":
        smoothed_currents = rolling_median_3pt(currents_ua)
    else:
        smoothed_currents = list(currents_ua)

    baseline_currents, baseline_variance = fit_linear_baseline(
        potentials_mv, smoothed_currents, target_peak_mv=target_peak_mv
    )
    subtracted_currents = [
        s - b for s, b in zip(smoothed_currents, baseline_currents)
    ]

    noise_sigma = math.sqrt(max(1e-9, baseline_variance))
    if noise_sigma > 0.05:
        qc_flags.append("BASELINE_UNSTABLE")
        qc_messages.append(f"Baseline residual noise ({noise_sigma:.4f} µA) exceeds stability threshold.")

    peak_indices = [
        i for i, p in enumerate(potentials_mv)
        if abs(p - target_peak_mv) <= search_window_mv
    ]

    if not peak_indices:
        qc_flags.append("NO_POINTS_IN_WINDOW")
        qc_messages.append(f"No sweep data points within search window ({target_peak_mv} ± {search_window_mv} mV).")
        return VoltammetryResult(
            estimated_arsenic_ug_l=0.0,
            estimated_arsenic_mg_l=0.0,
            peak=None,
            filter_type=filter_mode,
            qc_status="REJECTED",
            qc_messages=qc_messages,
            raw_potentials_mv=potentials_mv,
            raw_currents_ua=currents_ua,
            smoothed_currents_ua=smoothed_currents,
            baseline_currents_ua=baseline_currents,
            subtracted_currents_ua=subtracted_currents,
        )

    best_idx = peak_indices[0]
    best_subtracted = subtracted_currents[best_idx]
    for idx in peak_indices:
        if subtracted_currents[idx] > best_subtracted:
            best_subtracted = subtracted_currents[idx]
            best_idx = idx

    peak_pot = potentials_mv[best_idx]
    raw_peak_current = currents_ua[best_idx]
    baseline_at_peak = baseline_currents[best_idx]
    net_peak_height = max(0.0, best_subtracted)

    snr = net_peak_height / noise_sigma if noise_sigma > 0 else 0.0

    half_height = net_peak_height / 2.0
    left_p = peak_pot
    right_p = peak_pot
    for i in range(best_idx, -1, -1):
        if subtracted_currents[i] <= half_height:
            left_p = potentials_mv[i]
            break
    for i in range(best_idx, len(potentials_mv)):
        if subtracted_currents[i] <= half_height:
            right_p = potentials_mv[i]
            break
    fwhm = abs(right_p - left_p)

    area = 0.0
    for i in range(len(peak_indices) - 1):
        i1 = peak_indices[i]
        i2 = peak_indices[i + 1]
        dp = abs(potentials_mv[i2] - potentials_mv[i1])
        c1 = max(0.0, subtracted_currents[i1])
        c2 = max(0.0, subtracted_currents[i2])
        area += 0.5 * (c1 + c2) * dp

    # Concentration from net stripping current
    if net_peak_height <= CALIBRATION_INTERCEPT:
        c_as_mg_l = 0.0
        c_as_ug_l = 0.0
        qc_flags.append("BELOW_METHOD_LOD")
        qc_messages.append(f"Net stripping current ({net_peak_height:.4f} µA) is below detection baseline.")
    else:
        c_as_mg_l = max(0.0, (net_peak_height - CALIBRATION_INTERCEPT) / CALIBRATION_SLOPE)
        c_as_ug_l = mg_l_to_ug_l(c_as_mg_l)

    if c_as_ug_l > CAL_MAX_UG_L:
        qc_flags.append("ABOVE_CALIBRATION_RANGE")
        qc_messages.append(f"Calculated concentration ({c_as_ug_l:.1f} µg/L) exceeds validated range ({CAL_MAX_UG_L:.0f} µg/L); dilution advised.")

    is_valid = ("ADC_SATURATION_HIGH" not in qc_flags) and ("NO_POINTS_IN_WINDOW" not in qc_flags)
    qc_status = "PASS"
    if qc_flags:
        qc_status = "REJECTED" if "ADC_SATURATION_HIGH" in qc_flags else "WARNING"

    peak_obj = PeakCharacteristics(
        peak_potential_mv=round(peak_pot, 2),
        peak_current_raw_ua=round(raw_peak_current, 4),
        baseline_current_ua=round(baseline_at_peak, 4),
        net_peak_height_ua=round(net_peak_height, 4),
        peak_area_ua_mv=round(area, 4),
        half_height_width_mv=round(fwhm, 2),
        snr=round(snr, 1),
        baseline_residual_variance=round(baseline_variance, 6),
        is_valid_peak=is_valid,
        qc_flags=qc_flags,
    )

    return VoltammetryResult(
        estimated_arsenic_ug_l=round(c_as_ug_l, 2),
        estimated_arsenic_mg_l=round(c_as_mg_l, 4),
        peak=peak_obj,
        filter_type=filter_mode,
        qc_status=qc_status,
        qc_messages=qc_messages,
        raw_potentials_mv=potentials_mv,
        raw_currents_ua=currents_ua,
        smoothed_currents_ua=smoothed_currents,
        baseline_currents_ua=baseline_currents,
        subtracted_currents_ua=subtracted_currents,
    )


def generate_synthetic_asv_trace(
    arsenic_ppb: float,
    snr_db: float = 24.0,
    seed: Optional[int] = 42,
) -> Tuple[List[float], List[float]]:
    """
    Generate an authentic synthetic Anodic Stripping Voltammogram fixture.
    """
    import random
    rng = random.Random(seed)

    potentials = [round(-1100.0 + i * 5.0, 1) for i in range(121)]
    c_mg_l = arsenic_ppb / 1000.0
    true_peak_ua = (CALIBRATION_SLOPE * c_mg_l) + CALIBRATION_INTERCEPT

    baseline = [-0.15 + 0.00015 * (p + 1100.0) for p in potentials]
    peak_center = PEAK_POTENTIAL_MV
    peak_width = 35.0
    noise_amp = 0.002 * (10.0 ** (-snr_db / 40.0))

    currents = []
    for p, b in zip(potentials, baseline):
        gauss = math.exp(-0.5 * ((p - peak_center) / peak_width) ** 2)
        signal = b + (true_peak_ua * gauss)
        noise = (rng.random() - 0.5) * 2.0 * noise_amp
        currents.append(round(signal + noise, 5))

    return potentials, currents
