"""
AquaNet-V1: Multimodal Deep Feed-Forward Neural Network Classifier for Water Safety.

Architecture & Topology:
    Input Layer:      5 features [Arsenic mg/L, pH, Conductivity µS/cm, Turbidity NTU, Temp °C]
    Hidden Layer 1:   8 neurons (ReLU activation)
    Hidden Layer 2:   6 neurons (ReLU activation)
    Output Layer:     4 classes [Safe, Caution, Unsafe, Hazardous] (Softmax activation)

Total Nodes:    5 + 8 + 6 + 4 = 23 nodes
Total Synapses: 5*8 + 8*6 + 6*4 = 40 + 48 + 24 = 112 fully connected edges

How the weights were made (read this before quoting accuracy):
    V1's weights were NOT learned from data. They were set by hand from the WHO / BIS arsenic
    thresholds (10, 50 and 150 µg/L) - see scripts/train_and_deploy_aquanet_v2.py, which builds
    exactly these values. Only 20 of the 112 weights are non-zero and all of them start at the
    arsenic input, so pH, conductivity, turbidity and temperature cannot change the network's vote.
    Those four readings are handled by the fixed safety rules in forward_pass() below.
    For a model that actually learns all five inputs, see Neural_Network/aquanet_v2.py (AquaNet-V2).
    DISCLAIMER: screening aid only, not certified NABL / ISO-17025 drinking-water validation.
"""

from __future__ import annotations
import math
import time
from typing import Dict, List, Tuple, Any, Optional


# Standardization moments (empirical geochemical feature distribution)
INPUT_MEAN: List[float] = [0.08, 7.5, 600.0, 4.0, 25.0]
INPUT_STD: List[float] = [0.10, 0.7, 300.0, 3.0, 4.0]

# Valid operational domain bounds for geochemical sensors
FEATURE_BOUNDS = {
    "arsenic_mg_l": (0.0, 2.0),
    "ph": (4.5, 10.5),
    "conductivity_us_cm": (50.0, 5000.0),
    "turbidity_ntu": (0.0, 100.0),
    "temperature_c": (5.0, 45.0),
}

# Potability threshold limits based on WHO & BIS 10500 standards
POTABILITY_LIMITS = {
    "ph": (6.5, 8.5),
    "turbidity_ntu": 5.0,
    "conductivity_us_cm": 1500.0,
    "arsenic_who_mg_l": 0.010,
    "arsenic_bis_mg_l": 0.050,
    "arsenic_hazard_mg_l": 0.150,
    "method_lod_mg_l": 0.020,
}

# Hand-constructed threshold weights (encode the 10 / 50 / 150 µg/L arsenic limits exactly)
W1: List[List[float]] = [
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
]
B1: List[float] = [35.0000, -35.0000, 15.0000, -15.0000, -35.0000, 35.0000, 0.0000, 0.0000]

W2: List[List[float]] = [
    [  0.0000,   1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  1.0000,   0.0000,   0.0000,  -1.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   1.0000,   0.0000,   0.0000,  -1.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   1.0000,   0.0000,   0.0000,   0.0000],
]
B2: List[float] = [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000]

W3: List[List[float]] = [
    [ 20.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000, -20.0000,  20.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000, -20.0000,  20.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000,  20.0000],
]
B3: List[float] = [0.0000, 0.0001, 0.0000, 0.0000]

CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]
NODES_COUNT = 23
SYNAPSES_COUNT = 112  # Exact fully-connected count: 40 + 48 + 24 = 112


def relu(x: float) -> float:
    return max(0.0, x)


def calculate_entropy(probs: List[float]) -> float:
    """Calculate normalized Shannon entropy in [0.0, 1.0] across class probabilities."""
    ln4 = math.log(4)
    h = 0.0
    for p in probs:
        if p > 1e-12:
            h -= p * math.log(p)
    return max(0.0, min(1.0, h / ln4))


def softmax(logits: List[float]) -> List[float]:
    max_logit = max(logits)
    exps = [math.exp(val - max_logit) for val in logits]
    total = sum(exps)
    return [e / total for e in exps]


