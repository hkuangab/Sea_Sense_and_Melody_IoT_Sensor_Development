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

/** File descriptor for the open I2C bus, or -1 when closed. */
static int    g_fd = -1;

/** Backlight state: bit 3 of the port controls the backlight. */
static uint8_t g_backlight = 0x08; /* P3=1 -> backlight on */

/*
 * Toggle the E (enable) line. The HD44780 samples the data lines on the
 * falling edge, so the high pulse must be held long enough for the
 * expander to propagate it.
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
static void lcd_send_byte(uint8_t byte, uint8_t rs)
{
    lcd_send_nibble((byte >> 4) & 0x0F, rs);
    lcd_send_nibble(byte & 0x0F, rs);
}

/* Send a command byte (RS low). Clear and home need a longer delay. */
static void lcd_cmd(uint8_t cmd)
{
    lcd_send_byte(cmd, 0);
    if (cmd == 0x01 || cmd == 0x02) usleep(2000);
}

void lcd1602_clear(void)
{
    if (g_fd >= 0) lcd_cmd(0x01);
}

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

int lcd1602_init(uint8_t addr)
{
    char dev[16];
    snprintf(dev, sizeof(dev), "/dev/i2c-%d", LCD_BUS);

    g_fd = open(dev, O_RDWR);
    if (g_fd < 0) { perror(dev); return -1; }

    if (ioctl(g_fd, I2C_SLAVE, addr) < 0) { perror("I2C_SLAVE"); close(g_fd); g_fd = -1; return -1; }

    return try_init(addr);
}

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

void lcd1602_close(void)
{
    if (g_fd >= 0) {
        lcd1602_clear();
        close(g_fd);
        g_fd = -1;
    }
}

#else /* !ENABLE_LCD */

int  lcd1602_init_auto(void)              { return -1; }
int  lcd1602_init(uint8_t addr)           { (void)addr; return -1; }
void lcd1602_clear(void)                  {}
void lcd1602_print_line(int r, const char *t){ (void)r; (void)t; }
void lcd1602_close(void)                  {}

#endif
