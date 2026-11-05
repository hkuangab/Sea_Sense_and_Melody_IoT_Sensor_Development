/**
 * @file sound_sensor.c
 * @brief Implementation of the microphone sensor module (analogue only).
 *
 * See sound_sensor.h for the full interface documentation.
 *
 * Implementation notes:
 *   - All data comes from MCP3008 channel 1; no digital GPIO is used.
 *   - The per‑second spike counter is reset inside
 *     `sound_update_features()`, so that function must be called exactly
 *     once per second.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "sound_sensor.h"
#include "sensor_box.h"
#include "mcp3008.h"
#include "math_util.h"

#include <stdio.h>
#include <string.h>
#include <math.h>

#if ENABLE_SOUND

/**
 * @brief Touch count from the capacitive touch sensor (external).
 * Defined elsewhere; used here in the human‑presence heuristic.
 */
extern volatile int g_touch_count;

/**
 * @brief Ring buffer of raw ADC readings used for RMS energy calculation.
 * Size defined by `SOUND_ENERGY_WIN` in `sensor_box.h`.
 */
static int   g_energy_win[SOUND_ENERGY_WIN];

/**
 * @brief Write index for the energy ring buffer.
 */
static int   g_energy_head = 0;

/**
 * @brief Number of valid entries currently in the energy ring buffer.
 * Ranges from 0 to `SOUND_ENERGY_WIN`.
 */
static int   g_energy_count = 0;

/**
 * @brief Ring buffer of audible/not‑audible decisions (1 or 0).
 * Used to compute the continuity feature.
 * Size defined by `SOUND_CONT_WIN`.
 */
static uint8_t g_cont_win[SOUND_CONT_WIN];

/**
 * @brief Write index for the continuity ring buffer.
 */
static int   g_cont_head = 0;

/**
 * @brief Number of valid entries currently in the continuity ring buffer.
 * Ranges from 0 to `SOUND_CONT_WIN`.
 */
static int   g_cont_count = 0;

/**
 * @brief Accumulator for loud spikes (raw > 800) within the current second.
 * Reset to zero in `sound_update_features()`.
 */
static int   g_spike_count = 0;

/* Most recently computed feature values. */

/**
 * @brief Latest raw ADC reading from the microphone channel.
 */
static int   g_raw = 0;

/**
 * @brief RMS energy normalised to [0, 1], computed over the energy window.
 */
static float g_energy = 0.0f;

/**
 * @brief Speech rate – always 0.0 (no digital input).
 */
static float g_speech_rate = 0.0f;

/**
 * @brief Fraction of time the microphone detected audible sound over the
 *        continuity window.
 */
static float g_continuity = 0.0f;

/**
 * @brief Number of loud spikes in the most recent second.
 */
static int   g_spike = 0;

/**
 * @brief Human presence indicator (0 or 1).
 * 1 if energy > 0.1 or touch count > 0.
 */
static int   g_human_presence = 0;

/**
 * @brief Initialise the sound sensor.
 *
 * No hardware initialisation is required; the MCP3008 ADC is set up
 * independently. This function exists for interface consistency.
 *
 * @param None.
 * @return void.
 */
void sound_init(void)
{
    /* Nothing to do – analogue path only. */
    printf("sound: analogue-only mode (MCP3008 ch1)\n");
}

/**
 * @brief Acquire one microphone sample.
 *
 * Steps:
 *   1. Read MCP3008 channel 1 (microphone analogue output).
 *   2. If the read fails (returns negative), abort without updating state.
 *   3. Store the raw value in the energy ring buffer.
 *   4. Determine if the sample is “audible” (raw > 100) and store in
 *      the continuity ring buffer.
 *   5. If raw > 800, increment the per‑second spike counter.
 *
 * @param None.
 * @return void.
 */
void sound_sample(void)
{
    int adc = mcp3008_read_channel(MCP_CH_SOUND);
    if (adc < 0) return;

    g_raw = adc;

    int norm = adc; /* 0..1023 */
    g_energy_win[g_energy_head] = norm;
    g_energy_head = (g_energy_head + 1) % SOUND_ENERGY_WIN;
    if (g_energy_count < SOUND_ENERGY_WIN) g_energy_count++;

    /* Audible when the reading clears a fixed noise floor. */
    int active = (norm > 100) ? 1 : 0;
    g_cont_win[g_cont_head] = (uint8_t)active;
    g_cont_head = (g_cont_head + 1) % SOUND_CONT_WIN;
    if (g_cont_count < SOUND_CONT_WIN) g_cont_count++;

    /* Loud-spike detector: a hard threshold on the raw reading. */
    if (norm > 800) {
        g_spike_count++;
    }
}

