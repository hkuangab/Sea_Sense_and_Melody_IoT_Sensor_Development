/**
 * @file mcp3008.c
 * @brief Implementation of the MCP3008 SPI ADC driver.
 *
 * Implements the functions declared in mcp3008.h. Uses the Linux SPI
 * subsystem (spidev) for communication. The global file descriptor
 * @c g_fd tracks the open device; all read/write operations go through
 * a single SPI transfer structure.
 *
 * Author:   KUANG, Haozhe
 *           The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * mcp3008.c - implementation of the MCP3008 SPI ADC driver
 *
 * See mcp3008.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "mcp3008.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/spi/spidev.h>

/**
 * @brief File descriptor for the open spidev node.
 *
 * Initialised to -1 (closed). Updated by mcp3008_init() and reset by
 * mcp3008_close(). All SPI transactions check that this is non‑negative.
 */
static int g_fd = -1;

/**
 * @brief Open and configure the SPI device.
 *
 * Performs the following steps:
 *   1. Open the device node with O_RDWR.
 *   2. Set SPI mode, bits per word, and max speed via ioctl.
 *   3. Store the file descriptor in the global @c g_fd.
 *
 * @param[in] devpath  Path to the spidev node (e.g. "/dev/spidev0.0").
 * @return 0 on success, -1 on failure (error messages printed to stderr).
 */
int mcp3008_init(const char *devpath)
{
    int fd;
    uint8_t mode = MCP3008_MODE;
    uint8_t bpw  = MCP3008_BPW;
    uint32_t speed = MCP3008_SPEED;

    fd = open(devpath, O_RDWR);
    if (fd < 0) {
        perror(devpath);
        fprintf(stderr, "mcp3008: cannot open %s (need sudo?)\n", devpath);
        return -1;
    }

    if (ioctl(fd, SPI_IOC_WR_MODE, &mode) < 0) {
        perror("SPI_IOC_WR_MODE");
        close(fd);
        return -1;
    }
    if (ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bpw) < 0) {
        perror("SPI_IOC_WR_BITS_PER_WORD");
        close(fd);
        return -1;
    }
    if (ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed) < 0) {
        perror("SPI_IOC_WR_MAX_SPEED_HZ");
        close(fd);
        return -1;
    }

    g_fd = fd;
    printf("mcp3008: init OK (%s, mode %d, %d bpw, %d Hz)\n",
           devpath, mode, bpw, speed);
    return 0;
}

/**
 * @brief Initialise the ADC using the default device path.
 *
 * Simply delegates to mcp3008_init() with @ref MCP3008_DEV.
 *
 * @return 0 on success, -1 on failure.
 */
int mcp3008_init_default(void)
{
    return mcp3008_init(MCP3008_DEV);
}

/**
 * @brief Read one sample from a single‑ended input channel.
 *
 * Builds a three‑byte SPI message:
 *   Byte 0 : 0x01             (start bit)
 *   Byte 1 : 0x80 | (ch<<4)   (single‑ended flag + channel address)
 *   Byte 2 : 0x00             (dummy byte to clock in the result)
 *
 * After the transfer the 10‑bit value is extracted from bytes 1 and 2:
 *   result = ((rx[1] & 0x03) << 8) | rx[2]
 *
 * @param[in] ch  Channel number, 0…7.
 * @return The converted value (0 … @ref MCP3008_RES), or -1 if the
 *         device is not open or @p ch is out of range.
 */
int mcp3008_read_channel(int ch)
{
    int ret;
    uint8_t tx[3];
    uint8_t rx[3];
    struct spi_ioc_transfer tr;

    if (g_fd < 0) return -1;
    if (ch < 0 || ch > 7) return -1;

    /*
     * MCP3008 single-ended read protocol:
     *
     *   Start bit = 1, SGL/DIFF = 1 (single-ended),
     *   D2 D1 D0  = channel address, MSB first.
     *
     *   Byte 1: 0000 0001   (start)
     *   Byte 2: 1xxx xxxx   (SGL=1 + 3-bit address)
     *   Byte 3: 0000 0000   (don't care)
     *
     *   Result: bits [7:6] of byte 2 + all 8 bits of byte 3,
     *   concatenated into a 10-bit value.
     */
    tx[0] = 0x01;
    tx[1] = 0x80 | (ch << 4);
    tx[2] = 0x00;

    memset(&tr, 0, sizeof(tr));
    tr.tx_buf = (unsigned long)tx;
    tr.rx_buf = (unsigned long)rx;
    tr.len = 3;
    tr.speed_hz = MCP3008_SPEED;
    tr.bits_per_word = MCP3008_BPW;

    ret = ioctl(g_fd, SPI_IOC_MESSAGE(1), &tr);
    if (ret < 0) {
        perror("SPI_IOC_MESSAGE");
        return -1;
    }

    return ((rx[1] & 0x03) << 8) | rx[2];
}

/**
 * @brief Close the SPI device.
 *
 * If the device is currently open (g_fd ≥ 0), closes the file descriptor
 * and sets g_fd back to -1. Safe to call multiple times.
 */
void mcp3008_close(void)
{
    if (g_fd >= 0) {
        close(g_fd);
        g_fd = -1;
    }
}
