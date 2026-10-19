/**
 * @file sound_sensor.c
 * @brief Implementation of the microphone sensor module.
 *
 * See sound_sensor.h for the full interface documentation.
 *
 * Implementation notes:
 *   - The gpiod chip handle `g_seg_chip` is declared in `seg7_display.h`
 *     and is reused here; this module does NOT open its own chip.
 *   - The per‑second spike counter is reset inside
 *     `sound_update_features()`, so that function must be called exactly
 *     once per second.
 *   - The digital pulse counter (`g_sound_pulse_count`) is incremented
 *     on rising edges of GPIO18 and reset to zero in
 *     `sound_update_features()`.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * sound_sensor.c - implementation of the microphone sensor module
 *
 * See sound_sensor.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "sound_sensor.h"
#include "sensor_box.h"
#include "mcp3008.h"
#include "seg7_display.h"
#include "math_util.h"

#include <stdio.h>
#include <string.h>
#include <math.h>
#include <gpiod.h>

#if ENABLE_SOUND

/**
 * @brief Touch count from the capacitive touch sensor (external).
 * Defined elsewhere; used here in the human‑presence heuristic.
 */
extern volatile int g_touch_count;

/**
 * @brief Global pulse counter for the digital microphone output.
 *
 * Incremented on each rising edge of GPIO18 inside `sound_sample()`.
 * Reset to zero in `sound_update_features()`. Declared volatile because
 * it is written by the sampling loop and read by feature computation.
 */
volatile int g_sound_pulse_count = 0;

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
 * @brief Speech rate (digital pulse count / 10, clamped to [0, 1]).
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
 * @brief GPIO line number for the digital microphone output.
 */
#define SOUND_GPIO_LINE    18

/**
 * @brief Active level of the digital input.
 * Set to 1 if the module drives the line HIGH when sound is present;
 * set to 0 if it drives LOW. Adjust according to hardware.
 */
#define SOUND_IRQ_ACTIVE   1

/**
 * @brief Request object for the GPIO line (GPIO18).
 * NULL until `sound_init()` succeeds.
 */
static struct gpiod_line_request *g_req = NULL;

/**
 * @brief Previous digital level read from GPIO18.
 * Used for edge detection. Initialised to -1 to indicate “unknown”.
 */
static int   g_prev_level = -1;

/**
 * @brief Initialise the sound sensor.
 *
 * Requests GPIO18 through the shared chip handle `g_seg_chip`. If the
 * chip is not yet available (display driver not initialised), prints a
 * warning and continues with the digital path disabled. Otherwise,
 * configures the line as an input and reads the initial level.
 *
 * @param None.
 * @return void.
 */
void sound_init(void)
{
    if (!g_seg_chip) {
        fprintf(stderr,
                "sound: seg7 chip not ready, cannot request GPIO%d\n",
                SOUND_GPIO_LINE);
        return;
    }

    unsigned int line = SOUND_GPIO_LINE;

    struct gpiod_line_settings *s = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(s, GPIOD_LINE_DIRECTION_INPUT);

    struct gpiod_line_config *lc = gpiod_line_config_new();
    gpiod_line_config_add_line_settings(lc, &line, 1, s);

    struct gpiod_request_config *rc = gpiod_request_config_new();
    gpiod_request_config_set_consumer(rc, "sound");

    g_req = gpiod_chip_request_lines(g_seg_chip, rc, lc);
    if (!g_req) {
        fprintf(stderr,
                "sound: request GPIO%d failed, pulse counting disabled\n",
                SOUND_GPIO_LINE);
        return;
    }

    g_prev_level = gpiod_line_request_get_value(g_req, SOUND_GPIO_LINE);
    printf("sound: GPIO%d polling ready\n", SOUND_GPIO_LINE);
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
 *   6. If the digital GPIO line is available, detect rising edges and
 *      increment `g_sound_pulse_count` accordingly.
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

    /* Edge detection on the digital input, if available. */
    if (g_req) {
        int lvl = gpiod_line_request_get_value(g_req, SOUND_GPIO_LINE);
        if (g_prev_level < 0) g_prev_level = lvl;
        if (lvl == SOUND_IRQ_ACTIVE && g_prev_level != SOUND_IRQ_ACTIVE) {
            g_sound_pulse_count++;
        }
        g_prev_level = lvl;
    }
}

/**
 * @brief Compute all derived sound features.
 *
 * Called exactly once per second. Computes:
 *   - RMS energy over the energy window (normalised to [0, 1]).
 *   - Speech rate = min(g_sound_pulse_count / 10.0, 1.0).
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
     * Speech rate is the digital pulse count per ten seconds, expressed
     * as a ratio and clamped to [0, 1]. Modules without a digital
     * output will report zero here.
     */
    g_speech_rate = (float)g_sound_pulse_count / 10.0f;
    if (g_speech_rate > 1.0f) g_speech_rate = 1.0f;

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
 * @brief Release the module's GPIO request.
 *
 * Releases the GPIO line requested in `sound_init()`. Does NOT close
 * the shared chip handle (`g_seg_chip`); that is done by `main()`.
 * Sets `g_req` to NULL afterwards. Safe to call multiple times.
 *
 * @param None.
 * @return void.
 */
void sound_close(void)
{
    if (g_req) {
        gpiod_line_request_release(g_req);
        g_req = NULL;
    }
    /* The chip handle is owned by main() and must not be closed here. */
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
 * @brief Get the estimated speech rate (digital pulse count / 10).
 *
 * @return float Speech rate in [0, 1].
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
 * @brief Stub pulse counter when ENABLE_SOUND is not defined.
 * Always zero.
 */
volatile int g_sound_pulse_count = 0;

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