def check_bounds(
    arsenic_mg_l: float, ph: float, cond: float, turb: float, temp: float
) -> Tuple[bool, List[str]]:
    """Verify if raw physical inputs fall within the model's validated training envelope."""
    reasons = []
    oob = False

    # Check for NaN or Infinite values
    for val, name in [
        (arsenic_mg_l, "Arsenic"),
        (ph, "pH"),
        (cond, "Conductivity"),
        (turb, "Turbidity"),
        (temp, "Temperature"),
    ]:
        if math.isnan(val) or math.isinf(val):
            return True, [f"Sensor error: {name} value is non-finite ({val})."]

    if not (FEATURE_BOUNDS["arsenic_mg_l"][0] <= arsenic_mg_l <= FEATURE_BOUNDS["arsenic_mg_l"][1]):
        oob = True
        reasons.append(f"Arsenic ({arsenic_mg_l:.3f} mg/L) outside range {FEATURE_BOUNDS['arsenic_mg_l']}")
    if not (FEATURE_BOUNDS["ph"][0] <= ph <= FEATURE_BOUNDS["ph"][1]):
        oob = True
        reasons.append(f"pH ({ph:.2f}) outside range {FEATURE_BOUNDS['ph']}")
    if not (FEATURE_BOUNDS["conductivity_us_cm"][0] <= cond <= FEATURE_BOUNDS["conductivity_us_cm"][1]):
        oob = True
        reasons.append(f"Conductivity ({cond:.0f} µS/cm) outside range {FEATURE_BOUNDS['conductivity_us_cm']}")
    if not (FEATURE_BOUNDS["turbidity_ntu"][0] <= turb <= FEATURE_BOUNDS["turbidity_ntu"][1]):
        oob = True
        reasons.append(f"Turbidity ({turb:.1f} NTU) outside range {FEATURE_BOUNDS['turbidity_ntu']}")
    if not (FEATURE_BOUNDS["temperature_c"][0] <= temp <= FEATURE_BOUNDS["temperature_c"][1]):
        oob = True
        reasons.append(f"Temperature ({temp:.1f} °C) outside range {FEATURE_BOUNDS['temperature_c']}")
    return oob, reasons


def normalize_inputs(
    arsenic_mg_l: float,
    ph: float = 7.2,
    conductivity_us_cm: float = 400.0,
    turbidity_ntu: float = 2.0,
    temperature_c: float = 24.0,
) -> List[float]:
    """Standardize raw physical inputs using empirical z-score moments."""
    raw = [arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c]
    return [(raw[i] - INPUT_MEAN[i]) / INPUT_STD[i] for i in range(5)]


