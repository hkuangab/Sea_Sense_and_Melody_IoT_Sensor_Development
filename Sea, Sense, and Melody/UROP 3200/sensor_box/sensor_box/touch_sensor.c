/**
 * @file touch_sensor.c
 * @brief Implementation of the TTP223 touch sensor module.
 *
 * See touch_sensor.h for the full interface documentation.
 *
 * Implementation notes:
 *   - The gpiod chip handle `g_seg_chip` is declared in `seg7_display.h`
 *     and is reused here; this module does NOT open its own chip.
 *   - The polling thread runs at 1 kHz (POLL_MS = 1 ms).
 *   - A retrigger lockout of 200 ms prevents multiple counts from a
 *     single press due to contact bounce.
 *   - The timestamp window (`g_ts_win`) stores the time of each touch
 *     and is used to compute the frequency over the last
 *     TOUCH_COUNT_WIN seconds.
 *   - The interval window (`g_ival_win`) stores the gaps between
 *     consecutive touches and is used for pattern classification.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

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

/**
 * @brief Mutex protecting the shared touch counter and IRQ flag.
 */
static pthread_mutex_t g_mtx = PTHREAD_MUTEX_INITIALIZER;

/**
 * @brief Global cumulative touch count.
 *
 * Incremented by the polling thread under the mutex. Readable by other
 * modules (declared extern in touch_sensor.h).
 */
volatile int g_touch_count = 0;

/**
 * @brief GPIO line request object for the touch sensor input.
 * NULL until `touch_sensor_init()` succeeds.
 */
static struct gpiod_line_request *g_req = NULL;

/**
 * @brief Handle of the polling thread.
 */
static pthread_t g_thread;

/**
 * @brief Flag controlling the polling loop.
 * Set to 1 by `touch_sensor_init()`, set to 0 by `touch_sensor_close()`.
 */
static volatile int g_running = 0;

/* Timestamps of recent touches, used for frequency calculation. */
static time_t g_ts_win[TOUCH_COUNT_WIN];
static int    g_ts_head   = 0;
static int    g_ts_count  = 0;

/* Intervals between recent touches, used for pattern classification. */
static float  g_ival_win[TOUCH_IVAL_WIN];
static int    g_ival_head  = 0;
static int    g_ival_count = 0;

/**
 * @brief Timestamp of the most recently accepted touch.
 * Used to compute inter‑touch intervals.
 */
static time_t g_last_touch_ts = 0;

/* Most recently computed feature values. */
/**
 * @brief Pending IRQ flag (set by polling thread, cleared by accessor).
 */
static int   g_irq    = 0;

/**
 * @brief Touch frequency computed by `touch_sensor_update_features()`.
 */
static float g_freq   = 0.0f;

/**
 * @brief Pattern classification string ("rhythmic" or "random").
 */
static char  g_pattern_buf[16];

/**
 * @brief Human‑intent score computed by `touch_sensor_update_features()`.
 */
static float g_intent = 0.2f;

/** @cond INTERNAL */
/** @endcond */

/**
 * @brief Return the current monotonic time in milliseconds.
 *
 * Uses CLOCK_MONOTONIC to avoid jumps caused by system time adjustments.
 *
 * @return long Time in milliseconds since an unspecified epoch.
 */
static long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/**
 * @brief Recompute the touch frequency, pattern, and intent score.
 *
 * Walks the timestamp window and should be called once per second.
 *
 * Algorithm:
 *   - Frequency = number of touches within the last TOUCH_COUNT_WIN
 *     seconds divided by TOUCH_COUNT_WIN.
 *   - Pattern = "rhythmic" if the standard deviation of inter‑touch
 *     intervals is below 0.3 s, otherwise "random". Requires at least
 *     two intervals to decide.
 *   - Intent = 0.7 if frequency > 0.2 Hz, else 0.2.
 *
 * @param None.
 * @return void.
 */
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

/**
 * @brief Compatibility stub for the main loop.
 *
 * The actual polling happens in the dedicated thread, so this function
 * deliberately does nothing. It is retained so that the main loop's
 * structure does not need to special-case the touch module.
 *
 * @param None.
 * @return void.
 */
