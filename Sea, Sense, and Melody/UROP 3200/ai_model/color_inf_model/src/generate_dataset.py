#!/usr/bin/env python3
"""
generate_dataset.py — Synthetic Emotion Dataset with HSV Histogram Features
=============================================================================
Author: KUANG, Haozhe
Affiliation: Hong Kong University of Science and Technology (HKUST)
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Generates synthetic emotion dataset using 16 complex emotional states
    with HSV color profiles. Each sample represents a simulated camera frame
    with controlled color variations following Markov chain transitions.

    Features extracted:
        - 3 dominant colors (h, s, v, area_ratio) = 12 features
        - color_entropy, saturation_avg, area_imbalance
        - hue_shift, motion_color_change (temporal)

Output: ../data/emotion_synthetic_data.csv (16,000 rows, 17 features + label)
Usage:  python3 generate_dataset.py
=============================================================================
"""

import os
import sys
import math
import random
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import cv2

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emotion_profiles import (
    EMOTION_COLOR_PROFILES, TRANSITION_MATRIX, NUM_CLASSES,
    FEATURE_COLS, INPUT_DIM
)

# ═══════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════
CONFIG = {
    'samples_per_sequence': 500,     # Sequences per starting emotion
    'num_classes': NUM_CLASSES,
    'sequence_length': 20,           # Frames per sequence (Markov chain)
    'window_size': 12,               # Sliding window for training

    # Image preprocessing (simulated)
    'img_width': 120,
    'img_height': 90,
    'gaussian_kernel': (5, 5),
    'gaussian_sigma': 1.8,

    # HSV histogram binning
    'h_bins': 4,
    's_bins': 8,
    'v_bins': 8,
    'saturation_threshold': 25,
    'top_n_colors': 3,

    # Output
    'output_file': os.path.join(DATA_DIR, 'emotion_synthetic_data.csv'),
}


# ═══════════════════════════════════════════════════════════
# SIMULATION FUNCTIONS
# ═══════════════════════════════════════════════════════════

def sample_next_emotion(current_emotion: int) -> int:
    """
    Sample next emotion state using Markov transition probabilities.
    
    Args:
        current_emotion: Current emotion ID (0-15)
    
    Returns:
        Next emotion ID sampled from transition distribution
    """
    transitions = TRANSITION_MATRIX[current_emotion]
    states = list(transitions.keys())
    probs = list(transitions.values())
    return np.random.choice(states, p=probs)


def sample_color_with_noise(base_color: dict, noise: dict, color_idx: int,
                            instability: float) -> dict:
    """
    Sample a color with Gaussian noise, scaled by instability factor.
    
    Args:
        base_color: Base HSV values and ratio
        noise: Noise standard deviations
        color_idx: Index of this color (0, 1, 2)
        instability: Emotion's instability factor
    
    Returns:
        Perturbed color dict with h, s, v, ratio
    """
    # Scale noise by instability
    inst_factor = 1.0 + instability * random.uniform(-0.5, 0.5)
    
    h = base_color['h'] + np.random.normal(0, noise['h_std'][color_idx] * inst_factor)
    s = base_color['s'] + np.random.normal(0, noise['s_std'][color_idx] * inst_factor)
    v = base_color['v'] + np.random.normal(0, noise['v_std'][color_idx] * inst_factor)
    ratio = base_color['ratio'] + random.uniform(-noise['ratio_noise'],
                                                  noise['ratio_noise']) * inst_factor
    
    # Clamp to valid ranges
    h = max(0, min(179, round(h)))
    s = max(0, min(255, round(s)))
    v = max(0, min(255, round(v)))
    ratio = max(0.01, min(0.95, ratio))
    
    return {'h': h, 's': s, 'v': v, 'ratio': ratio}


