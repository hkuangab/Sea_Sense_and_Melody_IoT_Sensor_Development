#!/usr/bin/env python3
"""
camera_infer.py — Real-time Emotion Inference with HSV Histogram Features
==========================================================================
Author: KUANG, Haozhe
Affiliation: Hong Kong University of Science and Technology (HKUST)
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Runs real-time emotion classification using HSV histogram binning
    to extract top-3 dominant colors. Uses pre-trained GRU model with
    16 complex emotional states.

    ONLY COLOR-PATTERN DEMO, NOT REAL EMOTION.

Dependencies: picamera2, opencv-python, numpy, torch, scikit-learn
Usage:  python3 camera_infer.py
Keys:   q - Quit
        r - Reset temporal buffer
        d - Toggle debug overlay
        s - Save current frame to captured_frames/
===========================================================================
"""

import os
import sys
import time
import math
import pickle
import warnings
from collections import deque
from datetime import datetime
warnings.filterwarnings('ignore')

import cv2
import numpy as np
import torch
import torch.nn as nn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mood_model import GRUMoodClassifier, load_model
from emotion_profiles import (
    EMOTION_COLOR_PROFILES, NUM_CLASSES, FEATURE_COLS, INPUT_DIM
)

# ═══════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
DATA_DIR = os.path.join(BASE_DIR, 'data')
CAPTURE_DIR = os.path.join(BASE_DIR, 'captured_frames')

