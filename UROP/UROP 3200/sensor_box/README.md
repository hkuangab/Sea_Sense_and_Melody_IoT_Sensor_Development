<!--
  Sensor Box
  Copyright (c) 2026 KUANG, Haozhe
  The Hong Kong University of Science and Technology
  Email:  hkuangab@connect.ust.hk
  Date:   2026/10/06
  Version: 2.2.0
  SPDX-License-Identifier: MIT
-->
# Sensor Box

A multi-sensor data acquisition program for the Raspberry Pi 5. Reads an
MCP3008 SPI ADC for a light-dependent resistor and a microphone, counts
taps on a TTP223 capacitive sensor, drives a 5641BS common-anode
4-digit 7-segment module, and logs a 16x2 LCD. One sample per second is
written to the terminal, a CSV file, and a JSONL file.

## Project information

| Field    | Value                                              |
| -------- | -------------------------------------------------- |
| Author   | KUANG, Haozhe                                      |
| Affiliation | The Hong Kong University of Science and Technology |
| Email    | hkuangab@connect.ust.hk                            |
| Date     | 2026/10/06                                         |
| Version  | 2.2.0                                              |
| License  | MIT (see `LICENSE`)                                |




## Documentation

This document describes the public interfaces of every module in the Sensor Box
project. It is intended for developers who need to extend the system or write
analysis tools against the recorded data.

The internal implementation details (static functions, global state, helper
macros) are deliberately not part of this contract. They may change between
releases.

## 1. Overall architecture

The system is a single-process, multi-threaded C application. The main thread
runs a 1 kHz loop; one tick equals one millisecond. Sensor sampling happens
once per second, while the 7-segment display and the touch sensor run on their
own threads.

```
main thread (1 kHz loop)
   ├── light_sensor_sample()        once per second
   ├── sound_sample()              once per second
   ├── touch_sensor_tick()         no-op; the touch thread runs independently
   └── once per second:
        ├── light_sensor_update_features()
        ├── sound_update_features()
        ├── touch_sensor_update_features()
        ├── lcd1602_print_line()   (only if content changed)
        ├── csv_writer_append()
        ├── jsonl_writer_append()
        └── term_print_all()

display thread (seg7_scan_thread, ~125 Hz)
   └── multiplexes the four 7-segment digits

touch thread (touch_thread, 1 ms poll)
   └── edge detection with 200 ms retrigger lockout
```

## 2. Lifecycle and initialization order

The initialization order is **not** arbitrary. The system owns exactly one
`gpiod_chip` handle, opened by the 7-segment driver. All other modules that
need GPIO must reuse that handle instead of opening their own.

```
seg5641bs_init()       owns g_seg_chip, requests 12 lines at once
mcp3008_init_default() SPI, independent of gpiod
lcd1602_init()         I2C, independent of gpiod
light_sensor_sample()  warm-up read, avoids an all-zero first row
sound_init()           reuses g_seg_chip, requests GPIO18 only
touch_sensor_init()    reuses g_seg_chip, requests GPIO5 only
```

`seg5641bs_init()` **must** run before `touch_sensor_init()` and
`sound_sensor_init()`. If this order is violated, the latter two will fail
with `request GPIO5 failed` / `request GPIO18 failed`, because the lines
would be requested twice from the same chip.

Symmetrically, only `main()` may close the chip. The display, touch, and
sound modules release their line requests but must not close the chip:

```
main exit:
    csv_writer_close()
    jsonl_writer_close()
    touch_sensor_close()    releases its request only
    sound_close()           releases its request only
    lcd1602_close()
    seg5641bs_clear()
    seg5641bs_close()       releases its request only
    gpiod_chip_close(g_seg_chip)
    mcp3008_close()
```

## 3. Module reference

### 3.1 `sensor_box.h`

The single shared header. Defines the module switches, all window-size macros,
and the `struct sb_state` snapshot passed between the sampler, the writers,
and the terminal printer.

