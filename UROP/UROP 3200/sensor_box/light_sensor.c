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

#include "light_sensor.h"
#include "sensor_box.h"
#include "mcp3008.h"
#include "math_util.h"

#include <stdio.h>
#include <string.h>

#if ENABLE_LIGHT

/* Ring buffer holding the most recent LIGHT_WINDOW ADC readings. */
static int   g_win[LIGHT_WINDOW];
static int   g_win_head = 0;
static int   g_win_count = 0;

/*
 * Second-scale history of on/off states, used to count transitions.
 * One entry is recorded per call to light_sensor_sample(), so the window
 * covers roughly FLICKER_WINDOW seconds.
 */
static uint8_t g_flick_win[FLICKER_WINDOW];
static int   g_flick_head = 0;
static int   g_flick_count = 0;

/* Most recently computed feature values. */
static int   g_raw = 0;
static float g_brightness = 0.0f;
static float g_trend = 0.0f;
static float g_variance = 0.0f;
static int   g_is_daylight = 0;
static int   g_flicker_freq = 0;

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

int   light_get_raw(void)          { return g_raw; }
float light_get_brightness(void)   { return g_brightness; }
float light_get_trend(void)        { return g_trend; }
float light_get_variance(void)     { return g_variance; }
int   light_get_is_daylight(void)  { return g_is_daylight; }
int   light_get_flicker_freq(void) { return g_flicker_freq; }

#else /* !ENABLE_LIGHT */

void  light_sensor_sample(void) {}
void  light_sensor_update_features(void) {}

int   light_get_raw(void)          { return -1; }
float light_get_brightness(void)   { return -1.0f; }
float light_get_trend(void)        { return -1.0f; }
float light_get_variance(void)     { return -1.0f; }
int   light_get_is_daylight(void)  { return 0; }
int   light_get_flicker_freq(void) { return 0; }

#endif
