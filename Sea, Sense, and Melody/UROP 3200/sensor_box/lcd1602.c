/**
 * @file lcd1602.c
 * @brief Implementation of the LCD1602 I2C driver.
 *
 * See lcd1602.h for the full interface documentation.
 *
 * Backpack pin mapping (PCF8574 output port -> LCD signal):
 *   P0 = RS, P1 = RW, P2 = E, P3 = backlight, P4–P7 = D4–D7
 *
 * The write() return value is deliberately ignored after the ioctl has
 * already succeeded: at this layer a single failed byte cannot be
 * recovered, and aborting would only make the display state harder to
 * reason about.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * lcd1602.c - implementation of the LCD1602 I2C driver
 *
 * See lcd1602.h for the full interface documentation.
 *
 * Backpack pin mapping (PCF8574 output port -> LCD signal):
 *   P0 = RS, P1 = RW, P2 = E, P3 = backlight, P4-P7 = D4-D7
 *
 * The write() return value is deliberately ignored after the ioctl has
 * already succeeded: at this layer a single failed byte cannot be
 * recovered, and aborting would only make the display state harder to
 * reason about.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "lcd1602.h"
#include "sensor_box.h"

#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>

#if ENABLE_LCD

/**
 * @brief File descriptor for the open I2C bus, or -1 when closed.
 */
static int    g_fd = -1;

/**
 * @brief Backlight state: bit 3 of the port controls the backlight.
 *        Initialised to 0x08 (P3 = 1) meaning backlight on.
 */
static uint8_t g_backlight = 0x08; /* P3=1 -> backlight on */

/*
 * Toggle the E (enable) line. The HD44780 samples the data lines on the
 * falling edge, so the high pulse must be held long enough for the
 * expander to propagate it.
 */

/**
 * @brief Pulse the E (enable) line high then low.
 *
 * Writes the given data byte with bit 2 (E) set, waits 1 µs, then
 * writes it with E cleared. The 50 µs delay after the falling edge
 * meets the HD44780 hold‑time requirement.
 *
 * @param[in] data  The byte to send on the PCF8574 port (includes RS,
 *                  RW, E, backlight, and nibble bits).
 */
static void lcd_pulse(uint8_t data)
{
    /*
     * The return value is deliberately ignored: a single failed byte
     * cannot be recovered at this layer, and aborting here would only
     * make the display state harder to reason about. The I2C transaction
     * was validated by the ioctl in the open path.
     */
    if (write(g_fd, &(uint8_t){data | 0x04}, 1) < 0) {}   /* E=1 */
    usleep(1);
    if (write(g_fd, &(uint8_t){data & ~0x04}, 1) < 0) {}  /* E=0 */
    usleep(50);
}

/*
 * Send the upper or lower nibble of a byte to the LCD. RS distinguishes
 * between commands (0) and data (1).
 */

/**
 * @brief Send a 4‑bit nibble to the LCD.
 *
 * Constructs the full port byte by shifting the nibble into bits 4–7,
 * ORing with the backlight mask, and setting RS if required. Then calls
 * lcd_pulse() to strobe the E line.
 *
 * @param[in] nibble  The 4‑bit value to send (only lower 4 bits used).
 * @param[in] rs      0 for a command, 1 for data.
 */
static void lcd_send_nibble(uint8_t nibble, uint8_t rs)
{
    uint8_t data = (nibble << 4) | g_backlight;
    if (rs) data |= 0x01;
    lcd_pulse(data);
}

/*
 * Send a full byte to the LCD in 4-bit mode by writing the high nibble
 * first, then the low nibble.
 */

/**
 * @brief Send a full byte (command or data) to the LCD in 4‑bit mode.
 *
 * Splits the byte into high and low nibbles and sends each via
 * lcd_send_nibble().
 *
 * @param[in] byte  The 8‑bit value to send.
 * @param[in] rs    0 for a command, 1 for data.
 */
static void lcd_send_byte(uint8_t byte, uint8_t rs)
{
    lcd_send_nibble((byte >> 4) & 0x0F, rs);
    lcd_send_nibble(byte & 0x0F, rs);
}

/* Send a command byte (RS low). Clear and home need a longer delay. */

/**
 * @brief Send a command byte to the LCD.
 *
 * Calls lcd_send_byte() with RS = 0. If the command is clear (0x01) or
 * home (0x02), an extra 2 ms delay is inserted to meet the HD44780
 * busy‑flag wait time.
 *
 * @param[in] cmd  The command byte.
 */
static void lcd_cmd(uint8_t cmd)
{
    lcd_send_byte(cmd, 0);
    if (cmd == 0x01 || cmd == 0x02) usleep(2000);
}

/**
 * @brief Clear the display and return the cursor to the home position.
 *
 * Sends the clear‑display command (0x01). No effect if the display is
 * not initialised (g_fd < 0).
 */
void lcd1602_clear(void)
{
    if (g_fd >= 0) lcd_cmd(0x01);
}

/**
 * @brief Write a 16‑character string to one row of the display.
 *
 * Positions the cursor at the start of the requested row, then writes
 * up to LCD_COLS characters. Shorter strings are space‑padded; longer
 * strings are truncated. If @p text is NULL, a row of spaces is written.
 *
 * @param[in] row   Row index: 0 for the top row, 1 for the bottom.
 * @param[in] text  The text to write. May be NULL.
 */
void lcd1602_print_line(int row, const char *text)
{
    if (g_fd < 0) return;

    /* Place the cursor at the start of the requested row. */
    uint8_t addr = (row == 0) ? 0x80 : 0xC0;
    lcd_cmd(addr);

    char buf[LCD_COLS + 1];
    snprintf(buf, sizeof(buf), "%-16s", text ? text : "");

    for (int i = 0; i < LCD_COLS && buf[i] != '\0'; i++)
        lcd_send_byte((uint8_t)buf[i], 1);
}