| Macro | Default | Meaning |
| --- | --- | --- |
| `ENABLE_LIGHT` | 1 | Compile the light sensor module |
| `ENABLE_SOUND` | 1 | Compile the sound sensor module |
| `ENABLE_TOUCH` | 1 | Compile the touch sensor module |
| `ENABLE_7SEG` | 1 | Compile the 7-segment driver |
| `ENABLE_LCD` | 1 | Compile the LCD1602 driver |
| `LIGHT_WINDOW` | 15 | Samples kept for trend / variance |
| `FLICKER_WINDOW` | 10 | Seconds kept for edge counting |
| `SOUND_ENERGY_WIN` | 5 | Samples for RMS energy |
| `SOUND_CONT_WIN` | 5 | Seconds for audible-ratio window |
| `SPIKE_WINDOW` | 1 | Seconds for loud-spike counter |
| `TOUCH_COUNT_WIN` | 60 | Seconds for frequency calculation |
| `TOUCH_IVAL_WIN` | 5 | Touch intervals kept for pattern |

The global variables `g_touch_count` and `g_sound_pulse_count` are declared
here and defined in their respective modules.

### 3.2 `csv_writer.h`

```c
void csv_writer_append(const struct sb_state *st);
void csv_writer_close(void);
```

Appends one row in text mode (`"a"`). The header is written automatically on
the first call. Buffering is disabled (`_IONBF`) so a power loss loses at
most the current row rather than a kernel buffer.

### 3.3 `jsonl_writer.h`

```c
void jsonl_writer_append(const struct sb_state *st);
void jsonl_writer_close(void);
```

Same lifecycle as the CSV writer. Output is one JSON object per line,
structured as `light`, `sound`, `touch` sub-objects.

### 3.4 `lcd1602.h`

```c
int  lcd1602_init_auto(void);
int  lcd1602_init(uint8_t addr);
void lcd1602_clear(void);
void lcd1602_print_line(int row, const char *text);
void lcd1602_close(void);
```

Probes a fixed list of I2C addresses and returns on the first successful
handshake. Text shorter than 16 characters is padded with spaces.

### 3.5 `light_sensor.h`

```c
void  light_sensor_sample(void);
void  light_sensor_update_features(void);

int   light_get_raw(void);
float light_get_brightness(void);   /* raw / 1023 */
float light_get_trend(void);        /* least-squares slope over LIGHT_WINDOW */
float light_get_variance(void);
int   light_get_is_daylight(void);  /* brightness > 0.3 */
int   light_get_flicker_freq(void); /* edge transitions in FLICKER_WINDOW */
```

`sample()` reads the ADC and stores the value. `update_features()` computes
derived quantities from the window. Calling order matters: features read
stale data until `update_features()` has run at least once.

### 3.6 `math_util.h`

```c
float math_linreg_slope(const int *data, int count);
float math_variance(const int *data, int count);
float math_std(const float *data, int count);
```

All three return `0.0f` when `count < 2` rather than dividing by zero. The
slope function also guards against a degenerate determinant.

### 3.7 `mcp3008.h`

```c
int  mcp3008_init_default(void);
int  mcp3008_init(const char *devpath);
int  mcp3008_read_channel(int ch);  /* returns 0..1023, or -1 on error */
void mcp3008_close(void);
```

The device is opened with `O_RDWR`. Failure to open prints a hint about
running with `sudo`, since `/dev/spidev*` is root-owned by default.

### 3.8 `seg7_display.h`

```c
void seg5641bs_init(void);
void seg5641bs_show_number(int val);
void seg5641bs_clear(void);
void seg5641bs_close(void);
void seg7_set_decimal_point(int digit_idx, bool on);

extern struct gpiod_chip *g_seg_chip;
```

The external `g_seg_chip` handle is part of the contract because other
modules depend on it. `seg5641bs_show_number()` accepts any integer; values
outside `[0, 9999]` are clamped to zero or wrapped with modulo. Leading
zeros are blanked, so the value `1` lights only the units digit.

### 3.9 `sound_sensor.h`

```c
void sound_init(void);
void sound_sample(void);
void sound_update_features(void);
void sound_close(void);

int   sound_get_raw(void);
float sound_get_energy(void);        /* RMS, normalised to 0..1 */
float sound_get_speech_rate(void);   /* clamped to [0, 1] */
float sound_get_continuity(void);    /* audible ratio over SOUND_CONT_WIN */
int   sound_get_spike(void);
int   sound_get_human_presence(void);

extern volatile int g_sound_pulse_count;
```

`sound_human_presence` is `1` when energy exceeds `0.1` **or** the touch
count is non-zero. It is intentionally a heuristic rather than a measurement.

### 3.10 `term_print.h`

```c
void term_print_all(void);
```

