/*
 * term_print.c - implementation of the human-readable summary printer
 *
 * See term_print.h for the full interface documentation.
 *
 * The implementation pulls values directly from the sensor accessors
 * rather than from a snapshot structure. This is deliberate: the
 * printer runs after the feature-update pass, so the accessor values
 * are current, and it avoids taking a copy of the snapshot solely for
 * display purposes.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "term_print.h"
#include "sensor_box.h"

#include <stdio.h>
#include <time.h>

/* Sensor accessor declarations. The implementations live in their
 * respective modules; declaring them here avoids pulling every sensor
 * header into this file. */
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

/** Uptime reference, set by main() at startup. */
extern time_t g_start_time;

void term_print_all(void)
{
    char ts[32];
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm);

    int up = (int)difftime(now, g_start_time);

    printf("[%s] up=%ds | "
           "light: adc=%-5d b=%.3f trend=%+.2f var=%.4f day=%d flick=%d | "
           "sound: adc=%-5d eng=%.3f speech=%.2f cont=%.2f spike=%d hp=%d | "
           "touch: irq=%d cnt=%d freq=%.3f pat=%s intent=%.1f\n",
           ts, up,
           light_get_raw(), light_get_brightness(), light_get_trend(),
           light_get_variance(), light_get_is_daylight(), light_get_flicker_freq(),
           sound_get_raw(), sound_get_energy(), sound_get_speech_rate(),
           sound_get_continuity(), sound_get_spike(), sound_get_human_presence(),
           touch_sensor_get_irq(), touch_sensor_get_count(),
           touch_sensor_get_freq(), touch_sensor_get_pattern(),
           touch_sensor_get_intent());
}
