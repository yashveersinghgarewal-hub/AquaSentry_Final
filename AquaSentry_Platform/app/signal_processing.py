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
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .standards import (
    CALIBRATION_SLOPE,
    CALIBRATION_INTERCEPT,
    CAL_MAX_UG_L,
    LOD_UG_L,
    PEAK_POTENTIAL_MV,
    SWEEP_WINDOW_MV,
    PEAK_SEARCH_MV,
    QC_FLAT_RANGE_UA,
    QC_MAX_NOISE_UA,
    QC_DETECT_SNR,
    QC_FAULT_FLAGS,
    mg_l_to_ug_l,
)


ANALYSIS_VERSION = "asv-1.2.0"   # v5.8: bump whenever the maths below changes (stored with every scan)
MIN_POINTS = 10
MIN_BASELINE_POINTS_PER_SIDE = 4  # background line needs real shoulders on both sides of the peak


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
    # v5.8 features (review item 12): kept with the raw trace so a later model can learn from them
    baseline_slope_ua_per_mv: float = 0.0
    noise_sigma_ua: float = 0.0
    secondary_peaks: int = 0
    uncertainty_ug_l: Optional[float] = None    # expanded (k=2) estimate, see estimate_uncertainty()


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
    analysis_version: str = ANALYSIS_VERSION
    sweep_reversed: bool = False       # the device swept from positive to negative; arrays were reordered
    qc_flags: List[str] = field(default_factory=list)   # same as peak.qc_flags, also set when peak is None


def estimate_uncertainty(conc_ug_l: float, noise_sigma_ua: float, slope: float,
                         cal_rel_sd: float = 0.05, n_scans: int = 1) -> float:
    """Expanded uncertainty (k = 2) of one arsenic value, in µg/L.

    Measured part: the background noise of this scan divided by the calibration slope (how much the peak
    height can wander), divided by sqrt(scans averaged). Calibration part: the relative standard deviation of
    the calibration (5 % assumed until a laboratory calibration supplies its own residuals). Added in
    quadrature and doubled. This replaces the model's "confidence", which never measured anything."""
    if slope <= 0 or not math.isfinite(slope):
        return float("nan")
    u_noise = noise_sigma_ua / slope * 1000.0 / math.sqrt(max(1, n_scans))
    u_cal = cal_rel_sd * max(0.0, conc_ug_l)
    return round(2.0 * math.sqrt(u_noise * u_noise + u_cal * u_cal), 2)