def generate_frame_colors(emotion_id: int) -> list:
    """
    Generate a set of 3 dominant colors for a given emotion.
    
    Applies noise perturbation based on the emotion's instability factor.
    
    Args:
        emotion_id: Target emotion class ID
    
    Returns:
        List of 3 color dicts with h, s, v, ratio (ratios sum to ~1.0)
    """
    profile = EMOTION_COLOR_PROFILES[emotion_id]
    base_colors = profile['colors']
    noise = profile['noise']
    instability = profile['instability']
    
    # Sample perturbed colors
    sampled = []
    for i, base in enumerate(base_colors):
        sampled.append(sample_color_with_noise(base, noise, i, instability))
    
    # Renormalize ratios to sum to 1.0
    ratios = [c['ratio'] for c in sampled]
    total = sum(ratios)
    if total > 0:
        for c in sampled:
            c['ratio'] = c['ratio'] / total
    
    return sampled


def compute_derived_features(colors: list, prev_colors: list = None) -> dict:
    """
    Compute derived color features from top-3 dominant colors.
    
    Args:
        colors: List of 3 dicts with 'h', 's', 'v', 'ratio'
        prev_colors: Colors from previous frame (for temporal features)
    
    Returns:
        Dictionary with all 17 features
    """
    feats = {}
    
    # Primary color features (NaN-safe)
    for i, c in enumerate(colors):
        h_val = c['h'] if not (isinstance(c['h'], float) and math.isnan(c['h'])) else 0
        s_val = c['s'] if not (isinstance(c['s'], float) and math.isnan(c['s'])) else 0
        v_val = c['v'] if not (isinstance(c['v'], float) and math.isnan(c['v'])) else 0
        r_val = c['ratio'] if not (isinstance(c['ratio'], float) and math.isnan(c['ratio'])) else 0.0
        
        feats[f'c{i+1}_h'] = float(h_val)
        feats[f'c{i+1}_s'] = float(s_val)
        feats[f'c{i+1}_v'] = float(v_val)
        feats[f'c{i+1}_area_ratio'] = float(r_val)
    
    # --- Derived Feature 1: Color Entropy (Shannon, scaled to 0-1) ---
    ratios = [feats[f'c{i+1}_area_ratio'] for i in range(3)]
    total_r = sum(ratios)
    probs = [r / total_r for r in ratios] if total_r > 0 else [1/3] * 3
    entropy = -sum(p * math.log2(p) if p > 0 else 0 for p in probs)
    # Max entropy for 3 categories = log2(3) ≈ 1.585
    feats['color_entropy'] = min(entropy / 1.585, 1.0)
    
    # --- Derived Feature 2: Weighted Saturation Average (0-1) ---
    weights = [feats[f'c{i+1}_area_ratio'] for i in range(3)]
    sats = [feats[f'c{i+1}_s'] for i in range(3)]
    tw = sum(weights)
    feats['saturation_avg'] = sum(w * s for w, s in zip(weights, sats)) / (tw * 255) if tw > 0 else 0.0
    
    # --- Derived Feature 3: Area Imbalance ---
    denom = max(feats['c2_area_ratio'] + feats['c3_area_ratio'], 0.001)
    feats['area_imbalance'] = feats['c1_area_ratio'] / denom
    
    # --- Derived Features 4 & 5: Temporal Changes ---
    if prev_colors is not None:
        cur_hues = [feats[f'c{i+1}_h'] for i in range(3)]
        prev_hues = []
        for pc in prev_colors:
            ph = pc['h'] if not (isinstance(pc['h'], float) and math.isnan(pc['h'])) else 0
            prev_hues.append(float(ph))
        
        shifts = []
        for ch, ph in zip(cur_hues, prev_hues):
            diff = abs(ch - ph)
            circular_diff = min(diff, 180 - diff)
            shifts.append(circular_diff)
        
        feats['hue_shift'] = sum(shifts) / len(shifts)
        feats['motion_color_change'] = min(feats['hue_shift'] / 90.0, 1.0)
    else:
        feats['hue_shift'] = 0.0
        feats['motion_color_change'] = 0.0
    
    return feats


