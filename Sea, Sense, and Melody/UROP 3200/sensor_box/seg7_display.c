/**
 * @file seg7_display.c
 * @brief Implementation of the 5641BS 7‑segment display driver.
 *
 * See seg7_display.h for the full interface documentation.
 *
 * Scan cycle:
 *   1. Turn every digit off.
 *   2. Set the segment lines for the next digit.
 *   3. Turn that digit on.
 *   4. Wait approximately 2 ms.
 *   5. Turn that digit off.
 *
 * Turning the digits off before changing the segments prevents the
 * previous digit's segments from "ghosting" onto the next one, which
 * was visible at slower scan rates.
 *
 * Performance note: setting the segments currently takes eight
 * individual set_value calls, giving roughly 4000 ioctl calls per
 * second at the default scan rate. For higher scan rates this should
 * be replaced with a single gpiod_line_request_set_values batch call.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * seg7_display.c - implementation of the 5641BS 7-segment driver
 *
 * See seg7_display.h for the full interface documentation.
 *
 * Scan cycle:
 *   1. Turn every digit off.
 *   2. Set the segment lines for the next digit.
 *   3. Turn that digit on.
 *   4. Wait approximately 2 ms.
 *   5. Turn that digit off.
 *
 * Turning the digits off before changing the segments prevents the
 * previous digit's segments from "ghosting" onto the next one, which
 * was visible at slower scan rates.
 *
 * Performance note: setting the segments currently takes eight
 * individual set_value calls, giving roughly 4000 ioctl calls per
 * second at the default scan rate. For higher scan rates this should
 * be replaced with a single gpiod_line_request_set_values batch call.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "seg7_display.h"

#include <gpiod.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

/* ---------- Pin mapping (shares the chip with touch and sound) ---------- */

/*
 * Segment lines: a, b, c, d, e, f, g, dp.
 * Each entry is the BCM GPIO number connected to the corresponding
 * segment of every digit. The mapping was determined from the module
 * silkscreen and verified on the prototype hardware.
 */
static const unsigned int SEG_PINS[8] = {
    12, /* a  pin11 */
    22, /* b  pin7  */
    19, /* c  pin4  */
    16, /* d  pin2  */
    17, /* e  pin1  */
    13, /* f  pin10 */
    20, /* g  pin5  */
    18  /* dp pin3  */
};

/*
 * Digit-select lines: D1 (units), D2 (tens), D3 (hundreds), D4
 * (thousands). On a common-anode module, driving one of these high
 * connects the corresponding digit's common anode to Vcc.
 */
static const unsigned int DIG_PINS[4] = {
    21, /* D1 / units  pin6  */
    23, /* D2 / tens   pin8  */
    24, /* D3 / hundreds pin9  */
    6   /* D4 / thousands pin12 */
};

/*
 * Segment table for a common-anode module, bit order g f e d c b a,
 * where 0 means lit. Covers the digits 0 through 9.
 */
static const uint8_t SEG_CODE[10] = {
    0b11000000, /* 0 */
    0b11111001, /* 1 */
    0b10100100, /* 2 */
    0b10110000, /* 3 */
    0b10011001, /* 4 */
    0b10010010, /* 5 */
    0b10000010, /* 6 */
    0b11111000, /* 7 */
    0b10000000, /* 8 */
    0b10010000  /* 9 */
};

/* ---------- Global state (shared via seg7_display.h) ---------- */

/**
 * @brief Shared gpiod chip handle, opened by seg5641bs_init().
 * Other modules (touch, sound) reuse this pointer.
 */
struct gpiod_chip        *g_seg_chip = NULL;

/**
 * @brief Line request object covering all 12 GPIO lines.
 * NULL until seg5641bs_init() succeeds.
 */
struct gpiod_line_request *g_seg_req = NULL;

/**
 * @brief Handle of the display multiplexing thread.
 */
static pthread_t    g_scan_thread;

/**
 * @brief Flag controlling the scan loop.
 * Set to true by seg5641bs_init(), set to false by seg5641bs_close().
 */
static volatile bool g_running = false;

/**
 * @brief Array of the four digits currently being displayed (units first).
 * Protected by g_disp_mtx.
 */
static uint8_t g_digit[4] = { 0, 0, 0, 0 };

/**
 * @brief Whether each digit position is lit (true) or blanked (false).
 * Used for leading‑zero blanking. Protected by g_disp_mtx.
 */
static bool g_digit_on[4] = { true, true, true, true };

/**
 * @brief Mutex protecting g_digit and g_digit_on against concurrent
 * access by the scan thread and the show_number / decompose functions.
 */
static pthread_mutex_t g_disp_mtx = PTHREAD_MUTEX_INITIALIZER;

