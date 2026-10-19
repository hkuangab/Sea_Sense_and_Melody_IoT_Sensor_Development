/*
 * light_sensor.c - implementation of the light-dependent resistor module
 *
 * See light_sensor.h for the full interface documentation.
 *
 * Implementation note: the flicker counter operates on a one-second time
 * base. Each call to light_sensor_sample() records exactly one on/off
 * state, and update_features() counts the edges between consecutive
 * states. Earlier versions attempted to track the previous state with a
 * module-level variable, but that variable was overwritten before the
 * edge count could be computed; the current implementation uses a local
 * sweep instead.
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

#include "light_sensor.h"
#include "sensor_box.h"
#include "mcp3008.h"
#include "math_util.h"

#include <stdio.h>
#include <string.h>

#if ENABLE_LIGHT

/**
 * @brief Ring buffer storing the most recent LIGHT_WINDOW ADC readings.
 * 
 * Used by light_sensor_sample() to record raw ADC values and by
 * light_sensor_update_features() to compute trend and variance.
 */
static int   g_win[LIGHT_WINDOW];

/**
 * @brief Index where the next sample will be written in g_win.
 */
static int   g_win_head = 0;

/**
 * @brief Number of valid samples currently stored in g_win.
 * Ranges from 0 to LIGHT_WINDOW.
 */
static int   g_win_count = 0;

/*
 * Second-scale history of on/off states, used to count transitions.
 * One entry is recorded per call to light_sensor_sample(), so the window
 * covers roughly FLICKER_WINDOW seconds.
 */

/**
 * @brief Ring buffer storing the on/off state (0 or 1) for the last
 *        FLICKER_WINDOW calls to light_sensor_sample().
 * Used by light_sensor_update_features() to compute flicker frequency.
 */
static uint8_t g_flick_win[FLICKER_WINDOW];

/**
 * @brief Index where the next state will be written in g_flick_win.
 */
static int   g_flick_head = 0;

/**
 * @brief Number of valid states currently stored in g_flick_win.
 * Ranges from 0 to FLICKER_WINDOW.
 */
static int   g_flick_count = 0;

/* Most recently computed feature values. */

/**
 * @brief Latest raw ADC reading (0 – MCP3008_RES).
 */
static int   g_raw = 0;

/**
 * @brief Normalised brightness (raw / MCP3008_RES), range [0.0, 1.0].
 */
static float g_brightness = 0.0f;

/**
 * @brief Linear trend (slope) of the last LIGHT_WINDOW readings.
 * Computed by math_linreg_slope().
 */
static float g_trend = 0.0f;

/**
 * @brief Sample variance of the last LIGHT_WINDOW readings.
 * Computed by math_variance().
 */
static float g_variance = 0.0f;

/**
 * @brief Daylight flag: 1 if brightness > 0.3, else 0.
 */
static int   g_is_daylight = 0;

/**
 * @brief Number of on/off transitions observed in the last
 *        FLICKER_WINDOW seconds.
 */
static int   g_flicker_freq = 0;

/**
 * @brief Acquire one light sample from the ADC.
 *
 * Reads MCP3008 channel MCP_CH_LIGHT and stores the raw value in the
 * ring window g_win. Also records the current on/off state (based on a
 * 0.5 brightness threshold) in the flicker history buffer g_flick_win.
 * On a read failure (ADC returns negative) the previous values are kept.
 *
 * @param None.
 * @return void.
 */
void light_sensor_sample(void)
{
    int adc = mcp3008_read_channel(MCP_CH_LIGHT);
    if (adc < 0) {
        /* Read failed: keep the previous value rather than inventing one. */
        return;
    }

    g_raw = adc;
    g_brightness = (float)adc / (float)MCP3008_RES;

    g_win[g_win_head] = adc;
    g_win_head = (g_win_head + 1) % LIGHT_WINDOW;
    if (g_win_count < LIGHT_WINDOW) g_win_count++;

    /*
     * Record the current on/off state for flicker analysis. The 0.5
     * threshold is applied here so that the recorded history is
     * independent of any later recalibration.
     */
    int cur_state = (g_brightness > 0.5f) ? 1 : 0;
    g_flick_win[g_flick_head] = (uint8_t)cur_state;
    g_flick_head = (g_flick_head + 1) % FLICKER_WINDOW;
    if (g_flick_count < FLICKER_WINDOW) g_flick_count++;
}

