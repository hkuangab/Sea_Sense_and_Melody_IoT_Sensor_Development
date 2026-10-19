/**
 * @file sensor_box.h
 * @brief Shared state structure, message definitions, and compile‑time configuration.
 *
 * This header defines:
 *   - The master snapshot structure `sb_state` used by all output writers.
 *   - Inter‑process message formats for camera HSV data and inference results.
 *   - Compile‑time feature enable flags and window sizes for sensor algorithms.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026-10-19
 */

#ifndef SENSOR_BOX_H
#define SENSOR_BOX_H

/**
 * sensor_box.h — shared state structure and message definitions
 *
 * Author: KUANG, Haozhe (HKUST)
 * Date:   2026-10-19
 */

#include <stdint.h>
#include <time.h>

#ifdef __linux__
#  include <gpiod.h>
#endif

/* ---------- Global chip handle (owned by seg7_display) ---------- */
extern struct gpiod_chip *g_seg_chip;

/* ==================================================================
 * Feature enable flags
 * ------------------------------------------------------------------
 * These macros control whether each sensor compiles the real driver
 * or a stub. Previously ENABLE_LIGHT / ENABLE_SOUND were undefined,
 * causing the stub branches (which return -1) to be compiled – that
 * was why light/sound showed -1. The #ifndef guard allows the
 * Makefile to override via -D; if not defined, all features default
 * to enabled.
 * ================================================================== */
#ifndef ENABLE_LIGHT
#define ENABLE_LIGHT  1
#endif
#ifndef ENABLE_SOUND
#define ENABLE_SOUND  1
#endif
#ifndef ENABLE_TOUCH
#define ENABLE_TOUCH  1
#endif
#ifndef ENABLE_LCD
#define ENABLE_LCD    1
#endif
#ifndef ENABLE_CAMERA
#define ENABLE_CAMERA 1
#endif

/* ==================================================================
 * Window sizes used by the feature extractors
 * ================================================================== */
#ifndef LIGHT_WINDOW
#define LIGHT_WINDOW       10
#endif
#ifndef FLICKER_WINDOW
#define FLICKER_WINDOW     10
#endif
#ifndef SOUND_ENERGY_WIN
#define SOUND_ENERGY_WIN   10
#endif
#ifndef SOUND_CONT_WIN
#define SOUND_CONT_WIN     10
#endif
#ifndef TOUCH_COUNT_WIN
#define TOUCH_COUNT_WIN    10
#endif
#ifndef TOUCH_IVAL_WIN
#define TOUCH_IVAL_WIN     10
#endif

/* ---------- Message queue names ---------- */
#define CAM_MQ_NAME   "/sensor_box_cam"
#define INFER_MQ_NAME "/sensor_box_infer"

#define CAM_MQ_MAXMSG   10
#define INFER_MQ_MAXMSG 10

/**
 * @brief Camera colour cluster message sent from camera_sensor to main loop.
 *
 * Contains the top‑3 HSV clusters detected in the current frame, along
 * with a millisecond timestamp. Packed to avoid padding issues across
 * different compilers.
 */
typedef struct __attribute__((packed)) {
    uint64_t timestamp_ms; /**< Monotonic time when the frame was captured (ms). */
    int      top_count;    /**< Number of valid clusters (0..3). */
    int      top_h[3];     /**< Hue values of the top clusters (0..179). */
    int      top_s[3];     /**< Saturation values (0..255). */
    int      top_v[3];     /**< Value (brightness) values (0..255). */
} CamMessage;

/**
 * @brief Inference result message (legacy integer label format).
 *
 * Originally used by the Python inference process. The current version
 * sends plain text labels via a separate message queue, but this struct
 * is retained for backward compatibility.
 */
typedef struct __attribute__((packed)) {
    int   emotion_label; /**< Integer emotion class ID. */
    float confidence;    /**< Confidence score in [0.0, 1.0]. */
} InferResult;

/**
 * @brief Master snapshot structure – one row of CSV / one JSON object.
 *
 * Aggregates all sensor readings, time features, camera HSV clusters,
 * and the latest emotion inference result. Populated once per second
 * in the main loop.
 */
struct sb_state {
    /* Timestamp */
    const char *ts;                 /**< ISO 8601 string, e.g. "2026-10-18T12:34:56Z" */

    /* Time features */
    float time_of_day;              /**< Fractional time of day [0.0 .. 1.0] */
    int   day_of_week;              /**< 0=Sunday, 6=Saturday */
    int   session_elapsed;          /**< Seconds since program start */

    /* Light sensor */
    int   light_raw;                /**< Raw ADC reading */
    float light_brightness;         /**< Normalised brightness [0.0 .. 1.0] */
    float light_trend;              /**< Slope of recent readings (ADC/sample) */
    float light_variance;           /**< Variance of recent readings */
    int   light_is_daylight;        /**< Boolean: 1 = daylight detected */
    float light_flicker_freq;       /**< Estimated flicker frequency (Hz) */

    /* Sound sensor */
    int   sound_raw;                /**< Raw ADC reading */
    float sound_energy;             /**< RMS energy of recent window */
    float sound_speech_rate;        /**< Estimated syllable rate (Hz) */
    float sound_continuity;         /**< Fraction of window above threshold */
    int   sound_spike;              /**< Boolean: sudden loud event */
    int   sound_human_presence;     /**< Boolean: human speech detected */

    /* Touch sensor */
    int   touch_irq;                /**< Interrupt flag (1 = touched) */
    int   touch_count;              /**< Cumulative tap count in window */
    float touch_freq;               /**< Tap frequency (Hz) */
    const char *touch_pattern;      /**< Pattern string, e.g. "single", "double" */
    float touch_intent;             /**< Intent score derived from pattern */

    /* Camera HSV top-3 clusters */
    int   cam_top_count;            /**< Number of valid clusters (0..3) */
    int   cam_top1_h;               /**< Hue of dominant cluster */
    int   cam_top1_s;               /**< Saturation of dominant cluster */
    int   cam_top1_v;               /**< Value of dominant cluster */
    float cam_top1_ratio;           /**< Pixel ratio of cluster 1 */
    int   cam_top2_h;
    int   cam_top2_s;
    int   cam_top2_v;
    float cam_top2_ratio;           /**< Pixel ratio of cluster 2 */
    int   cam_top3_h;
    int   cam_top3_s;
    int   cam_top3_v;
    float cam_top3_ratio;           /**< Pixel ratio of cluster 3 */

    /* Emotion inference result */
    char  emotion_label[64];        /**< Text label, e.g. "Happy", "Sad" */
    float emotion_conf;             /**< Confidence [0.0 .. 1.0] */
};

#endif /* SENSOR_BOX_H */