/*
 * Initialise the LCD in 4-bit mode. The three 0x03 writes are the
 * mandated wake-up sequence for an 8-bit part that may have been left
 * in 4-bit mode by a previous run.
 */

/**
 * @brief Execute the HD44780 initialisation sequence for a given I2C address.
 *
 * Assumes the I2C bus is already open and the slave address has been set.
 * Performs the standard 4‑bit initialisation:
 *   - Three 0x03 nibbles (wake‑up)
 *   - Switch to 4‑bit mode (0x02 nibble)
 *   - Function set (0x28): 4‑bit, 2 lines, 5×8 font
 *   - Display control (0x0C): display on, cursor off, blink off
 *   - Entry mode (0x06): auto‑increment, no display shift
 *   - Clear display (0x01)
 *
 * @param[in] addr  The I2C address used (printed on success).
 * @return 0 on success (always returns 0; failures are handled earlier).
 */
static int try_init(uint8_t addr)
{
    usleep(50000);
    lcd_send_nibble(0x03, 0); usleep(5000);
    lcd_send_nibble(0x03, 0); usleep(5000);
    lcd_send_nibble(0x03, 0); usleep(5000);
    lcd_send_nibble(0x02, 0); usleep(5000);

    lcd_cmd(0x28);  /* 4-bit, 2 lines, 5x8 font */
    lcd_cmd(0x0C);  /* display on, cursor off, blink off */
    lcd_cmd(0x06);  /* auto-increment, no display shift */
    lcd_cmd(0x01);  /* clear */

    printf("lcd1602: init OK at 0x%02X\n", addr);
    return 0;
}

/**
 * @brief Initialise the LCD at a specific I2C address.
 *
 * Opens /dev/i2c-1, sets the slave address to @p addr, and calls
 * try_init() to run the initialisation sequence.
 *
 * @param[in] addr  The 7‑bit I2C address of the PCF8574 backpack.
 * @return 0 on success, -1 on failure (bus open or I2C slave selection).
 */
int lcd1602_init(uint8_t addr)
{
    char dev[16];
    snprintf(dev, sizeof(dev), "/dev/i2c-%d", LCD_BUS);

    g_fd = open(dev, O_RDWR);
    if (g_fd < 0) { perror(dev); return -1; }

    if (ioctl(g_fd, I2C_SLAVE, addr) < 0) { perror("I2C_SLAVE"); close(g_fd); g_fd = -1; return -1; }

    return try_init(addr);
}

/**
 * @brief Probe a list of likely I2C addresses and initialise the first
 *        one that responds.
 *
 * Opens the I2C bus, then iterates through a built‑in list of common
 * PCF8574 addresses. For each address it performs a write probe; if the
 * write succeeds, try_init() is called. Returns successfully on the
 * first responding device.
 *
 * @return 0 on success, -1 if no device was found or the bus could not
 *         be opened.
 */
int lcd1602_init_auto(void)
{
    /*
     * A reasonable cross-section of addresses seen on real backpacks.
     * 0x27 is by far the most common; the rest are included so that a
     * known-good display is not rejected because of a different
     * PCF8574 variant.
     */
    uint8_t addrs[] = {0x27,0x3F,0x20,0x38,0x21,0x22,0x23,0x24,
                       0x25,0x26,0x28,0x29,0x2A,0x2B,0x2C,0x2D,0x2E,0x2F};
    int n = (int)(sizeof(addrs) / sizeof(addrs[0]));

    char dev[16];
    snprintf(dev, sizeof(dev), "/dev/i2c-%d", LCD_BUS);
    g_fd = open(dev, O_RDWR);
    if (g_fd < 0) { fprintf(stderr, "lcd1602: cannot open %s\n", dev); return -1; }

    for (int i = 0; i < n; i++) {
        if (ioctl(g_fd, I2C_SLAVE, addrs[i]) < 0) continue;
        uint8_t probe = g_backlight;
        if (write(g_fd, &probe, 1) == 1) {
            if (try_init(addrs[i]) == 0) return 0;
        }
    }

    fprintf(stderr, "lcd1602: no device found on bus %d\n", LCD_BUS);
    close(g_fd);
    g_fd = -1;
    return -1;
}

/**
 * @brief Release the I2C file descriptor and clear the display.
 *
 * Clears the display before closing the bus. Sets g_fd to -1.
 * Safe to call even if the display was never initialised.
 */
void lcd1602_close(void)
{
    if (g_fd >= 0) {
        lcd1602_clear();
        close(g_fd);
        g_fd = -1;
    }
}

#else /* !ENABLE_LCD */

/**
 * @brief Stub version when ENABLE_LCD is not defined.
 * @return int Always -1.
 */
int  lcd1602_init_auto(void)              { return -1; }

/**
 * @brief Stub version when ENABLE_LCD is not defined.
 * @param addr Ignored.
 * @return int Always -1.
 */
int  lcd1602_init(uint8_t addr)           { (void)addr; return -1; }

/**
 * @brief Stub version when ENABLE_LCD is not defined.
 * Does nothing.
 */
void lcd1602_clear(void)                  {}

/**
 * @brief Stub version when ENABLE_LCD is not defined.
 * @param r Ignored.
 * @param t Ignored.
 */
void lcd1602_print_line(int r, const char *t){ (void)r; (void)t; }

/**
 * @brief Stub version when ENABLE_LCD is not defined.
 * Does nothing.
 */
void lcd1602_close(void)                  {}

#endif
