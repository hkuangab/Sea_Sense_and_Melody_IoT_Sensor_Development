#!/usr/bin/env python3
"""
generate_dataset.py — Multi‑modal Sensor Dataset Generator for Emotion Classifier
===================================================================================

Generates synthetic training sequences matching the sensor_box.csv format.
Each sequence contains 12 consecutive frames of 26-dimensional features:
  [light(6), sound(6), touch(5), camera(9)]

Author: KUANG, Haozhe
Affiliation: HKUST
Email: hkuangab@connect.ust.hk
Date: October 2026
"""

import os
import sys
import math
import time
import numpy as np

# ---------------------------------------------------------------------------
# Emotion profiles – 20 vivid emotion classes
# Format: {class_id: {'name': ..., 'mean': [...], 'std': [...]}}
# Feature order (26 dims):
#   light_raw, light_brightness, light_trend, light_variance,
#   light_is_daylight, light_flicker_freq,
#   sound_raw, sound_energy, sound_speech_rate, sound_continuity,
#   sound_spike, sound_human_presence,
#   touch_irq, touch_count, touch_freq, touch_intent, touch_pattern_enc,
#   cam_top_count, cam_top1_h, cam_top1_s, cam_top1_v,
#   cam_top2_s, cam_top2_v, cam_top3_h, cam_top3_s, cam_top3_v
# ---------------------------------------------------------------------------
EMOTION_PROFILES = {
    0: {
        'name': 'Serene Bliss',
        'mean': [330, 0.322, 0.0, 50.0, 1, 0,
                 180, 0.280, 0.0, 0.850, 0, 1,
                 0, 0, 0.0, 0.2, 0,
                 3, 5, 10, 4, 9, 4, 4, 3, 10],
        'std':  [20, 0.020, 1.5, 30.0, 0.1, 0.1,
                 40, 0.080, 0.0, 0.100, 0.1, 0.1,
                 0.3, 5, 0.05, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    1: {
        'name': 'Joyful Exuberance',
        'mean': [370, 0.365, 1.0, 110.0, 1, 0,
                 580, 0.445, 0.007, 0.960, 0.2, 1,
                 0.8, 14, 0.190, 0.7, 1,
                 3, 7, 11, 7, 10, 6, 5, 10, 4],
        'std':  [30, 0.025, 2.0, 60.0, 0.1, 0.1,
                 65, 0.090, 0.003, 0.060, 0.1, 0.1,
                 0.5, 7, 0.045, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    2: {
        'name': 'Melancholic Nostalgia',
        'mean': [265, 0.259, -1.8, 155.0, 0.7, 0,
                 105, 0.225, 0.0, 0.720, 0, 1,
                 0, 0, 0.0, 0.2, 0,
                 3, 3, 2, 6, 1, 3, 0, 1, 5],
        'std':  [25, 0.022, 2.5, 80.0, 0.2, 0.1,
                 30, 0.065, 0.0, 0.120, 0.1, 0.1,
                 0.2, 3, 0.02, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    3: {
        'name': 'Furious Rage',
        'mean': [305, 0.302, 2.5, 235.0, 0.9, 0,
                 540, 0.485, 0.012, 0.870, 0.3, 1,
                 1.2, 30, 0.510, 0.8, 1,
                 3, 5, 10, 4, 9, 4, 4, 3, 10],
        'std':  [35, 0.032, 3.2, 145.0, 0.2, 0.1,
                 75, 0.097, 0.005, 0.075, 0.1, 0.1,
                 0.6, 9, 0.055, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    4: {
        'name': 'Anxious Trembling',
        'mean': [275, 0.269, -0.5, 195.0, 0.8, 0,
                 450, 0.375, 0.009, 0.820, 0.1, 1,
                 0.6, 18, 0.620, 0.5, 0,
                 3, 4, 8, 5, 7, 5, 2, 3, 8],
        'std':  [28, 0.023, 2.8, 98.0, 0.2, 0.1,
                 55, 0.088, 0.004, 0.093, 0.1, 0.1,
                 0.4, 6, 0.048, 0.2, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    5: {
        'name': 'Calm Contentment',
        'mean': [340, 0.332, 0.3, 42.0, 1, 0,
                 165, 0.263, 0.0, 0.890, 0, 1,
                 0, 0, 0.0, 0.3, 0,
                 3, 6, 9, 5, 8, 5, 3, 4, 9],
        'std':  [18, 0.018, 1.2, 25.0, 0.1, 0.1,
                 35, 0.072, 0.0, 0.086, 0.1, 0.1,
                 0.2, 4, 0.04, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    6: {
        'name': 'Ecstatic Wonder',
        'mean': [388, 0.379, 1.8, 138.0, 1, 0,
                 610, 0.462, 0.011, 0.970, 0.2, 1,
                 1.1, 22, 0.680, 0.8, 1,
                 3, 7, 12, 7, 11, 7, 6, 11, 5],
        'std':  [32, 0.026, 2.2, 69.0, 0.1, 0.1,
                 70, 0.091, 0.004, 0.058, 0.1, 0.1,
                 0.5, 8, 0.052, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    7: {
        'name': 'Gloomy Despair',
        'mean': [242, 0.237, -2.2, 198.0, 0.6, 0,
                 88, 0.197, 0.0, 0.670, 0, 1,
                 0, 0, 0.0, 0.1, 0,
                 3, 2, 1, 5, 0, 2, 0, 0, 4],
        'std':  [22, 0.021, 2.7, 92.0, 0.2, 0.1,
                 28, 0.059, 0.0, 0.128, 0.1, 0.1,
                 0.2, 2, 0.02, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    8: {
        'name': 'Playful Mischief',
        'mean': [349, 0.341, 0.8, 108.0, 1, 0,
                 505, 0.418, 0.013, 0.910, 0.2, 1,
                 0.7, 16, 0.530, 0.6, 1,
                 3, 6, 10, 5, 9, 5, 4, 4, 9],
        'std':  [27, 0.024, 1.9, 65.0, 0.1, 0.1,
                 58, 0.087, 0.005, 0.079, 0.1, 0.1,
                 0.4, 6, 0.047, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    9: {
        'name': 'Tender Affection',
        'mean': [322, 0.315, -0.2, 38.0, 1, 0,
                 205, 0.295, 0.0, 0.930, 0, 1,
                 0, 0, 0.0, 0.4, 0,
                 3, 5, 9, 4, 8, 4, 3, 3, 8],
        'std':  [19, 0.019, 1.3, 22.0, 0.1, 0.1,
                 42, 0.076, 0.0, 0.078, 0.1, 0.1,
                 0.2, 3, 0.03, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    10: {
        'name': 'Irritated Frustration',
        'mean': [287, 0.281, 1.2, 186.0, 0.9, 0,
                 498, 0.454, 0.017, 0.860, 0.3, 1,
                 1.0, 26, 0.710, 0.7, 1,
                 3, 5, 10, 4, 9, 4, 4, 3, 10],
        'std':  [33, 0.031, 2.9, 132.0, 0.2, 0.1,
                 68, 0.094, 0.006, 0.081, 0.1, 0.1,
                 0.5, 8, 0.053, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    11: {
        'name': 'Peaceful Slumber',
        'mean': [252, 0.246, -0.8, 28.0, 0.5, 0,
                 95, 0.213, 0.0, 0.990, 0, 0,
                 0, 0, 0.0, 0.1, 0,
                 2, 4, 8, 3, 7, 3, 2, 2, 7],
        'std':  [16, 0.016, 1.0, 18.0, 0.2, 0.1,
                 25, 0.061, 0.0, 0.042, 0.1, 0.1,
                 0.2, 2, 0.02, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    12: {
        'name': 'Exhilarating Thrill',
        'mean': [397, 0.388, 2.8, 212.0, 1, 0,
                 642, 0.493, 0.018, 0.940, 0.3, 1,
                 1.5, 35, 0.760, 0.9, 1,
                 3, 7, 12, 7, 11, 7, 6, 11, 5],
        'std':  [36, 0.033, 3.5, 162.0, 0.1, 0.1,
                 80, 0.099, 0.006, 0.068, 0.1, 0.1,
                 0.6, 10, 0.057, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    13: {
        'name': 'Wistful Longing',
        'mean': [277, 0.267, -1.0, 124.0, 0.8, 0,
                 139, 0.241, 0.0, 0.770, 0, 1,
                 0, 0, 0.0, 0.3, 0,
                 3, 4, 7, 5, 6, 4, 1, 2, 6],
        'std':  [24, 0.022, 2.3, 76.0, 0.2, 0.1,
                 33, 0.069, 0.0, 0.109, 0.1, 0.1,
                 0.2, 4, 0.03, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    14: {
        'name': 'Determined Grit',
        'mean': [363, 0.355, 1.5, 149.0, 1, 0,
                 488, 0.433, 0.010, 0.895, 0.1, 1,
                 0.9, 20, 0.590, 0.7, 1,
                 3, 6, 10, 5, 9, 5, 4, 4, 9],
        'std':  [29, 0.026, 2.4, 103.0, 0.1, 0.1,
                 62, 0.084, 0.004, 0.074, 0.1, 0.1,
                 0.4, 7, 0.046, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    15: {
        'name': 'Bittersweet Reminiscence',
        'mean': [293, 0.284, -0.6, 173.0, 0.8, 0,
                 221, 0.310, 0.003, 0.830, 0.1, 1,
                 0.2, 8, 0.038, 0.4, 0,
                 3, 5, 9, 4, 8, 4, 3, 3, 8],
        'std':  [26, 0.024, 2.1, 111.0, 0.2, 0.1,
                 47, 0.077, 0.002, 0.095, 0.1, 0.1,
                 0.3, 5, 0.036, 0.2, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    16: {
        'name': 'Awestruck Reverence',
        'mean': [406, 0.404, 2.2, 201.0, 1, 0,
                 598, 0.471, 0.015, 0.955, 0.2, 1,
                 1.3, 28, 0.730, 0.8, 1,
                 3, 7, 12, 7, 11, 7, 6, 11, 5],
        'std':  [34, 0.028, 3.0, 157.0, 0.1, 0.1,
                 72, 0.093, 0.005, 0.063, 0.1, 0.1,
                 0.5, 9, 0.054, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    17: {
        'name': 'Sullen Resignation',
        'mean': [248, 0.244, -1.5, 187.0, 0.7, 0,
                 119, 0.234, 0.0, 0.740, 0, 1,
                 0, 0, 0.0, 0.2, 0,
                 3, 3, 2, 6, 1, 3, 0, 1, 5],
        'std':  [23, 0.021, 2.6, 94.0, 0.2, 0.1,
                 31, 0.063, 0.0, 0.116, 0.1, 0.1,
                 0.2, 3, 0.02, 0.1, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    18: {
        'name': 'Radiant Hope',
        'mean': [373, 0.364, 1.3, 86.0, 1, 0,
                 532, 0.425, 0.006, 0.948, 0.1, 1,
                 0.5, 12, 0.630, 0.6, 1,
                 3, 6, 10, 5, 9, 5, 4, 4, 9],
        'std':  [28, 0.025, 1.8, 52.0, 0.1, 0.1,
                 60, 0.085, 0.003, 0.071, 0.1, 0.1,
                 0.4, 6, 0.044, 0.2, 0.4,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    },
    19: {
        'name': 'Embarrassed Fluster',
        'mean': [309, 0.299, 0.5, 214.0, 0.9, 0,
                 467, 0.389, 0.014, 0.845, 0.2, 1,
                 0.4, 15, 0.545, 0.5, 0,
                 3, 5, 10, 4, 9, 4, 4, 3, 10],
        'std':  [31, 0.029, 2.6, 151.0, 0.2, 0.1,
                 64, 0.092, 0.005, 0.089, 0.1, 0.1,
                 0.4, 7, 0.049, 0.2, 0.3,
                 0.5, 1, 2, 1, 2, 1, 1, 1, 2]
    }
}

NUM_CLASSES = len(EMOTION_PROFILES)
FEATURE_DIM = 26

# ---------------------------------------------------------------------------
# Dataset configuration
# ---------------------------------------------------------------------------
DATASET_CONFIG = {
    'num_sequences': 62500,
    'sequence_length': 27,
    'noise_level': 0.07,
    'valid_window': 15,
    'extract_length': 12,
    'random_state': 42,
}


def print_dataset_info():
    """
    Print a formatted summary of the dataset configuration and emotion classes.

    Displays the number of classes, feature dimensions, sequence lengths,
    noise level, random seed, and lists all emotion profile names with IDs.

    Parameters: None

    Returns: None
    """
    print("\n" + "=" * 65)
    print("  MULTI-MODAL DATASET GENERATION INFO")
    print("=" * 65)
    print(f"  Number of emotion classes:     {NUM_CLASSES}")
    print(f"  Feature dimensions:            {FEATURE_DIM}")
    print(f"  Sequence length (raw):         {DATASET_CONFIG['sequence_length']}")
    print(f"  Extract length:                {DATASET_CONFIG['extract_length']}")
    print(f"  Noise level:                   {DATASET_CONFIG['noise_level']}")
    print(f"  Random seed:                   {DATASET_CONFIG['random_state']}")
    print("=" * 65)
    print("\n  Emotion Classes:")
    for pid, prof in EMOTION_PROFILES.items():
        print(f"    [{pid:2d}] {prof['name']:<30s}")
    print("=" * 65 + "\n")


def sample_features(profile_id):
    """
    Generate a single 26-dimensional feature vector sampled from a Gaussian
    distribution defined by the emotion profile with the given ID.

    The vector is constructed as:
        feature = mean + noise_level * std * 2.0 * N(0,1)
    followed by clamping to physically plausible ranges for each sensor modality.

    Parameters:
        profile_id (int): Integer ID of the emotion profile (0..19).

    Returns:
        np.ndarray: A 1-D float32 array of shape (26,) containing the sampled
                    and clamped feature vector.
    """
    prof = EMOTION_PROFILES[profile_id]
    mean = np.array(prof['mean'], dtype=np.float32)
    std  = np.array(prof['std'],  dtype=np.float32)

    # Add Gaussian noise scaled by noise_level
    noise = np.random.normal(0, DATASET_CONFIG['noise_level'], FEATURE_DIM).astype(np.float32)
    vec = mean + noise * std * 2.0

    # Clamp to sensible ranges
    vec[0] = np.clip(vec[0], 0, 1023)              # light_raw
    vec[1] = np.clip(vec[1], 0.0, 1.0)             # brightness
    vec[3] = max(vec[3], 0.0)                      # variance >= 0
    vec[4] = np.round(np.clip(vec[4], 0, 1))       # is_daylight binary
    vec[5] = max(vec[5], 0.0)                      # flicker_freq >= 0

    vec[6] = np.clip(vec[6], 0, 1023)              # sound_raw
    vec[7] = np.clip(vec[7], 0.0, 1.0)             # energy
    vec[8] = max(vec[8], 0.0)                      # speech_rate >= 0
    vec[9] = np.clip(vec[9], 0.0, 1.0)             # continuity
    vec[10] = np.round(np.clip(vec[10], 0, 1))     # spike binary
    vec[11] = np.round(np.clip(vec[11], 0, 1))     # human_presence binary

    vec[12] = max(vec[12], 0)                      # touch_irq
    vec[13] = max(vec[13], 0)                      # touch_count
    vec[14] = max(vec[14], 0.0)                    # touch_freq
    vec[15] = np.clip(vec[15], 0.0, 1.0)           # touch_intent
    vec[16] = np.round(np.clip(vec[16], 0, 1))     # touch_pattern_enc

    vec[17] = np.clip(vec[17], 0, 3)               # cam_top_count
    for idx in range(18, 26):
        vec[idx] = np.clip(vec[idx], 0, 15)        # HSV bins

    vec = np.nan_to_num(vec, nan=0.0)
    return vec


def generate_base_sequence(profile_id, length):
    """
    Generate a raw (pre-noise) sequence of feature vectors for a single emotion.

    Each time step is independently sampled via `sample_features`, then a small
    temporal drift is added to consecutive frames to simulate natural variation.
    After drift, values are re-clamped to valid ranges.

    Parameters:
        profile_id (int): Emotion class ID (0..19).
        length (int): Number of time steps in the sequence (e.g., 27).

    Returns:
        np.ndarray: Float32 array of shape (length, 26) representing the base
                    sequence before transition noise is applied.
    """
    seq = np.zeros((length, FEATURE_DIM), dtype=np.float32)
    for t in range(length):
        vec = sample_features(profile_id)
        if t > 0:
            drift = np.random.normal(0, 0.015, FEATURE_DIM).astype(np.float32)
            vec = vec + drift * 30.0
            # Re-clamp (simplified)
            vec[0] = np.clip(vec[0], 0, 1023)
            vec[1] = np.clip(vec[1], 0.0, 1.0)
            vec[3] = max(vec[3], 0.0)
            vec[4] = np.round(np.clip(vec[4], 0, 1))
            vec[5] = max(vec[5], 0.0)
            vec[6] = np.clip(vec[6], 0, 1023)
            vec[7] = np.clip(vec[7], 0.0, 1.0)
            vec[8] = max(vec[8], 0.0)
            vec[9] = np.clip(vec[9], 0.0, 1.0)
            vec[10] = np.round(np.clip(vec[10], 0, 1))
            vec[11] = np.round(np.clip(vec[11], 0, 1))
            vec[12] = max(vec[12], 0)
            vec[13] = max(vec[13], 0)
            vec[14] = max(vec[14], 0.0)
            vec[15] = np.clip(vec[15], 0.0, 1.0)
            vec[16] = np.round(np.clip(vec[16], 0, 1))
            vec[17] = np.clip(vec[17], 0, 3)
            for idx in range(18, 26):
                vec[idx] = np.clip(vec[idx], 0, 15)
        seq[t] = vec
    return seq


def add_transition_noise(seq):
    """
    Apply additional Gaussian noise to an entire sequence to simulate
    measurement jitter and transient effects.

    Noise is sampled as N(0, noise_level*2) and scaled by 20, then added
    element-wise. All values are subsequently clamped to the same physical
    bounds used in `sample_features`.

    Parameters:
        seq (np.ndarray): Float32 array of shape (length, 26).

    Returns:
        np.ndarray: Float32 array of same shape after noise addition and clamping.
    """
    noise = np.random.normal(0, DATASET_CONFIG['noise_level'] * 2.0, seq.shape).astype(np.float32)
    noisy = seq + noise * 20.0
    # Re-clamp
    noisy[:,0] = np.clip(noisy[:,0], 0, 1023)
    noisy[:,1] = np.clip(noisy[:,1], 0.0, 1.0)
    noisy[:,3] = np.maximum(noisy[:,3], 0)
    noisy[:,4] = np.round(np.clip(noisy[:,4], 0, 1))
    noisy[:,5] = np.maximum(noisy[:,5], 0)
    noisy[:,6] = np.clip(noisy[:,6], 0, 1023)
    noisy[:,7] = np.clip(noisy[:,7], 0.0, 1.0)
    noisy[:,8] = np.maximum(noisy[:,8], 0)
    noisy[:,9] = np.clip(noisy[:,9], 0.0, 1.0)
    noisy[:,10] = np.round(np.clip(noisy[:,10], 0, 1))
    noisy[:,11] = np.round(np.clip(noisy[:,11], 0, 1))
    noisy[:,12] = np.maximum(noisy[:,12], 0)
    noisy[:,13] = np.maximum(noisy[:,13], 0)
    noisy[:,14] = np.maximum(noisy[:,14], 0)
    noisy[:,15] = np.clip(noisy[:,15], 0.0, 1.0)
    noisy[:,16] = np.round(np.clip(noisy[:,16], 0, 1))
    noisy[:,17] = np.clip(noisy[:,17], 0, 3)
    for idx in range(18, 26):
        noisy[:,idx] = np.clip(noisy[:,idx], 0, 15)
    return noisy


def extract_valid_subsequence(seq, target_len):
    """
    Extract a contiguous subsequence of fixed length from a longer sequence,
    starting from a predefined offset (`valid_window`).

    This simulates ignoring the initial transient frames and keeping only the
    stable portion of the signal.

    Parameters:
        seq (np.ndarray): Full sequence of shape (length, 26).
        target_len (int): Desired length of the extracted subsequence (default 12).

    Returns:
        np.ndarray: Subsequence of shape (target_len, 26). If the sequence is
                    shorter than valid_window + target_len, the last `target_len`
                    frames are returned instead.
    """
    start = DATASET_CONFIG['valid_window']
    end = start + target_len
    if end <= seq.shape[0]:
        return seq[start:end]
    return seq[-target_len:]


def generate_dataset():
    """
    Generate the full synthetic dataset consisting of `num_sequences` examples.

    For each example:
        - Select an emotion class (cycling through 0..19).
        - Generate a raw sequence of length `sequence_length`.
        - Apply transition noise.
        - Extract a valid subsequence of length `extract_length` (12).
        - Append to the collection.

    Progress is printed every 10,000 sequences along with estimated time remaining.

    Parameters: None

    Returns:
        tuple: (X, y) where
            X: np.ndarray of shape (num_sequences, 12, 26), dtype float32
            y: np.ndarray of shape (num_sequences,), dtype int64, class labels 0..19
    """
    print("[INFO] Generating multi-modal synthetic dataset...")
    start_time = time.time()
    np.random.seed(DATASET_CONFIG['random_state'])

    num_base = DATASET_CONFIG['num_sequences']
    extract_len = DATASET_CONFIG['extract_length']

    all_X = []
    all_y = []

    for i in range(num_base):
        profile_id = i % NUM_CLASSES
        seq = generate_base_sequence(profile_id, DATASET_CONFIG['sequence_length'])
        seq = add_transition_noise(seq)
        core = extract_valid_subsequence(seq, extract_len)
        all_X.append(core)
        all_y.append(profile_id)

        if (i+1) % 10000 == 0:
            elapsed = time.time() - start_time
            progress = (i+1)/num_base*100
            rate = (i+1)/elapsed
            eta = (num_base-i-1)/rate if rate>0 else 0
            print(f"[INFO] Generated {i+1}/{num_base} ({progress:.1f}%) [{rate:.0f} seq/s, ETA {eta:.0f}s]")

    X = np.array(all_X, dtype=np.float32)
    y = np.array(all_y, dtype=np.int64)

    elapsed = time.time() - start_time
    print(f"\n[INFO] Done in {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"[INFO] X shape: {X.shape}")
    print(f"[INFO] y shape: {y.shape}")
    print(f"[INFO] Feature range: [{X.min():.2f}, {X.max():.2f}]")
    print(f"[INFO] NaN count: {np.isnan(X).sum()}")
    label_counts = np.bincount(y, minlength=NUM_CLASSES)
    print(f"[INFO] Samples per class: {label_counts}")
    return X, y


def save_dataset(X, y, output_dir="toy_dataset"):
    """
    Save the generated dataset to NumPy binary files (.npy).

    Creates the output directory if it does not exist. Prints file sizes.

    Parameters:
        X (np.ndarray): Feature tensor of shape (N, 12, 26).
        y (np.ndarray): Label vector of shape (N,).
        output_dir (str): Directory path for saving (default "toy_dataset").

    Returns: None
    """
    os.makedirs(output_dir, exist_ok=True)
    x_path = os.path.join(output_dir, "X_seq.npy")
    y_path = os.path.join(output_dir, "y_labels.npy")
    np.save(x_path, X)
    np.save(y_path, y)
    x_size = os.path.getsize(x_path)/(1024 * 1024)
    y_size = os.path.getsize(y_path)/1024
    print(f"\n[INFO] Saved X: {x_path} ({x_size:.1f} MB)")
    print(f"[INFO] Saved y: {y_path} ({y_size:.1f} KB)")


def main():
    """
    Main entry point: prints banner, dataset info, generates dataset, and saves it.

    Parameters: None

    Returns: None
    """
    print("=" * 75)
    print("  MULTI-MODAL SENSOR DATASET GENERATOR")
    print("  Author: KUANG, Haozhe | HKUST")
    print("=" * 75)
    print_dataset_info()
    X, y = generate_dataset()
    save_dataset(X, y)
    print("\n[INFO] Ready for training: python3 train_model.py")


if __name__ == "__main__":
    main()