def forward_pass(
    arsenic_mg_l: float,
    ph: float = 7.2,
    conductivity_us_cm: float = 400.0,
    turbidity_ntu: float = 2.0,
    temperature_c: float = 24.0,
) -> Dict[str, Any]:
    """
    Execute forward inference through the 5-8-6-4 AquaNet neural network with safety guardrails.
    """
    t_start = time.perf_counter()

    is_oob, reasons = check_bounds(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c)

    x = normalize_inputs(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c)

    # Hidden Layer 1 (8 neurons)
    h1 = [relu(sum(w * val for w, val in zip(W1[i], x)) + B1[i]) for i in range(8)]

    # Hidden Layer 2 (6 neurons)
    h2 = [relu(sum(w * val for w, val in zip(W2[i], h1)) + B2[i]) for i in range(6)]

    # Output Layer (4 logits + Softmax)
    logits = [sum(w * val for w, val in zip(W3[i], h2)) + B3[i] for i in range(4)]
    probs = softmax(logits)

    best_idx = max(range(4), key=lambda i: probs[i])
    raw_predicted_class = CLASSES[best_idx]
    confidence_pct = round(probs[best_idx] * 100, 1)

    predicted_class = raw_predicted_class
    override_applied = False
    override_reason = "NOMINAL"

    # 1. Out-of-bounds safety gate: Never declare Safe or Caution when inputs violate physical domain
    if is_oob:
        if predicted_class in ("Safe", "Caution"):
            predicted_class = "Unsafe"
            override_applied = True
            override_reason = "SAFETY_OVERRIDE_OUT_OF_BOUNDS"
        reasons.append("Out-of-bounds safety gate: physical parameters outside validated envelope. Safe status revoked.")

    # 2. Arsenic statutory precedence
    if arsenic_mg_l > POTABILITY_LIMITS["arsenic_hazard_mg_l"]:
        if predicted_class != "Hazardous":
            predicted_class = "Hazardous"
            override_applied = True
            override_reason = "SAFETY_OVERRIDE_ARSENIC_ACUTE_HAZARD"
        reasons.append(f"Precedence rule: measured arsenic > {POTABILITY_LIMITS['arsenic_hazard_mg_l']} mg/L exceeds acute hazard threshold.")
    elif arsenic_mg_l >= POTABILITY_LIMITS["arsenic_bis_mg_l"]:
        if predicted_class in ("Safe", "Caution"):
            predicted_class = "Unsafe"
            override_applied = True
            override_reason = "SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS"
        reasons.append(f"Precedence rule: measured arsenic >= {POTABILITY_LIMITS['arsenic_bis_mg_l']} mg/L (BIS 10500 limit). Downgrade prohibited.")
    elif arsenic_mg_l < POTABILITY_LIMITS["method_lod_mg_l"] and predicted_class == "Safe":
        reasons.append(f"Method limit notice: measured arsenic < {POTABILITY_LIMITS['method_lod_mg_l']} mg/L is below method LOD.")

    # 3. Multi-parameter drinking water quality assessment (WHO / BIS 10500)
    if not is_oob:
        # Severe pH anomaly (outside 6.0 - 9.0)
        if ph < 6.0 or ph > 9.0:
            if predicted_class in ("Safe", "Caution"):
                predicted_class = "Unsafe"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_SEVERE_PH_VIOLATION"
            reasons.append(f"Drinking water standard: pH ({ph:.2f}) severely violates potability range (6.5 - 8.5).")
        elif ph < POTABILITY_LIMITS["ph"][0] or ph > POTABILITY_LIMITS["ph"][1]:
            if predicted_class == "Safe":
                predicted_class = "Caution"
                override_applied = True
                override_reason = "POTABILITY_ADVISORY_PH_EXCEEDANCE"
            reasons.append(f"Drinking water standard: pH ({ph:.2f}) slightly outside desirable range (6.5 - 8.5).")

        # High turbidity (> 5.0 NTU BIS permissible, > 10.0 NTU Unsafe)
        if turbidity_ntu > 10.0:
            if predicted_class in ("Safe", "Caution"):
                predicted_class = "Unsafe"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_HIGH_TURBIDITY"
            reasons.append(f"Drinking water standard: Turbidity ({turbidity_ntu:.1f} NTU) indicates severe suspended solids (> 10.0 NTU).")
        elif turbidity_ntu > POTABILITY_LIMITS["turbidity_ntu"]:
            if predicted_class == "Safe":
                predicted_class = "Caution"
                override_applied = True
                override_reason = "POTABILITY_ADVISORY_TURBIDITY"
            reasons.append(f"Drinking water standard: Turbidity ({turbidity_ntu:.1f} NTU) exceeds BIS permissible limit ({POTABILITY_LIMITS['turbidity_ntu']:.1f} NTU).")

        # High conductivity / TDS (> 2000 µS/cm)
        if conductivity_us_cm > 2000.0:
            if predicted_class in ("Safe", "Caution"):
                predicted_class = "Unsafe"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_HIGH_SALINITY"
            reasons.append(f"Drinking water standard: Conductivity ({conductivity_us_cm:.0f} µS/cm) exceeds permissible salinity limit.")
        elif conductivity_us_cm > POTABILITY_LIMITS["conductivity_us_cm"]:
            if predicted_class == "Safe":
                predicted_class = "Caution"
                override_applied = True
                override_reason = "POTABILITY_ADVISORY_CONDUCTIVITY"
            reasons.append(f"Drinking water standard: Conductivity ({conductivity_us_cm:.0f} µS/cm) exceeds desirable TDS limit ({POTABILITY_LIMITS['conductivity_us_cm']:.0f} µS/cm).")

    entropy = calculate_entropy(probs)
    high_uncertainty = entropy > 0.65
    dirichlet_confidence = max(0.0, 1.0 - entropy)

    if high_uncertainty and not override_applied and predicted_class == "Safe":
        predicted_class = "Caution"
        override_applied = True
        override_reason = "ADVISORY_HIGH_UNCERTAINTY"
        reasons.append("Model uncertainty notice: High Shannon entropy (> 0.65) indicates ambiguous classification boundary.")

    t_elapsed = (time.perf_counter() - t_start) * 1000.0
    latency_ms = max(0.02, round(t_elapsed, 3))

    return {
        "predicted_class": predicted_class,
        "raw_model_class": raw_predicted_class,
        "confidence_pct": confidence_pct,
        "model_version": "AquaNet-V1",
        "dataset_provenance": "Hand-constructed from WHO/BIS arsenic thresholds (not trained on data)",
        "nodes_count": NODES_COUNT,
        "synapses_count": SYNAPSES_COUNT,
        "is_out_of_bounds": is_oob,
        "entropy": round(entropy, 4),
        "uncertainty_index": round(entropy, 4),
        "dirichlet_confidence": round(dirichlet_confidence, 4),
        "high_uncertainty": high_uncertainty,
        "latency_ms": latency_ms,
        "reason_codes": reasons,
        "override_applied": override_applied,
        "override_reason": override_reason,
        "probabilities": {CLASSES[i]: round(probs[i] * 100, 2) for i in range(4)},
        "activations": {
            "input": [round(val, 3) for val in x],
            "hidden_1": [round(val, 3) for val in h1],
            "hidden_2": [round(val, 3) for val in h2],
            "output_logits": [round(val, 3) for val in logits],
        },
        "disclaimer": (
            "Model classification models hydrogeochemical covariance based on synthetic training data. "
            "It is a screening aid, not a certified laboratory potability certificate."
        ),
    }