/**
 * @brief Compute all derived light features from the ring windows.
 *
 * Must be called at least once after sampling to obtain valid results.
 * Calculates:
 *   - Trend (least‑squares slope over g_win)
 *   - Variance (sample variance over g_win)
 *   - Daylight flag (brightness > 0.3)
 *   - Flicker frequency (number of on/off transitions in g_flick_win)
 *
 * @param None.
 * @return void.
 */
void light_sensor_update_features(void)
{
    /* Trend: slope of the least-squares line through the window. */
    g_trend = math_linreg_slope(g_win, g_win_count);

    /* Variance of the same window. */
    g_variance = math_variance(g_win, g_win_count);

    /* Daylight decision: a fixed threshold on normalised brightness. */
    g_is_daylight = (g_brightness > 0.3f) ? 1 : 0;

    /*
     * Flicker frequency: number of on/off transitions in the recorded
     * history. The sweep uses a local previous-state variable because
     * the circular buffer does not guarantee that adjacent array
     * positions correspond to adjacent points in time.
     */
    g_flicker_freq = 0;
    if (g_flick_count >= 2) {
        int transitions = 0;
        int prev = g_flick_win[0];

        for (int i = 1; i < g_flick_count; i++) {
            if ((int)g_flick_win[i] != prev) {
                transitions++;
                prev = g_flick_win[i];
            }
        }
        g_flicker_freq = transitions;
    }
}

/**
 * @brief Get the latest raw ADC value.
 *
 * @return int Raw ADC reading (0–1023 for a 10‑bit converter).
 */
int   light_get_raw(void)          { return g_raw; }

/**
 * @brief Get the normalised brightness.
 *
 * @return float Brightness in range [0.0, 1.0].
 */
float light_get_brightness(void)   { return g_brightness; }

/**
 * @brief Get the linear trend (slope) of the last LIGHT_WINDOW samples.
 *
 * @return float Slope value (positive = increasing brightness).
 */
float light_get_trend(void)        { return g_trend; }

/**
 * @brief Get the sample variance of the last LIGHT_WINDOW samples.
 *
 * @return float Variance value.
 */
float light_get_variance(void)     { return g_variance; }

/**
 * @brief Check whether the current ambient light is considered daylight.
 *
 * @return int 1 if brightness > 0.3, 0 otherwise.
 */
int   light_get_is_daylight(void)  { return g_is_daylight; }

/**
 * @brief Get the number of on/off transitions in the last
 *        FLICKER_WINDOW seconds.
 *
 * @return int Transition count (flicker frequency).
 */
int   light_get_flicker_freq(void) { return g_flicker_freq; }

#else /* !ENABLE_LIGHT */

/**
 * @brief Stub version when ENABLE_LIGHT is not defined.
 * Does nothing.
 */
void  light_sensor_sample(void) {}

/**
 * @brief Stub version when ENABLE_LIGHT is not defined.
 * Does nothing.
 */
void  light_sensor_update_features(void) {}

/**
 * @brief Stub accessor returning -1.
 * @return int Always -1.
 */
int   light_get_raw(void)          { return -1; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float light_get_brightness(void)   { return -1.0f; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float light_get_trend(void)        { return -1.0f; }

/**
 * @brief Stub accessor returning -1.0f.
 * @return float Always -1.0f.
 */
float light_get_variance(void)     { return -1.0f; }

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   light_get_is_daylight(void)  { return 0; }

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   light_get_flicker_freq(void) { return 0; }

#endif
