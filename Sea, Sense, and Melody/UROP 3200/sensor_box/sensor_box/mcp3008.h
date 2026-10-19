/**
 * @file mcp3008.h
 * @brief Driver for the MCP3008 10‑bit SPI analogue‑to‑digital converter.
 *
 * Provides initialisation, single‑channel read, and close routines.
 * The driver communicates over /dev/spidev using Linux SPI ioctls.
 * Configuration: mode 0, 8 bits per word, 1 MHz clock.
 *
 * Channels:
 *   - 0 : light‑dependent resistor (LDR)
 *   - 1 : microphone analogue output
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * mcp3008.h - driver for the MCP3008 10-bit SPI analogue-to-digital converter
 *
 * Communicates with the converter over /dev/spidev using the standard
 * Linux SPI ioctls. Configured for mode 0, 8 bits per word, and 1 MHz.
 * Eight single-ended channels are available; this project uses channel 0
 * for the light-dependent resistor and channel 1 for the microphone.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef MCP3008_H
#define MCP3008_H

#include <stddef.h>
#include <stdint.h>

/** @brief Default SPI device node (bus 0, chip select 0). */
#define MCP3008_DEV     "/dev/spidev0.0"

/**
 * @brief SPI clock speed in Hz.
 *
 * The MCP3008 datasheet permits up to 3.6 MHz at 5 V; 1 MHz is used
 * conservatively to avoid signal‑integrity problems on prototype wiring.
 */
#define MCP3008_SPEED   1000000

/** @brief SPI mode: CPOL = 0, CPHA = 0. */
#define MCP3008_MODE    0

/** @brief Bits per word (fixed at 8 by the ioctl configuration). */
#define MCP3008_BPW     8

/**
 * @brief Maximum ADC value (2^10 − 1).
 *
 * Used for normalising raw readings to a [0.0, 1.0] range.
 */
#define MCP3008_RES     1023

/** @brief Channel 0: light‑dependent resistor (voltage divider output). */
#define MCP_CH_LIGHT    0

/** @brief Channel 1: microphone analogue output. */
#define MCP_CH_SOUND    1

/**
 * @brief Initialise the ADC using the default device path (@ref MCP3008_DEV).
 *
 * @return 0 on success, -1 on failure. On failure a diagnostic message
 *         (including a suggestion to run with sudo) is printed to stderr.
 */
int  mcp3008_init_default(void);

/**
 * @brief Initialise the ADC using an explicit device path.
 *
 * Opens the specified spidev node, configures mode, bits per word, and
 * speed via ioctl calls.
 *
 * @param[in] devpath  Path to the spidev node, e.g. "/dev/spidev0.0".
 * @return 0 on success, -1 on failure (details printed to stderr).
 */
int  mcp3008_init(const char *devpath);

/**
 * @brief Read one sample from a single‑ended input channel.
 *
 * Sends a three‑byte SPI transaction according to the MCP3008 protocol:
 * start bit, single‑ended flag, channel address, then dummy byte.
 * The 10‑bit result is reconstructed from the returned bytes.
 *
 * @param[in] ch  Channel number, 0…7.
 * @return The converted value (0 … @ref MCP3008_RES), or -1 if the
 *         device is not open or @p ch is out of range.
 */
int  mcp3008_read_channel(int ch);

/**
 * @brief Close the SPI device.
 *
 * Closes the file descriptor and resets the internal handle. It is safe
 * to call when the device is already closed (no operation performed).
 */
void mcp3008_close(void);

#endif /* MCP3008_H */
