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

/** Default SPI device node, i.e. SPI bus 0, chip select 0. */
#define MCP3008_DEV     "/dev/spidev0.0"

/** Clock speed in Hz. The MCP3008 datasheet allows up to 3.6 MHz at
 *  5 V; 1 MHz is conservative and avoids signal-integrity issues on
 *  the prototype's jumper wires. */
#define MCP3008_SPEED   1000000

/** SPI mode: CPOL=0, CPHA=0. */
#define MCP3008_MODE    0

/** Bits per word, fixed at 8 by the ioctl configuration. */
#define MCP3008_BPW     8

/** ADC resolution expressed as the maximum readable value, i.e. 2^10 - 1. */
#define MCP3008_RES     1023

/** Channel 0: light-dependent resistor (voltage divider output). */
#define MCP_CH_LIGHT    0

/** Channel 1: microphone analogue output. */
#define MCP_CH_SOUND    1

/**
 * @brief Initialise the ADC using the default device path.
 * @return 0 on success, -1 on failure. A failure message suggesting the
 *         use of sudo is printed to stderr.
 */
int  mcp3008_init_default(void);

/**
 * @brief Initialise the ADC using an explicit device path.
 *
 * @param[in] devpath Path to the spidev node, e.g. "/dev/spidev0.0".
 * @return 0 on success, -1 on failure.
 */
int  mcp3008_init(const char *devpath);

/**
 * @brief Read one sample from a single-ended input channel.
 *
 * @param[in] ch Channel number, 0..7.
 * @return The converted value, 0..1023, or -1 if the device is not open
 *         or @p ch is out of range.
 */
int  mcp3008_read_channel(int ch);

/**
 * @brief Close the SPI device.
 *
 * Safe to call when the device is already closed.
 */
void mcp3008_close(void);

#endif /* MCP3008_H */
