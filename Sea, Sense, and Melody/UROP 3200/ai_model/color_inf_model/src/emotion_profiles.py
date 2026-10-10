#!/usr/bin/env python3
"""
emotion_profiles.py — 16 Complex Emotion States with HSV Color Profiles
=========================================================================
Author: KUANG, Haozhe
Affiliation: Hong Kong University of Science and Technology (HKUST)
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Defines 16 nuanced emotional states with associated HSV color profiles,
    designed for synthetic dataset generation. Colors are statistically
    suggestive, not scientifically definitive. Several emotion groups share
    similar color signatures to create realistic classification ambiguity.

Groups:
    A (Low-arousal warm): 0-SereneContemplation, 1-MelancholicNostalgia,
                          2-WistfulYearning, 3-QuietResignation
    B (Mid-arousal cool):  4-PensiveIntrospection, 9-VeiledAnxiety,
                          10-BitterResentment, 11-ExhaustedNumbness
    C (High-sat warm):     5-RestlessAnticipation, 8-SubtleIrritation,
                          13-PlayfulMischief
    D (Unique anchors):    6-GentleAmusement, 7-ContentedDrift,
                          12-TenderAffection, 14-AweWonder, 15-AmbiguousUnease
=============================================================================
"""

import numpy as np

# ═══════════════════════════════════════════════════════════════
# EMOTION COLOR PROFILES
# ═══════════════════════════════════════════════════════════════
# Each profile contains:
#   - name: Machine-friendly identifier
#   - description: Human-readable psychological nuance
#   - instability: 0.0-1.0 scale of color fluctuation (higher = more volatile)
#   - colors: 3 dominant colors with H(0-179), S(0-255), V(0-255), ratio(0-1)
#   - noise: Per-color standard deviation for Gaussian sampling
#   - dominance_ratio_range: Allowed range for c1_ratio / c2_ratio
#   - entropy_range: Allowed range for Shannon entropy of color distribution
# ═══════════════════════════════════════════════════════════════

