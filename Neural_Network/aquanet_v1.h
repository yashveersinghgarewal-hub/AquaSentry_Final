/**
 * AquaNet-V1: Multimodal Deep Feed-Forward Neural Network Classifier for Water Safety.
 * Topology: 5 Inputs -> 8 Hidden (ReLU) -> 6 Hidden (ReLU) -> 4 Outputs (Softmax)
 * Total Nodes: 23 | Total Synapses: 112 | Memory Footprint: < 1 KB Flash/RAM
 *
 * Microcontroller & Embedded Targets: ESP32, STM32, Arduino (RP2040, SAMD21), Bare Metal C99.
 * Includes Float32 and INT8 Quantized Fixed-Point Forward Engines.
 */

#ifndef AQUANET_V1_H
#define AQUANET_V1_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define AQUANET_INPUT_FEATURES  5
#define AQUANET_HIDDEN_1_NODES  8
#define AQUANET_HIDDEN_2_NODES  6
#define AQUANET_OUTPUT_CLASSES  4
#define AQUANET_TOTAL_NODES     23
#define AQUANET_TOTAL_SYNAPSES  112

typedef enum {
    AQUANET_CLASS_SAFE = 0,
    AQUANET_CLASS_CAUTION = 1,
    AQUANET_CLASS_UNSAFE = 2,
    AQUANET_CLASS_HAZARDOUS = 3
} aquanet_class_t;

typedef struct {
    aquanet_class_t predicted_class;     // Final safety classification
    aquanet_class_t raw_model_class;     // Raw un-overridden neural prediction
    float confidence_pct;                // Prediction confidence (0.0 - 100.0%)
    float probabilities[4];              // Softmax class probabilities [Safe, Caution, Unsafe, Hazardous]
    float entropy;                       // Normalized Shannon entropy H in [0.0, 1.0]
    bool high_uncertainty;               // True if entropy > 0.65 (Out-of-Distribution or ambiguous)
    bool is_out_of_bounds;               // True if sensor inputs exceed physical operational limits
    bool override_applied;               // True if safety guardrails or potability rules intervened
    const char *reason_code;             // Machine-readable diagnostic code
    const char *predicted_class_name;    // "Safe", "Caution", "Unsafe", or "Hazardous"
} aquanet_result_t;

/**
 * Execute forward pass through AquaNet-V1 with deterministic safety guardrails (Float32).
 */
aquanet_result_t aquanet_predict(
    float arsenic_mg_l,
    float ph,
    float conductivity_us_cm,
    float turbidity_ntu,
    float temperature_c
);

/**
 * Fixed-point INT8 forward pass for integer-only microcontrollers.
 * Weight parameters stored as int8_t (112 bytes flash), accumulators in int32_t.
 */
aquanet_result_t aquanet_predict_int8(
    float arsenic_mg_l,
    float ph,
    float conductivity_us_cm,
    float turbidity_ntu,
    float temperature_c
);

/**
 * Compute normalized Shannon entropy H in [0.0, 1.0] across class probabilities.
 */
float aquanet_calculate_entropy(const float probabilities[4]);

/**
 * Standard addition slope and concentration matrix solver.
 * @param ip_sample  Measured peak current of unspiked sample (uA)
 * @param ip_spiked  Measured peak current after standard spike (uA)
 * @param c_spike    Known standard spike concentration added (mg/L)
 * @return float     Calculated original sample concentration (mg/L), or -1.0 on invalid
 */
float aquanet_standard_addition(float ip_sample, float ip_spiked, float c_spike);

/**
 * Check if physical inputs are within validated operational sensor bounds.
 */
bool aquanet_check_bounds(
    float arsenic_mg_l,
    float ph,
    float cond,
    float turb,
    float temp
);

#ifdef __cplusplus
}
#endif

#endif /* AQUANET_V1_H */
