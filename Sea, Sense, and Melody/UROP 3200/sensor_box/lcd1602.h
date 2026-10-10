/*
 * lcd1602.h - LCD1602 driver over I2C (PCF8574 backpack)
 *
 * Drives a standard HD44780-compatible 16x2 character LCD through a
 * PCF8574 I/O expander on the I2C bus. Uses 4-bit mode: the expander's
 * lower four bits carry the LCD data lines D4-D7 and the upper four
 * carry RS, RW, E, and the backlight control.
 *
 * The address of the expander varies by board revision; lcd1602_init_auto
 * probes a built-in list rather than assuming 0x27.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef LCD1602_H
#define LCD1602_H

#include <stddef.h>
#include <stdint.h>

/** I2C bus number, i.e. /dev/i2c-1. */
#define LCD_BUS         1

/** Most common PCF8574 address for LCD backpacks. */
#define LCD_I2C_ADDR    0x27

/** Number of visible columns on the display. */
#define LCD_COLS        16

/** Number of rows on the display. */
#define LCD_ROWS        2

/** @name Initialisation */
/**@{*/

/**
 * @brief Probe a list of likely I2C addresses and initialise the first
 *        one that responds.
 *
 * @return 0 on success, -1 if no device was found or the bus could not
 *         be opened.
 */
int  lcd1602_init_auto(void);

/**
 * @brief Initialise the LCD at a specific I2C address.
 *
 * @param[in] addr The 7-bit I2C address of the PCF8574 backpack.
 * @return 0 on success, -1 on failure.
 */
int  lcd1602_init(uint8_t addr);

/** @} */

/** @name Display control */
/**@{*/

/** Clear the display and return the cursor to the home position. */
void lcd1602_clear(void);

/**
 * @brief Write a 16-character string to one row of the display.
 *
 * Shorter strings are padded with spaces. Longer strings are truncated
 * to LCD_COLS characters.
 *
 * @param[in] row   Row index: 0 for the top row, 1 for the bottom.
 * @param[in] text  The text to write. May be NULL, in which case a row
 *                  of spaces is written.
 */
void lcd1602_print_line(int row, const char *text);

/** @} */

/** Release the I2C file descriptor and clear the display. */
void lcd1602_close(void);

#endif /* LCD1602_H */