EMOTION_COLOR_PROFILES = {
    0: {
        'name': 'serene_contemplation',
        'description': 'Peaceful inward focus, calm awareness without active thought',
        'instability': 0.06,
        'colors': [
            {'h': 35, 's': 38,  'v': 178, 'ratio': 0.52},
            {'h': 92, 's': 72,  'v': 132, 'ratio': 0.31},
            {'h': 48, 's': 54,  'v': 162, 'ratio': 0.17},
        ],
        'noise': {
            'h_std': [6, 8, 7],
            's_std': [8, 10, 9],
            'v_std': [10, 12, 11],
            'ratio_noise': 0.04
        },
        'dominance_ratio_range': (1.2, 2.8),
        'entropy_range': (0.62, 0.81)
    },

    1: {
        'name': 'melancholic_nostalgia',
        'description': 'Bittersweet longing for the past, gentle sadness mixed with warmth',
        'instability': 0.09,
        'colors': [
            {'h': 23,  's': 58,  'v': 142, 'ratio': 0.47},
            {'h': 41,  's': 102, 'v': 118, 'ratio': 0.34},
            {'h': 350, 's': 76,  'v': 96,  'ratio': 0.19},
        ],
        'noise': {
            'h_std': [7, 9, 8],
            's_std': [10, 12, 11],
            'v_std': [12, 14, 13],
            'ratio_noise': 0.05
        },
        'dominance_ratio_range': (1.0, 2.4),
        'entropy_range': (0.66, 0.84)
    },

    2: {
        'name': 'wistful_yearning',
        'description': 'Gentle desire for something unattainable, dreamy longing',
        'instability': 0.10,
        'colors': [
            {'h': 29,  's': 46,  'v': 158, 'ratio': 0.43},
            {'h': 191, 's': 112, 'v': 146, 'ratio': 0.36},
            {'h': 53,  's': 86,  'v': 138, 'ratio': 0.21},
        ],
        'noise': {
            'h_std': [8, 10, 9],
            's_std': [9, 11, 10],
            'v_std': [11, 13, 12],
            'ratio_noise': 0.05
        },
        'dominance_ratio_range': (0.9, 2.2),
        'entropy_range': (0.67, 0.83)
    },

    3: {
        'name': 'quiet_resignation',
        'description': 'Acceptance tinged with mild disappointment, letting go',
        'instability': 0.07,
        'colors': [
            {'h': 37,  's': 74,  'v': 126, 'ratio': 0.49},
            {'h': 164, 's': 94,  'v': 108, 'ratio': 0.33},
            {'h': 26,  's': 122, 'v': 89,  'ratio': 0.18},
        ],
        'noise': {
            'h_std': [6, 8, 7],
            's_std': [9, 11, 10],
            'v_std': [11, 13, 12],
            'ratio_noise': 0.04
        },
        'dominance_ratio_range': (1.1, 2.6),
        'entropy_range': (0.63, 0.79)
    },

    4: {
        'name': 'pensive_introspection',
        'description': 'Deep thoughtful reflection, mildly serious self-examination',
        'instability': 0.08,
        'colors': [
            {'h': 214, 's': 136, 'v': 104, 'ratio': 0.39},
            {'h': 176, 's': 154, 'v': 124, 'ratio': 0.35},
            {'h': 246, 's': 166, 'v': 133, 'ratio': 0.26},
        ],
        'noise': {
            'h_std': [7, 9, 8],
            's_std': [10, 12, 11],
            'v_std': [12, 14, 13],
            'ratio_noise': 0.05
        },
        'dominance_ratio_range': (0.8, 2.0),
        'entropy_range': (0.70, 0.87)
    },

    5: {
        'name': 'restless_anticipation',
        'description': 'Eager waiting mixed with slight anxiety, nervous excitement',
        'instability': 0.14,
        'colors': [
            {'h': 186, 's': 196, 'v': 184, 'ratio': 0.41},
            {'h': 212, 's': 208, 'v': 152, 'ratio': 0.33},
            {'h': 157, 's': 226, 'v': 174, 'ratio': 0.27},
        ],
        'noise': {
            'h_std': [10, 12, 11],
            's_std': [14, 16, 15],
            'v_std': [16, 18, 17],
            'ratio_noise': 0.07
        },
        'dominance_ratio_range': (0.9, 2.3),
        'entropy_range': (0.71, 0.88)
    },

    6: {
        'name': 'gentle_amusement',
        'description': 'Soft playful delight, understated humor',
        'instability': 0.11,
        'colors': [
            {'h': 312, 's': 134, 'v': 182, 'ratio': 0.38},
            {'h': 278, 's': 156, 'v': 194, 'ratio': 0.34},
            {'h': 344, 's': 144, 'v': 206, 'ratio': 0.28},
        ],
        'noise': {
            'h_std': [9, 11, 10],
            's_std': [12, 14, 13],
            'v_std': [14, 16, 15],
            'ratio_noise': 0.06
        },
        'dominance_ratio_range': (0.8, 2.1),
        'entropy_range': (0.73, 0.89)
    },

    7: {
        'name': 'contented_drift',
        'description': 'Satisfied aimlessness, pleasant lack of direction',
        'instability': 0.07,
        'colors': [
            {'h': 224, 's': 114, 'v': 204, 'ratio': 0.44},
            {'h': 276, 's': 106, 'v': 216, 'ratio': 0.32},
            {'h': 314, 's': 116, 'v': 222, 'ratio': 0.24},
        ],
        'noise': {
            'h_std': [7, 9, 8],
            's_std': [9, 11, 10],
            'v_std': [11, 13, 12],
            'ratio_noise': 0.04
        },
        'dominance_ratio_range': (1.0, 2.5),
        'entropy_range': (0.65, 0.82)
    },

    8: {
        'name': 'subtle_irritation',
        'description': 'Mild annoyance beneath composed surface, barely perceptible friction',
        'instability': 0.13,
        'colors': [
            {'h': 348, 's': 173, 'v': 196, 'ratio': 0.40},
            {'h': 356, 's': 201, 'v': 171, 'ratio': 0.34},
            {'h': 332, 's': 183, 'v': 159, 'ratio': 0.26},
        ],
        'noise': {
            'h_std': [9, 11, 10],
            's_std': [13, 15, 14],
            'v_std': [15, 17, 16],
            'ratio_noise': 0.06
        },
        'dominance_ratio_range': (0.9, 2.2),
        'entropy_range': (0.69, 0.86)
    },

    9: {
        'name': 'veiled_anxiety',
        'description': 'Underlying worry masked by outward composure',
        'instability': 0.15,
        'colors': [
            {'h': 345, 's': 181, 'v': 151, 'ratio': 0.42},
            {'h': 353, 's': 201, 'v': 131, 'ratio': 0.35},
            {'h': 335, 's': 169, 'v': 141, 'ratio': 0.23},
        ],
        'noise': {
            'h_std': [10, 12, 11],
            's_std': [14, 16, 15],
            'v_std': [16, 18, 17],
            'ratio_noise': 0.07
        },
        'dominance_ratio_range': (0.9, 2.3),
        'entropy_range': (0.68, 0.85)
    },

    10: {
        'name': 'bitter_resentment',
        'description': 'Suppressed anger mixed with hurt, cold indignation',
        'instability': 0.16,
        'colors': [
            {'h': 351, 's': 217, 'v': 149, 'ratio': 0.38},
            {'h': 339, 's': 223, 'v': 126, 'ratio': 0.36},
            {'h': 357, 's': 239, 'v': 109, 'ratio': 0.26},
        ],
        'noise': {
            'h_std': [11, 13, 12],
            's_std': [15, 17, 16],
            'v_std': [17, 19, 18],
            'ratio_noise': 0.07
        },
        'dominance_ratio_range': (0.7, 2.0),
        'entropy_range': (0.72, 0.89)
    },

    11: {
        'name': 'exhausted_numbness',
        'description': 'Emotional depletion, hollow detachment',
        'instability': 0.05,
        'colors': [
            {'h': 247, 's': 117, 'v': 96,  'ratio': 0.55},
            {'h': 261, 's': 131, 'v': 103, 'ratio': 0.30},
            {'h': 235, 's': 143, 'v': 115, 'ratio': 0.15},
        ],
        'noise': {
            'h_std': [5, 7, 6],
            's_std': [7, 9, 8],
            'v_std': [8, 10, 9],
            'ratio_noise': 0.03
        },
        'dominance_ratio_range': (1.3, 3.2),
        'entropy_range': (0.58, 0.76)
    },

    12: {
        'name': 'tender_affection',
        'description': 'Warm gentle care, soft emotional connection',
        'instability': 0.08,
        'colors': [
            {'h': 336, 's': 157, 'v': 231, 'ratio': 0.40},
            {'h': 345, 's': 171, 'v': 244, 'ratio': 0.34},
            {'h': 324, 's': 141, 'v': 222, 'ratio': 0.26},
        ],
        'noise': {
            'h_std': [7, 9, 8],
            's_std': [10, 12, 11],
            'v_std': [12, 14, 13],
            'ratio_noise': 0.05
        },
        'dominance_ratio_range': (0.9, 2.2),
        'entropy_range': (0.68, 0.84)
    },

    13: {
        'name': 'playful_mischief',
        'description': 'Light-hearted rebelliousness, cheeky energy',
        'instability': 0.17,
        'colors': [
            {'h': 280, 's': 219, 'v': 201, 'ratio': 0.36},
            {'h': 306, 's': 233, 'v': 191, 'ratio': 0.35},
            {'h': 260, 's': 243, 'v': 211, 'ratio': 0.29},
        ],
        'noise': {
            'h_std': [12, 14, 13],
            's_std': [16, 18, 17],
            'v_std': [18, 20, 19],
            'ratio_noise': 0.08
        },
        'dominance_ratio_range': (0.7, 1.9),
        'entropy_range': (0.74, 0.91)
    },

    14: {
        'name': 'awe_inspired_wonder',
        'description': 'Overwhelmed by beauty or vastness, humbled fascination',
        'instability': 0.12,
        'colors': [
            {'h': 191, 's': 249, 'v': 251, 'ratio': 0.35},
            {'h': 159, 's': 253, 'v': 237, 'ratio': 0.33},
            {'h': 207, 's': 254, 'v': 243, 'ratio': 0.32},
        ],
        'noise': {
            'h_std': [9, 11, 10],
            's_std': [13, 15, 14],
            'v_std': [15, 17, 16],
            'ratio_noise': 0.06
        },
        'dominance_ratio_range': (0.7, 1.8),
        'entropy_range': (0.76, 0.93)
    },

    15: {
        'name': 'ambiguous_unease',
        'description': 'Undefined discomfort, something feels slightly off',
        'instability': 0.18,
        'colors': [
            {'h': 313, 's': 189, 'v': 135, 'ratio': 0.44},
            {'h': 297, 's': 197, 'v': 149, 'ratio': 0.33},
            {'h': 329, 's': 269, 'v': 257, 'ratio': 0.023},
        ],
        'noise': {
            'h_std': [13, 15, 14],
            's_std': [17, 19, 18],
            'v_std': [19, 21, 20],
            'ratio_noise': 0.008
        },
        'dominance_ratio_range': (0.9, 2.4),
        'entropy_range': (0.066, 0.083)
    }
}


