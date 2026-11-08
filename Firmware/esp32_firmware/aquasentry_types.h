#pragma once
/* Data structures shared by the sketch's functions. They must live in a header: when building a
 * .ino the Arduino IDE / arduino-cli inserts a prototype for every function just above the first
 * function in the sketch, so a struct defined further down is unknown at that point. */
#include <stdint.h>
#include <stdbool.h>

/* One finished test, queued from the sensor task to the telemetry task and stored in the LittleFS
 * offline buffer. Do not reorder fields: buffered records on flash use this layout. */
typedef struct {
    float arsenic_mg_l;
    float ph;
    float conductivity_us_cm;
    float turbidity_ntu;
    float temperature_c;
    float peak_current_ua;     // net peak after background removal
    float peak_mv;
    uint32_t seq;              // reading number, persisted in flash (used to avoid duplicates)
    uint32_t timestamp_unix;
    uint8_t predicted_class;
    uint8_t qc_result;         // v5.7 (was padding): 0 = not reported (older records), 1 = scans passed, 2 = failed
    uint8_t good_scans;        // v5.7 (was padding): scans that passed their checks and were averaged
    uint8_t qc_reserved;       // v5.7 (was padding): keep 0
    float confidence_pct;
    float entropy;
    bool high_uncertainty;
    int8_t battery_pct;        // 0-100, -1 = no battery monitor
    uint8_t arsenic_species;   // v5.6: 0 unknown, 1 As(III) only (no reagent), 2 total arsenic (reagent dosed)
    uint8_t qc_reserved2;      // v5.7 (was padding): keep 0
    uint16_t cal_tag;          // v5.6: CRC-16 of the calibration id used (0 = factory calibration)
    uint16_t qc_bits;          // v5.7 (was padding): QC_* fault / warning bits, see esp32_firmware.ino
    float cu_peak_ua;          // v5.6: copper stripping peak, NAN if not scanned
} sensor_reading_t;            // 60 bytes; v5.5 records were 52 and are converted on start-up.
                               // v5.7 only used padding bytes, so 5.6 records read back with qc_result 0.

#define RECORD_SIZE_V55 52     /* size of sensor_reading_t in firmware 5.2 - 5.5 */

/* Result of one anodic stripping voltammetry scan. */
typedef struct {
    float net_peak_ua;   // peak height above the fitted background
    float peak_mv;       // where the peak was found
    float snr;           // net peak / background noise
    int points;
    float cu_peak_ua;    // copper peak (v5.6), NAN when the copper check is off
    uint16_t qc;         // v5.7: QC_* bits for this scan (0 = passed every check)
} asv_result_t;

/* Header of /offline.bin: [header][record 0][record 1]...[record N-1]. */
typedef struct {
    uint32_t magic;          // 'AQB1'
    uint16_t record_size;    // sizeof(sensor_reading_t) when the file was made
    uint16_t capacity;
    uint32_t head, tail, count;
} offline_header_t;
