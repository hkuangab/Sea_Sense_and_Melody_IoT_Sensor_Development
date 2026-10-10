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

volatile int g_sound_pulse_count = 0;

/* Window of recent ADC readings used for RMS energy. */
static int   g_energy_win[SOUND_ENERGY_WIN];
static int   g_energy_head = 0;
static int   g_energy_count = 0;

/* Second-scale history of audible/not-audible decisions. */
static uint8_t g_cont_win[SOUND_CONT_WIN];
static int   g_cont_head = 0;
static int   g_cont_count = 0;

/* Loud spikes counted during the current second. */
static int   g_spike_count = 0;

/* Most recently computed feature values. */
static int   g_raw = 0;
static float g_energy = 0.0f;
static float g_speech_rate = 0.0f;
static float g_continuity = 0.0f;
static int   g_spike = 0;
static int   g_human_presence = 0;

/* GPIO18 digital input. */
#define SOUND_GPIO_LINE    18
#define SOUND_IRQ_ACTIVE   1   /* 1 = active high; set to 0 if your module
                                * drives the line low when sound is present. */

static struct gpiod_line_request *g_req = NULL;
static int   g_prev_level = -1;

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

void sound_close(void)
{
    if (g_req) {
        gpiod_line_request_release(g_req);
        g_req = NULL;
    }
    /* The chip handle is owned by main() and must not be closed here. */
}

int   sound_get_raw(void)            { return g_raw; }
float sound_get_energy(void)         { return g_energy; }
float sound_get_speech_rate(void)    { return g_speech_rate; }
float sound_get_continuity(void)     { return g_continuity; }
int   sound_get_spike(void)          { return g_spike; }
int   sound_get_human_presence(void) { return g_human_presence; }

#else /* !ENABLE_SOUND */

volatile int g_sound_pulse_count = 0;

void  sound_init(void) {}
void  sound_sample(void) {}
void  sound_update_features(void) {}
void  sound_close(void) {}

int   sound_get_raw(void)            { return -1; }
float sound_get_energy(void)         { return -1.0f; }
float sound_get_speech_rate(void)    { return -1.0f; }
float sound_get_continuity(void)     { return -1.0f; }
int   sound_get_spike(void)          { return 0; }
int   sound_get_human_presence(void) { return 0; }

#endif
