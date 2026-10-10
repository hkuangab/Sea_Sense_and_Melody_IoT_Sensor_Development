/*
 * main.c - Sensor Box main loop
 *
 * Owns the 1 kHz tick loop and the program lifecycle. The loop is
 * structured as a sequence of optional, order-sensitive phases:
 *
 *   1. Acquire one sample from every sensor (once per second).
 *   2. Run the touch detector (a no-op here; the real work happens in
 *      its own thread).
 *   3. Push the current touch count to the 7-segment display as soon
 *      as it changes, rather than waiting for the next second boundary.
 *   4. Once per second, update all derived features and hand a snapshot
 *      to every output backend.
 *   5. On shutdown, release resources in the reverse order of
 *      initialisation, taking care not to close the shared chip handle
 *      more than once.
 *
 * The shared chip handle owned by the display driver is the central
 * invariant of the lifecycle. Every other module that touches GPIO
 * depends on it, and only this file is permitted to close it.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 * Version: 2.2.0
 */

#include "sensor_box.h"

#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __linux__
#  include <gpiod.h>
#endif

#include "csv_writer.h"
#include "jsonl_writer.h"
#include "lcd1602.h"
#include "light_sensor.h"
#include "mcp3008.h"
#include "seg7_display.h"
#include "sound_sensor.h"
#include "term_print.h"
#include "touch_sensor.h"

/** One tick equals one millisecond; 1000 ticks make one second. */
#define TICKS_PER_SECOND 1000

/* Forward declarations for the lifecycle handlers. */
static void on_signal(int sig);
static void install_signal_handler(void);
static void lcd_put_line(int row, const char *text);
static void build_snapshot(struct sb_state *st);

/** Uptime reference, exported for the terminal printer. */
time_t g_start_time = 0;

/*
 * Last value pushed to the 7-segment display. Compared on every tick so
 * that a change triggers an immediate update instead of waiting for the
 * next one-second boundary.
 */
static int g_last_seg_count = -1;

/** Most recent content written to each LCD row, for change detection. */
static char g_lcd_line0[17] = "";
static char g_lcd_line1[17] = "";

/** Set to 1 by the signal handler; the main loop exits cleanly when set. */
static volatile sig_atomic_t g_stop = 0;

/** @brief Signal handler: request a clean shutdown. */
static void on_signal(int sig)
{
    (void)sig;
    g_stop = 1;
}

/** @brief Install handlers for SIGINT and SIGTERM. */
static void install_signal_handler(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT,  &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}

/**
 * @brief Write a line to the LCD only when its content has changed.
 *
 * The LCD controller has a measurable write latency, and the program
 * has no reason to redraw text that is already on screen. Skipping
 * identical writes keeps the display responsive during the one-second
 * update pass.
 *
 * @param[in] row  Row index: 0 for the top row, 1 for the bottom.
 * @param[in] text The text to write, or NULL for a blank line.
 */
static void lcd_put_line(int row, const char *text)
{
    char buf[17];
    snprintf(buf, sizeof(buf), "%-16s", text ? text : "");
    char *cur = (row == 0) ? g_lcd_line0 : g_lcd_line1;

    if (memcmp(cur, buf, 16) == 0)
        return;                 /* unchanged, skip the I/O */
    memcpy(cur, buf, 16);

    lcd1602_print_line(row, buf);
}

/**
 * @brief Build a snapshot from the current accessor values.
 *
 * The returned pointers reference a static timestamp buffer, so the
 * snapshot is not safe to retain across calls. It is intended to live
 * only for the duration of one output pass.
 *
 * @param[out] st The snapshot to populate.
 */
