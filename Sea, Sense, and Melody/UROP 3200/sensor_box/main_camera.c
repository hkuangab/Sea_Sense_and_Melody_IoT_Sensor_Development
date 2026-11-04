/**
 * @file main_camera.c
 * @brief Sensor Box main loop with camera HSV support (libcamera).
 *
 * Orchestrates periodic sampling of all sensors, processes incoming
 * camera colour cluster messages, receives emotion inference results
 * as plain text strings, and outputs data via CSV, JSONL, LCD, 7‑seg
 * display, and terminal.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026-10-19
 */

/*
 * main_camera.c - Sensor Box main loop with camera HSV support (libcamera)
 * MODIFIED: receive emotion label as string (instead of InferResult struct)
 *           and pass it directly to camera_set_emotion().
 *
 * Author:   KUANG, Haozhe
 * Date:     2026/10/19
 */

#include "sensor_box.h"

#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>

#ifdef __linux__
#  include <gpiod.h>
#endif

#include <mqueue.h>
#include <fcntl.h>
#include <sys/stat.h>

#include "csv_writer.h"
#include "jsonl_writer.h"
#include "lcd1602.h"
#include "light_sensor.h"
#include "mcp3008.h"
#include "seg7_display.h"
#include "sound_sensor.h"
#include "term_print.h"
#include "touch_sensor.h"
#include "camera_sensor.h"

#define TICKS_PER_SECOND 200

static void on_signal(int sig);
static void install_signal_handler(void);
static void lcd_put_line(int row, const char *text);
static void build_snapshot(struct sb_state *st);

time_t g_start_time = 0;
static int g_last_seg_count = -1;
static char g_lcd_line0[17] = "";
static char g_lcd_line1[17] = "";
static volatile sig_atomic_t g_stop = 0;

/* MQ handles */
static mqd_t g_cam_mq_recv   = (mqd_t)-1;
static mqd_t g_infer_mq_recv = (mqd_t)-1;

/**
 * @brief Signal handler for SIGINT/SIGTERM.
 *
 * Sets the global stop flag so the main loop exits cleanly.
 *
 * @param[in] sig Signal number (unused).
 * @return void.
 */
static void on_signal(int sig)
{
    (void)sig;
    g_stop = 1;
}

/**
 * @brief Install signal handlers for graceful shutdown.
 *
 * Registers on_signal() for both SIGINT (Ctrl+C) and SIGTERM.
 *
 * @param None.
 * @return void.
 */
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
 * @brief Update one line of the 16×2 LCD display, avoiding repeated writes.
 *
 * Compares the new text with the previously written line and only sends
 * the update if the content has changed. This reduces I2C traffic.
 *
 * @param[in] row  Row index (0 or 1).
 * @param[in] text Null‑terminated string to display (up to 16 characters).
 * @return void.
 */
static void lcd_put_line(int row, const char *text)
{
    char buf[17];
    snprintf(buf, sizeof(buf), "%-16s", text ? text : "");
    char *cur = (row == 0) ? g_lcd_line0 : g_lcd_line1;
    if (memcmp(cur, buf, 16) == 0)
        return;
    memcpy(cur, buf, 16);
    lcd1602_print_line(row, buf);
}

/**
 * @brief Build a complete snapshot of the current sensor state.
 *
 * Reads all sensor values through their respective accessor functions,
 * obtains the current UTC time, and fills the @p st structure. Called
 * once per second.
 *
 * @param[out] st Pointer to an sb_state structure to populate.
 * @return void.
 */
