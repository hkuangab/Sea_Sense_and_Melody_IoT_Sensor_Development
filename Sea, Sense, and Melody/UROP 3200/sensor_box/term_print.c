/**
 * @file term_print.c
 * @brief Implementation of the human‑readable summary printer.
 *
 * Gathers the current state from all sensor modules and prints a
 * formatted line to stdout. The line includes an ISO 8601 timestamp,
 * session uptime, light/sound/touch readings, camera HSV clusters,
 * and the latest emotion classification.
 *
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date:   2026-10-19
 */

/*
 * term_print.c - implementation of the human-readable summary printer
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Date:     2026-10-17 (updated: camera now shows top-3 HSV)
 * Updated:  2026-10-19 added emotion label display
 */

#include "term_print.h"
#include "sensor_box.h"

#include <stdio.h>
#include <time.h>

/* Sensor accessor declarations */
extern int   light_get_raw(void);
extern float light_get_brightness(void);
extern float light_get_trend(void);
extern float light_get_variance(void);
extern int   light_get_is_daylight(void);
extern int   light_get_flicker_freq(void);

extern int   sound_get_raw(void);
extern float sound_get_energy(void);
extern float sound_get_speech_rate(void);
extern float sound_get_continuity(void);
extern int   sound_get_spike(void);
extern int   sound_get_human_presence(void);

extern int   touch_sensor_get_irq(void);
extern int   touch_sensor_get_count(void);
extern float touch_sensor_get_freq(void);
extern const char *touch_sensor_get_pattern(void);
extern float touch_sensor_get_intent(void);

/* Camera TOP3 accessors */
extern int camera_get_top_count(void);
extern int camera_get_top_h(int index);
extern int camera_get_top_s(int index);
extern int camera_get_top_v(int index);

/* ADDED: emotion label accessor */
extern const char *camera_get_emotion_label(void);
extern float camera_get_emotion_conf(void);

extern time_t g_start_time;

/**
 * @brief Print a one‑line summary of the current sensor state.
 *
 * Formats a line containing:
 *   - ISO 8601 UTC timestamp
 *   - Session uptime in seconds
 *   - Light sensor: raw ADC, brightness, trend, variance, daylight flag,
 *     flicker frequency
 *   - Sound sensor: raw ADC, energy, speech rate, continuity, spike flag,
 *     human presence flag
 *   - Touch sensor: IRQ status, tap count, frequency, pattern string,
 *     intent value
 *   - Camera: top‑3 HSV tuples (or "none")
 *   - Emotion: label string and confidence percentage
 *
 * @param None.
 * @return void.
 */
void term_print_all(void)
{
    char ts[32];
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm);

    int up = (int)difftime(now, g_start_time);

    char cam_str[64] = "";
    int n = camera_get_top_count();
    if (n > 0) {
        snprintf(cam_str, sizeof(cam_str),
                 "(%d,%d,%d) (%d,%d,%d) (%d,%d,%d)",
                 camera_get_top_h(0), camera_get_top_s(0), camera_get_top_v(0),
                 camera_get_top_h(1), camera_get_top_s(1), camera_get_top_v(1),
                 camera_get_top_h(2), camera_get_top_s(2), camera_get_top_v(2));
    } else {
        snprintf(cam_str, sizeof(cam_str), "none");
    }

    /* ADDED: get emotion label and confidence */
    const char *emotion = camera_get_emotion_label();
    float conf = camera_get_emotion_conf();
    if (!emotion) emotion = "none";

    printf("[%s] up=%ds | "
           "light: adc=%-5d b=%.3f trend=%+.2f var=%.4f day=%d flick=%d | "
           "sound: adc=%-5d eng=%.3f speech=%.2f cont=%.2f spike=%d hp=%d | "
           "touch: irq=%d cnt=%d freq=%.3f pat=%s intent=%.1f | "
           "camera: %s | "
           "emotion: %s (%.1f%%)\n",
           ts, up,
           light_get_raw(), light_get_brightness(), light_get_trend(),
           light_get_variance(), light_get_is_daylight(), light_get_flicker_freq(),
           sound_get_raw(), sound_get_energy(), sound_get_speech_rate(),
           sound_get_continuity(), sound_get_spike(), sound_get_human_presence(),
           touch_sensor_get_irq(), touch_sensor_get_count(),
           touch_sensor_get_freq(), touch_sensor_get_pattern(),
           touch_sensor_get_intent(),
           cam_str,
           emotion, conf * 100.0f);
}
