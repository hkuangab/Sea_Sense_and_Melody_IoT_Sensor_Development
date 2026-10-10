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
 * Requests GPIO18 through the shared chip handle. Safe to call even if
 * the display driver has not yet initialised, but in that case the
 * digital pulse counter will be disabled (the analogue path still works).
 */
void sound_init(void);

/**
 * @brief Acquire one microphone sample.
 *
 * Reads the ADC, updates the energy and audible-ratio windows, counts
 * loud spikes, and (when the digital input is available) detects edges
 * on GPIO18.
 */
void sound_sample(void);

/**
 * @brief Compute all derived sound features.
 *
 * Resets the per-second spike counter, so it must be called exactly once
 * per second.
 */
void sound_update_features(void);

/**
 * @brief Release the module's GPIO request.
 *
 * Does not close the shared chip handle; that is the responsibility of
 * main().
 */
void sound_close(void);

/** @name Accessors */
/**@{*/
int   sound_get_raw(void);
float sound_get_energy(void);
float sound_get_speech_rate(void);
float sound_get_continuity(void);
int   sound_get_spike(void);
int   sound_get_human_presence(void);
/**@}*/

/** Digital pulse count accumulated by the sampler, reset every second. */
extern volatile int g_sound_pulse_count;

#endif /* SOUND_SENSOR_H */