/**
 * @brief Compute all derived sound features.
 *
 * Called exactly once per second. Computes:
 *   - RMS energy over the energy window (normalised to [0, 1]).
 *   - Speech rate = 0.0 (no digital input).
 *   - Continuity = fraction of audible samples in the continuity window.
 *   - Spike count = snapshot of the per‑second spike accumulator, then
 *     resets it to zero.
 *   - Human presence = (energy > 0.1 OR g_touch_count > 0) ? 1 : 0.
 *
 * @param None.
 * @return void.
 */
void sound_update_features(void)
{
    /* RMS energy, normalised to [0, 1]. */
    float sum = 0.0f;
    for (int i = 0; i < g_energy_count; i++) {
        float v = (float)g_energy_win[i] / (float)MCP3008_RES;
        sum += v * v;
    }
    if (g_energy_count > 0)
        g_energy = (float)sqrtf(sum / (float)g_energy_count);
    else
        g_energy = 0.0f;

    /*
     * Speech rate is always 0 because there is no digital pulse input.
     */
    g_speech_rate = 0.0f;

    /* Audible ratio over the continuity window. */
    int ones = 0;
    for (int i = 0; i < g_cont_count; i++) ones += g_cont_win[i];
    if (g_cont_count > 0)
        g_continuity = (float)ones / (float)g_cont_count;
    else
        g_continuity = 0.0f;

    /* Snapshot and reset the per-second spike counter. */
    g_spike = g_spike_count;
    g_spike_count = 0;

    /* Heuristic presence indicator. */
    g_human_presence = (g_energy > 0.1f || g_touch_count > 0) ? 1 : 0;
}

/**
 * @brief Release any resources held by the module.
 *
 * No resources to release (no GPIO lines or dynamic allocations).
 * Safe to call multiple times.
 *
 * @param None.
 * @return void.
 */
void sound_close(void)
{
    /* Nothing to do. */
}

/**
 * @brief Get the latest raw ADC value from the microphone.
 *
 * @return int Raw ADC reading (0–1023).
 */
int   sound_get_raw(void)            { return g_raw; }

/**
 * @brief Get the RMS energy level, normalised to [0, 1].
 *
 * @return float Energy value.
 */
float sound_get_energy(void)         { return g_energy; }

/**
 * @brief Get the speech rate – always 0.0.
 *
 * @return float Always 0.0.
 */
float sound_get_speech_rate(void)    { return g_speech_rate; }

/**
 * @brief Get the fraction of time the microphone detected audible sound.
 *
 * @return float Continuity ratio in [0, 1].
 */
float sound_get_continuity(void)     { return g_continuity; }

/**
 * @brief Get the number of loud spikes in the last second.
 *
 * @return int Spike count.
 */
int   sound_get_spike(void)          { return g_spike; }

/**
 * @brief Get the human presence indicator.
 *
 * @return int 1 if presence detected, 0 otherwise.
 */
int   sound_get_human_presence(void) { return g_human_presence; }

#else /* !ENABLE_SOUND */

/**
 * @brief Stub initialisation. Does nothing.
 */
void  sound_init(void) {}

/**
 * @brief Stub sample acquisition. Does nothing.
 */
void  sound_sample(void) {}

/**
 * @brief Stub feature update. Does nothing.
 */
void  sound_update_features(void) {}

/**
 * @brief Stub close. Does nothing.
 */
void  sound_close(void) {}

/**
 * @brief Stub accessor returning -1.
 * @return int Always -1.
 */
int   sound_get_raw(void)            { return -1; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float sound_get_energy(void)         { return -1.0f; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float sound_get_speech_rate(void)    { return -1.0f; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float sound_get_continuity(void)     { return -1.0f; }

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   sound_get_spike(void)          { return 0; }

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   sound_get_human_presence(void) { return 0; }

#endif
