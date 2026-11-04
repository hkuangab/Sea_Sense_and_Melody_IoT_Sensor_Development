/**
 * @file csv_writer.c
 * @brief Implementation of the CSV file writer.
 *
 * Writes sensor_box.csv one row per second. The file is opened in append
 * mode; the header row is written only when the file is empty. All data
 * rows are flushed immediately after writing.
 *
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date:   2026-10-19
 */

/*
 * csv_writer.c — writes sensor_box.csv one row per second
 *
 * Author: KUANG, Haozhe (HKUST)
 * Date:   2026-10-19
 */

#include "sensor_box.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#define CSV_FILE "sensor_box.csv"

/** @brief File pointer for the CSV output file. NULL when not open. */
static FILE *g_csv = NULL;

/** @brief Non‑zero after the header row has been written. */
static int   g_header_written = 0;

/* Column headers – must match struct sb_state field order exactly */
static const char *COLUMN_HEADERS[] = {
    "ts",
    "time_of_day",
    "day_of_week",
    "session_elapsed",
    "light_raw",
    "light_brightness",
    "light_trend",
    "light_variance",
    "light_is_daylight",
    "light_flicker_freq",
    "sound_raw",
    "sound_energy",
    "sound_speech_rate",
    "sound_continuity",
    "sound_spike",
    "sound_human_presence",
    "touch_irq",
    "touch_count",
    "touch_freq",
    "touch_pattern",
    "touch_intent",
    "cam_top_count",
    "cam_top1_h",
    "cam_top1_s",
    "cam_top1_v",
    "cam_top1_ratio",
    "cam_top2_h",
    "cam_top2_s",
    "cam_top2_v",
    "cam_top2_ratio",
    "cam_top3_h",
    "cam_top3_s",
    "cam_top3_v",
    "cam_top3_ratio",
    "emotion_label",
    "emotion_conf"
};

#define NUM_COLS (sizeof(COLUMN_HEADERS) / sizeof(COLUMN_HEADERS[0]))

/* ---------- Helper: write a single quoted string ---------- */

/**
 * @brief Write a string to the CSV file enclosed in double quotes,
 *        escaping any embedded double‑quote characters by doubling them.
 *
 * @param[in] fp  Output file stream.
 * @param[in] s   Null‑terminated string to write. May be NULL (then writes
 *                an empty quoted string).
 * @return void.
 */
static void write_quoted_string(FILE *fp, const char *s)
{
    fputc('"', fp);
    while (*s) {
        if (*s == '"')
            fputs("\"\"", fp);
        else
            fputc(*s, fp);
        s++;
    }
    fputc('"', fp);
}

/* ---------- Public API ---------- */

/**
 * @brief Append one row to the CSV file.
 *
 * Opens the file on the first call if it is not already open, and writes
 * the header row at that point (if the file was empty). Subsequent calls
 * append data rows only. Each row contains all fields from the snapshot
 * structure in the order defined by COLUMN_HEADERS.
 *
 * @param[in] st Pointer to the snapshot structure to serialise.
 *               Must not be NULL.
 * @return void.
 */
void csv_writer_append(const struct sb_state *st)
{
    if (!g_csv) {
        g_csv = fopen(CSV_FILE, "a");
        if (!g_csv) {
            fprintf(stderr, "ERROR: cannot open %s: %s\n", CSV_FILE, strerror(errno));
            return;
        }
        fseek(g_csv, 0, SEEK_END);
        long sz = ftell(g_csv);
        if (sz == 0) {
            g_header_written = 0;
        } else {
            g_header_written = 1;
        }
    }

    if (!g_header_written) {
        for (size_t i = 0; i < NUM_COLS; i++) {
            if (i > 0) fputc(',', g_csv);
            fputs(COLUMN_HEADERS[i], g_csv);
        }
        fputc('\n', g_csv);
        fflush(g_csv);
        g_header_written = 1;
    }

    /* Write data row */
    write_quoted_string(g_csv, st->ts ? st->ts : "");

    fprintf(g_csv, ",%.6f",   st->time_of_day);
    fprintf(g_csv, ",%d",     st->day_of_week);
    fprintf(g_csv, ",%d",     st->session_elapsed);

    fprintf(g_csv, ",%d",     st->light_raw);
    fprintf(g_csv, ",%.4f",   st->light_brightness);
    fprintf(g_csv, ",%+.2f",  st->light_trend);
    fprintf(g_csv, ",%.4f",   st->light_variance);
    fprintf(g_csv, ",%d",     st->light_is_daylight);
    fprintf(g_csv, ",%.1f",   st->light_flicker_freq);

    fprintf(g_csv, ",%d",     st->sound_raw);
    fprintf(g_csv, ",%.4f",   st->sound_energy);
    fprintf(g_csv, ",%.4f",   st->sound_speech_rate);
    fprintf(g_csv, ",%.4f",   st->sound_continuity);
    fprintf(g_csv, ",%d",     st->sound_spike);
    fprintf(g_csv, ",%d",     st->sound_human_presence);

    fprintf(g_csv, ",%d",     st->touch_irq);
    fprintf(g_csv, ",%d",     st->touch_count);
    fprintf(g_csv, ",%.3f",   st->touch_freq);
    fputc(',', g_csv);
    write_quoted_string(g_csv, st->touch_pattern ? st->touch_pattern : "");
    fprintf(g_csv, ",%.1f",   st->touch_intent);

    fprintf(g_csv, ",%d",     st->cam_top_count);
    fprintf(g_csv, ",%d",     st->cam_top1_h);
    fprintf(g_csv, ",%d",     st->cam_top1_s);
    fprintf(g_csv, ",%d",     st->cam_top1_v);
    fprintf(g_csv, ",%.4f",   st->cam_top1_ratio);
    fprintf(g_csv, ",%d",     st->cam_top2_h);
    fprintf(g_csv, ",%d",     st->cam_top2_s);
    fprintf(g_csv, ",%d",     st->cam_top2_v);
    fprintf(g_csv, ",%.4f",   st->cam_top2_ratio);
    fprintf(g_csv, ",%d",     st->cam_top3_h);
    fprintf(g_csv, ",%d",     st->cam_top3_s);
    fprintf(g_csv, ",%d",     st->cam_top3_v);
    fprintf(g_csv, ",%.4f",   st->cam_top3_ratio);

    /* MODIFIED: output emotion_label as quoted string */
    fputc(',', g_csv);
    write_quoted_string(g_csv, st->emotion_label);
    fprintf(g_csv, ",%.4f",   st->emotion_conf);

    fputc('\n', g_csv);
    fflush(g_csv);
}

/**
 * @brief Flush and close the CSV file.
 *
 * Closes the underlying file stream and sets the global file pointer to
 * NULL. Safe to call multiple times; subsequent calls do nothing.
 *
 * @param None.
 * @return void.
 */
void csv_writer_close(void)
{
    if (g_csv) {
        fclose(g_csv);
        g_csv = NULL;
    }
}
