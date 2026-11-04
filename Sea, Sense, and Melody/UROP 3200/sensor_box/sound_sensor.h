/**
 * @file sound_sensor.h
 * @brief Microphone sensor module using analogue input only.
 *
 * The microphone signal is acquired via MCP3008 channel 1 (analogue).
 * Features extracted include RMS energy, continuity, spike count,
 * and a human presence heuristic.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef SOUND_SENSOR_H
#define SOUND_SENSOR_H

#include <stddef.h>
#include <stdint.h>

/**
 * @brief Initialise the sound sensor.
 *
 * Currently a no‑op since the module relies solely on the MCP3008 ADC,
 * which is initialised separately.
 *
 * @param None.
 * @return void.
 */
void sound_init(void);

/**
 * @brief Acquire one microphone sample.
 *
 * Reads MCP3008 channel 1 (analogue microphone output) and updates
 * the internal ring buffers for energy and continuity calculations.
 * Also counts loud spikes (raw > 800).
 *
 * @param None.
 * @return void.
 */
void sound_sample(void);

/**
 * @brief Compute all derived sound features.
 *
 * Must be called exactly once per second. Computes:
 *   - RMS energy (normalised to [0, 1]) over the energy window.
 *   - Speech rate (always 0, as no digital input is present).
 *   - Continuity (fraction of time audible over the continuity window).
 *   - Spike count (snapshot of the per‑second loud‑spike accumulator).
 *   - Human presence heuristic (energy > 0.1 OR touch count > 0).
 *
 * @param None.
 * @return void.
 */
void sound_update_features(void);

/**
 * @brief Release any resources held by the module.
 *
 * Currently a no‑op (no GPIO lines or dynamic allocations).
 *
 * @param None.
 * @return void.
 */
void sound_close(void);

/** @name Accessors
 *  Return the most recently computed sound feature. */
/**@{*/

/**
 * @brief Get the latest raw ADC value from the microphone.
 *
 * @return int Raw ADC reading (0–1023 for a 10‑bit converter).
 */
int   sound_get_raw(void);

/**
 * @brief Get the RMS energy level, normalised to [0, 1].
 *
 * @return float Energy value (0.0 = silence, 1.0 = maximum).
 */
float sound_get_energy(void);

/**
 * @brief Get the estimated speech rate.
 *
 * Always returns 0.0 because the module uses only an analogue
 * microphone and cannot measure pulse density.
 *
 * @return float Always 0.0.
 */
float sound_get_speech_rate(void);

/**
 * @brief Get the fraction of time the microphone detected audible sound.
 *
 * Computed as the proportion of samples in the continuity window whose
 * raw value exceeded the noise floor (100). Range [0, 1].
 *
 * @return float Continuity ratio.
 */
float sound_get_continuity(void);

/**
 * @brief Get the number of loud spikes (raw > 800) in the last second.
 *
 * @return int Spike count.
 */
int   sound_get_spike(void);

/**
 * @brief Get the human presence indicator.
 *
 * Returns 1 if either the RMS energy exceeds 0.1 or the touch sensor
 * count is positive, otherwise 0.
 *
 * @return int Presence flag (0 or 1).
 */
int   sound_get_human_presence(void);

/**@}*/

#endif /* SOUND_SENSOR_H */
