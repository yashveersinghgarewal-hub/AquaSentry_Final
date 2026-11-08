#pragma once
/* Stand-in for ESP-IDF driver/gpio.h. The host build takes the ESP32-C3/S3 path (deep-sleep hold
 * needed) so that both branches of the sketch are type-checked across the host targets. */
typedef int esp_err_t;
typedef enum { GPIO_NUM_NC = -1 } gpio_num_t;
esp_err_t gpio_hold_en(gpio_num_t gpio_num);
esp_err_t gpio_hold_dis(gpio_num_t gpio_num);
#define SOC_GPIO_SUPPORT_HOLD_IO_IN_DSLP 1
void gpio_deep_sleep_hold_en(void);
void gpio_deep_sleep_hold_dis(void);
