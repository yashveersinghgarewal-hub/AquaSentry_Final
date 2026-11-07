/**
 * AquaNet-V1: Multimodal Deep Feed-Forward Neural Network Classifier for Water Safety.
 * C99 Reference Implementation for Microcontrollers & Edge Compute.
 * Includes Float32 and INT8 Quantized Fixed-Point Forward Engines.
 */

#include "aquanet_v1.h"
#include <math.h>
#include <string.h>

/* Normalization Moments (Mean and Std) */
static const float INPUT_MEAN[5] = {0.08f, 7.5f, 600.0f, 4.0f, 25.0f};
static const float INPUT_STD[5]  = {0.10f, 0.7f, 300.0f, 3.0f, 4.0f};

/* Operational Sensor Bounds */
static const float BOUND_AS_MIN   = 0.0f;
static const float BOUND_AS_MAX   = 2.0f;
static const float BOUND_PH_MIN   = 4.5f;
static const float BOUND_PH_MAX   = 10.5f;
static const float BOUND_EC_MIN   = 50.0f;
static const float BOUND_EC_MAX   = 5000.0f;
static const float BOUND_TURB_MIN = 0.0f;
static const float BOUND_TURB_MAX = 100.0f;
static const float BOUND_TEMP_MIN = 5.0f;
static const float BOUND_TEMP_MAX = 45.0f;

/* Drinking Water Potability Guidelines (WHO & BIS 10500) */
static const float POTABLE_PH_MIN     = 6.5f;
static const float POTABLE_PH_MAX     = 8.5f;
static const float POTABLE_TURB_MAX   = 5.0f;
static const float POTABLE_EC_MAX     = 1500.0f;
static const float POTABLE_AS_BIS     = 0.050f;
static const float POTABLE_AS_HAZARD  = 0.150f;

