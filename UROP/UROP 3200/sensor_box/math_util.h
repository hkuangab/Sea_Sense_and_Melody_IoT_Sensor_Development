/*
 * math_util.h - lightweight mathematical helpers
 *
 * Small, dependency-free primitives used by the sensor feature extractors.
 * Every function here is safe to call with fewer than two samples: it will
 * return 0.0f rather than dividing by zero.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#ifndef MATH_UTIL_H
#define MATH_UTIL_H

#include <stddef.h>

/**
 * @brief Compute the slope of a simple linear regression line.
 *
 * Fits y = a*x + b to the first @p count samples using least squares
 * and returns the slope @c a.  The x coordinate is the sample index,
 * so the result has units of ADC counts per sample and can be used
 * directly as a trend indicator.
 *
 * @param[in] data  Array of raw samples (typically ADC values).
 * @param[in] count Number of valid samples; must be >= 2 for a fit.
 * @return The fitted slope, or 0.0f if @p count is less than 2 or the
 *         determinant is degenerate.
 */
float math_linreg_slope(const int *data, int count);

/**
 * @brief Compute the sample variance of an integer array.
 *
 * Uses Bessel's correction (divides by n-1), so the result is an unbiased
 * estimate of the population variance. Used for the light variance feature.
 *
 * @param[in] data  Array of samples.
 * @param[in] count Number of valid samples.
 * @return The sample variance, or 0.0f if @p count is less than 2.
 */
float math_variance(const int *data, int count);

/**
 * @brief Compute the sample standard deviation of a float array.
 *
 * A thin wrapper over variance; included for symmetry with math_variance
 * and for any caller that prefers floats.
 *
 * @param[in] data  Array of samples.
 * @param[in] count Number of valid samples.
 * @return The sample standard deviation, or 0.0f if @p count is less
 *         than 2.
 */
float math_std(const float *data, int count);

#endif /* MATH_UTIL_H */
