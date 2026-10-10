/*
 * jsonl_writer.c - implementation of the JSONL writer
 *
 * See jsonl_writer.h for the full interface documentation.
 *
 * The output is a single line per call, with no embedded newlines, so
 * that standard line-oriented tools (awk, jq, tail -f) can process it.
 * The schema mirrors the CSV column layout field for field.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "jsonl_writer.h"
#include "sensor_box.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static FILE *g_fp = NULL;
static const char *g_path = "sensor_box.jsonl";

void jsonl_writer_append(const struct sb_state *st)
{
    if (!g_fp) {
        g_fp = fopen(g_path, "a");
        if (!g_fp) { perror("jsonl_writer: fopen"); return; }
        setvbuf(g_fp, NULL, _IONBF, 0);
    }

    fprintf(g_fp,
        "{"
        "\"ts\":\"%s\","
        "\"time_of_day\":%.4f,"
        "\"day_of_week\":%d,"
        "\"session_elapsed\":%d,"
        "\"light\":{"
            "\"raw_adc\":%d,\"brightness\":%.4f,\"trend\":%.6f,"
            "\"variance\":%.6f,\"is_daylight\":%d,\"flicker_freq\":%d"
        "},"
        "\"sound\":{"
            "\"raw_adc\":%d,\"energy\":%.4f,\"speech_rate\":%.4f,"
            "\"continuity\":%.4f,\"sudden_spike\":%d,\"human_presence\":%d"
        "},"
        "\"touch\":{"
            "\"irq\":%d,\"count_60s\":%d,\"freq\":%.4f,"
            "\"pattern\":\"%s\",\"intent\":%.1f"
        "}"
        "}\n",
        st->ts,
        st->time_of_day, st->day_of_week, st->session_elapsed,
        st->light_raw, st->light_brightness, st->light_trend,
        st->light_variance, st->light_is_daylight, st->light_flicker_freq,
        st->sound_raw, st->sound_energy, st->sound_speech_rate,
        st->sound_continuity, st->sound_spike, st->sound_human_presence,
        st->touch_irq, st->touch_count, st->touch_freq,
        st->touch_pattern, st->touch_intent);
}

void jsonl_writer_close(void)
{
    if (g_fp) { fclose(g_fp); g_fp = NULL; }
}
