/*
 * csv_writer.c - implementation of the append-only CSV writer
 *
 * See csv_writer.h for the full interface documentation.
 *
 * The column order is fixed and is documented in docs/API.md. Any
 * change to either the header or the format string must be reflected
 * there, and ideally in the JSONL writer as well, so that the two
 * output streams remain comparable.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "csv_writer.h"
#include "sensor_box.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/** Open file handle, or NULL when the file has not been opened yet. */
static FILE *g_fp = NULL;

/** Output file path. Kept as a static so that the call sites stay clean. */
static const char *g_path = "sensor_box.csv";

/** Set to 1 once the header has been written. */
static int g_header_written = 0;

/** @brief Write the CSV header row. */
static void write_header(void)
{
    if (!g_fp) return;
    fprintf(g_fp,
        "ts,time_of_day,day_of_week,session_elapsed,"
        "light_raw,light_brightness,light_trend,light_variance,light_is_daylight,light_flicker_freq,"
        "sound_raw,sound_energy,sound_speech_rate,sound_continuity,sound_spike,sound_human_presence,"
        "touch_irq,touch_count,touch_freq,touch_pattern,touch_intent\n");
    fflush(g_fp);
    g_header_written = 1;
}

void csv_writer_append(const struct sb_state *st)
{
    if (!g_fp) {
        g_fp = fopen(g_path, "a");
        if (!g_fp) { perror("csv_writer: fopen"); return; }
        /* No buffering: a crash or power loss must not lose more than
         * the current row, and must never corrupt earlier rows. */
        setvbuf(g_fp, NULL, _IONBF, 0);
        if (!g_header_written) write_header();
    }

    fprintf(g_fp,
        "%s,%.4f,%d,%d,"
        "%d,%.4f,%.6f,%.6f,%d,%d,"
        "%d,%.4f,%.4f,%.4f,%d,%d,"
        "%d,%d,%.4f,%s,%.1f\n",
        st->ts,
        st->time_of_day, st->day_of_week, st->session_elapsed,
        st->light_raw, st->light_brightness, st->light_trend,
        st->light_variance, st->light_is_daylight, st->light_flicker_freq,
        st->sound_raw, st->sound_energy, st->sound_speech_rate,
        st->sound_continuity, st->sound_spike, st->sound_human_presence,
        st->touch_irq, st->touch_count, st->touch_freq,
        st->touch_pattern, st->touch_intent);
}

void csv_writer_close(void)
{
    if (g_fp) { fclose(g_fp); g_fp = NULL; }
}