def _rejected(potentials, currents, flags, messages, filter_mode, smoothed=None, baseline=None, reversed_=False):
    smoothed = smoothed if smoothed is not None else list(currents)
    baseline = baseline if baseline is not None else [0.0] * len(currents)
    return VoltammetryResult(
        estimated_arsenic_ug_l=0.0, estimated_arsenic_mg_l=0.0, peak=None, filter_type=filter_mode,
        qc_status="REJECTED", qc_messages=messages, raw_potentials_mv=list(potentials), raw_currents_ua=list(currents),
        smoothed_currents_ua=smoothed, baseline_currents_ua=baseline,
        subtracted_currents_ua=[a - b for a, b in zip(smoothed, baseline)], sweep_reversed=reversed_,
        qc_flags=list(flags),
    )


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
        fit_linear_baseline.last_outliers = 0
        return baseline, 0.01

    def fit(xs, ys):
        n_pts = len(xs)
        mean_x = sum(xs) / n_pts
        mean_y = sum(ys) / n_pts
        ss_xx = sum((x - mean_x) ** 2 for x in xs)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        sl = ss_xy / ss_xx if ss_xx != 0 else 0.0
        ic = mean_y - sl * mean_x
        res = [(y - (sl * x + ic)) for x, y in zip(xs, ys)]
        return sl, ic, res, sum(r * r for r in res) / max(1, n_pts - 2)

    # v5.8: robust fit. A second stripping peak (copper, a shoulder, a spike) that sits in the background region
    # would otherwise tilt the line and change the arsenic value; points far above the line are dropped and the
    # line refitted (two passes), so such bumps stay in the subtracted trace where they can be seen and counted.
    n_start = len(base_x)
    slope, intercept, residuals, variance = fit(base_x, base_y)
    for _ in range(3):
        # robust scale (median absolute deviation): a wide bump must not inflate the yardstick it is judged by
        med = sorted(residuals)[len(residuals) // 2]
        mad = sorted(abs(r - med) for r in residuals)[len(residuals) // 2]
        sd = max(1.4826 * mad, 1e-6)
        keep = [(x, y) for x, y, r in zip(base_x, base_y, residuals) if abs(r - med) <= 3.0 * sd]
        if len(keep) < 4 or len(keep) == len(base_x):
            break
        base_x, base_y = [k[0] for k in keep], [k[1] for k in keep]
        slope, intercept, residuals, variance = fit(base_x, base_y)

    baseline = [slope * p + intercept for p in potentials]
    fit_linear_baseline.last_outliers = n_start - len(base_x)   # read by process_voltammetry_trace
    return baseline, variance


def process_voltammetry_trace(
    potentials_mv: List[float],
    currents_ua: List[float],
    target_peak_mv: float = PEAK_POTENTIAL_MV,
    search_window_mv: float = PEAK_SEARCH_MV,
    filter_mode: str = "savitzky_golay",
    slope: float = CALIBRATION_SLOPE,
    intercept: float = CALIBRATION_INTERCEPT,
    lod_ug_l: float = LOD_UG_L,
    strict: bool = True,
    cal_rel_sd: float = 0.05,
) -> VoltammetryResult:
    """
    Process raw ASV voltammetric scan arrays and return rigorous peak and concentration metrics.

    strict=True (the /api/voltammetry/process endpoint): a trace that cannot be analysed at all (too short,
    non-finite numbers, lengths differ, invalid calibration) raises ValueError -> HTTP 422.
    strict=False (stored device scans): the same cases come back as a REJECTED result with the reason, so the
    failed run is kept as evidence (review item 40 / 42) and never turns into a concentration.

    Fail-safe QC: a scan that looks like a disconnected / dry electrode (FLAT_SIGNAL), is too noisy to see
    arsenic at the detection limit (NOISE_ABOVE_LOD, BASELINE_UNSTABLE), is clipped, or whose biggest
    current sits at the edge of the search window (PEAK_AT_WINDOW_EDGE: the real peak may be outside it)
    is REJECTED. A rejected scan must be reported as "test failed", never as a low arsenic value.
    """
    qc_flags = []
    qc_messages = []
    potentials_mv = [float(v) for v in potentials_mv]
    currents_ua = [float(v) for v in currents_ua]

    def fail(flag: str, msg: str):
        if strict:
            raise ValueError(msg)
        return _rejected(potentials_mv, currents_ua, [flag], [msg], filter_mode)

    if len(potentials_mv) != len(currents_ua):
        return fail("MALFORMED_TRACE", "Potentials and currents arrays must have identical length.")
    if len(potentials_mv) < MIN_POINTS:
        return fail("TOO_FEW_POINTS", f"Insufficient points for voltammetric trace analysis (minimum {MIN_POINTS} required).")
    if any(math.isnan(v) or math.isinf(v) for v in potentials_mv + currents_ua):
        return fail("NON_FINITE", "Trace contains non-finite numbers (NaN or Infinity).")
    if not (math.isfinite(slope) and slope > 0 and math.isfinite(intercept)):
        return fail("INVALID_CALIBRATION", f"Calibration slope must be a positive number (got {slope}).")

    # Sweep order (review item 42): a stripping sweep runs from negative to positive. A reversed sweep is
    # accepted and reordered; a jumbled or repeating potential axis is not a sweep and is rejected.
    sweep_reversed = False
    diffs = [b - a for a, b in zip(potentials_mv, potentials_mv[1:])]
    if all(d < 0 for d in diffs):
        potentials_mv, currents_ua, sweep_reversed = potentials_mv[::-1], currents_ua[::-1], True
    elif not all(d > 0 for d in diffs):
        return fail("NONMONOTONIC_SWEEP", "Potentials must increase (or decrease) steadily through the sweep; "
                                           "this trace repeats or jumps back, so no peak can be located.")

    # Check for ADC saturation / clipping
    max_c = max(currents_ua)
    min_c = min(currents_ua)
    if any(c >= 10.0 for c in currents_ua) or currents_ua.count(max_c) > 3:
        qc_flags.append("ADC_SATURATION_HIGH")
        qc_messages.append("Signal clipping/saturation detected at upper ADC rail.")
    if any(c <= -10.0 for c in currents_ua) or currents_ua.count(min_c) > 3:
        qc_flags.append("ADC_SATURATION_LOW")
        qc_messages.append("Signal clipping/saturation detected at lower ADC rail.")
    if (max_c - min_c) < QC_FLAT_RANGE_UA:
        qc_flags.append("FLAT_SIGNAL")
        qc_messages.append(f"The scan is flat (varies by only {max_c - min_c:.4f} µA): the electrode looks "
                           "disconnected, dry or worn out. This is not a clean-water result.")

    if filter_mode == "savitzky_golay":
        smoothed_currents = savitzky_golay_5pt(currents_ua)
    elif filter_mode == "rolling_median":
        smoothed_currents = rolling_median_3pt(currents_ua)
    else:
        smoothed_currents = list(currents_ua)

    # The background line needs shoulders on both sides of the peak (review item 42: "missing shoulders").
    left_sh = sum(1 for p in potentials_mv if p < target_peak_mv - 105.0)
    right_sh = sum(1 for p in potentials_mv if p > target_peak_mv + 105.0)
    if left_sh < MIN_BASELINE_POINTS_PER_SIDE or right_sh < MIN_BASELINE_POINTS_PER_SIDE:
        msg = (f"The sweep has too few points outside the peak region ({left_sh} before, {right_sh} after; "
               f"{MIN_BASELINE_POINTS_PER_SIDE} needed on each side) to fit a background line.")
        if strict:
            raise ValueError(msg)
        return _rejected(potentials_mv, currents_ua, ["INSUFFICIENT_BASELINE"], [msg], filter_mode,
                         smoothed_currents, None, sweep_reversed)
    covers = potentials_mv[0] <= target_peak_mv - SWEEP_WINDOW_MV and potentials_mv[-1] >= target_peak_mv + SWEEP_WINDOW_MV
    if not covers:
        qc_flags.append("PARTIAL_WINDOW")
        qc_messages.append(f"The sweep does not cover the whole arsenic window ({target_peak_mv:.0f} ± {SWEEP_WINDOW_MV:.0f} mV).")

    baseline_currents, baseline_variance = fit_linear_baseline(
        potentials_mv, smoothed_currents, target_peak_mv=target_peak_mv
    )
    subtracted_currents = [
        s - b for s, b in zip(smoothed_currents, baseline_currents)
    ]
    b_slope = ((baseline_currents[-1] - baseline_currents[0]) / (potentials_mv[-1] - potentials_mv[0])
               if potentials_mv[-1] != potentials_mv[0] else 0.0)

    outliers = getattr(fit_linear_baseline, "last_outliers", 0)
    if outliers > max(2, 0.05 * len(potentials_mv)):
        qc_flags.append("BASELINE_OUTLIERS")
        qc_messages.append(f"{outliers} points in the background region were spikes or bumps and were left out of "
                           "the background fit (electrical noise or another stripping peak).")
    noise_sigma = math.sqrt(max(1e-9, baseline_variance))
    if noise_sigma > QC_MAX_NOISE_UA:
        qc_flags.append("BASELINE_UNSTABLE")
        qc_messages.append(f"Baseline residual noise ({noise_sigma:.4f} µA) exceeds stability threshold.")
    # Smallest arsenic level this particular scan could detect (3 x noise). If it is worse than the method LOD,
    # a "below LOD" answer from this scan would be false reassurance.
    scan_lod_ug_l = QC_DETECT_SNR * noise_sigma / slope * 1000.0 if slope > 0 else float("inf")
    if scan_lod_ug_l > lod_ug_l and "BASELINE_UNSTABLE" not in qc_flags:
        qc_flags.append("NOISE_ABOVE_LOD")
        qc_messages.append(f"This scan is too noisy to detect arsenic at {lod_ug_l:.0f} µg/L "
                           f"(it could only see about {scan_lod_ug_l:.0f} µg/L).")

    peak_indices = [
        i for i, p in enumerate(potentials_mv)
        if abs(p - target_peak_mv) <= search_window_mv
    ]

    if not peak_indices:
        qc_flags.append("NO_POINTS_IN_WINDOW")
        qc_messages.append(f"No sweep data points within search window ({target_peak_mv} ± {search_window_mv} mV).")
        return _rejected(potentials_mv, currents_ua, qc_flags, qc_messages, filter_mode,
                         smoothed_currents, baseline_currents, sweep_reversed)

    best_idx = peak_indices[0]
    best_subtracted = subtracted_currents[best_idx]
    for idx in peak_indices:
        if subtracted_currents[idx] > best_subtracted:
            best_subtracted = subtracted_currents[idx]
            best_idx = idx

    # Is the biggest current at the edge of the window and still rising outwards? Then the true peak is outside.
    at_edge = False
    if best_idx in (peak_indices[0], peak_indices[-1]):
        step = -1 if best_idx == peak_indices[0] else 1
        nb = best_idx + step
        at_edge = 0 <= nb < len(subtracted_currents) and subtracted_currents[nb] >= best_subtracted
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
    if net_peak_height <= intercept:
        c_as_mg_l = 0.0
        c_as_ug_l = 0.0
        qc_flags.append("BELOW_METHOD_LOD")
        qc_messages.append(f"Net stripping current ({net_peak_height:.4f} µA) is below detection baseline.")
    else:
        c_as_mg_l = max(0.0, (net_peak_height - intercept) / slope)
        c_as_ug_l = mg_l_to_ug_l(c_as_mg_l)
        if snr < QC_DETECT_SNR:
            qc_flags.append("LOW_SNR")
            qc_messages.append(f"Peak is only {snr:.1f}x the background noise; treat the value as an estimate.")

    if at_edge and net_peak_height > intercept:
        qc_flags.append("PEAK_AT_WINDOW_EDGE")
        qc_messages.append(f"The largest current is at the edge of the search window ({peak_pot:.0f} mV) and still "
                           "rising: the real arsenic peak may be outside it, so arsenic could be under-read.")
    elif abs(peak_pot - target_peak_mv) > SWEEP_WINDOW_MV and net_peak_height > intercept:
        qc_flags.append("PEAK_SHIFTED")
        qc_messages.append(f"Peak found at {peak_pot:.0f} mV, more than {SWEEP_WINDOW_MV:.0f} mV from the expected "
                           f"{target_peak_mv:.0f} mV. Check the reference electrode.")

    # Secondary peaks (review item 12): other bumps above 3 sigma outside the main peak, e.g. copper or a
    # second stripping process. Counted, not interpreted.
    secondary = 0
    thr = QC_DETECT_SNR * noise_sigma
    # the main peak's own region: contiguous points around the maximum still above half the detection threshold
    lo_i, hi_i = best_idx, best_idx
    while lo_i > 0 and subtracted_currents[lo_i - 1] > thr / 2:
        lo_i -= 1
    while hi_i < len(subtracted_currents) - 1 and subtracted_currents[hi_i + 1] > thr / 2:
        hi_i += 1
    for i in range(1, len(subtracted_currents) - 1):
        if lo_i - 1 <= i <= hi_i + 1:
            continue
        if subtracted_currents[i] > thr and subtracted_currents[i] >= subtracted_currents[i - 1] and subtracted_currents[i] > subtracted_currents[i + 1]:
            secondary += 1
    uncertainty = estimate_uncertainty(c_as_ug_l, noise_sigma, slope, cal_rel_sd)

    if c_as_ug_l > CAL_MAX_UG_L:
        qc_flags.append("ABOVE_CALIBRATION_RANGE")
        qc_messages.append(f"Calculated concentration ({c_as_ug_l:.1f} µg/L) exceeds validated range ({CAL_MAX_UG_L:.0f} µg/L); dilution advised.")

    faults = [f for f in qc_flags if f in QC_FAULT_FLAGS]
    is_valid = not faults
    qc_status = "PASS"
    if qc_flags:
        qc_status = "REJECTED" if faults else "WARNING"

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
        baseline_slope_ua_per_mv=round(b_slope, 7),
        noise_sigma_ua=round(noise_sigma, 6),
        secondary_peaks=secondary,
        uncertainty_ug_l=uncertainty,
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
        sweep_reversed=sweep_reversed,
        qc_flags=list(qc_flags),
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
