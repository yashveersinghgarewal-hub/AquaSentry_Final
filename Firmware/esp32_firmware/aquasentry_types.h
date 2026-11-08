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
    float confidence_pct;
    float entropy;
    bool high_uncertainty;
    int8_t battery_pct;        // 0-100, -1 = no battery monitor (fits in the old padding: same record size)
} sensor_reading_t;

/* Result of one anodic stripping voltammetry scan. */
typedef struct {
    float net_peak_ua;   // peak height above the fitted background
    float peak_mv;       // where the peak was found
    float snr;           // net peak / background noise
    int points;
} asv_result_t;

/* Header of /offline.bin: [header][record 0][record 1]...[record N-1]. */
typedef struct {
    uint32_t magic;          // 'AQB1'
    uint16_t record_size;    // sizeof(sensor_reading_t) when the file was made
    uint16_t capacity;
    uint32_t head, tail, count;
} offline_header_t;
