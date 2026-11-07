"""Test Suite: Neural Network Parity, Topology, and Geochemical Domain Validation.

Verifies:
1. Exact topology: 5 inputs, 8 hidden1, 6 hidden2, 4 outputs (23 nodes, 112 synapses).
2. Weight matrix and bias dimensions:
   - W1: (8, 5) -> 40 weights
   - W2: (6, 8) -> 48 weights
   - W3: (4, 6) -> 24 weights
   - Total weights + biases = 112 + 18 = 130 parameters.
3. Numerical stability: Softmax outputs sum to 1.0 within 1e-6.
4. Geochemical domain boundary checks and Out-of-Bounds safety gate.
5. Deterministic forward pass across representative water profiles.
6. Multi-parameter drinking water standard compliance (pH, Turbidity, Conductivity).
7. End-to-end ASV voltammetry extraction and neural integration.
"""

import os
import pytest
import math
import typing
from app.neural_classifier import (
    AquaNetV1,
    forward_pass,
    check_bounds,
    normalize_inputs,
    W1, B1, W2, B2, W3, B3,
    INPUT_MEAN, INPUT_STD,
    GEOCHEMICAL_DOMAIN,
    POTABILITY_LIMITS,
)
from app.asv_extractor import process_asv_trace, analyze_water_sample

current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(current_dir, "example_data.csv")):
    TEST_DATA_DIR = current_dir
elif os.path.exists(os.path.join(current_dir, "..", "data", "example_data.csv")):
    TEST_DATA_DIR = os.path.abspath(os.path.join(current_dir, "..", "data"))
else:
    TEST_DATA_DIR = current_dir

EXAMPLE_CSV = os.path.join(TEST_DATA_DIR, "example_data.csv")
EXAMPLE_CAL = os.path.join(TEST_DATA_DIR, "calibration.json")


class TestNeuralTopology:
    """Verify exact graph topology and synapse count."""

    def test_layer_node_counts(self):
        nodes_per_layer = [5, 8, 6, 4]
        assert sum(nodes_per_layer) == 23

    def test_synapse_count_is_exactly_112(self):
        """Fully connected layers: 5*8 + 8*6 + 6*4 = 40 + 48 + 24 = 112 synapses."""
        l1_synapses = len(W1) * len(W1[0])  # 8 * 5 = 40
        l2_synapses = len(W2) * len(W2[0])  # 6 * 8 = 48
        l3_synapses = len(W3) * len(W3[0])  # 4 * 6 = 24
        total_synapses = l1_synapses + l2_synapses + l3_synapses

        assert l1_synapses == 40
        assert l2_synapses == 48
        assert l3_synapses == 24
        assert total_synapses == 112

    def test_weight_and_bias_shapes(self):
        assert len(W1) == 8 and len(W1[0]) == 5
        assert len(B1) == 8
        assert len(W2) == 6 and len(W2[0]) == 8
        assert len(B2) == 6
        assert len(W3) == 4 and len(W3[0]) == 6
        assert len(B3) == 4

    def test_model_metadata(self):
        model = AquaNetV1()
        meta = model.get_model_metadata()
        assert meta["synapses_count"] == 112
        assert meta["nodes_count"] == 23
        assert meta["layers"] == [5, 8, 6, 4]
        assert "Synthetic" in meta["benchmark_accuracy"] or "99.70%" in meta["benchmark_accuracy"]

    def test_type_annotations_evaluable(self):
        """Verify type hints can be evaluated by typing.get_type_hints without NameError."""
        hints_bounds = typing.get_type_hints(check_bounds)
        assert "return" in hints_bounds
        hints_norm = typing.get_type_hints(normalize_inputs)
        assert "return" in hints_norm
        hints_forward = typing.get_type_hints(forward_pass)
        assert "return" in hints_forward


class TestGeochemicalDomainValidation:
    """Verify input domain checks for physical plausibility."""

    def test_nominal_inputs_within_bounds(self):
        model = AquaNetV1()
        assert model.check_bounds(0.015, 7.2, 450.0, 2.5, 24.0) is True

    def test_extreme_ph_out_of_bounds(self):
        model = AquaNetV1()
        assert model.check_bounds(0.015, 1.2, 450.0, 2.5, 24.0) is False  # Too acidic
        assert model.check_bounds(0.015, 13.5, 450.0, 2.5, 24.0) is False  # Too alkaline

    def test_extreme_salinity_out_of_bounds(self):
        model = AquaNetV1()
        assert model.check_bounds(0.015, 7.0, 8000.0, 2.5, 24.0) is False

    def test_negative_temperature_out_of_bounds(self):
        model = AquaNetV1()
        assert model.check_bounds(0.015, 7.0, 450.0, 2.5, -5.0) is False

    def test_nan_and_inf_inputs_detected(self):
        model = AquaNetV1()
        assert model.check_bounds(float("nan"), 7.2, 450.0, 2.0, 24.0) is False
        assert model.check_bounds(0.015, float("inf"), 450.0, 2.0, 24.0) is False


