/*
 * seg7_display.h - 5641BS 4-digit common-anode 7-segment display driver
 *
 * Drives a 5641BS 4-digit 7-segment module over 12 GPIO lines (8
 * segment lines and 4 digit-select lines) using time-division
 * multiplexing. A dedicated scan thread cycles through the digits at
 * roughly 125 Hz, which is well above the flicker-fusion threshold.
 *
 * Polarity: this is a common-anode module. Segment lines are active-low
 * (0 = lit) and digit-select lines are active-high (1 = selected). The
 * previous revision had both polarities inverted, which left every digit
 * selected and produced a distorted readout.
 *
 * IMPORTANT: this module owns the only gpiod chip handle in the system.
 * Other modules that need GPIO must reuse it rather than opening their
 * own, or the requests will conflict.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef SEG7_DISPLAY_H
#define SEG7_DISPLAY_H

#include <stdbool.h>
#include <stdint.h>

/** The shared chip handle. Other modules depend on this. */
struct gpiod_chip;
extern struct gpiod_chip *g_seg_chip;

/**
 * @brief Initialise the display and start the scan thread.
 *
 * Opens /dev/gpiochip0, requests all 12 lines in a single call, blanks
 * the display, and starts the multiplexing thread. Safe to call more
 * than once; subsequent calls will print a warning and return.
 */
void seg5641bs_init(void);

/**
 * @brief Display an unsigned integer on the module.
 *
 * Values outside [0, 9999] are clamped to 0 or wrapped with modulo
 * before display. Leading zeros are blanked, so the value 1 lights
 * only the units digit.
 *
 * @param[in] val The number to display.
 */
void seg5641bs_show_number(int val);

/**
 * @brief Blank the display.
 *
 * On a common-anode module this means driving all segment lines high
 * and all digit-select lines low. The previous revision got this wrong
 * and "clearing" actually turned every segment on.
 */
void seg5641bs_clear(void);

/**
 * @brief Stop the scan thread and release the line request.
 *
 * Does not close the chip handle; that is the responsibility of main().
 */
void seg5641bs_close(void);

/**
 * @brief Reserved interface for decimal-point control.
 *
 * Currently a no-op: the module displays plain integers and does not
 * use the decimal point. The function is retained so that future
 * extensions (for example a temperature readout) do not need to change
 * the public interface.
 *
 * @param[in] digit_idx  Digit position, 0 = units.
 * @param[in] on         true to light the point, false to leave it off.
 */
void seg7_set_decimal_point(int digit_idx, bool on);

#endif /* SEG7_DISPLAY_H */
