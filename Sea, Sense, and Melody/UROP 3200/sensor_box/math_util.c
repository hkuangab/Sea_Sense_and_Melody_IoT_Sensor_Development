/*
 * math_util.c - implementation of the lightweight mathematical helpers
 *
 * See math_util.h for the full interface documentation.
 *
 * Author:   KUANG, Haozhe
 *          The Hong Kong University of Science and Technology
 * Email:    hkuangab@connect.ust.hk
 * Date:     2026/10/06
 */

#include "math_util.h"
#include <math.h>

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