/** @cond INTERNAL */
/** @endcond */

/* ---------- Low-level segment and digit control ---------- */

/**
 * @brief Write all eight segment lines from a segment‑code byte.
 *
 * Iterates over SEG_PINS and sets each line to the corresponding bit
 * of the code byte. Bit 0 in the code corresponds to segment 'a', bit 1
 * to 'b', etc. On a common‑anode module, a 0 bit means the segment is
 * lit (active‑low), so the bit value is written directly.
 *
 * @param[in] code  Segment code byte (e.g. 0b11000000 for digit '0').
 * @return void.
 */
static void seg7_set_segments(uint8_t code)
{
    if (!g_seg_req)
        return;

    /* Common-anode encoding: bit 0 in the code means the segment is
     * off, so the value is written directly to the line. */
    for (int i = 0; i < 8; i++) {
        int val = (code >> i) & 1;
        gpiod_line_request_set_value(g_seg_req, SEG_PINS[i], val);
    }
}

/**
 * @brief Turn every digit off.
 *
 * On a common‑anode module, the digit‑select lines are active‑high;
 * writing 0 to all of them deselects every digit.
 *
 * @param None.
 * @return void.
 */
static void seg7_all_dig_off(void)
{
    if (!g_seg_req)
        return;

    for (int i = 0; i < 4; i++)
        gpiod_line_request_set_value(g_seg_req, DIG_PINS[i], 0);
}

/**
 * @brief Turn one digit on.
 *
 * Drives the corresponding digit‑select line high.
 *
 * @param[in] i  Digit index (0 = units, 3 = thousands).
 * @return void.
 */
static void seg7_dig_on(uint8_t i)
{
    if (!g_seg_req || i >= 4)
        return;

    gpiod_line_request_set_value(g_seg_req, DIG_PINS[i], 1);
}

/**
 * @brief Turn one digit off.
 *
 * Drives the corresponding digit‑select line low.
 *
 * @param[in] i  Digit index (0 = units, 3 = thousands).
 * @return void.
 */
static void seg7_dig_off(uint8_t i)
{
    if (!g_seg_req || i >= 4)
        return;

    gpiod_line_request_set_value(g_seg_req, DIG_PINS[i], 0);
}

/*
 * Break a value in [0, 9999] into individual digits and decide which
 * positions should actually be lit. The mutex is held only while
 * copying the result, so the scan thread is not blocked for long.
 */

/**
 * @brief Decompose an integer into digit values and blanking flags.
 *
 * Extracts the four decimal digits of @p val (modulo 10000) and stores
 * them in g_digit[]. Determines which positions should be lit based on
 * leading‑zero blanking: a digit is lit only if the value has a non‑zero
 * digit in that place or if it is the units digit (always lit). The
 * arrays are updated under the protection of g_disp_mtx.
 *
 * @param[in] val  The value to display (clamped to [0, 9999]).
 * @return void.
 */
static void seg7_decompose(int val)
{
    if (val < 0)
        val = 0;
    if (val > 9999)
        val = val % 10000;

    pthread_mutex_lock(&g_disp_mtx);

    int div = 1;
    for (int i = 0; i < 4; i++) {
        g_digit[i] = (val / div) % 10;
        div *= 10;
    }

    /*
     * Leading-zero blanking. A position is lit only when the value has
     * a non-zero digit in that place. The units digit is always lit.
     */
    g_digit_on[3] = (val >= 1000);
    g_digit_on[2] = (val >= 100);
    g_digit_on[1] = (val >= 10);
    g_digit_on[0] = true;

    pthread_mutex_unlock(&g_disp_mtx);
}

/* ---------- Scan thread ---------- */

/**
 * @brief Body of the display multiplexing thread.
 *
 * Runs while g_running is true. Cycles through the four digits:
 *   - Acquires the mutex to read g_digit and g_digit_on.
 *   - Turns all digits off.
 *   - If the current digit is enabled, sets its segment pattern and
 *     turns that digit on.
 *   - Waits ~2 ms (nanosleep).
 *   - Turns that digit off.
 * On exit, leaves the display dark.
 *
 * @param arg  Unused (required by pthread API).
 * @return void* Always NULL.
 */
static void *scan_thread(void *arg)
{
    (void)arg;

    while (g_running) {
        for (int i = 0; i < 4; i++) {
            if (!g_running)
                break;

            pthread_mutex_lock(&g_disp_mtx);
            bool on = g_digit_on[i];
            uint8_t code = SEG_CODE[g_digit[i]];
            pthread_mutex_unlock(&g_disp_mtx);

            /* Blank all digits before changing the segments, to avoid
             * ghosting the previous digit onto this one. */
            seg7_all_dig_off();

            if (on) {
                seg7_set_segments(code);
                seg7_dig_on(i);
            }

            /* One digit lit for ~2 ms -> full cycle ~8 ms -> ~125 Hz. */
            struct timespec ts = { 0, 2000000 };
            nanosleep(&ts, NULL);

            seg7_dig_off(i);
        }
    }

    /* Leave the display dark when the thread exits. */
    seg7_all_dig_off();
    seg7_set_segments(0xFF);

    return NULL;
}

