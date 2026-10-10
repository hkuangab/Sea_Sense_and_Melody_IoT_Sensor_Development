/*
 * sensor_box.h - main header for the Sensor Box application
 *
 * Defines the module switches, the window-size macros, and the global state
 * structure that is shared between the sampler, the writers, and the
 * terminal printer.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 * Version: 2.2.0
 */

#ifndef SENSOR_BOX_H
#define SENSOR_BOX_H

#include <stddef.h>
#include <stdint.h>

/* =====================================================================
 * Module switches
 *
 * Set any of these to 0 to exclude the corresponding module at compile
 * time. When a module is disabled, its accessor functions return -1 for
 * analogue-style values and 0 for counts, so that callers do not need a
 * separate code path for the disabled case.
 * =================================================================== */
#define ENABLE_LIGHT   1
#define ENABLE_SOUND   1
#define ENABLE_TOUCH   1
#define ENABLE_7SEG    1
#define ENABLE_LCD     1

/* =====================================================================
 * Window sizes
 *
 * Each sensor maintains a ring buffer of recent samples. The size of that
 * buffer determines both the latency and the stability of the derived
 * features: larger windows smooth out noise but react more slowly to
 * genuine changes.
 * =================================================================== */

/** Number of light samples kept for trend and variance. */
#define LIGHT_WINDOW         15

/** Number of seconds kept for light on/off edge counting. */
#define FLICKER_WINDOW       10

/** Number of sound samples kept for RMS energy. */
#define SOUND_ENERGY_WIN     5

/** Number of seconds kept for the audible-ratio window. */
#define SOUND_CONT_WIN       5

/** Window, in seconds, for the loud-spike counter. */
#define SPIKE_WINDOW         1

/** Window, in seconds, over which touch frequency is calculated. */
#define TOUCH_COUNT_WIN      60

/** Number of recent touch intervals kept for pattern classification. */
#define TOUCH_IVAL_WIN       5

/* =====================================================================
 * Global state structure
 *
 * One snapshot is built by main() on every tick that lands on a one-second
 * boundary, and the same snapshot is handed to every output backend. This
 * keeps the CSV, JSONL, and terminal output perfectly aligned: they all
 * describe the same moment in time.
 * =================================================================== */

/**
 * @brief One second of sensor readings, passed to all output backends.
 */
struct sb_state {
    /** ISO 8601 timestamp in UTC, e.g. "2026-09-29T10:30:00Z". */
    const char *ts;

    /** Fractional hour divided by 24, so the value lies in [0, 1). */
    float       time_of_day;

    /** Day of week, 0 = Sunday through 6 = Saturday. */
    int         day_of_week;

    /** Seconds elapsed since the program started. */
    int         session_elapsed;

    /* -----------------------------------------------------------------
     * Light sensor (MCP3008 channel 0)
     * ----------------------------------------------------------------- */

    /** Raw ADC reading, range 0..1023. */
    int         light_raw;

    /** Brightness normalised to [0, 1], i.e. raw / 1023. */
    float       light_brightness;

    /** Slope of the least-squares line fitted to the last LIGHT_WINDOW
     *  samples. Positive means the light level is rising. */
    float       light_trend;

    /** Sample variance over the last LIGHT_WINDOW samples. */
    float       light_variance;

    /** 1 when brightness exceeds 0.3, 0 otherwise. */
    int         light_is_daylight;

    /** Number of on/off edge transitions in the last FLICKER_WINDOW
     *  seconds. */
    int         light_flicker_freq;

    /* -----------------------------------------------------------------
     * Sound sensor (MCP3008 channel 1, plus GPIO18 for digital pulses)
     * ----------------------------------------------------------------- */

    /** Raw ADC reading from the microphone, range 0..1023. */
    int         sound_raw;

    /** RMS energy, normalised to [0, 1], over SOUND_ENERGY_WIN. */
    float       sound_energy;

    /** Digital pulse density from GPIO18, per ten seconds, clamped to
     *  [0, 1]. */
    float       sound_speech_rate;

    /** Ratio of audible seconds over the last SOUND_CONT_WIN. */
    float       sound_continuity;

    /** Number of loud spikes counted in the last SPIKE_WINDOW second. */
    int         sound_spike;

    /** Heuristic: 1 when energy > 0.1 or touch_count > 0, else 0. */
    int         sound_human_presence;

    /* -----------------------------------------------------------------
     * Touch sensor (TTP223 on GPIO5)
     * ----------------------------------------------------------------- */

    /** Whether a touch edge occurred during the current second. Cleared
     *  after it has been read once. */
    int         touch_irq;

    /** Number of touches recorded in the last TOUCH_COUNT_WIN seconds. */
    int         touch_count;

    /** touch_count divided by TOUCH_COUNT_WIN. */
    float       touch_freq;

    /** "rhythmic" when intervals are regular, "random" otherwise. */
    const char *touch_pattern;

    /** Interaction intent score: 0.7 when touch_freq > 0.2, else 0.2. */
    float       touch_intent;
};

/* =====================================================================
 * Cross-module globals
 *
 * These are defined in their respective modules and referenced elsewhere.
 * They are declared here so that all modules agree on their types.
 * =================================================================== */

/** Touch count maintained by touch_sensor.c and read by the main loop. */
extern volatile int g_touch_count;

/** Microphone digital pulse count, reset by the main loop every second. */
extern volatile int g_sound_pulse_count;

#endif /* SENSOR_BOX_H */