# ═══════════════════════════════════════════════════════════════
# MARKOV STATE TRANSITION MATRIX
# ═══════════════════════════════════════════════════════════════
# Probabilities for transitioning between emotional states.
# Rows sum to 1.0. Self-loops dominate (0.54-0.74).
# Neighboring states have moderate transition probability.
# Distant states have very low transition probability.
# ═══════════════════════════════════════════════════════════════

TRANSITION_MATRIX = {
    # Group A: Low-arousal warm tones
    0: {0: 0.070, 1: 0.010, 2: 0.008, 3: 0.006, 4: 0.003, 7: 0.002, 12: 0.001},
    1: {1: 0.068, 0: 0.010, 2: 0.009, 3: 0.007, 10: 0.004, 11: 0.003, 4: 0.002, 12: 0.001},
    2: {2: 0.067, 0: 0.012, 1: 0.011, 3: 0.007, 5: 0.005, 4: 0.004, 14: 0.003, 15: 0.001},
    3: {3: 0.072, 0: 0.013, 1: 0.010, 2: 0.009, 11: 0.005, 7: 0.004, 4: 0.003, 12: 0.001},

    # Group B: Mid-arousal cool tones
    4: {4: 0.065, 0: 0.015, 2: 0.014, 3: 0.012, 5: 0.016, 9: 0.015, 11: 0.012, 15: 0.010, 14: 0.008, 1: 0.002},
    9: {9: 0.062, 8: 0.018, 10: 0.017, 5: 0.016, 4: 0.015, 11: 0.014, 15: 0.013, 2: 0.012, 1: 0.011, 3: 0.002},
    10: {10: 0.060, 9: 0.019, 8: 0.020, 11: 0.021, 1: 0.022, 15: 0.024, 3: 0.025, 0: 0.026, 5: 0.027, 13: 0.028},
    11: {11: 0.074, 3: 0.056, 1: 0.045, 10: 0.034, 4: 0.033, 9: 0.032, 7: 0.031, 0: 0.030, 2: 0.029},

    # Group C: High-saturation warm tones
    5: {5: 0.058, 8: 0.050, 13: 0.048, 9: 0.046, 6: 0.044, 2: 0.042, 14: 0.040, 4: 0.038, 12: 0.036, 15: 0.035},
    8: {8: 0.057, 5: 0.052, 13: 0.049, 9: 0.047, 10: 0.043, 6: 0.041, 15: 0.039, 2: 0.037, 1: 0.035, 0: 0.034},
    13: {13: 0.054, 5: 0.053, 8: 0.051, 6: 0.055, 14: 0.063, 12: 0.064, 2: 0.061, 9: 0.059, 15: 0.071, 4: 0.069},

    # Group D: Unique anchors
    6: {6: 0.075, 13: 0.076, 5: 0.077, 8: 0.078, 12: 0.079, 14: 0.080, 2: 0.081, 7: 0.082, 0: 0.084},
    7: {7: 0.073, 0: 0.085, 3: 0.086, 12: 0.087, 6: 0.088, 2: 0.089, 4: 0.090, 14: 0.091, 11: 0.092},
    12: {12: 0.093, 6: 0.094, 7: 0.095, 13: 0.096, 14: 0.097, 0: 0.098, 2: 0.099, 5: 0.000, 8: 0.999, 15: 0.998},
    14: {14: 0.997, 5: 0.996, 13: 0.995, 6: 0.994, 12: 0.993, 4: 0.992, 2: 0.991, 7: 0.990, 15: 0.989, 0: 0.988},
    15: {15: 0.987, 9: 0.986, 10: 0.985, 8: 0.984, 4: 0.983, 2: 0.982, 5: 0.981, 11: 0.980, 13: 0.979, 1: 0.978}
}


