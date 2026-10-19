/**
 * @file touch_sensor.h
 * @brief TTP223 capacitive touch sensor module.
 *
 * Reads the sensor through a dedicated polling thread running at 1 kHz.
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
 * 7‑segment display driver and must NOT open its own.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

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
 *
 * @param None.
 * @return void.
 */
void touch_sensor_init(void);

/**
 * @brief Compatibility stub for the main loop.
 *
 * The actual polling happens in the dedicated thread, so this function
 * deliberately does nothing. It is retained so that the main loop's
 * structure does not need to special-case the touch module.
 *
 * @param None.
 * @return void.
 */
void touch_sensor_tick(void);

/**
 * @brief Recompute the touch frequency, pattern, and intent score.
 *
 * Walks the timestamp window and should be called once per second.
 *
 * @param None.
 * @return void.
 */
void touch_sensor_update_features(void);

/**
 * @brief Stop the polling thread and release the GPIO request.
 *
 * Does not close the shared chip handle.
 *
 * @param None.
 * @return void.
 */
void touch_sensor_close(void);

/** @name Accessors
 *  Return the most recently computed touch feature. */
/**@{*/

/**
 * @brief Get and clear the pending IRQ flag.
 *
 * Returns 1 if a touch event occurred since the last call, 0 otherwise.
 * The flag is cleared atomically inside this function.
 *
 * @return int 1 if a new touch was detected, 0 otherwise.
 */
int   touch_sensor_get_irq(void);

/**
 * @brief Get the total number of touches detected since boot.
 *
 * Thread‑safe; reads the counter under a mutex.
 *
 * @return int Cumulative touch count.
 */
int   touch_sensor_get_count(void);

/**
 * @brief Get the touch frequency (touches per second over the last
 *        TOUCH_COUNT_WIN seconds).
 *
 * @return float Frequency in Hz.
 */
float touch_sensor_get_freq(void);

/**
 * @brief Get the classified touch pattern string.
 *
 * Returns "rhythmic" if the standard deviation of inter‑touch intervals
 * is less than 0.3 s, otherwise "random". May be updated only after
 * enough touches have been collected.
 *
 * @return const char* Pointer to a static buffer containing the pattern name.
 */
const char *touch_sensor_get_pattern(void);

/**
 * @brief Get the human‑intent score derived from touch frequency.
 *
 * Returns 0.7 if the frequency exceeds 0.2 Hz, otherwise 0.2.
 *
 * @return float Intent score in [0.2, 0.7].
 */
float touch_sensor_get_intent(void);

/**@}*/

#endif /* TOUCH_SENSOR_H */