/* ---------- Public interface ---------- */

/**
 * @brief Initialise the display and start the scan thread.
 *
 * Opens /dev/gpiochip0, requests all 12 lines in a single call, blanks
 * the display, and starts the multiplexing thread. Prints an error
 * message and returns early on any failure. Safe to call more than
 * once; subsequent calls will print a warning and return.
 *
 * @param None.
 * @return void.
 */
void seg5641bs_init(void)
{
    if (g_seg_req) {
        fprintf(stderr, "seg7: already initialized\n");
        return;
    }

    g_seg_chip = gpiod_chip_open("/dev/gpiochip0");
    if (!g_seg_chip) {
        perror("seg7: chip open failed");
        return;
    }

    /*
     * Request all 12 lines in one call. Earlier versions passed a
     * count of 1, which left 11 lines unconfigured; touch and sound
     * would then fail when they tried to reuse the handle.
     */
    unsigned int all[12];
    memcpy(all, SEG_PINS, 8 * sizeof(unsigned int));
    memcpy(all + 8, DIG_PINS, 4 * sizeof(unsigned int));

    struct gpiod_line_settings *s = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(s, GPIOD_LINE_DIRECTION_OUTPUT);
    gpiod_line_settings_set_output_value(s, 1);   /* high = segment off */

    struct gpiod_line_config *lc = gpiod_line_config_new();
    gpiod_line_config_add_line_settings(lc, all, 12, s);

    struct gpiod_request_config *rc = gpiod_request_config_new();
    gpiod_request_config_set_consumer(rc, "5641bs");

    g_seg_req = gpiod_chip_request_lines(g_seg_chip, rc, lc);
    if (!g_seg_req) {
        perror("seg7: request lines failed");
        gpiod_chip_close(g_seg_chip);
        g_seg_chip = NULL;
        return;
    }

    /* Start dark. */
    seg7_all_dig_off();
    seg7_set_segments(0xFF);

    g_running = true;
    if (pthread_create(&g_scan_thread, NULL, scan_thread, NULL) != 0) {
        perror("seg7: pthread_create failed");
        g_running = false;
    }

    fprintf(stdout,
            "seg7: init OK (5641BS common-anode, 8 seg + 4 dig, 12 pins)\n");
}

/**
 * @brief Display an unsigned integer on the module.
 *
 * Delegates to seg7_decompose() which extracts the digits and updates
 * the shared arrays. The scan thread picks up the new values on its
 * next cycle.
 *
 * @param[in] val The number to display (clamped to [0, 9999]).
 * @return void.
 */
void seg5641bs_show_number(int val)
{
    seg7_decompose(val);
}

/**
 * @brief Blank the display.
 *
 * Immediately turns all segments off and deselects all digits.
 * Does not affect the internally stored digit values.
 *
 * @param None.
 * @return void.
 */
void seg5641bs_clear(void)
{
    /* Common-anode: segments high = all off, digits low = none selected. */
    seg7_set_segments(0xFF);
    seg7_all_dig_off();
}

/**
 * @brief Stop the scan thread and release the line request.
 *
 * Sets g_running to false, joins the scan thread, then releases the
 * GPIO line request. Does NOT close the chip handle (g_seg_chip); that
 * is the responsibility of main().
 *
 * @param None.
 * @return void.
 */
void seg5641bs_close(void)
{
    g_running = false;

    pthread_join(g_scan_thread, NULL);

    /*
     * Release the request but do not close the chip. The chip is
     * documented as being owned by main(); closing it here would leave
     * touch and sound holding dangling pointers.
     */
    if (g_seg_req) {
        gpiod_line_request_release(g_seg_req);
        g_seg_req = NULL;
    }
}

/**
 * @brief Reserved interface for decimal‑point control.
 *
 * Currently a no‑op: the module displays plain integers and does not
 * use the decimal point. The function is retained so that future
 * extensions (for example a temperature readout) do not need to change
 * the public interface.
 *
 * @param[in] digit_idx  Digit position, 0 = units (ignored).
 * @param[in] on         true to light the point, false to leave it off (ignored).
 * @return void.
 */
void seg7_set_decimal_point(int digit_idx, bool on)
{
    (void)digit_idx;
    (void)on;
    /* Plain-integer display does not use the decimal point. */
}