# ═══════════════════════════════════════════════════════════
# DATASET GENERATION
# ═══════════════════════════════════════════════════════════

def generate_sequence(start_emotion: int, length: int) -> list:
    """
    Generate a sequence of frames following Markov emotion transitions.
    
    Args:
        start_emotion: Initial emotion ID
        length: Number of frames to generate
    
    Returns:
        List of records (dicts with features + label)
    """
    records = []
    current_emotion = start_emotion
    prev_colors = None
    
    for frame_idx in range(length):
        # Generate frame colors for current emotion
        colors = generate_frame_colors(current_emotion)
        
        # Compute features
        feats = compute_derived_features(colors, prev_colors)
        feats['ground_truth_mood'] = current_emotion
        
        records.append(feats)
        prev_colors = colors
        
        # Transition to next emotion (except last frame)
        if frame_idx < length - 1:
            current_emotion = sample_next_emotion(current_emotion)
    
    return records


def generate_dataset():
    """
    Generate the complete synthetic emotion dataset.
    
    For each of 16 emotions, generates 500 sequences of 20 frames each.
    Total: 16 x 500 x 20 = 160,000 frames
    After sliding window: ~(160000 - 12 + 1) ≈ 159,989 samples
    
    Actually we'll sample evenly: 1000 frames per emotion after windowing.
    So generate enough sequences to cover ~1000 samples per class.
    """
    print('=' * 65)
    print('  Synthetic Emotion Dataset Generation')
    print(f'  Emotions: {NUM_CLASSES} complex states')
    print(f'  Method: Markov chain + HSV Histogram Binning')
    print(f'  Output: {CONFIG["output_file"]}')
    print('=' * 65)
    
    all_records = []
    targets_per_class = {pid: 0 for pid in range(NUM_CLASSES)}
    target_total = 60000  # Total samples desired
    
    # Generate sequences until we have enough samples
    sequences_generated = 0
    total_samples = 0
    
    while total_samples < target_total:
        # Pick a starting emotion (cycle through all)
        start_emotion = sequences_generated % NUM_CLASSES
        
        # Generate sequence
        seq = generate_sequence(start_emotion, CONFIG['sequence_length'])
        
        # Apply sliding window to create training samples
        for i in range(len(seq) - CONFIG['window_size'] + 1):
            window = seq[i:i + CONFIG['window_size']]
            
            # Label is the emotion at the LAST frame of the window
            label = window[-1]['ground_truth_mood']
            
            # Only keep the last frame's features as the sample
            # (the temporal features already encode the window context)
            record = window[-1].copy()
            all_records.append(record)
            targets_per_class[label] = targets_per_class.get(label, 0) + 1
            total_samples += 1
            
            if total_samples >= target_total:
                break
        
        sequences_generated += 1
        
        if sequences_generated % 50 == 0:
            print(f'  Generated {total_samples}/{target_total} samples '
                  f'({sequences_generated} sequences)')
    
    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    
    # Reorder columns to match expected format
    expected_cols = FEATURE_COLS + ['ground_truth_mood']
    df = df[expected_cols]
    
    # Save to CSV
    output_path = CONFIG['output_file']
    df.to_csv(output_path, index=False)
    
    print(f'\n{"=" * 57}')
    print(f'Dataset saved to: {output_path}')
    print(f'Total samples: {len(df)}')
    print(f'Feature columns: {len(FEATURE_COLS)}')
    print(f'Class distribution:')
    dist = df['ground_truth_mood'].value_counts().sort_index()
    for cls_id, count in dist.items():
        name = EMOTION_COLOR_PROFILES[cls_id]['name']
        print(f'  [{cls_id:2d}] {name:25s}: {count:5d} samples')
    print(f'{"=" * 57}')


if __name__ == '__main__':
    generate_dataset()