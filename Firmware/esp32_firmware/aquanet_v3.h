/**
 * AquaNet-V3 (5-16-12-4) - trained water-safety classifier for ESP32 / any C99 microcontroller.
 * GENERATED from aquanet_v3_amd2015_balanced.json by scripts/gen_c_v3.py - do not edit by hand.
 *
 * - float32 only (the ESP32 has a hardware FPU), weights in flash, no malloc, only <math.h>
 * - 352 parameters = 1408 bytes of flash; RAM use < 200 bytes on the stack
 * - Inputs: arsenic (mg/L), pH, conductivity (uS/cm), turbidity (NTU), temperature (C)
 * - Same safety rules as the server: a rule can only make the verdict stricter.
 */
#ifndef AQUANET_V3_H
#define AQUANET_V3_H
#ifdef __cplusplus
extern "C" {
#endif

#include "aquanet_v1.h"   /* reuses aquanet_class_t and aquanet_result_t */

#define AQUANET_V3_ARCH "5-16-12-4"
#define AQUANET_V3_PARAMS 352

aquanet_result_t aquanet_v3_predict(float arsenic_mg_l, float ph, float conductivity_us_cm,
                                    float turbidity_ntu, float temperature_c);

#ifdef __cplusplus
}
#endif
#endif