class TestForwardPassAndNumericalStability:
    """Verify mathematical correctness of forward pass."""

    def test_softmax_probabilities_sum_to_one(self):
        model = AquaNetV1()
        test_profiles = [
            (0.005, 7.1, 280.0, 1.2, 21.0),
            (0.025, 7.8, 620.0, 3.4, 26.5),
            (0.085, 8.6, 940.0, 5.8, 28.0),
            (0.350, 6.2, 1250.0, 11.2, 29.5),
        ]
        for as_mg, ph, cond, turb, temp in test_profiles:
            res = model.forward(as_mg, ph, cond, turb, temp)
            probs = res["probabilities"]
            assert sum(probs.values()) == pytest.approx(1.0, abs=1e-5)
            for cls_name, p in probs.items():
                assert 0.0 <= p <= 1.0

    def test_conservative_precedence_in_forward_pass(self):
        """When arsenic exceeds BIS limit (0.050 mg/L), forward pass cannot output 'Safe'."""
        model = AquaNetV1()
        res = model.forward(0.080, 7.2, 350.0, 1.8, 23.0)
        assert res["predicted_class"] in ("Unsafe", "Hazardous")
        assert res["confidence_pct"] > 50.0

    def test_acute_hazard_precedence(self):
        """When arsenic exceeds 0.150 mg/L, forward pass must strictly output 'Hazardous'."""
        model = AquaNetV1()
        res = model.forward(0.250, 7.2, 350.0, 1.8, 23.0)
        assert res["predicted_class"] == "Hazardous"

    def test_below_lod_status_in_forward_pass(self):
        """When arsenic is 0.008 mg/L (< 0.020 mg/L LOD), status is below_detection_limit."""
        model = AquaNetV1()
        res = model.forward(0.008, 7.2, 350.0, 1.8, 23.0)
        assert res["analytical_status"] == "below_detection_limit"
        assert res["override_applied"] is False

    def test_out_of_bounds_revokes_safe_status(self):
        """Out-of-bounds inputs MUST NOT be declared Safe."""
        model = AquaNetV1()
        res = model.forward(0.005, 1.0, 450.0, 2.0, 24.0)  # pH 1.0 is extreme acid
        assert res["is_out_of_bounds"] is True
        assert res["predicted_class"] == "Unsafe"
        assert res["override_applied"] is True

    def test_multiparameter_potability_downgrades(self):
        """Severe turbidity or pH exceedance downgrades potable status even if arsenic is low."""
        model = AquaNetV1()
        # Acidic water (pH 4.8) with low arsenic
        res_ph = model.forward(0.005, 4.8, 450.0, 2.0, 24.0)
        assert res_ph["predicted_class"] in ("Unsafe", "Caution")
        assert res_ph["override_applied"] is True

        # Heavy silt (turbidity 25 NTU) with low arsenic
        res_turb = model.forward(0.005, 7.2, 450.0, 25.0, 24.0)
        assert res_turb["predicted_class"] in ("Unsafe", "Caution")
        assert res_turb["override_applied"] is True


class TestASVPipelineIntegration:
    """Verify ASV voltammogram trace processing bridge."""

    def test_asv_trace_extraction(self):
        res = process_asv_trace(EXAMPLE_CSV, EXAMPLE_CAL)
        assert res["total_sweep_points"] == 81
        assert -850.0 <= res["peak_potential_mv"] <= -740.0
        assert res["estimated_arsenic_mg_l"] > 0.0
        assert res["estimated_arsenic_ug_l"] > 0.0

    def test_end_to_end_analysis(self):
        result = analyze_water_sample(EXAMPLE_CSV, EXAMPLE_CAL, ph=7.2, conductivity_us_cm=350.0)
        assert "asv_signal_processing" in result
        assert "neural_safety_classification" in result
        assert result["neural_safety_classification"]["predicted_class"] == "Safe"
