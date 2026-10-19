/**
 * @file jsonl_writer.c
 * @brief Implementation of the JSON Lines (JSONL) writer.
 *
 * Writes sensor_box.jsonl one JSON object per second. The file is opened
 * in append mode on the first call. Each line is a self‑contained JSON
 * object with nested structures for light, sound, touch, camera, and
 * emotion data. Buffering is disabled to minimise data loss on crash.
 *
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date:   2026-10-19
 */

/*
 * jsonl_writer.c — writes sensor_box.jsonl one JSON object per second
 *
 * Author: KUANG, Haozhe (HKUST)
 * Date:   2026-10-19
 */

#include "sensor_box.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define JSONL_FILE "sensor_box.jsonl"

/** @brief File pointer for the JSONL output file. NULL when not open. */
static FILE *g_jsonl = NULL;

/**
 * @brief Append one JSON object to the output stream.
 *
 * Opens the file on the first call if it is not already open. Writes a
 * single line containing a complete JSON object with all snapshot fields.
 * The file is flushed immediately after writing.
 *
 * @param[in] st Pointer to the snapshot structure to serialise.
 *               Must not be NULL.
 * @return void.
 */
void jsonl_writer_append(const struct sb_state *st)
{
    if (!g_jsonl) {
        g_jsonl = fopen(JSONL_FILE, "a");
        if (!g_jsonl) {
            fprintf(stderr, "ERROR: cannot open %s: %s\n", JSONL_FILE, strerror(errno));
            return;
        }
    }

    /* Write one JSON line */
    fprintf(g_jsonl,
        "{"
        "\"ts\":\"%s\","
        "\"time_of_day\":%.6f,"
        "\"day_of_week\":%d,"
        "\"session_elapsed\":%d,"
        "\"light\":{"
            "\"raw\":%d,"
            "\"brightness\":%.4f,"
            "\"trend\":%+.2f,"
            "\"variance\":%.4f,"
            "\"is_daylight\":%d,"
            "\"flicker_freq\":%.1f"
        "},"
        "\"sound\":{"
            "\"raw\":%d,"
            "\"energy\":%.4f,"
            "\"speech_rate\":%.4f,"
            "\"continuity\":%.4f,"
            "\"spike\":%d,"
            "\"human_presence\":%d"
        "},"
        "\"touch\":{"
            "\"irq\":%d,"
            "\"count\":%d,"
            "\"freq\":%.3f,"
            "\"pattern\":\"%s\","
            "\"intent\":%.1f"
        "},"
        "\"camera\":{"
            "\"top_count\":%d,"
            "\"top1\":{\"h\":%d,\"s\":%d,\"v\":%d,\"ratio\":%.4f},"
            "\"top2\":{\"h\":%d,\"s\":%d,\"v\":%d,\"ratio\":%.4f},"
            "\"top3\":{\"h\":%d,\"s\":%d,\"v\":%d,\"ratio\":%.4f}"
        "},"
        "\"emotion\":{"
            /* MODIFIED: label is now a string */
            "\"label\":\"%s\","
            "\"confidence\":%.4f"
        "}"
        "}\n",

        st->ts ? st->ts : "",
        st->time_of_day,
        st->day_of_week,
        st->session_elapsed,

        st->light_raw,
        st->light_brightness,
        st->light_trend,
        st->light_variance,
        st->light_is_daylight,
        st->light_flicker_freq,

        st->sound_raw,
        st->sound_energy,
        st->sound_speech_rate,
        st->sound_continuity,
        st->sound_spike,
        st->sound_human_presence,

        st->touch_irq,
        st->touch_count,
        st->touch_freq,
        st->touch_pattern ? st->touch_pattern : "",
        st->touch_intent,

        st->cam_top_count,
        st->cam_top1_h, st->cam_top1_s, st->cam_top1_v, st->cam_top1_ratio,
        st->cam_top2_h, st->cam_top2_s, st->cam_top2_v, st->cam_top2_ratio,
        st->cam_top3_h, st->cam_top3_s, st->cam_top3_v, st->cam_top3_ratio,

        st->emotion_label,   /* now a string */
        st->emotion_conf
    );

    fflush(g_jsonl);
}

/**
 * @brief Flush and close the JSONL file.
 *
 * Closes the underlying file stream and sets the global file pointer to
 * NULL. Safe to call multiple times; subsequent calls do nothing.
 *
 * @param None.
 * @return void.
 */
void jsonl_writer_close(void)
{
    if (g_jsonl) {
        fclose(g_jsonl);
        g_jsonl = NULL;
    }
}
