/**
 * @file camera_sensor.h
 * @brief libcamera camera module for HSV colour extraction
 *
 * Captures one frame per second using libcamera (Raspberry Pi 5 CSI),
 * extracts the three most saturated colour clusters, and displays the
 * live feed in an SDL2 window. The window shows colour swatches, HSV
 * values, and the latest emotion classification from Python inference.
 *
 * All functions are designed to be callable from C code (extern "C").
 *
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date:   2026-10-19
 */

/*
 * camera_sensor.h — libcamera camera module for HSV colour extraction
 *
 * Captures one frame per second using libcamera (Raspberry Pi 5 CSI),
 * extracts the three most saturated colour clusters, and displays the
 * live feed in an SDL2 window. The window shows colour swatches, HSV
 * values, and the latest emotion classification from Python inference.
 *
 * All functions are designed to be callable from C code (extern "C").
 *
 * Author: KUANG, Haozhe (HKUST)
 * Date:   2026-10-19
 */

#ifndef CAMERA_SENSOR_H
#define CAMERA_SENSOR_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Open the libcamera camera and configure the video stream.
 *
 * Creates the camera worker thread, opens the libcamera pipeline,
 * allocates buffers, and starts the capture loop. Also opens the POSIX
 * message queue for sending colour data to the main process.
 *
 * @return 0 on success, -1 on failure (details printed to stderr).
 */
int  camera_init(void);

/**
 * @brief Capture one frame and compute HSV statistics.
 *
 * This function is intentionally empty because the actual capture runs
 * continuously in a separate thread started by camera_init(). It is
 * retained for compatibility with the main loop's sampling interface.
 *
 * @param None.
 * @return void.
 */
void camera_sample(void);

/**
 * @brief Release all camera resources and stop the worker thread.
 *
 * Joins the camera thread, closes the message queue, releases the
 * camera, and cleans up SDL resources.
 *
 * @param None.
 * @return void.
 */
void camera_close(void);

/** @name Colour cluster accessors
 *  Valid after camera_sample() has been called at least once. */
/**@{*/

/**
 * @brief Get the number of dominant colour clusters found (0..3).
 *
 * @return int Number of clusters (0 if no frame processed yet).
 */
int   camera_get_top_count(void);

/**
 * @brief Get the hue bin index of the i-th dominant colour.
 *
 * @param[in] index  Cluster index (0, 1, or 2).
 * @return int Hue bin index in [0, H_BINS-1].
 */
int   camera_get_top_h(int index);

/**
 * @brief Get the saturation bin index of the i-th dominant colour.
 *
 * @param[in] index  Cluster index (0, 1, or 2).
 * @return int Saturation bin index in [0, S_BINS-1].
 */
int   camera_get_top_s(int index);

/**
 * @brief Get the value (brightness) bin index of the i-th dominant colour.
 *
 * @param[in] index  Cluster index (0, 1, or 2).
 * @return int Value bin index in [0, V_BINS-1].
 */
int   camera_get_top_v(int index);

/**
 * @brief Get the pixel ratio of the i-th dominant colour cluster.
 *
 * @param[in] index  Cluster index (0, 1, or 2).
 * @return float Ratio in [0.0, 1.0] representing the fraction of sampled
 *         pixels belonging to that cluster.
 */
float camera_get_top_ratio(int index);

/**@}*/

/**
 * @brief Update the SDL window title with the current top-3 HSV values.
 *
 * Reads the current emotion label and confidence under the mutex and
 * sets the window title accordingly. No effect if the window does not
 * exist.
 *
 * @param None.
 * @return void.
 */
void camera_set_window_title(void);

/**
 * @brief Store the latest emotion classification result.
 *
 * Thread‑safe; copies the label string and confidence value into
 * internal storage protected by a mutex.
 *
 * @param[in] label       Null‑terminated emotion string (e.g. "happy").
 *                        May be NULL to clear the label.
 * @param[in] confidence  Confidence value in [0.0, 1.0].
 * @return void.
 */
void camera_set_emotion(const char *label, float confidence);

/**
 * @brief Get the stored emotion label.
 *
 * Returns a pointer to the internal buffer. The caller should copy the
 * string if it needs to keep it after the next call. Thread‑safe (uses
 * a mutex), but typically called from the main thread only.
 *
 * @return const char* Pointer to the emotion label string (may be empty).
 */
const char *camera_get_emotion_label(void);

/**
 * @brief Get the stored emotion confidence.
 *
 * Thread‑safe.
 *
 * @return float Confidence value in [0.0, 1.0].
 */
float camera_get_emotion_conf(void);

#ifdef __cplusplus
}
#endif

#endif /* CAMERA_SENSOR_H */
