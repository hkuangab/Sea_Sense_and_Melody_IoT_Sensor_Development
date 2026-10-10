/*
 * term_print.h - human-readable summary printer
 *
 * Prints one line to stdout summarising the current state of all three
 * sensors. Intended for interactive use; for archival or programmatic
 * consumption use the CSV or JSONL writers instead.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef TERM_PRINT_H
#define TERM_PRINT_H

/**
 * @brief Print a one-line summary of the current sensor state.
 *
 * The line is prefixed with an ISO 8601 UTC timestamp and the session
 * uptime in seconds.
 */
void term_print_all(void);

#endif /* TERM_PRINT_H */
