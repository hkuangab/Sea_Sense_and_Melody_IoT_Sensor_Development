# Sensor Box

A multi\-threaded C application for Raspberry Pi 5\. Samples light, sound, and touch sensors at 1 kHz, computes high\-level derived features, and logs data to CSV and JSONL\. Local human\-readable feedback is provided via a 7\-segment multiplexed display and I²C LCD1602\.

## Table of Contents

1. Overview

2. System Architecture

3. Quick Start

    - Dependencies

    - Build

    - Run

4. Initialisation \& Resource Lifecycle

    - Initialisation Order

    - Cleanup Order

5. Module API Reference

6. Data Output Specification

    - CSV Layout

    - JSONL Schema

7. GPIO \& Peripheral Allocation

8. Configuration Macros

9. Known Limitations

10. License

## Overview

Sensor Box is a single\-process multi\-threaded C sensor acquisition system for Raspberry Pi 5\.

- Main thread runs a 1 kHz tick loop \(1 ms per tick\)\.

- Sensor raw sampling and feature extraction are triggered once per second\.

- Independent dedicated threads for 7\-segment display multiplexing and touch sensor edge detection\.

- Persistent logging: CSV \+ JSONL line\-delimited records\.

- Local display: 4\-digit 7\-segment multiplexed display \+ I²C LCD1602\.

- GPIO abstraction based on `libgpiod`; SPI for MCP3008 ADC; I²C for LCD1602\.

## System Architecture

```
Main thread (1 kHz / 1 ms tick)
├─ light_sensor_sample()       │ 1 Hz
├─ sound_sample()              │ 1 Hz
├─ touch_sensor_tick()         │ no-op; touch sampling runs on separate thread
└─ Once per second:
   ├─ light_sensor_update_features()
   ├─ sound_update_features()
   ├─ touch_sensor_update_features()
   ├─ lcd1602_print_line()     │ only on content change
   ├─ csv_writer_append()
   ├─ jsonl_writer_append()
   └─ term_print_all()

Display thread (seg7_scan_thread, ~125 Hz)
└─ Multiplex 4-digit 7-segment display

Touch thread (touch_thread, 1 ms poll)
└─ Edge detection with 200 ms retrigger lockout
```

> Note: Raw sensor reads are scheduled once per second, while the main thread maintains a 1 kHz timing base\.
> 
> 

## Quick Start

### Dependencies

- `libgpiod-dev` ≥ 1\.6 — GPIO control

- `libi2c-dev` — I²C for LCD1602

- SPI enabled via `raspi-config` \(required for MCP3008 ADC\)

```bash
sudo apt update
sudo apt install libgpiod-dev libi2c-dev
```

### Build

A `Makefile` is included in the project root\.

```bash
make
```

### Run

SPI and I²C device nodes are owned by root by default; launch with `sudo`\.

```bash
sudo ./sensor_box
```

Output files are created in the working directory:

- `sensor_data.csv`

- `sensor_data.jsonl`

## Initialisation \& Resource Lifecycle

### Initialisation Order

The system maintains **one shared ****`gpiod_chip`**** handle**, opened by the 7\-segment driver\. All other GPIO consumers reuse this chip handle and must not open a separate chip instance\.

**Mandatory startup sequence:**

1. `seg5641bs_init()` → opens `g_seg_chip`, requests 12 GPIO lines for 7\-segment

2. `mcp3008_init_default()` → SPI ADC \(independent of gpiod\)

3. `lcd1602_init()` → I²C LCD \(independent of gpiod\)

4. `light_sensor_sample()` → warm\-up read to avoid all\-zero first record

5. `sound_init()` → reuses `g_seg_chip`, requests GPIO18

6. `touch_sensor_init()` → reuses `g_seg_chip`, requests GPIO5

> ⚠️ `seg5641bs_init()`**must run before**`touch_sensor_init()` and `sound_init()`\.
> If violated, GPIO line request will fail, as lines cannot be double\-requested from the same gpiod chip\.
> 
> 

### Cleanup Order

Only `main()` closes the global gpiod chip handle\. Peripheral modules release line requests but **must not close the chip**\.

Cleanup sequence on exit:

1. `csv_writer_close()`

2. `jsonl_writer_close()`

3. `touch_sensor_close()` → release line request only

4. `sound_close()` → release line request only

5. `lcd1602_close()`

6. `seg5641bs_clear()`

7. `seg5641bs_close()` → release line request only

8. `gpiod_chip_close(g_seg_chip)`

9. `mcp3008_close()`

## Module API Reference

### `sensor_box.h`

Top\-level shared header\. Defines compile\-time module switches, sliding window macros, and `struct sb_state` — the unified sensor snapshot passed between sampling, feature extraction and logging modules\.