static void build_snapshot(struct sb_state *st)
{
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);

    static char ts_buf[32];
    strftime(ts_buf, sizeof(ts_buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
    st->ts = ts_buf;

    /* Express the time of day as a fraction of the day, in [0, 1). */
    st->time_of_day       = (float)tm.tm_hour + (float)tm.tm_min / 60.0f
                          + (float)tm.tm_sec / 3600.0f;
    st->time_of_day      /= 24.0f;
    st->day_of_week       = tm.tm_wday;
    st->session_elapsed   = (int)difftime(now, g_start_time);

    st->light_raw         = light_get_raw();
    st->light_brightness  = light_get_brightness();
    st->light_trend       = light_get_trend();
    st->light_variance    = light_get_variance();
    st->light_is_daylight = light_get_is_daylight();
    st->light_flicker_freq= light_get_flicker_freq();

    st->sound_raw            = sound_get_raw();
    st->sound_energy         = sound_get_energy();
    st->sound_speech_rate    = sound_get_speech_rate();
    st->sound_continuity     = sound_get_continuity();
    st->sound_spike          = sound_get_spike();
    st->sound_human_presence = sound_get_human_presence();

    st->touch_irq      = touch_sensor_get_irq();
    st->touch_count    = touch_sensor_get_count();
    st->touch_freq     = touch_sensor_get_freq();
    st->touch_pattern  = touch_sensor_get_pattern();
    st->touch_intent   = touch_sensor_get_intent();
}

int main(void)
{
    fprintf(stdout, "Sensor Box 2.2.0 starting...\n");
    fflush(stdout);

    install_signal_handler();
    g_start_time = time(NULL);

    /*
     * The display driver MUST run first: it owns the only gpiod chip
     * handle, and the touch and sound drivers reuse that handle to
     * request their own lines. Reversing this order reproduces the
     * "request GPIO5 failed" failure.
     */
    seg5641bs_init();
    mcp3008_init_default();
    lcd1602_init(LCD_I2C_ADDR);
    light_sensor_sample();           /* warm up so row one is not all zeros */
    sound_init();
    touch_sensor_init();

    /* Show zero on the display until the first real count arrives. */
    seg5641bs_show_number(0);

    fprintf(stdout, "Started. Press Ctrl+C to exit.\n");
    fflush(stdout);

    unsigned long tick = 0;

    while (!g_stop) {
        /* ---- Sample both ADC channels once per second. ---- */
        if (tick % TICKS_PER_SECOND == 0) {
            light_sensor_sample();   /* channel 0: light-dependent resistor */
            sound_sample();          /* channel 1: microphone */
        }

        /* Touch detection runs in its own thread. */
        touch_sensor_tick();

        /* ---- Update the 7-segment display as soon as the count
         *      changes, rather than at the next second boundary. ---- */
        int tc = touch_sensor_get_count();
        if (tc != g_last_seg_count) {
            seg5641bs_show_number(tc);
            g_last_seg_count = tc;
        }

        /* ---- Once per second: update features, refresh the LCD, and
         *      hand a snapshot to every output backend. ---- */
        if (tick % TICKS_PER_SECOND == 0) {
            light_sensor_update_features();
            sound_update_features();
            touch_sensor_update_features();

            char line0[17];
            snprintf(line0, sizeof(line0), "Touch:%4d %s", tc,
                     sound_get_human_presence() ? "ON " : "off");
            lcd_put_line(0, line0);

            int _raw = light_get_raw();
            int _sp  = sound_get_spike();
            int _e100 = (int)(sound_get_energy() * 100.0f);   /* 0..100 */
            char line1[17];

            /* "L:NNNN E:XX.Y S:N" is exactly 16 bytes and never
             * overflows the 17-byte buffer. */
            line1[0]  = 'L'; line1[1]  = ':';
            line1[2]  = (char)('0' + (_raw / 1000) % 10);
            line1[3]  = (char)('0' + (_raw / 100)  % 10);
            line1[4]  = (char)('0' + (_raw / 10)   % 10);
            line1[5]  = (char)('0' + (_raw % 10));
            line1[6]  = ' '; line1[7]  = 'E'; line1[8]  = ':';
            line1[9]  = (char)('0' + (_e100 / 100) % 10);
            line1[10] = (char)('0' + (_e100 / 10)  % 10);
            line1[11] = '.';
            line1[12] = (char)('0' + (_e100 % 10));
            line1[13] = ' '; line1[14] = 'S'; line1[15] = (char)('0' + (_sp % 10));
            line1[16] = '\0';
            lcd_put_line(1, line1);

            struct sb_state st;
            build_snapshot(&st);
            csv_writer_append(&st);
            jsonl_writer_append(&st);
            term_print_all();
        }

        tick++;
        struct timespec ts = { 0, 1000000 };   /* 1 ms */
        nanosleep(&ts, NULL);
    }

    fprintf(stdout, "\nShutting down...\n");
    fflush(stdout);

    csv_writer_close();
    jsonl_writer_close();

    touch_sensor_close();
    sound_close();
    lcd1602_close();
    seg5641bs_clear();
    seg5641bs_close();

    /*
     * The chip handle is closed exactly once, here. The display, touch,
     * and sound modules released only their own requests; closing the
     * chip from any of them would leave the others with dangling
     * pointers.
     */
    if (g_seg_chip) {
        gpiod_chip_close(g_seg_chip);
        g_seg_chip = NULL;
    }

    mcp3008_close();

    fprintf(stdout, "Bye.\n");
    return 0;
}