void touch_sensor_tick(void)
{
    /* Polling happens in the dedicated thread. */
}

/**
 * @brief Body of the touch detector thread.
 *
 * Polls GPIO5 at 1 kHz. Detects rising edges (configurable active level)
 * and, subject to the retrigger lockout, increments the touch counter
 * and records timestamps.
 *
 * @param arg Unused (required by pthread API).
 * @return void* Always NULL.
 */
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

/**
 * @brief Initialise the touch sensor.
 *
 * Requests GPIO5 through the shared chip handle and starts the polling
 * thread. Safe to call before the display driver has initialised, but
 * the thread will not be created in that case.
 *
 * @param None.
 * @return void.
 */
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

/**
 * @brief Stop the polling thread and release the GPIO request.
 *
 * Signals the thread to exit, joins it, then releases the GPIO line.
 * Does not close the shared chip handle.
 *
 * @param None.
 * @return void.
 */
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

/**
 * @brief Get and clear the pending IRQ flag.
 *
 * Atomically reads and resets the flag under the mutex.
 *
 * @return int 1 if a new touch was detected since the last call, 0 otherwise.
 */
int touch_sensor_get_irq(void)
{
    pthread_mutex_lock(&g_mtx);
    int v = g_irq; g_irq = 0;
    pthread_mutex_unlock(&g_mtx);
    return v;
}

/**
 * @brief Get the total number of touches detected since boot.
 *
 * Thread‑safe; reads the counter under the mutex.
 *
 * @return int Cumulative touch count.
 */
int touch_sensor_get_count(void)
{
    pthread_mutex_lock(&g_mtx);
    int v = g_touch_count;
    pthread_mutex_unlock(&g_mtx);
    return v;
}

/**
 * @brief Get the touch frequency (touches per second over the last
 *        TOUCH_COUNT_WIN seconds).
 *
 * @return float Frequency in Hz.
 */
float touch_sensor_get_freq(void)          { return g_freq; }

/**
 * @brief Get the classified touch pattern string.
 *
 * Returns "rhythmic" if the standard deviation of inter‑touch intervals
 * is less than 0.3 s, otherwise "random". May be updated only after
 * enough touches have been collected.
 *
 * @return const char* Pointer to a static buffer containing the pattern name.
 */
const char *touch_sensor_get_pattern(void) { return g_pattern_buf; }

/**
 * @brief Get the human‑intent score derived from touch frequency.
 *
 * Returns 0.7 if the frequency exceeds 0.2 Hz, otherwise 0.2.
 *
 * @return float Intent score in [0.2, 0.7].
 */
float touch_sensor_get_intent(void)        { return g_intent; }

#else /* !ENABLE_TOUCH */

/**
 * @brief Stub global touch counter when ENABLE_TOUCH is not defined.
 * Always zero.
 */
volatile int g_touch_count = 0;

/**
 * @brief Stub initialisation. Does nothing.
 */
void  touch_sensor_init(void) {}

/**
 * @brief Stub tick. Does nothing.
 */
void  touch_sensor_tick(void) {}

/**
 * @brief Stub feature update. Does nothing.
 */
void  touch_sensor_update_features(void) {}

/**
 * @brief Stub close. Does nothing.
 */
void  touch_sensor_close(void) {}

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   touch_sensor_get_irq(void)           { return 0; }

/**
 * @brief Stub accessor returning 0.
 * @return int Always 0.
 */
int   touch_sensor_get_count(void)         { return 0; }

/**
 * @brief Stub accessor returning 0.0f.
 * @return float Always 0.0f.
 */
float touch_sensor_get_freq(void)          { return 0.0f; }

/**
 * @brief Stub accessor returning "random".
 * @return const char* Always "random".
 */
const char *touch_sensor_get_pattern(void) { return "random"; }

/**
 * @brief Stub accessor returning 0.2f.
 * @return float Always 0.2f.
 */
float touch_sensor_get_intent(void)        { return 0.2f; }

#endif
