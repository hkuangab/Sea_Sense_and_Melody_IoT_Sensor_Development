/**
 * @file jsonl_writer.h
 * @brief JSON Lines (JSONL) append‑only writer.
 *
 * Emits one JSON object per line. Unlike the CSV writer, the values are
 * grouped into light, sound, and touch sub‑objects, which makes the
 * stream easier to consume from a document store or a log pipeline.
 *
 * Buffering is disabled for the same reason as in the CSV writer.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/17 (updated: added camera HSV fields)
 */

/*
 * jsonl_writer.h - JSON Lines (JSONL) append-only writer
 *
 * Emits one JSON object per line. Unlike the CSV writer, the values are
 * grouped into light, sound, and touch sub-objects, which makes the
 * stream easier to consume from a document store or a log pipeline.
 *
 * Buffering is disabled for the same reason as in the CSV writer.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/17 (updated: added camera HSV fields)
 */

#ifndef JSONL_WRITER_H
#define JSONL_WRITER_H

#include "sensor_box.h"

/**
 * @brief Append one JSON object to the output stream.
 *
 * Opens the file on the first call if it is not already open.
 * Each call writes exactly one line containing a complete JSON object.
 *
 * @param[in] st The snapshot to serialise. Must not be NULL.
 * @return void.
 */
void jsonl_writer_append(const struct sb_state *st);

/**
 * @brief Flush and close the JSONL file.
 *
 * Safe to call when the file is already closed; does nothing in that case.
 *
 * @param None.
 * @return void.
 */
void jsonl_writer_close(void);

#endif /* JSONL_WRITER_H */
