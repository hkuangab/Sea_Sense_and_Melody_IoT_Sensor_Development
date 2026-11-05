/**
 * @file lcd1602.h
 * @brief LCD1602 driver over I2C (PCF8574 backpack).
 *
 * Drives a standard HD44780‑compatible 16×2 character LCD through a
 * PCF8574 I/O expander on the I2C bus. Uses 4‑bit mode: the expander's
 * lower four bits carry the LCD data lines D4–D7 and the upper four
 * carry RS, RW, E, and the backlight control.
 *
 * The address of the expander varies by board revision; lcd1602_init_auto
 * probes a built‑in list rather than assuming 0x27.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

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

/** @brief I2C bus number, i.e. /dev/i2c-1. */
#define LCD_BUS         1

/** @brief Most common PCF8574 address for LCD backpacks. */
#define LCD_I2C_ADDR    0x27

/** @brief Number of visible columns on the display. */
#define LCD_COLS        16

/** @brief Number of rows on the display. */
#define LCD_ROWS        2

/** @name Initialisation */
/**@{*/

/**
 * @brief Probe a list of likely I2C addresses and initialise the first
 *        one that responds.
 *
 * Opens the I2C bus (/dev/i2c-1) and iterates through a predefined list
 * of possible PCF8574 addresses. For each address it attempts a write
 * probe; if successful, the LCD initialisation sequence is executed.
 *
 * @return 0 on success, -1 if no device was found or the bus could not
 *         be opened.
 */
int  lcd1602_init_auto(void);

/**
 * @brief Initialise the LCD at a specific I2C address.
 *
 * Opens the I2C bus and sets the slave address to @p addr, then runs
 * the HD44780 4‑bit initialisation sequence.
 *
 * @param[in] addr The 7‑bit I2C address of the PCF8574 backpack.
 * @return 0 on success, -1 on failure (bus open or I2C slave selection).
 */
int  lcd1602_init(uint8_t addr);

/** @} */

/** @name Display control */
/**@{*/

/**
 * @brief Clear the display and return the cursor to the home position.
 *
 * Sends the clear‑display command (0x01). No effect if the display is
 * not initialised.
 */
void lcd1602_clear(void);

/**
 * @brief Write a 16‑character string to one row of the display.
 *
 * Shorter strings are padded with spaces. Longer strings are truncated
 * to LCD_COLS characters. If @p text is NULL, a row of spaces is written.
 *
 * @param[in] row   Row index: 0 for the top row, 1 for the bottom.
 * @param[in] text  The text to write. May be NULL.
 */
void lcd1602_print_line(int row, const char *text);

/** @} */

/**
 * @brief Release the I2C file descriptor and clear the display.
 *
 * Clears the display before closing the bus. Safe to call even if the
 * display was never initialised (no operation performed).
 */
void lcd1602_close(void);

#endif /* LCD1602_H */
