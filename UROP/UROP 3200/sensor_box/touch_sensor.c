/*
 * touch_sensor.c - implementation of the TTP223 touch sensor module
 *
 * See touch_sensor.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "touch_sensor.h"
#include "sensor_box.h"
#include "seg7_display.h"
#include "math_util.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#include <gpiod.h>

#if ENABLE_TOUCH

/* Effective level of the TTP223 output. Set to 0 if "pinctrl get 5"
 * shows the line going low when the pad is touched. */
#define TOUCH_ACTIVE          1

/* Polling period of the detector thread, in milliseconds. */
#define POLL_MS                1

/* Minimum interval between accepted touches, in milliseconds. Without
 * this, one press can register as several because the pad's output
 * tends to bounce on release. */
#define RETRIGGER_LOCKOUT_MS   200

/** The GPIO line connected to the TTP223 OUT pin. */
#define TOUCH_GPIO_LINE        5

static pthread_mutex_t g_mtx = PTHREAD_MUTEX_INITIALIZER;

volatile int g_touch_count = 0;

static struct gpiod_line_request *g_req = NULL;
static pthread_t g_thread;
static volatile int g_running = 0;

/* Timestamps of recent touches, used for frequency calculation. */
static time_t g_ts_win[TOUCH_COUNT_WIN];
static int    g_ts_head   = 0;
static int    g_ts_count  = 0;

/* Intervals between recent touches, used for pattern classification. */
static float  g_ival_win[TOUCH_IVAL_WIN];
static int    g_ival_head  = 0;
static int    g_ival_count = 0;

static time_t g_last_touch_ts = 0;

/* Most recently computed feature values. */
static int   g_irq    = 0;
static float g_freq   = 0.0f;
static char  g_pattern_buf[16];
static float g_intent = 0.2f;

/** @cond INTERNAL */
/** @endcond */

/** @brief Return the current monotonic time in milliseconds. */
static long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

void touch_sensor_update_features(void)
{
    int count = 0;
    time_t now = time(NULL);

    for (int i = 0; i < g_ts_count; i++) {
        if (difftime(now, g_ts_win[i]) <= (double)TOUCH_COUNT_WIN) {
            count++;
        }
    }
    g_freq = (float)count / (float)TOUCH_COUNT_WIN;

    if (g_ival_count >= 2) {
        float std = math_std(g_ival_win, g_ival_count);
        snprintf(g_pattern_buf, sizeof(g_pattern_buf),
                 "%s", (std < 0.3f) ? "rhythmic" : "random");
    } else {
        snprintf(g_pattern_buf, sizeof(g_pattern_buf), "random");
    }

    g_intent = (g_freq > 0.2f) ? 0.7f : 0.2f;
}

void touch_sensor_tick(void)
{
    /* Polling happens in the dedicated thread. */
}

/** @brief Body of the touch detector thread. */
static void *touch_thread(void *arg)
{
    (void)arg;
    int prev = -1;
    long last_trigger_ms = 0;

    if (g_req) {
        prev = gpiod_line_request_get_value(g_req, TOUCH_GPIO_LINE);
    }

    while (g_running) {
        if (g_req) {
            int cur = gpiod_line_request_get_value(g_req, TOUCH_GPIO_LINE);
            long t = now_ms();

            /*
             * Edge detector: count a touch when the previous sample
             * was not at the active level and the current one is.
             * The retrigger lockout prevents a single press from
             * being counted multiple times.
             */
            if (prev != TOUCH_ACTIVE && cur == TOUCH_ACTIVE) {
                if (t - last_trigger_ms >= RETRIGGER_LOCKOUT_MS) {
                    pthread_mutex_lock(&g_mtx);
                    g_touch_count++;
                    g_irq = 1;
                    last_trigger_ms = t;

                    time_t now = time(NULL);
                    g_ts_win[g_ts_head] = now;
                    g_ts_head = (g_ts_head + 1) % TOUCH_COUNT_WIN;
                    if (g_ts_count < TOUCH_COUNT_WIN) g_ts_count++;

                    if (g_last_touch_ts != 0) {
                        float iv = (float)difftime(now, g_last_touch_ts);
                        g_ival_win[g_ival_head] = iv;
                        g_ival_head = (g_ival_head + 1) % TOUCH_IVAL_WIN;
                        if (g_ival_count < TOUCH_IVAL_WIN) g_ival_count++;
                    }
                    g_last_touch_ts = now;
                    pthread_mutex_unlock(&g_mtx);
                }
            }
            prev = cur;
        }
        usleep(POLL_MS * 1000);
    }
    return NULL;
}

void touch_sensor_init(void)
{
    if (!g_seg_chip) {
        fprintf(stderr,
                "touch: seg7 chip not ready, cannot request GPIO%d\n",
                TOUCH_GPIO_LINE);
        return;
    }

    unsigned int line = TOUCH_GPIO_LINE;
    struct gpiod_line_settings *s = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(s, GPIOD_LINE_DIRECTION_INPUT);

    struct gpiod_line_config *lc = gpiod_line_config_new();
    gpiod_line_config_add_line_settings(lc, &line, 1, s);

    struct gpiod_request_config *rc = gpiod_request_config_new();
    gpiod_request_config_set_consumer(rc, "touch");

    g_req = gpiod_chip_request_lines(g_seg_chip, rc, lc);
    if (!g_req) {
        fprintf(stderr, "touch: request GPIO%d failed\n", TOUCH_GPIO_LINE);
        return;
    }

    g_running = 1;
    if (pthread_create(&g_thread, NULL, touch_thread, NULL) != 0) {
        fprintf(stderr, "touch: cannot create polling thread\n");
        gpiod_line_request_release(g_req);
        g_req = NULL;
        g_running = 0;
        return;
    }
    printf("touch: polling thread started on GPIO%d (active=%d, %dms lockout)\n",
           TOUCH_GPIO_LINE, TOUCH_ACTIVE, RETRIGGER_LOCKOUT_MS);
}

void touch_sensor_close(void)
{
    if (g_running) {
        g_running = 0;
        pthread_join(g_thread, NULL);
    }
    if (g_req) {
        gpiod_line_request_release(g_req);
        g_req = NULL;
    }
}

int touch_sensor_get_irq(void)
{
    pthread_mutex_lock(&g_mtx);
    int v = g_irq; g_irq = 0;
    pthread_mutex_unlock(&g_mtx);
    return v;
}

int touch_sensor_get_count(void)
{
    pthread_mutex_lock(&g_mtx);
    int v = g_touch_count;
    pthread_mutex_unlock(&g_mtx);
    return v;
}

float touch_sensor_get_freq(void)          { return g_freq; }
const char *touch_sensor_get_pattern(void) { return g_pattern_buf; }
float touch_sensor_get_intent(void)        { return g_intent; }

#else /* !ENABLE_TOUCH */

volatile int g_touch_count = 0;

void  touch_sensor_init(void) {}
void  touch_sensor_tick(void) {}
void  touch_sensor_update_features(void) {}
void  touch_sensor_close(void) {}

int   touch_sensor_get_irq(void)           { return 0; }
int   touch_sensor_get_count(void)         { return 0; }
float touch_sensor_get_freq(void)          { return 0.0f; }
const char *touch_sensor_get_pattern(void) { return "random"; }
float touch_sensor_get_intent(void)        { return 0.2f; }

#endif