static void build_snapshot(struct sb_state *st)
{
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);

    static char ts_buf[32];
    strftime(ts_buf, sizeof(ts_buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
    st->ts = ts_buf;

    st->time_of_day       = ((float)tm.tm_hour + (float)tm.tm_min / 60.0f
                           + (float)tm.tm_sec / 3600.0f) / 24.0f;
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

    /* Camera top-3 HSV */
    st->cam_top_count = camera_get_top_count();
    st->cam_top1_h    = camera_get_top_h(0);
    st->cam_top1_s    = camera_get_top_s(0);
    st->cam_top1_v    = camera_get_top_v(0);
    st->cam_top1_ratio = camera_get_top_ratio(0);
    st->cam_top2_h    = camera_get_top_h(1);
    st->cam_top2_s    = camera_get_top_s(1);
    st->cam_top2_v    = camera_get_top_v(1);
    st->cam_top2_ratio = camera_get_top_ratio(1);
    st->cam_top3_h    = camera_get_top_h(2);
    st->cam_top3_s    = camera_get_top_s(2);
    st->cam_top3_v    = camera_get_top_v(2);
    st->cam_top3_ratio = camera_get_top_ratio(2);

    /* MODIFIED: copy emotion label string instead of assigning int */
    const char *label = camera_get_emotion_label();
    if (label) {
        strncpy(st->emotion_label, label, sizeof(st->emotion_label) - 1);
        st->emotion_label[sizeof(st->emotion_label) - 1] = '\0';
    } else {
        st->emotion_label[0] = '\0';
    }
    st->emotion_conf  = camera_get_emotion_conf();
}

/**
 * @brief Program entry point.
 *
 * Initialises all hardware peripherals, opens inter‑process message queues,
 * enters the main control loop running at 200 Hz, and performs cleanup on
 * shutdown.
 *
 * The main loop:
 *   1. Samples light and sound sensors once per second.
 *   2. Runs the touch sensor tick every 5 ms.
 *   3. Updates the 7‑segment display when the touch count changes.
 *   4. Drains camera and inference message queues.
 *   5. Once per second, updates features, refreshes the LCD, builds a
 *      snapshot, and writes to CSV, JSONL, and terminal.
 *
 * @param None.
 * @return int Exit status (0 on normal exit).
 */
int main(void)
{
    fprintf(stdout, "Sensor Box 2.3.5 starting...\n");
    fflush(stdout);

    install_signal_handler();
    g_start_time = time(NULL);

    seg5641bs_init();
    mcp3008_init_default();
    lcd1602_init(LCD_I2C_ADDR);
    light_sensor_sample();
    sound_init();
    touch_sensor_init();

    if (ENABLE_CAMERA) {
        if (camera_init() != 0) {
            fprintf(stderr, "Warning: camera unavailable, continuing without video\n");
        }
    }

    /* Open camera MQ (wait for camera_sensor to create it) */
    do {
        g_cam_mq_recv = mq_open(CAM_MQ_NAME, O_RDONLY | O_NONBLOCK);
        if (g_cam_mq_recv == (mqd_t)-1) {
            if (errno == ENOENT) {
                fprintf(stderr, "Waiting for camera queue...\n");
                sleep(1);
            } else {
                perror("mq_open cam recv");
                break;
            }
        }
    } while (g_cam_mq_recv == (mqd_t)-1);

    /* Inference MQ – now receives plain text strings (max 63 chars + null) */
    mq_unlink(INFER_MQ_NAME);
    struct mq_attr infer_attr;
    infer_attr.mq_flags   = 0;
    infer_attr.mq_maxmsg  = INFER_MQ_MAXMSG;
    infer_attr.mq_msgsize = 64;          /* enough for a label string */
    infer_attr.mq_curmsgs = 0;
    g_infer_mq_recv = mq_open(INFER_MQ_NAME, O_CREAT | O_RDONLY | O_NONBLOCK,
                              0644, &infer_attr);
    if (g_infer_mq_recv == (mqd_t)-1) {
        perror("mq_open infer recv");
    }

    seg5641bs_show_number(0);
    fprintf(stdout, "Started. Press Ctrl+C to exit.\n");
    fflush(stdout);

    unsigned long tick = 0;

    while (!g_stop) {

        /* ---- Phase 1: Sample light/sound once per second ---- */
        if (tick % TICKS_PER_SECOND == 0) {
            light_sensor_sample();
            sound_sample();
        }

        /* ---- Phase 2: Touch detector tick (runs every 5ms) ---- */
        touch_sensor_tick();

        /* ---- Phase 3: 7-seg display update on change ---- */
        int tc = touch_sensor_get_count();
        if (tc != g_last_seg_count) {
            seg5641bs_show_number(tc);
            g_last_seg_count = tc;
        }

        /* ---- Phase 4: Per-tick MQ drain ---- */
        /* Drain camera MQ */
        if (g_cam_mq_recv != (mqd_t)-1) {
            CamMessage cam_msg;
            ssize_t rlen = mq_receive(g_cam_mq_recv, (char*)&cam_msg,
                                      sizeof(cam_msg), NULL);
            if (rlen == sizeof(CamMessage)) {
                /* Already handled by accessors; this just drains queue */
            } else if (rlen == -1 && errno != EAGAIN) {
                perror("mq_receive cam");
            }
        }

        /* Receive inference result as a plain string (real-time, every tick) */
        if (g_infer_mq_recv != (mqd_t)-1) {
            char label_buf[64];
            ssize_t rlen = mq_receive(g_infer_mq_recv, label_buf, sizeof(label_buf), NULL);
            if (rlen > 0) {
                label_buf[rlen] = '\0';               /* ensure null termination */
                /* Remove trailing newline if present */
                size_t len = strlen(label_buf);
                if (len > 0 && label_buf[len-1] == '\n')
                    label_buf[len-1] = '\0';

                /* Update camera overlay with the received label.
                 * Confidence is not transmitted in this simple string mode;
                 * we keep the previous confidence or set to 0.0f.
                 * You can also parse "label|confidence" format if needed.
                 */
                camera_set_emotion(label_buf, 0.0f);
            } else if (rlen == -1 && errno != EAGAIN) {
                perror("mq_receive infer");
            }
        }

        /* ---- Phase 5: Once per second, full update ---- */
        if (tick % TICKS_PER_SECOND == 0) {
            light_sensor_update_features();
            sound_update_features();
            touch_sensor_update_features();

            if (ENABLE_CAMERA) {
                camera_sample();  /* triggers SDL update */
            }

            camera_set_window_title();

            /* LCD lines */
            char line0[17];
            snprintf(line0, sizeof(line0), "Touch:%4d %s", tc,
                     sound_get_human_presence() ? "ON " : "off");
            lcd_put_line(0, line0);

            int _raw = light_get_raw();
            int _sp  = sound_get_spike();
            int _e100 = (int)(sound_get_energy() * 100.0f);
            char line1[17];
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
            fflush(stdout);
        }

        tick++;
        struct timespec ts = { 0, 5000000 };
        nanosleep(&ts, NULL);
    }

    /* ---- Cleanup ---- */
    fprintf(stdout, "\nShutting down...\n");
    fflush(stdout);

    csv_writer_close();
    jsonl_writer_close();
    touch_sensor_close();
    sound_close();
    lcd1602_close();
    seg5641bs_clear();
    seg5641bs_close();

    if (ENABLE_CAMERA) {
        camera_close();
    }

    if (g_infer_mq_recv != (mqd_t)-1) {
        mq_close(g_infer_mq_recv);
        mq_unlink(INFER_MQ_NAME);
    }
    if (g_cam_mq_recv != (mqd_t)-1) {
        mq_close(g_cam_mq_recv);
    }

    if (g_seg_chip) {
        gpiod_chip_close(g_seg_chip);
        g_seg_chip = NULL;
    }

    mcp3008_close();
    fprintf(stdout, "Bye.\n");
    return 0;
}