Global variables:

- `g_touch_count`

- `g_sound_pulse_count`

|Macro|Default|Description|
|---|---|---|
|`ENABLE_LIGHT`|1|Build light sensor module|
|`ENABLE_SOUND`|1|Build sound sensor module|
|`ENABLE_TOUCH`|1|Build touch sensor module|
|`ENABLE_7SEG`|1|Build 7\-segment display driver|
|`ENABLE_LCD`|1|Build LCD1602 driver|
|`LIGHT_WINDOW`|15|Sample buffer size for light trend \& variance|
|`FLICKER_WINDOW`|10|Seconds for light edge / flicker counting|
|`SOUND_ENERGY_WIN`|5|Samples for sound RMS energy|
|`SOUND_CONT_WIN`|5|Second window for audible ratio calculation|
|`SPIKE_WINDOW`|1|Seconds for loud spike counter|
|`TOUCH_COUNT_WIN`|60|Second window for touch frequency|
|`TOUCH_IVAL_WIN`|5|Touch interval buffer for pattern analysis|

### `csv_writer.h`

```c
void csv_writer_append(const struct sb_state *st);
void csv_writer_close(void);
```

Append one CSV record\. Header is automatically written on first call\. File opened in append mode \(`"a"`\)\. Stream buffering disabled \(`_IONBF`\) to limit data loss on power failure to at most one row\.

### `jsonl_writer.h`

```c
void jsonl_writer_append(const struct sb_state *st);
void jsonl_writer_close(void);
```

Line\-delimited JSON output\. One JSON object per line, grouped into `light`, `sound`, `touch` sub\-objects\. Lifecycle matches CSV writer\.

### `lcd1602.h`

```c
int lcd1602_init_auto(void);
int lcd1602_init(uint8_t addr);
void lcd1602_clear(void);
void lcd1602_print_line(int row, const char *text);
void lcd1602_close(void);
```

`lcd1602_init_auto()` probes a predefined I²C address list and returns on first successful handshake\. Text shorter than 16 characters is space\-padded to fill LCD width\.

### `light_sensor.h`

```c
void light_sensor_sample(void);
void light_sensor_update_features(void);
int light_get_raw(void);
float light_get_brightness(void);    /* raw / 1023 */
float light_get_trend(void);         /* least-squares slope over LIGHT_WINDOW */
float light_get_variance(void);
int light_get_is_daylight(void);     /* brightness > 0.3 */
int light_get_flicker_freq(void);    /* edge transitions in FLICKER_WINDOW */
```

`light_sensor_sample()` reads ADC and stores raw value\.
`light_sensor_update_features()` computes derived metrics from sliding window\.

> Order dependency: feature getters return stale values until `update_features()` runs at least once\.
> 
> 

### `math_util.h`

```c
float math_linreg_slope(const int *data, int count);
float math_variance(const int *data, int count);
float math_std(const float *data, int count);
```

Safety guard: returns `0.0f` when `count < 2` to avoid division by zero\. Linear slope implementation also handles degenerate determinant cases\.

### `mcp3008.h`

```c
int mcp3008_init_default(void);
int mcp3008_init(const char *devpath);
int mcp3008_read_channel(int ch); /* returns 0..1023, -1 on error */
void mcp3008_close(void);
```

Opens SPI device with `O_RDWR`\. On open failure, prints hint to run with `sudo` because `/dev/spidev*` is root\-owned by default\.

### `seg7_display.h`

```c
void seg5641bs_init(void);
void seg5641bs_show_number(int val);
void seg5641bs_clear(void);
void seg5641bs_close(void);
void seg7_set_decimal_point(int digit_idx, bool on);
extern struct gpiod_chip *g_seg_chip;
```

`g_seg_chip` is exposed as part of the module contract for other GPIO modules to reuse\.
`seg5641bs_show_number()` accepts integer input; values outside `[0,9999]` clamped or wrapped modulo\. Leading zeros are blanked\.

### `sound_sensor.h`

```c
void sound_init(void);
void sound_sample(void);
void sound_update_features(void);
void sound_close(void);
int sound_get_raw(void);
float sound_get_energy(void);        /* RMS normalized to [0,1] */
float sound_get_speech_rate(void);   /* clamped [0,1] */
float sound_get_continuity(void);    /* audible ratio over SOUND_CONT_WIN */
int sound_get_spike(void);
int sound_get_human_presence(void);
extern volatile int g_sound_pulse_count;
```

`sound_get_human_presence()` = 1 when sound energy \> 0\.1 **or** touch count \> 0\. This is a heuristic presence indicator, not calibrated measurement\.

### `term_print.h`

```c
void term_print_all(void);
```

