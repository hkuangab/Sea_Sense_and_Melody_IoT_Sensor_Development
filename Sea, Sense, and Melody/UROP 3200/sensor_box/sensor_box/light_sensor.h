/*
 * light_sensor.h - light-dependent resistor sensor module
 *
 * Reads the LDR through MCP3008 channel 0 and derives six features:
 * raw ADC, normalised brightness, a linear trend, sample variance,
 * a daylight/no-daylight decision, and a flicker frequency.
 *
 * The module is split into two phases: light_sensor_sample() runs once
 * per second and only acquires data, while light_sensor_update_features()
 * runs after all sampling is complete and computes the derived values.
 * This separation keeps the per-tick cost low.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date: 2026/10/06
 */

#ifndef LIGHT_SENSOR_H
#define LIGHT_SENSOR_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Acquire one light sample from the ADC.
 *
 * Reads MCP3008 channel MCP_CH_LIGHT and stores the value in the ring
 * window. Also records the current on/off state for flicker detection.
 * On a read failure the previous value is retained rather than being
 * overwritten with an error sentinel.
 *
 * @param None.
 * @return void.
 */
void light_sensor_sample(void);

/**
 * @brief Compute all derived light features from the ring window.
 *
 * Must be called at least once before the accessor functions return
 * meaningful values. Calling it again replaces the previous result.
 *
 * @param None.
 * @return void.
 */
void light_sensor_update_features(void);

/** @name Accessors
 *  Return the most recently computed feature. */
/**@{*/

/**
 * @brief Get the latest raw ADC value.
 *
 * @return int Raw ADC reading (0–MCP3008_RES).
 */
int   light_get_raw(void);

/**
 * @brief Get the normalised brightness.
 *
 * @return float Brightness in range [0.0, 1.0].
 */
float light_get_brightness(void);

/**
 * @brief Get the linear trend (slope) of the last LIGHT_WINDOW samples.
 *
 * @return float Slope value.
 */
float light_get_trend(void);

/**
 * @brief Get the sample variance of the last LIGHT_WINDOW samples.
 *
 * @return float Variance value.
 */
float light_get_variance(void);

/**
 * @brief Check whether the current ambient light is considered daylight.
 *
 * @return int 1 if brightness > 0.3, 0 otherwise.
 */
int   light_get_is_daylight(void);

/**
 * @brief Get the number of on/off transitions in the last
 *        FLICKER_WINDOW seconds.
 *
 * @return int Transition count (flicker frequency).
 */
int   light_get_flicker_freq(void);

/**@}*/

#endif /* LIGHT_SENSOR_H */
