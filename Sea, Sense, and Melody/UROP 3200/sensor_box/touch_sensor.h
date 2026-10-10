/*
 * touch_sensor.h - TTP223 capacitive touch sensor module
 *
 * Reads the sensor through a dedicated polling thread running at 1 kHz.
 * Touch detection uses a simple edge detector with a retrigger lockout,
 * which is more reliable than the debounce state machine used previously:
 * that state machine required multiple samples within a confirmation
 * window, but the main loop only called it once per second, so the
 * window could never be satisfied and the count never advanced.
 *
 * The effective level is configurable through TOUCH_ACTIVE in the
 * implementation file. Inspect the line with "pinctrl get 5" while
 * touching the pad to determine the correct value.
 *
 * IMPORTANT: this module reuses the gpiod chip handle owned by the
 * 7-segment display driver and must NOT open its own.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef TOUCH_SENSOR_H
#define TOUCH_SENSOR_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Initialise the touch sensor.
 *
 * Requests GPIO5 through the shared chip handle and starts the polling
 * thread. Safe to call before the display driver has initialised, but
 * the thread will not be created in that case.
 */
void touch_sensor_init(void);

/**
 * @brief Compatibility stub for the main loop.
 *
 * The actual polling happens in the dedicated thread, so this function
 * deliberately does nothing. It is retained so that the main loop's
 * structure does not need to special-case the touch module.
 */
void touch_sensor_tick(void);

/**
 * @brief Recompute the touch frequency, pattern, and intent score.
 *
 * Walks the timestamp window and should be called once per second.
 */
void touch_sensor_update_features(void);

/**
 * @brief Stop the polling thread and release the GPIO request.
 *
 * Does not close the shared chip handle.
 */
void touch_sensor_close(void);

/** @name Accessors */
/**@{*/
int   touch_sensor_get_irq(void);
int   touch_sensor_get_count(void);
float touch_sensor_get_freq(void);
const char *touch_sensor_get_pattern(void);
float touch_sensor_get_intent(void);
/**@}*/

#endif /* TOUCH_SENSOR_H */