# Ensure capture directory exists
os.makedirs(CAPTURE_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════
CONFIG = {
    # Model paths
    'model_path': os.path.join(MODELS_DIR, 'lstm_emotion_model.pth'),
    'scaler_path': os.path.join(MODELS_DIR, 'scaler.pkl'),

    # Camera settings
    'camera_resolution': (640, 480),    # 4:3 aspect ratio
    'target_size': (160, 120),           # Processing size
    'frame_interval': 0.01,              # Even faster capture

    # HSV histogram binning
    'gaussian_kernel': (5, 5),
    'gaussian_sigma': 1.8,
    'h_bins': 4,
    's_bins': 8,
    'v_bins': 8,
    'saturation_threshold': 25,
    'top_n_colors': 3,

    # Temporal window
    'window_size': 12,

    # Display
    'display_width': 1360,               # More reasonable large window
    'display_height': 760,               # Leave room for taskbar
    'overlay_alpha': 0.55,

    # Smoothing
    'prediction_smoothing': 5,
    'confidence_threshold': 0.3,
    
    # Capture
    'save_original_only': True,
}

# ═══════════════════════════════════════════════════════════
# EMOTION DISPLAY INFO
# ═══════════════════════════════════════════════════════════

EMOTION_LABELS = {
    pid: info['name'].replace('_', ' ').title()
    for pid, info in EMOTION_COLOR_PROFILES.items()
}

# BGR colors for display (derived from HSV base)
EMOTION_DISPLAY_COLORS = {}
for pid, info in EMOTION_COLOR_PROFILES.items():
    base = info['colors'][0]
    h_clamped = min(max(base['h'], 0), 179)
    s_clamped = min(max(base['s'], 0), 255)
    v_clamped = min(max(base['v'], 0), 255)
    hsv_pixel = np.uint8([[[h_clamped, s_clamped, v_clamped]]])
    bgr = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
    EMOTION_DISPLAY_COLORS[pid] = (int(bgr[0]), int(bgr[1]), int(bgr[2]))

INSTABILITY_COLORS = {
    'stable': (100, 200, 100),
    'moderate': (100, 180, 220),
    'volatile': (100, 100, 220)
}


# ═══════════════════════════════════════════════════════════
# HSV HISTOGRAM COLOR EXTRACTION
# ═══════════════════════════════════════════════════════════

def extract_top_colors_from_hsv(hsv_img: np.ndarray) -> list:
    """
    Extract top-N dominant colors using HSV histogram binning.
    """
    blurred = cv2.GaussianBlur(hsv_img, CONFIG['gaussian_kernel'], CONFIG['gaussian_sigma'])
    
    saturation = blurred[:, :, 1].astype(np.int32)
    value = blurred[:, :, 2].astype(np.int32)
    hue = blurred[:, :, 0].astype(np.int32)
    
    grayscale_mask = saturation < CONFIG['saturation_threshold']
    color_mask = ~grayscale_mask
    
    if not np.any(color_mask):
        return [
            {'h': np.nan, 's': np.nan, 'v': np.nan, 'ratio': np.nan},
            {'h': np.nan, 's': np.nan, 'v': np.nan, 'ratio': np.nan},
            {'h': np.nan, 's': np.nan, 'v': np.nan, 'ratio': np.nan}
        ]
    
    h_bin_size = 180 // CONFIG['h_bins']
    s_bin_size = 256 // CONFIG['s_bins']
    v_bin_size = 256 // CONFIG['v_bins']
    
    h_quant = (hue[color_mask] // h_bin_size).clip(0, CONFIG['h_bins'] - 1)
    s_quant = (saturation[color_mask] // s_bin_size).clip(0, CONFIG['s_bins'] - 1)
    v_quant = (value[color_mask] // v_bin_size).clip(0, CONFIG['v_bins'] - 1)
    
    bin_index = (h_quant * CONFIG['s_bins'] * CONFIG['v_bins'] +
                 s_quant * CONFIG['v_bins'] +
                 v_quant)
    
    unique_bins, counts = np.unique(bin_index, return_counts=True)
    
    sorted_indices = np.argsort(counts)[::-1]
    top_bins = unique_bins[sorted_indices[:CONFIG['top_n_colors']]]
    top_counts = counts[sorted_indices[:CONFIG['top_n_colors']]]
    
    total_color_pixels = np.sum(color_mask)
    
    result = []
    for bin_idx, count in zip(top_bins, top_counts):
        h_bin = bin_idx // (CONFIG['s_bins'] * CONFIG['v_bins'])
        remainder = bin_idx % (CONFIG['s_bins'] * CONFIG['v_bins'])
        s_bin = remainder // CONFIG['v_bins']
        v_bin = remainder % CONFIG['v_bins']
        
        rep_h = h_bin * h_bin_size + h_bin_size // 2
        rep_s = s_bin * s_bin_size + s_bin_size // 2
        rep_v = v_bin * v_bin_size + v_bin_size // 2
        ratio = count / total_color_pixels if total_color_pixels > 0 else 0.0
        
        result.append({'h': rep_h, 's': rep_s, 'v': rep_v, 'ratio': ratio})
    
    while len(result) < CONFIG['top_n_colors']:
        result.append({'h': np.nan, 's': np.nan, 'v': np.nan, 'ratio': np.nan})
    
    return result


def compute_derived_features(colors: list, prev_colors: list = None) -> np.ndarray:
    """
    Compute derived color features from top-3 dominant colors.
    """
    def safe_val(c, key, default=0.0):
        val = c[key]
        if isinstance(val, float) and math.isnan(val):
            return default
        return float(val)
    
    c1_h = safe_val(colors[0], 'h')
    c1_s = safe_val(colors[0], 's')
    c1_v = safe_val(colors[0], 'v')
    c1_r = safe_val(colors[0], 'ratio')
    
    c2_h = safe_val(colors[1], 'h')
    c2_s = safe_val(colors[1], 's')
    c2_v = safe_val(colors[1], 'v')
    c2_r = safe_val(colors[1], 'ratio')
    
    c3_h = safe_val(colors[2], 'h')
    c3_s = safe_val(colors[2], 's')
    c3_v = safe_val(colors[2], 'v')
    c3_r = safe_val(colors[2], 'ratio')
    
    ratios = [c1_r, c2_r, c3_r]
    total_r = sum(ratios)
    probs = [r / total_r for r in ratios] if total_r > 0 else [1/3] * 3
    entropy = -sum(p * math.log2(p) if p > 0 else 0 for p in probs)
    color_entropy = min(entropy / 1.585, 1.0)
    
    weights = [c1_r, c2_r, c3_r]
    sats = [c1_s, c2_s, c3_s]
    tw = sum(weights)
    saturation_avg = sum(w * s for w, s in zip(weights, sats)) / (tw * 255) if tw > 0 else 0.0
    
    denom = max(c2_r + c3_r, 0.001)
    area_imbalance = c1_r / denom
    
    if prev_colors is not None and len(prev_colors) == 3:
        cur_hues = [c1_h, c2_h, c3_h]
        prev_hues = [safe_val(pc, 'h') for pc in prev_colors]
        
        shifts = []
        for ch, ph in zip(cur_hues, prev_hues):
            diff = abs(ch - ph)
            circular_diff = min(diff, 180 - diff)
            shifts.append(circular_diff)
        
        hue_shift = sum(shifts) / len(shifts)
        motion_color_change = min(hue_shift / 90.0, 1.0)
    else:
        hue_shift = 0.0
        motion_color_change = 0.0
    
    return np.array([
        c1_h, c1_s, c1_v, c1_r,
        c2_h, c2_s, c2_v, c2_r,
        c3_h, c3_s, c3_v, c3_r,
        color_entropy, saturation_avg, area_imbalance,
        hue_shift, motion_color_change
    ], dtype=np.float32)


# ═══════════════════════════════════════════════════════════
# CAMERA INFERENCE APP
# ═══════════════════════════════════════════════════════════

class EmotionInferenceApp:
    """
    Real-time emotion inference from camera feed using HSV color analysis.
    """
    
    def __init__(self):
        """Initialize camera, model, display, and state."""
        self.running = True
        self.debug_mode = False
        self.frame_count = 0
        self.fps_counter = 0
        self.fps_timer = time.time()
        self.current_fps = 0.0
        self.last_raw_frame = None
        
        # Temporal buffers
        self.feature_buffer = deque(maxlen=CONFIG['window_size'])
        self.prev_colors = None
        
        # Prediction smoothing
        self.prediction_history = deque(maxlen=CONFIG['prediction_smoothing'])
        self.probability_history = deque(maxlen=CONFIG['prediction_smoothing'])
        
        # Current state
        self.current_prediction = -1
        self.current_confidence = 0.0
        self.all_probabilities = None
        
        # Load artifacts
        self._load_artifacts()
        
        # Initialize camera
        self._init_camera()
        
        # Create display window - large but not fullscreen
        cv2.namedWindow('Emotion Color Analysis - 16 States', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Emotion Color Analysis - 16 States',
                         CONFIG['display_width'], CONFIG['display_height'])
    
    def _load_artifacts(self):
        """Load pre-trained model and scaler."""
        print('[INFO] Loading model artifacts ...')
        
        if not os.path.exists(CONFIG['model_path']):
            print(f'[ERROR] Model not found: {CONFIG["model_path"]}')
            print('Please run train_model.py first.')
            sys.exit(1)
        
        if not os.path.exists(CONFIG['scaler_path']):
            print(f'[ERROR] Scaler not found: {CONFIG["scaler_path"]}')
            print('Please run train_model.py first.')
            sys.exit(1)
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = load_model(CONFIG['model_path'], self.device)
        self.model.eval()
        print(f'[INFO] Model loaded on {self.device}')
        
        with open(CONFIG['scaler_path'], 'rb') as f:
            self.scaler = pickle.load(f)
        print(f'[INFO] Scaler loaded: {self.scaler.mean_.shape}')
    
    def _init_camera(self):
        """Initialize PiCamera2."""
        try:
            from picamera2 import Picamera2
            from libcamera import Transform
            self.camera = Picamera2()
            
            config = self.camera.create_preview_configuration(
                main={"size": CONFIG['camera_resolution'], "format": "RGB888"},
                lores={"size": CONFIG['target_size'], "format": "RGB888"},
                transform=Transform(vflip=1, hflip=1),
                controls={
                    "FrameRate": 15,
                    "AwbEnable": True,
                    "AeEnable": True
                }
            )
            self.camera.configure(config)
            self.camera.start()
            
            print('[INFO] Warming up camera ...')
            time.sleep(2)
            print('[INFO] Camera ready!')
            
        except ImportError:
            print('[ERROR] picamera2 not installed.')
            print('Install: pip install picamera2')
            sys.exit(1)
        except Exception as e:
            print(f'[ERROR] Failed to initialize camera: {e}')
            sys.exit(1)
    
    def save_current_frame(self, frame: np.ndarray):
        """
        Save the current frame to captured_frames/ directory with timestamp.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        
        if self.current_prediction >= 0 and self.current_confidence >= CONFIG['confidence_threshold']:
            label = EMOTION_LABELS.get(self.current_prediction, 'unknown').replace(' ', '_')
            conf_str = f"{self.current_confidence:.2f}".replace('.', 'p')
            filename = f"frame_{timestamp}_{label}_conf{conf_str}.jpg"
        else:
            filename = f"frame_{timestamp}_collecting.jpg"
        
        filepath = os.path.join(CAPTURE_DIR, filename)
        
        # Convert RGB to BGR for OpenCV saving
        save_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        success = cv2.imwrite(filepath, save_frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        
        if success:
            print(f'[SAVED] {filepath}')
        else:
            print(f'[ERROR] Failed to save {filepath}')
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Process a single frame through the full pipeline.
        """
        self.frame_count += 1
        
        # Store raw frame for saving (BEFORE any modifications)
        self.last_raw_frame = frame.copy()
        
        # Resize to target for analysis
        small = cv2.resize(frame, CONFIG['target_size'], interpolation=cv2.INTER_AREA)
        
        # Convert to HSV
        hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
        
        # Extract dominant colors
        colors = extract_top_colors_from_hsv(hsv)
        
        # Compute features
        features = compute_derived_features(colors, self.prev_colors)
        self.prev_colors = colors
        
        # Add to temporal buffer
        self.feature_buffer.append(features)
        
        # Run inference if buffer is full
        if len(self.feature_buffer) == CONFIG['window_size']:
            self._run_inference()
        
        # Draw minimal overlay
        display = self._draw_minimal_overlay(frame.copy(), colors)
        
        return display
    
    def _run_inference(self):
        """Run GRU inference on current temporal window."""
        seq = np.stack(list(self.feature_buffer), axis=0)
        
        seq_flat = seq.reshape(-1, INPUT_DIM)
        seq_norm = self.scaler.transform(seq_flat).reshape(1, CONFIG['window_size'], INPUT_DIM)
        
        seq_tensor = torch.tensor(seq_norm, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            logits = self.model(seq_tensor)
            probs = torch.softmax(logits, dim=1)
            confidence, pred = torch.max(probs, dim=1)
        
        self.all_probabilities = probs.cpu().numpy()[0]
        
        self.prediction_history.append(pred.item())
        self.probability_history.append(confidence.item())
        
        if len(self.prediction_history) == CONFIG['prediction_smoothing']:
            smoothed_pred = max(set(self.prediction_history),
                              key=self.prediction_history.count)
            avg_confidence = np.mean(self.probability_history)
            
            self.current_prediction = smoothed_pred
            self.current_confidence = avg_confidence
    
    def _get_instability_label(self, instability: float) -> tuple:
        """Categorize instability level."""
        if instability < 0.08:
            return 'stable', INSTABILITY_COLORS['stable']
        elif instability < 0.13:
            return 'moderate', INSTABILITY_COLORS['moderate']
        else:
            return 'volatile', INSTABILITY_COLORS['volatile']
    
    def _draw_minimal_overlay(self, frame: np.ndarray, colors: list) -> np.ndarray:
        """
        Draw minimal overlay to maximize visible camera area.
        """
        h, w = frame.shape[:2]
        
        # ═══ Top bar: Compact ═══
        bar_height = 40
        
        if self.current_prediction >= 0 and self.current_confidence >= CONFIG['confidence_threshold']:
            label = EMOTION_LABELS.get(self.current_prediction, 'Unknown')
            color = EMOTION_DISPLAY_COLORS.get(self.current_prediction, (128, 128, 128))
            profile = EMOTION_COLOR_PROFILES.get(self.current_prediction, {})
            instability = profile.get('instability', 0.0)
            inst_label, inst_color = self._get_instability_label(instability)
            
            # Colored bar
            cv2.rectangle(frame, (0, 0), (w, bar_height), color, -1)
            
            # Emotion name
            cv2.putText(frame, label, (12, 29),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.70, (255, 255, 255), 2)
            
            # Info on right
            info = f'Conf:{self.current_confidence:.0%}  {inst_label}'
            cv2.putText(frame, info, (w - 340, 21),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.47, (255, 255, 255), 1)
            
            # FPS
            self.fps_counter += 1
            elapsed = time.time() - self.fps_timer
            if elapsed >= 1.0:
                self.current_fps = self.fps_counter / elapsed
                self.fps_counter = 0
                self.fps_timer = time.time()
            
            cv2.putText(frame, f'{self.current_fps:.1f}FPS', (w - 155, 21),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.40, (222, 231, 248), 1)
            
            # Save hint
            cv2.putText(frame, '[S] Save', (w - 145, 35),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (209, 222, 244), 1)
        else:
            # Collecting indicator
            cv2.rectangle(frame, (0, 0), (w, bar_height), (50, 50, 50), -1)
            text = f'Collecting... {len(self.feature_buffer)}/{CONFIG["window_size"]}' if len(self.feature_buffer) > 0 else 'Collecting...'
            cv2.putText(frame, text, (12, 29),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.60, (216, 217, 221), 1)
            
            cv2.putText(frame, '[S] Save', (w - 148, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (176, 191, 224), 1)
        
        # ═══ Bottom: Color swatches ═══
        swatch_h = 54
        swatch_y = h - swatch_h - 6
        swatch_w = 52
        swatch_x_start = (w - (swatch_w * 3 + 24)) // 2
        
        for i, color_info in enumerate(colors):
            sx = swatch_x_start + i * (swatch_w + 8)
            
            if not (isinstance(color_info.get('ratio'), float) and math.isnan(color_info.get('ratio', float('nan')))):
                h_clamped = min(max(int(color_info['h']), 0), 179)
                s_clamped = min(max(int(color_info['s']), 0), 255)
                v_clamped = min(max(int(color_info['v']), 0), 255)
                hsv_pixel = np.uint8([[[h_clamped, s_clamped, v_clamped]]])
                bgr = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
                color_bgr = (int(bgr[0]), int(bgr[1]), int(bgr[2]))
                
                cv2.rectangle(frame, (sx, swatch_y), (sx + swatch_w, swatch_y + swatch_h), color_bgr, -1)
                cv2.rectangle(frame, (sx, swatch_y), (sx + swatch_w, swatch_y + swatch_h), (178, 179, 193), 1)
                cv2.putText(frame, f'{color_info["ratio"]:.0%}', (sx + 6, swatch_y + swatch_h - 6),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.38, (242, 244, 252), 1)
            else:
                cv2.rectangle(frame, (sx, swatch_y), (sx + swatch_w, swatch_y + swatch_h), (28, 30, 32), -1)
                cv2.rectangle(frame, (sx, swatch_y), (sx + swatch_w, swatch_y + swatch_h), (138, 139, 151), 1)
        
        # ═══ Debug Mode: Probability bars ═══
        if self.debug_mode and self.all_probabilities is not None:
            debug_x = 8
            debug_y = bar_height + 6
            debug_h = 226
            
            debug_bg = frame[debug_y:debug_y + debug_h, debug_x:debug_x + 350]
            cv2.addWeighted(debug_bg, 0.25, np.zeros_like(debug_bg), 0.75, 0, debug_bg)
            frame[debug_y:debug_y + debug_h, debug_x:debug_x + 350] = debug_bg
            
            bar_max_w = 188
            for pid in range(NUM_CLASSES):
                prob = self.all_probabilities[pid]
                label = EMOTION_LABELS.get(pid, f'Class {pid}')
                short_label = label[:16]
                bar_w = int(prob * bar_max_w)
                bar_y = debug_y + 16 + pid * 13
                
                color = EMOTION_DISPLAY_COLORS.get(pid, (122, 133, 147))
                cv2.rectangle(frame, (debug_x + 114, bar_y), (debug_x + 103 + bar_w, bar_y + 10), color, -1)
                cv2.putText(frame, short_label, (debug_x + 4, bar_y + 9),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.375, (173, 174, 187), 1)
                cv2.putText(frame, f'{prob:.1%}', (debug_x + 105 + bar_w, bar_y + 9),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.365, (204, 229, 227), 1)
        
        return frame
    
    def run(self):
        """Main loop: capture, process, display."""
        print('\n' + '=' * 62)
        print('  Emotion Color Analysis - LARGE WINDOW')
        print('=' * 61)
        print(f'  Window size: {CONFIG["display_width"]}x{CONFIG["display_height"]}')
        print('  Controls:')
        print('    q - Quit')
        print('    r - Reset temporal buffer')
        print('    d - Toggle debug overlay')
        print('    s - Save current frame')
        print('=' * 49 + '\n')
        
        try:
            while self.running:
                loop_start = time.time()
                
                # Capture frame
                frame = self.camera.capture_array("main")
                
                # Process (with minimal overlay)
                display = self.process_frame(frame)
                
                # Show
                cv2.imshow('Emotion Color Analysis - 16 States', display)
                
                # Handle keys - poll frequently with small delay
                key = cv2.pollKey()
                if key != -1:
                    key_char = key & 0xFF
                    if key_char == ord('q'):
                        print('[INFO] Quitting...')
                        break
                    elif key_char == ord('r'):
                        self.feature_buffer.clear()
                        self.prediction_history.clear()
                        self.probability_history.clear()
                        self.current_prediction = -1
                        self.current_confidence = 0.0
                        self.all_probabilities = None
                        print('[INFO] Buffer reset')
                    elif key_char == ord('d'):
                        self.debug_mode = not self.debug_mode
                        print(f'[INFO] Debug mode: {"ON" if self.debug_mode else "OFF"}')
                    elif key_char == ord('s'):
                        if self.last_raw_frame is not None:
                            print(f'[DEBUG] Saving frame, shape={self.last_raw_frame.shape}')
                            self.save_current_frame(self.last_raw_frame)
                        else:
                            print('[WARN] No frame available to save yet')
                
                # Adaptive sleep to maintain frame rate
                elapsed = time.time() - loop_start
                sleep_time = CONFIG['frame_interval'] - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print('\n[INFO] Interrupted by user')
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Release resources."""
        print('[INFO] Cleaning up...')
        if hasattr(self, 'camera'):
            self.camera.stop()
            print('[INFO] Camera released')
        cv2.destroyAllWindows()
        print('[INFO] Done.')


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    """Entry point."""
    print('=' * 77)
    print('  Real-time Emotion Inference from HSV Color Features')
    print('  Author: KUANG, Haozhe | HKUST')
    print('  ONLY COLOR-PATTERN DEMO, NOT REAL EMOTION')
    print('=' * 74)
    print(f'  Captures saved to: {CAPTURE_DIR}')
    print(f'  Display: {CONFIG["display_width"]}x{CONFIG["display_height"]} (large window)')
    print('=' * 70)
    
    app = EmotionInferenceApp()
    app.run()


if __name__ == '__main__':
    main()