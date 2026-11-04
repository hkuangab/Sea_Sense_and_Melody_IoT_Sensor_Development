/**
 * @file csv_writer.h
 * @brief Append‑only CSV file writer.
 *
 * Opens the output file in append mode, writes the header on the first
 * call, and appends one row per snapshot thereafter. Buffering is
 * disabled so that a power failure loses at most the current row.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/17 (updated: added camera HSV columns)
 */

/*
 * csv_writer.h - append-only CSV file writer
 *
 * Opens the output file in append mode, writes the header on the first
 * call, and appends one row per snapshot thereafter. Buffering is
 * disabled so that a power failure loses at most the current row.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/17 (updated: added camera HSV columns)
 */

#ifndef CSV_WRITER_H
#define CSV_WRITER_H

#include "sensor_box.h"

/**
 * @brief Append one row to the CSV file.
 *
 * Opens the file on the first call if it is not already open, and writes
 * the header row at that point. Subsequent calls append data rows only.
 *
 * @param[in] st The snapshot to serialise. Must not be NULL.
 * @return void.
 */
void csv_writer_append(const struct sb_state *st);

/**
 * @brief Flush and close the CSV file.
 *
 * Safe to call when the file is already closed; does nothing in that case.
 *
 * @param None.
 * @return void.
 */
void csv_writer_close(void);

#endif /* CSV_WRITER_H */