/* Pre-trained Synapse Weights (Float32) */
static const float W1[8][5] = {
    { 50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {-50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    { 50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {-50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    { 50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {-50.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f}
};
static const float B1[8] = {35.0000f, -35.0000f, 15.0000f, -15.0000f, -35.0000f, 35.0000f, 0.0000f, 0.0000f};

static const float W2[6][8] = {
    {  0.0000f,   1.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  1.0000f,   0.0000f,   0.0000f,  -1.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  1.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   1.0000f,   0.0000f,   0.0000f,  -1.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   1.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   0.0000f,   0.0000f,   1.0000f,   0.0000f,   0.0000f,   0.0000f}
};
static const float B2[6] = {0.0000f, 0.0000f, 0.0000f, 0.0000f, 0.0000f, 0.0000f};

static const float W3[4][6] = {
    { 20.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f, -20.0000f,  20.0000f,   0.0000f,   0.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   0.0000f, -20.0000f,  20.0000f,   0.0000f},
    {  0.0000f,   0.0000f,   0.0000f,   0.0000f,   0.0000f,  20.0000f}
};
static const float B3[4] = {0.0000f, 0.0001f, 0.0000f, 0.0000f};

/* Pre-trained Quantized Weights (INT8 = 112 bytes flash, INT16 = 36 bytes flash) */
static const int8_t W1_INT8[8][5] = {
    { 50,   0,   0,   0,   0},
    {-50,   0,   0,   0,   0},
    { 50,   0,   0,   0,   0},
    {-50,   0,   0,   0,   0},
    { 50,   0,   0,   0,   0},
    {-50,   0,   0,   0,   0},
    {  0,   0,   0,   0,   0},
    {  0,   0,   0,   0,   0}
};
static const int16_t B1_INT16[8] = {35, -35, 15, -15, -35, 35, 0, 0};

static const int8_t W2_INT8[6][8] = {
    { 0,  1,  0,  0,  0,  0,  0,  0},
    { 1,  0,  0, -1,  0,  0,  0,  0},
    { 1,  0,  0,  0,  0,  0,  0,  0},
    { 0,  0,  1,  0,  0, -1,  0,  0},
    { 0,  0,  1,  0,  0,  0,  0,  0},
    { 0,  0,  0,  0,  1,  0,  0,  0}
};
static const int16_t B2_INT16[6] = {0, 0, 0, 0, 0, 0};

static const int8_t W3_INT8[4][6] = {
    { 20,   0,   0,   0,   0,   0},
    {  0, -20,  20,   0,   0,   0},
    {  0,   0,   0, -20,  20,   0},
    {  0,   0,   0,   0,   0,  20}
};
static const int16_t B3_INT16[4] = {0, 0, 0, 0};

static const char *CLASS_NAMES[4] = {"Safe", "Caution", "Unsafe", "Hazardous"};

static inline float relu_f(float x) {
    return (x > 0.0f) ? x : 0.0f;
}

static inline int32_t relu_i32(int32_t x) {
    return (x > 0) ? x : 0;
}

bool aquanet_check_bounds(float arsenic, float ph, float cond, float turb, float temp) {
    if (isnan(arsenic) || isinf(arsenic) ||
        isnan(ph) || isinf(ph) ||
        isnan(cond) || isinf(cond) ||
        isnan(turb) || isinf(turb) ||
        isnan(temp) || isinf(temp)) {
        return false;
    }
    if (arsenic < BOUND_AS_MIN || arsenic > BOUND_AS_MAX) return false;
    if (ph < BOUND_PH_MIN || ph > BOUND_PH_MAX) return false;
    if (cond < BOUND_EC_MIN || cond > BOUND_EC_MAX) return false;
    if (turb < BOUND_TURB_MIN || turb > BOUND_TURB_MAX) return false;
    if (temp < BOUND_TEMP_MIN || temp > BOUND_TEMP_MAX) return false;
    return true;
}

float aquanet_calculate_entropy(const float probabilities[4]) {
    float h = 0.0f;
    const float ln4 = 1.3862943611198906f; // ln(4)
    for (int i = 0; i < 4; i++) {
        float p = probabilities[i];
        if (p > 1e-7f) {
            h -= p * logf(p);
        }
    }
    float norm_h = h / ln4;
    if (norm_h < 0.0f) norm_h = 0.0f;
    if (norm_h > 1.0f) norm_h = 1.0f;
    return norm_h;
}

float aquanet_standard_addition(float ip_sample, float ip_spiked, float c_spike) {
    float delta_i = ip_spiked - ip_sample;
    if (delta_i <= 1e-6f || c_spike <= 0.0f || ip_sample <= 0.0f) {
        return -1.0f; // Invalid calibration or negative slope
    }
    float slope = delta_i / c_spike;
    return ip_sample / slope;
}

static void apply_safety_guardrails(
    aquanet_result_t *result,
    float arsenic_mg_l,
    float ph,
    float conductivity_us_cm,
    float turbidity_ntu
) {
    /* 1. Out of bounds -> never allow Safe/Caution */
    if (result->is_out_of_bounds) {
        if (result->predicted_class == AQUANET_CLASS_SAFE || result->predicted_class == AQUANET_CLASS_CAUTION) {
            result->predicted_class = AQUANET_CLASS_UNSAFE;
            result->override_applied = true;
            result->reason_code = "SAFETY_OVERRIDE_OUT_OF_BOUNDS";
        }
    }

    /* 2. Statutory Arsenic limits (BIS 10500 50 ug/L, Acute Hazard 150 ug/L) */
    if (arsenic_mg_l > POTABLE_AS_HAZARD) {
        if (result->predicted_class != AQUANET_CLASS_HAZARDOUS) {
            result->predicted_class = AQUANET_CLASS_HAZARDOUS;
            result->override_applied = true;
            result->reason_code = "SAFETY_OVERRIDE_ARSENIC_ACUTE_HAZARD";
        }
    } else if (arsenic_mg_l >= POTABLE_AS_BIS) {
        if (result->predicted_class == AQUANET_CLASS_SAFE || result->predicted_class == AQUANET_CLASS_CAUTION) {
            result->predicted_class = AQUANET_CLASS_UNSAFE;
            result->override_applied = true;
            result->reason_code = "SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS";
        }
    }

    /* 3. Multi-parameter Potability Assessment (WHO/BIS) */
    if (!result->is_out_of_bounds) {
        if (ph < 6.0f || ph > 9.0f) {
            if (result->predicted_class == AQUANET_CLASS_SAFE || result->predicted_class == AQUANET_CLASS_CAUTION) {
                result->predicted_class = AQUANET_CLASS_UNSAFE;
                result->override_applied = true;
                result->reason_code = "SAFETY_OVERRIDE_SEVERE_PH_VIOLATION";
            }
        } else if (ph < POTABLE_PH_MIN || ph > POTABLE_PH_MAX) {
            if (result->predicted_class == AQUANET_CLASS_SAFE) {
                result->predicted_class = AQUANET_CLASS_CAUTION;
                result->override_applied = true;
                result->reason_code = "POTABILITY_ADVISORY_PH_EXCEEDANCE";
            }
        }

        if (turbidity_ntu > 10.0f) {
            if (result->predicted_class == AQUANET_CLASS_SAFE || result->predicted_class == AQUANET_CLASS_CAUTION) {
                result->predicted_class = AQUANET_CLASS_UNSAFE;
                result->override_applied = true;
                result->reason_code = "SAFETY_OVERRIDE_HIGH_TURBIDITY";
            }
        } else if (turbidity_ntu > POTABLE_TURB_MAX) {
            if (result->predicted_class == AQUANET_CLASS_SAFE) {
                result->predicted_class = AQUANET_CLASS_CAUTION;
                result->override_applied = true;
                result->reason_code = "POTABILITY_ADVISORY_TURBIDITY";
            }
        }

        if (conductivity_us_cm > 2000.0f) {
            if (result->predicted_class == AQUANET_CLASS_SAFE || result->predicted_class == AQUANET_CLASS_CAUTION) {
                result->predicted_class = AQUANET_CLASS_UNSAFE;
                result->override_applied = true;
                result->reason_code = "SAFETY_OVERRIDE_HIGH_SALINITY";
            }
        } else if (conductivity_us_cm > POTABLE_EC_MAX) {
            if (result->predicted_class == AQUANET_CLASS_SAFE) {
                result->predicted_class = AQUANET_CLASS_CAUTION;
                result->override_applied = true;
                result->reason_code = "POTABILITY_ADVISORY_CONDUCTIVITY";
            }
        }
    }

    /* 4. High Uncertainty Advisory */
    if (result->high_uncertainty && !result->override_applied && result->predicted_class == AQUANET_CLASS_SAFE) {
        result->predicted_class = AQUANET_CLASS_CAUTION;
        result->override_applied = true;
        result->reason_code = "ADVISORY_HIGH_UNCERTAINTY";
    }

    result->predicted_class_name = CLASS_NAMES[result->predicted_class];
}

aquanet_result_t aquanet_predict(
    float arsenic_mg_l,
    float ph,
    float conductivity_us_cm,
    float turbidity_ntu,
    float temperature_c
) {
    aquanet_result_t result;
    memset(&result, 0, sizeof(result));

    /* 1. Check physical bounds */
    result.is_out_of_bounds = !aquanet_check_bounds(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c);

    /* 2. Standardize inputs */
    float x[5];
    x[0] = (arsenic_mg_l - INPUT_MEAN[0]) / INPUT_STD[0];
    x[1] = (ph - INPUT_MEAN[1]) / INPUT_STD[1];
    x[2] = (conductivity_us_cm - INPUT_MEAN[2]) / INPUT_STD[2];
    x[3] = (turbidity_ntu - INPUT_MEAN[3]) / INPUT_STD[3];
    x[4] = (temperature_c - INPUT_MEAN[4]) / INPUT_STD[4];

    /* 3. Layer 1 (5 -> 8 ReLU) */
    float h1[8];
    for (int i = 0; i < 8; i++) {
        float sum = B1[i];
        for (int j = 0; j < 5; j++) {
            sum += W1[i][j] * x[j];
        }
        h1[i] = relu_f(sum);
    }

    /* 4. Layer 2 (8 -> 6 ReLU) */
    float h2[6];
    for (int i = 0; i < 6; i++) {
        float sum = B2[i];
        for (int j = 0; j < 8; j++) {
            sum += W2[i][j] * h1[j];
        }
        h2[i] = relu_f(sum);
    }

    /* 5. Layer 3 (6 -> 4 Output Logits) */
    float logits[4];
    for (int i = 0; i < 4; i++) {
        float sum = B3[i];
        for (int j = 0; j < 6; j++) {
            sum += W3[i][j] * h2[j];
        }
        logits[i] = sum;
    }

    /* 6. Softmax Normalization */
    float max_logit = logits[0];
    for (int i = 1; i < 4; i++) {
        if (logits[i] > max_logit) max_logit = logits[i];
    }

    float exps[4];
    float sum_exp = 0.0f;
    for (int i = 0; i < 4; i++) {
        exps[i] = expf(logits[i] - max_logit);
        sum_exp += exps[i];
    }

    int best_idx = 0;
    for (int i = 0; i < 4; i++) {
        result.probabilities[i] = exps[i] / sum_exp;
        if (result.probabilities[i] > result.probabilities[best_idx]) {
            best_idx = i;
        }
    }

    result.raw_model_class = (aquanet_class_t)best_idx;
    result.predicted_class = result.raw_model_class;
    result.confidence_pct = result.probabilities[best_idx] * 100.0f;
    result.entropy = aquanet_calculate_entropy(result.probabilities);
    result.high_uncertainty = (result.entropy > 0.65f);
    result.override_applied = false;
    result.reason_code = "NOMINAL_NEURAL_INFERENCE";

    /* 7. Safety Precedence Guardrails */
    apply_safety_guardrails(&result, arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu);

    return result;
}

aquanet_result_t aquanet_predict_int8(
    float arsenic_mg_l,
    float ph,
    float conductivity_us_cm,
    float turbidity_ntu,
    float temperature_c
) {
    aquanet_result_t result;
    memset(&result, 0, sizeof(result));

    result.is_out_of_bounds = !aquanet_check_bounds(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c);

    /* Quantize input features into fixed-point Q10 (scale = 1024) */
    const int32_t SCALE = 1024;
    int32_t x_q[5];
    x_q[0] = (int32_t)roundf(((arsenic_mg_l - INPUT_MEAN[0]) / INPUT_STD[0]) * (float)SCALE);
    x_q[1] = (int32_t)roundf(((ph - INPUT_MEAN[1]) / INPUT_STD[1]) * (float)SCALE);
    x_q[2] = (int32_t)roundf(((conductivity_us_cm - INPUT_MEAN[2]) / INPUT_STD[2]) * (float)SCALE);
    x_q[3] = (int32_t)roundf(((turbidity_ntu - INPUT_MEAN[3]) / INPUT_STD[3]) * (float)SCALE);
    x_q[4] = (int32_t)roundf(((temperature_c - INPUT_MEAN[4]) / INPUT_STD[4]) * (float)SCALE);

    /* Layer 1: INT8 weights, INT16 biases scaled by SCALE */
    int32_t h1_q[8];
    for (int i = 0; i < 8; i++) {
        int32_t sum = (int32_t)B1_INT16[i] * SCALE;
        for (int j = 0; j < 5; j++) {
            sum += (int32_t)W1_INT8[i][j] * x_q[j];
        }
        h1_q[i] = relu_i32(sum);
    }

    /* Layer 2: INT8 weights, INT16 biases */
    int32_t h2_q[6];
    for (int i = 0; i < 6; i++) {
        int32_t sum = (int32_t)B2_INT16[i] * SCALE;
        for (int j = 0; j < 8; j++) {
            sum += (int32_t)W2_INT8[i][j] * h1_q[j];
        }
        h2_q[i] = relu_i32(sum);
    }

    /* Layer 3: INT8 weights, INT16 biases -> convert to float logits */
    float logits[4];
    for (int i = 0; i < 4; i++) {
        int32_t sum = (int32_t)B3_INT16[i] * SCALE;
        for (int j = 0; j < 6; j++) {
            sum += (int32_t)W3_INT8[i][j] * h2_q[j];
        }
        logits[i] = (float)sum / (float)SCALE;
    }

    /* Softmax Normalization */
    float max_logit = logits[0];
    for (int i = 1; i < 4; i++) {
        if (logits[i] > max_logit) max_logit = logits[i];
    }

    float exps[4];
    float sum_exp = 0.0f;
    for (int i = 0; i < 4; i++) {
        exps[i] = expf(logits[i] - max_logit);
        sum_exp += exps[i];
    }

    int best_idx = 0;
    for (int i = 0; i < 4; i++) {
        result.probabilities[i] = exps[i] / sum_exp;
        if (result.probabilities[i] > result.probabilities[best_idx]) {
            best_idx = i;
        }
    }

    result.raw_model_class = (aquanet_class_t)best_idx;
    result.predicted_class = result.raw_model_class;
    result.confidence_pct = result.probabilities[best_idx] * 100.0f;
    result.entropy = aquanet_calculate_entropy(result.probabilities);
    result.high_uncertainty = (result.entropy > 0.65f);
    result.override_applied = false;
    result.reason_code = "NOMINAL_NEURAL_INFERENCE";

    /* Safety Precedence Guardrails */
    apply_safety_guardrails(&result, arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu);

    return result;
}