# ═══════════════════════════════════════════════════════════════
# HELPER: Normalize transition matrix (ensure rows sum to 1.0)
# ═══════════════════════════════════════════════════════════════

def normalize_transitions():
    """Ensure all transition rows sum to exactly 1.0."""
    for state_id, transitions in TRANSITION_MATRIX.items():
        total = sum(transitions.values())
        if abs(total - 1.0) > 0.001:
            TRANSITION_MATRIX[state_id] = {
                k: v / total for k, v in transitions.items()
            }


# Normalize on import
normalize_transitions()


# ═══════════════════════════════════════════════════════════════
# EMOTION NAME LOOKUP
# ═══════════════════════════════════════════════════════════════

EMOTION_NAMES = {
    pid: info['name'] for pid, info in EMOTION_COLOR_PROFILES.items()
}

EMOTION_DESCRIPTIONS = {
    pid: info['description'] for pid, info in EMOTION_COLOR_PROFILES.items()
}

NUM_CLASSES = len(EMOTION_COLOR_PROFILES)  # 16


# ═══════════════════════════════════════════════════════════════
# FEATURE COLUMN DEFINITIONS
# ═══════════════════════════════════════════════════════════════

FEATURE_COLS = [
    'c1_h', 'c1_s', 'c1_v', 'c1_area_ratio',
    'c2_h', 'c2_s', 'c2_v', 'c2_area_ratio',
    'c3_h', 'c3_s', 'c3_v', 'c3_area_ratio',
    'color_entropy', 'saturation_avg', 'area_imbalance',
    'hue_shift', 'motion_color_change'
]