GEOCHEMICAL_DOMAIN = FEATURE_BOUNDS


class AquaNetV1:
    """Object-oriented interface to the AquaNet-V1 neural model."""

    def __init__(self):
        self.nodes_count = NODES_COUNT
        self.synapses_count = SYNAPSES_COUNT

    def forward(
        self,
        arsenic_mg_l: float,
        ph: float = 7.2,
        conductivity: float = 400.0,
        turbidity: float = 2.0,
        temperature: float = 24.0,
    ) -> Dict[str, Any]:
        res = forward_pass(
            arsenic_mg_l=arsenic_mg_l,
            ph=ph,
            conductivity_us_cm=conductivity,
            turbidity_ntu=turbidity,
            temperature_c=temperature,
        )
        probs_normalized = {k: v / 100.0 for k, v in res["probabilities"].items()}
        override_applied = res["override_applied"]
        reason_code = res["override_reason"]
        analytical_status = "below_detection_limit" if arsenic_mg_l < POTABILITY_LIMITS["method_lod_mg_l"] else "within_calibrated_range"
        return {
            "predicted_class": res["predicted_class"],
            "raw_class": res["raw_model_class"],
            "raw_model_class": res["raw_model_class"],
            "confidence_pct": res["confidence_pct"],
            "probabilities": probs_normalized,
            "probabilities_pct": res["probabilities"],
            "override_applied": override_applied,
            "reason_code": reason_code,
            "reason_codes": res["reason_codes"],
            "analytical_status": analytical_status,
            "is_out_of_bounds": res["is_out_of_bounds"],
            "entropy": res["entropy"],
            "uncertainty_index": res["uncertainty_index"],
            "dirichlet_confidence": res["dirichlet_confidence"],
            "high_uncertainty": res["high_uncertainty"],
            "latency_ms": res["latency_ms"],
            "nodes_count": res["nodes_count"],
            "synapses_count": res["synapses_count"],
            "activations": res["activations"],
            "disclaimer": res["disclaimer"],
        }

    def predict_int8(
        self,
        arsenic_mg_l: float,
        ph: float = 7.2,
        conductivity: float = 400.0,
        turbidity: float = 2.0,
        temperature: float = 24.0,
    ) -> Dict[str, Any]:
        """Quantized INT8 fixed-point forward inference matching aquanet_predict_int8 in C99."""
        t_start = time.perf_counter()
        is_oob, reasons = check_bounds(arsenic_mg_l, ph, conductivity, turbidity, temperature)

        SCALE = 1024
        raw = [arsenic_mg_l, ph, conductivity, turbidity, temperature]
        x_q = [round(((raw[i] - INPUT_MEAN[i]) / INPUT_STD[i]) * SCALE) for i in range(5)]

        # Layer 1: INT8 weights, INT16 biases
        h1_q = [max(0, sum(int(round(w)) * val for w, val in zip(W1[i], x_q)) + int(round(B1[i])) * SCALE) for i in range(8)]
        # Layer 2: INT8 weights, INT16 biases
        h2_q = [max(0, sum(int(round(w)) * val for w, val in zip(W2[i], h1_q)) + int(round(B2[i])) * SCALE) for i in range(6)]
        # Layer 3: INT8 weights, INT16 biases -> convert to float logits
        logits = [(sum(int(round(w)) * val for w, val in zip(W3[i], h2_q)) + int(round(B3[i])) * SCALE) / float(SCALE) for i in range(4)]

        probs = softmax(logits)
        best_idx = max(range(4), key=lambda i: probs[i])
        raw_predicted_class = CLASSES[best_idx]
        confidence_pct = round(probs[best_idx] * 100, 1)

        predicted_class = raw_predicted_class
        override_applied = False
        override_reason = "NOMINAL_INT8"

        entropy = calculate_entropy(probs)
        high_uncertainty = entropy > 0.65
        dirichlet_confidence = max(0.0, 1.0 - entropy)

        if is_oob:
            if predicted_class in ("Safe", "Caution"):
                predicted_class = "Unsafe"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_OUT_OF_BOUNDS"
        elif arsenic_mg_l > POTABILITY_LIMITS["arsenic_hazard_mg_l"]:
            if predicted_class != "Hazardous":
                predicted_class = "Hazardous"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_ARSENIC_ACUTE_HAZARD"
        elif arsenic_mg_l >= POTABILITY_LIMITS["arsenic_bis_mg_l"]:
            if predicted_class in ("Safe", "Caution"):
                predicted_class = "Unsafe"
                override_applied = True
                override_reason = "SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS"

        if not is_oob:
            if ph < 6.0 or ph > 9.0:
                if predicted_class in ("Safe", "Caution"):
                    predicted_class = "Unsafe"
                    override_applied = True
                    override_reason = "SAFETY_OVERRIDE_SEVERE_PH_VIOLATION"
            elif ph < POTABILITY_LIMITS["ph"][0] or ph > POTABILITY_LIMITS["ph"][1]:
                if predicted_class == "Safe":
                    predicted_class = "Caution"
                    override_applied = True
                    override_reason = "POTABILITY_ADVISORY_PH_EXCEEDANCE"

            if turbidity > 10.0:
                if predicted_class in ("Safe", "Caution"):
                    predicted_class = "Unsafe"
                    override_applied = True
                    override_reason = "SAFETY_OVERRIDE_HIGH_TURBIDITY"
            elif turbidity > POTABILITY_LIMITS["turbidity_ntu"]:
                if predicted_class == "Safe":
                    predicted_class = "Caution"
                    override_applied = True
                    override_reason = "POTABILITY_ADVISORY_TURBIDITY"

            if conductivity > 2000.0:
                if predicted_class in ("Safe", "Caution"):
                    predicted_class = "Unsafe"
                    override_applied = True
                    override_reason = "SAFETY_OVERRIDE_HIGH_SALINITY"
            elif conductivity > POTABILITY_LIMITS["conductivity_us_cm"]:
                if predicted_class == "Safe":
                    predicted_class = "Caution"
                    override_applied = True
                    override_reason = "POTABILITY_ADVISORY_CONDUCTIVITY"

        if high_uncertainty and not override_applied and predicted_class == "Safe":
            predicted_class = "Caution"
            override_applied = True
            override_reason = "ADVISORY_HIGH_UNCERTAINTY"

        latency_ms = max(0.01, round((time.perf_counter() - t_start) * 1000.0, 3))

        return {
            "predicted_class": predicted_class,
            "raw_class": raw_predicted_class,
            "raw_model_class": raw_predicted_class,
            "confidence_pct": confidence_pct,
            "probabilities": {CLASSES[i]: probs[i] for i in range(4)},
            "probabilities_pct": {CLASSES[i]: round(probs[i] * 100, 2) for i in range(4)},
            "entropy": round(entropy, 4),
            "uncertainty_index": round(entropy, 4),
            "dirichlet_confidence": round(dirichlet_confidence, 4),
            "high_uncertainty": high_uncertainty,
            "override_applied": override_applied,
            "reason_code": override_reason,
            "is_out_of_bounds": is_oob,
            "latency_ms": latency_ms,
            "quantization": "INT8_fixed_point_Q10",
        }

    def check_bounds(
        self, arsenic_mg_l: float, ph: float, cond: float, turb: float, temp: float
    ) -> bool:
        oob, _ = check_bounds(arsenic_mg_l, ph, cond, turb, temp)
        return not oob

    def get_model_metadata(self) -> Dict[str, Any]:
        return {
            "name": "AquaNet-V1",
            "layers": [5, 8, 6, 4],
            "nodes_count": NODES_COUNT,
            "synapses_count": SYNAPSES_COUNT,
            "benchmark_accuracy": "Not trained: exact by construction on arsenic thresholds (Synthetic rule check)",
        }