Prints a single human-readable line to stdout, prefixed with an ISO 8601 UTC
timestamp and the session uptime.

### 3.11 `touch_sensor.h`

```c
void touch_sensor_init(void);
void touch_sensor_tick(void);
void touch_sensor_update_features(void);
void touch_sensor_close(void);

int   touch_sensor_get_irq(void);          /* clears the flag on read */
int   touch_sensor_get_count(void);        /* count over TOUCH_COUNT_WIN */
float touch_sensor_get_freq(void);         /* count / TOUCH_COUNT_WIN */
const char *touch_sensor_get_pattern(void); /* "rhythmic" | "random" */
float touch_sensor_get_intent(void);
```

The effective level is `TOUCH_ACTIVE` in `touch_sensor.c` and defaults to
`1` (active high). If `pinctrl get 5` shows the line going low on touch,
set it to `0`.

## 4. Data layout

### 4.1 CSV columns

```
ts, time_of_day, day_of_week, session_elapsed,
light_raw, light_brightness, light_trend, light_variance,
light_is_daylight, light_flicker_freq,
sound_raw, sound_energy, sound_speech_rate, sound_continuity,
sound_spike, sound_human_presence,
touch_irq, touch_count, touch_freq, touch_pattern, touch_intent
```

`ts` is ISO 8601 in UTC. `time_of_day` is the fractional hour divided by 24,
so it lies in `[0, 1)`. `touch_pattern` is the only non-numeric field and
is unquoted.

### 4.2 JSONL schema

```json
{
  "ts": "2026-09-29T10:30:00Z",
  "time_of_day": 0.4271,
  "day_of_week": 2,
  "session_elapsed": 12345,
  "light":  { "raw_adc": 512, "brightness": 0.5000, "trend": -0.312000,
               "variance": 184.200000, "is_daylight": 1, "flicker_freq": 3 },
  "sound":  { "raw_adc": 487, "energy": 0.2450, "speech_rate": 0.3000,
               "continuity": 0.6000, "sudden_spike": 0, "human_presence": 1 },
  "touch":  { "irq": 1, "count_60s": 4, "freq": 0.0667,
               "pattern": "random", "intent": 0.2 }
}
```

## 5. GPIO allocation

| GPIO (BCM) | Owner | Direction | Notes |
| --- | --- | --- | --- |
| 5  | touch | input | TTP223 OUT; effective level is configurable |
| 18 | sound | input | Microphone DO; also shares the chip with seg7 |
| 12 | seg7 | output | Segment `a` |
| 22 | seg7 | output | Segment `b` |
| 19 | seg7 | output | Segment `c` |
| 16 | seg7 | output | Segment `d` |
| 17 | seg7 | output | Segment `e` |
| 13 | seg7 | output | Segment `f` |
| 20 | seg7 | output | Segment `g` |
| 18 | seg7 | output | Decimal point (note: also used by sound as input) |
| 21 | seg7 | output | Digit 1 (units) |
| 23 | seg7 | output | Digit 2 |
| 24 | seg7 | output | Digit 3 |
| 6  | seg7 | output | Digit 4 (thousands) |
| 8  | SPI | CE0 | MCP3008 CS |
| 11 | SPI | SCK | MCP3008 clock |
| 10 | SPI | MOSI | MCP3008 |
| 9  | SPI | MISO | MCP3008 |
| 2  | I2C | SDA | LCD1602 |
| 3  | I2C | SCL | LCD1602 |

**Pin 12 (GPIO18) is shared between seg7 and sound.** This works only because
both modules operate on the same `gpiod_chip` handle and the display driver
claims the line as output while the sound driver claims it as input through
separate requests. Do not add a third consumer of GPIO18, and do not change
either direction without reviewing the other.

## 6. Known limitations

- `sound_speech_rate` requires a microphone module with a digital output.
  Purely analogue modules (e.g. MAX9814) report zero for this field.
- `touch_pattern` reports `"random"` until at least two touch intervals have
  been recorded.
- `touch_intent` is a two-level heuristic (`0.2` or `0.7`); it is not a
  trained classifier.
- The 7-segment scan calls `gpiod_line_request_set_value` eight times per
  digit, giving roughly 4000 ioctl calls per second at the current scan
  rate. For higher scan rates, replace these with a single
  `gpiod_line_request_set_values` batch call.
- The CSV and JSONL files are appended to without rotation. Long runs will
  grow without bound.
