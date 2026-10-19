/**
 * @file sound_sensor.h
 * @brief Microphone sensor module combining analogue and digital inputs.
 *
 * Two acquisition paths are combined:
 *   - Analogue signal on MCP3008 channel 1 → energy, speech rate,
 *     continuity, spike count.
 *   - Digital signal on GPIO18 → pulse counting (edge detection).
 *
 * Both paths are sampled once per second. The digital path reuses the
 * gpiod chip handle owned by the 7‑segment display driver and must NOT
 * open its own chip, as that would conflict with the display’s request
 * on GPIO18.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * sound_sensor.h - microphone sensor module
 *
 * Combines two acquisition paths: an analogue signal on MCP3008 channel 1
 * for energy and waveform features, and a digital signal on GPIO18 for
 * pulse counting. Both are sampled once per second.
 *
 * IMPORTANT: this module reuses the gpiod chip handle owned by the
 * 7-segment display driver. It must NOT open its own chip, as that
 * would conflict with the display's request on GPIO18.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
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
 * Requests GPIO18 through the shared chip handle (`g_seg_chip` owned by
 * the 7‑segment display driver). If the display driver has not yet
 * initialised, the digital pulse counter will be disabled, but the
 * analogue path (ADC) will still work.
 *
 * @param None.
 * @return void.
 */
void sound_init(void);

/**
 * @brief Acquire one microphone sample.
 *
 * Performs the following actions:
 *   - Reads MCP3008 channel 1 (analogue microphone output).
 *   - Updates the energy ring window (`g_energy_win`) with the raw value.
 *   - Updates the audible‑state ring window (`g_cont_win`) based on a
 *     noise‑floor threshold (raw > 100).
 *   - Counts loud spikes (raw > 800) in a per‑second accumulator.
 *   - When the digital GPIO input is available, detects rising edges on
 *     GPIO18 and increments the external pulse counter.
 *
 * @param None.
 * @return void.
 */
void sound_sample(void);

/**
 * @brief Compute all derived sound features.
 *
 * Must be called exactly once per second. Resets the per‑second spike
 * counter (`g_spike_count`) after snapshotting it, so it is critical
 * that no other function reads that counter between the reset and the
 * next call.
 *
 * Derived features computed:
 *   - RMS energy (normalised to [0, 1]) over the energy window.
 *   - Speech rate (digital pulse count / 10, clamped to [0, 1]).
 *   - Continuity (fraction of time audible over the continuity window).
 *   - Spike count (snapshot of the per‑second loud‑spike accumulator).
 *   - Human presence heuristic (energy > 0.1 OR touch count > 0).
 *
 * @param None.
 * @return void.
 */
void sound_update_features(void);

/**
 * @brief Release the module's GPIO request.
 *
 * Releases the GPIO line requested during `sound_init()`. Does NOT close
 * the shared gpiod chip handle; that is the responsibility of `main()`.
 * Safe to call even if `sound_init()` never succeeded.
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
 * @brief Get the estimated speech rate as a fraction of full activity.
 *
 * Derived from the digital pulse count divided by 10, clamped to [0, 1].
 * A value of 1.0 indicates at least 10 pulses were counted in the last
 * second (i.e. continuous speech).
 *
 * @return float Speech rate in [0, 1].
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

/**
 * @brief Digital pulse count accumulated by the sampler.
 *
 * Incremented on each rising edge of GPIO18. Reset to 0 every second
 * by `sound_update_features()`. Declared `volatile` because it may be
 * modified by interrupt‑like polling in `sound_sample()` and read by
 * other modules.
 */
extern volatile int g_sound_pulse_count;

#endif /* SOUND_SENSOR_H */