Print human\-readable status line to stdout, prefixed with ISO 8601 UTC timestamp and session uptime\.

### `touch_sensor.h`

```c
void touch_sensor_init(void);
void touch_sensor_tick(void);
void touch_sensor_update_features(void);
void touch_sensor_close(void);
int touch_sensor_get_irq(void);      /* clears flag on read */
int touch_sensor_get_count(void);    /* count over TOUCH_COUNT_WIN */
float touch_sensor_get_freq(void);   /* count / TOUCH_COUNT_WIN */
const char* touch_sensor_get_pattern(void); /* "rhythmic" | "random" */
float touch_sensor_get_intent(void);
```

Touch active level defined in `touch_sensor.c` as `TOUCH_ACTIVE`, default `1` \(active high\)\. If hardware pulls low on touch, set to `0`\.

## Data Output Specification

### CSV Layout

Columns:

```
ts, time_of_day, day_of_week, session_elapsed,
light_raw, light_brightness, light_trend, light_variance,
light_is_daylight, light_flicker_freq,
sound_raw, sound_energy, sound_speech_rate, sound_continuity,
sound_spike, sound_human_presence,
touch_irq, touch_count, touch_freq, touch_pattern, touch_intent
```

- `ts`: ISO 8601 UTC timestamp

- `time_of_day`: fractional hour / 24, range `[0,1)`

- `touch_pattern`: only non\-numeric field, unquoted string

### JSONL Schema

Each line is a standalone JSON object:

```json
{
  "ts": "2026-09-29T10:30:00Z",
  "time_of_day": 0.4271,
  "day_of_week": 2,
  "session_elapsed": 12345,
  "light": {
    "raw_adc": 512,
    "brightness": 0.5000,
    "trend": -0.312000,
    "variance": 184.200000,
    "is_daylight": 1,
    "flicker_freq": 3
  },
  "sound": {
    "raw_adc": 487,
    "energy": 0.2450,
    "speech_rate": 0.3000,
    "continuity": 0.6000,
    "sudden_spike": 0,
    "human_presence": 1
  },
  "touch": {
    "irq": 1,
    "count_60s": 4,
    "freq": 0.0667,
    "pattern": "random",
    "intent": 0.2
  }
}
```

## GPIO \& Peripheral Allocation

|BCM GPIO|Owner|Direction|Description|
|---|---|---|---|
|5|touch|input|TTP223 touch sensor OUT, configurable active level|
|18|sound|input|Microphone digital DO|
|12|seg7|output|Segment a|
|22|seg7|output|Segment b|
|19|seg7|output|Segment c|
|16|seg7|output|Segment d|
|17|seg7|output|Segment e|
|13|seg7|output|Segment f|
|20|seg7|output|Segment g|
|18|seg7|output|Decimal point **shared with sound**|
|21|seg7|output|Digit 1 \(units\)|
|23|seg7|output|Digit 2|
|24|seg7|output|Digit 3|
|6|seg7|output|Digit 4 \(thousands\)|
|8|SPI|CS|MCP3008 chip select CE0|
|11|SPI|SCK|MCP3008 clock|
|10|SPI|MOSI|MCP3008|
|9|SPI|MISO|MCP3008|
|2|I2C|SDA|LCD1602|
|3|I2C|SCL|LCD1602|

> ⚠️ GPIO18 is shared between seg7 \(output\) and sound \(input\)\.
> This works because both modules use the same `gpiod_chip` handle and request separate line configurations\. Do not attach a third device to GPIO18\. Changing direction in one module requires review of the other\.
> 
> 

## Configuration Macros

All compile\-time switches and window sizes are defined in `sensor_box.h`\. Enable or disable entire sensor subsystems at build time via `ENABLE_LIGHT`, `ENABLE_SOUND`, `ENABLE_TOUCH`, `ENABLE_7SEG`, and `ENABLE_LCD`\. Sliding window sizes control the trade\-off between feature smoothing and responsiveness\.

## Known Limitations

1. `sound_speech_rate` only works with digital\-output microphone modules\. Analogue mics such as MAX9814 will always return zero\.

2. `touch_pattern` remains `"random"` until at least two touch intervals have been captured\.

3. `touch_intent` is a simple two\-state heuristic \(0\.2 / 0\.7\), not a trained machine learning classifier\.

4. The 7\-segment display implementation calls `gpiod_line_request_set_value` 8 times per digit, \~4000 ioctl syscalls/sec at current scan rate\. Higher refresh rates can use batch `gpiod_line_request_set_values` to reduce syscall overhead\.

5. CSV / JSONL log files are appended continuously with **no log rotation**\. Long\-running deployments will create unbounded file growth\.

## License

Add your license here, e\.g\. MIT / Apache 2\.0\.