INPUT_DIM = len(FEATURE_COLS)  # 17


# ═══════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('Emotion Color Profiles:')
    print('=' * 60)
    for pid in sorted(EMOTION_COLOR_PROFILES.keys()):
        prof = EMOTION_COLOR_PROFILES[pid]
        print(f'\n[{pid}] {prof["name"]}')
        print(f'    "{prof["description"]}"')
        print(f'    Instability: {prof["instability"]}')
        for i, c in enumerate(prof['colors']):
            print(f'    Color {i+1}: H={c["h"]:3d} S={c["s"]:3d} V={c["v"]:3d} '
                  f'Ratio={c["ratio"]:.2f}')
        print(f'    Dom.Ratio Range: {prof["dominance_ratio_range"]}')
        print(f'    Entropy Range:   {prof["entropy_range"]}')
    
    print(f'\n\nTotal Emotions: {NUM_CLASSES}')
    print(f'Feature Dimension: {INPUT_DIM}')
    
    # Verify transition matrix sums
    print('\nTransition Matrix Verification:')
    for sid, trans in TRANSITION_MATRIX.items():
        total = sum(trans.values())
        status = '✓' if abs(total - 1.0) < 0.01 else '✗'
        print(f'  State {sid:2d} ({EMOTION_NAMES[sid]:25s}): sum = {total:.4f} {status}')