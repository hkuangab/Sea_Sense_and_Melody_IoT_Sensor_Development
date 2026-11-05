#!/usr/bin/env python3
"""
emotion_profiles.py — 20 Multi-Modal Emotion Profiles (26-dim)
================================================================

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Defines 20 synthetic emotion profiles with mean/std for 26-dimensional
    sensor features. Used as target classes for the attentional GRU classifier.

    Each profile corresponds to a distinct emotional state (e.g., "Serene Bliss")
    and provides a 26-element mean vector and a 26-element standard deviation
    vector. During dataset generation, samples are drawn from a multivariate
    Gaussian distribution parameterized by these means and stds.

Feature order (26 dims, zero-indexed):
    Index   Feature name
    ------  ------------------------------------
    0       light_raw
    1       light_brightness
    2       light_trend
    3       light_variance
    4       light_is_daylight
    5       light_flicker_freq
    6       sound_raw
    7       sound_energy
    8       sound_speech_rate
    9       sound_continuity
    10      sound_spike
    11      sound_human_presence
    12      touch_irq
    13      touch_count
    14      touch_freq
    15      touch_intent
    16      touch_pattern_enc           # 0=random, 1=rhythmic
    17      cam_top_count
    18      cam_top1_h
    19      cam_top1_s
    20      cam_top1_v
    21      cam_top2_s
    22      cam_top2_v
    23      cam_top3_h
    24      cam_top3_s
    25      cam_top3_v

Usage:
    from emotion_profiles import EMOTION_PROFILES, NUM_CLASSES, INPUT_DIM, WINDOW_SIZE

Notes:
    These profiles are synthetic and intended for demonstration / prototyping
    purposes only. Real-world deployment would require calibration against
    actual sensor readings and user feedback.
"""

# ---------------------------------------------------------------------------
# EMOTION_PROFILES dictionary
# ---------------------------------------------------------------------------
# Each key is an integer class ID (0..19). Each value is a dict containing:
#   'name' : human-readable emotion label (str)
#   'mean' : list of 26 floats — expected value of each feature for this emotion
#   'std'  : list of 26 floats — per-feature standard deviation for sampling noise
#
# The order of elements inside 'mean' and 'std' exactly follows the 26-dim
# feature order documented above.
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


EMOTION_COLOR_PROFILES = {
    0:  {"name": "calm_serenity",      "colors": [{"h": 200, "s": 120, "v": 220}], "instability": 0.05},
    1:  {"name": "warm_affection",     "colors": [{"h": 10,  "s": 170, "v": 230}], "instability": 0.07},
    2:  {"name": "melancholy_blue",    "colors": [{"h": 220, "s": 140, "v": 150}], "instability": 0.09},
    3:  {"name": "anxious_tension",    "colors": [{"h": 30,  "s": 190, "v": 180}], "instability": 0.18},
    4:  {"name": "excited_joy",        "colors": [{"h": 45,  "s": 210, "v": 240}], "instability": 0.14},
    5:  {"name": "dark_despair",       "colors": [{"h": 240, "s": 120, "v": 70}],  "instability": 0.12},
    6:  {"name": "romantic_blush",     "colors": [{"h": 350, "s": 150, "v": 225}], "instability": 0.08},
    7:  {"name": "cold_detachment",    "colors": [{"h": 190, "s": 60,  "v": 200}], "instability": 0.06},
    8:  {"name": "fiery_anger",        "colors": [{"h": 0,   "s": 235, "v": 220}], "instability": 0.22},
    9:  {"name": "mysterious_depth",   "colors": [{"h": 270, "s": 160, "v": 130}], "instability": 0.11},
    10: {"name": "fresh_renewal",      "colors": [{"h": 110, "s": 170, "v": 215}], "instability": 0.07},
    11: {"name": "nostalgic_warmth",   "colors": [{"h": 25,  "s": 150, "v": 205}], "instability": 0.08},
    12: {"name": "dreamy_softness",    "colors": [{"h": 300, "s": 110, "v": 220}], "instability": 0.09},
    13: {"name": "tense_alertness",    "colors": [{"h": 60,  "s": 200, "v": 225}], "instability": 0.16},
    14: {"name": "peaceful_glow",      "colors": [{"h": 170, "s": 120, "v": 230}], "instability": 0.05},
    15: {"name": "stormy_turmoil",     "colors": [{"h": 210, "s": 210, "v": 120}], "instability": 0.20},
}

# ---------------------------------------------------------------------------
# Global constants derived from EMOTION_PROFILES
# ---------------------------------------------------------------------------
# NUM_CLASSES: number of emotion categories (20)
NUM_CLASSES = len(EMOTION_PROFILES)

# INPUT_DIM: dimensionality of the feature vector (26)
INPUT_DIM = 26

# WINDOW_SIZE: number of consecutive time steps fed into the GRU model (12)
WINDOW_SIZE = 12

# FEATURE_COLS: human-readable column names corresponding to the 26 dimensions
# This list is provided for documentation and debugging purposes.
FEATURE_COLS = [
    "light_raw", "light_brightness", "light_trend", "light_variance",
    "light_is_daylight", "light_flicker_freq",
    "sound_raw", "sound_energy", "sound_speech_rate", "sound_continuity",
    "sound_spike", "sound_human_presence",
    "touch_irq", "touch_count", "touch_freq", "touch_intent", "touch_pattern_enc",
    "cam_top_count", "cam_top1_h", "cam_top1_s", "cam_top1_v",
    "cam_top2_s", "cam_top2_v", "cam_top3_h", "cam_top3_s", "cam_top3_v"
]