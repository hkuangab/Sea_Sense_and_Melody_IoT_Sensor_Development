/**
 * @file math_util.c
 * @brief Implementation of the lightweight mathematical helpers.
 *
 * See math_util.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

/*
 * math_util.c - implementation of the lightweight mathematical helpers
 *
 * See math_util.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "math_util.h"
#include <math.h>

/**
 * @brief Compute the slope of a simple linear regression line.
 *
 * Implements the ordinary least‑squares formula for slope:
 *   a = (n·Σxy - Σx·Σy) / (n·Σxx - (Σx)²)
 * where x is the sample index and y is the sample value.
 * Returns 0.0f if the denominator is too small (degenerate data).
 *
 * @param[in] data  Array of raw samples (typically ADC values).
 * @param[in] count Number of valid samples; must be >= 2 for a fit.
 * @return The fitted slope, or 0.0f if @p count is less than 2 or the
 *         determinant is degenerate.
 */
float math_linreg_slope(const int *data, int count)
{
    if (count < 2) return 0.0f;

    float sum_x = 0.0f, sum_y = 0.0f, sum_xy = 0.0f, sum_xx = 0.0f;

    for (int i = 0; i < count; i++) {
        float x = (float)i;
        float y = (float)data[i];
        sum_x  += x;
        sum_y  += y;
        sum_xy += x * y;
        sum_xx += x * x;
    }

    float denom = (float)count * sum_xx - sum_x * sum_x;
    if (fabsf(denom) < 1e-6f) return 0.0f;

    return ((float)count * sum_xy - sum_x * sum_y) / denom;
}

/**
 * @brief Compute the sample variance of an integer array.
 *
 * Calculates the unbiased sample variance:
 *   s² = Σ(xᵢ - x̄)² / (n-1)
 * Returns 0.0f if there are fewer than 2 samples.
 *
 * @param[in] data  Array of samples.
 * @param[in] count Number of valid samples.
 * @return The sample variance, or 0.0f if @p count is less than 2.
 */
float math_variance(const int *data, int count)
{
    if (count < 2) return 0.0f;

    float mean = 0.0f;
    for (int i = 0; i < count; i++) mean += (float)data[i];
    mean /= (float)count;

    float var = 0.0f;
    for (int i = 0; i < count; i++) {
        float d = (float)data[i] - mean;
        var += d * d;
    }
    return var / (float)(count - 1);
}

/**
 * @brief Compute the sample standard deviation of a float array.
 *
 * Returns the square root of the unbiased sample variance.
 * Returns 0.0f if there are fewer than 2 samples.
 *
 * @param[in] data  Array of samples.
 * @param[in] count Number of valid samples.
 * @return The sample standard deviation, or 0.0f if @p count is less
 *         than 2.
 */
float math_std(const float *data, int count)
{
    if (count < 2) return 0.0f;

    float mean = 0.0f;
    for (int i = 0; i < count; i++) mean += data[i];
    mean /= (float)count;

    float var = 0.0f;
    for (int i = 0; i < count; i++) {
        float d = data[i] - mean;
        var += d * d;
    }
    return (float)sqrtf(var / (float)(count - 1));
}
