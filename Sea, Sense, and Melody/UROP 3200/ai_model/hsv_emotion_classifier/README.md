# HSV Emotion Classifier

Real-time HSV color sequence → composite emotion classifier for Raspberry Pi 5.

> **Disclaimer:** This classifies **color patterns**, NOT facial expressions. It maps temporal sequences of dominant HSV colors to composite mood profiles based on color-psychology priors.

- **Author:** KUANG, Haozhe
- **Affiliation:** The Hong Kong University of Science and Technology (HKUST)
- **Email:** [hkuangab@connect.ust.hk](mailto:hkuangab@connect.ust.hk)
- **Date:** October 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [How It Works](#how-it-works)
4. [The 16 Composite Emotions](#the-16-composite-emotions)
5. [System Requirements](#system-requirements)
6. [Installation](#installation)
7. [Usage](#usage)
8. [Camera Controls](#camera-controls)
9. [Feature Vector (17 Dimensions)](#feature-vector-17-dimensions)
10. [Model Architecture](#model-architecture)
11. [Performance Notes](#performance-notes)
12. [Troubleshooting](#troubleshooting)
13. [License & Disclaimer](#license--disclaimer)

---

## Overview

The **HSV Emotion Classifier** is built for the UROP 3200 program at HKUST. A Raspberry Pi 5 + PiCamera2 captures live video, extracts the dominant HSV colors of each frame, and feeds a 12-frame temporal window into a GRU network that outputs one of 16 composite emotional states.

### What it actually does
- Watches the *scene palette* (ambient color), not faces
- Converts per-frame dominant colors into a 17-d feature vector
- Uses sequence context (12 frames ≈ 0.8 s) to stabilize prediction

### What it does NOT do
- No facial expression analysis
- No person identification
- No claim of physiological/emotional ground truth

### Intended uses
- Mood-responsive ambient lighting
- Art / installation feedback
- Color-psychology teaching demos
- Interactive media

---

## Project Structure

```text
hsv_emotion_classifier/
│
├── emotion_profiles.py      # 16 composite emotions + anchor HSV colors
├── mood_model.py            # GRU definition
├── generate_dataset.py      # synthetic sequence generator
├── train_model.py           # training script
├── camera_infer.py          # live PiCamera2 inference
│
├── requirements.txt
├── README.md
│
├── trained_model/
│   ├── gru_mood_model.pth
│   └── scaler.pkl
│
├── toy_dataset/
│   ├── X_seq.npy            # (N, 12, 17)
│   └── y_labels.npy         # (N,)
│
└── captured_frames/         # created on first 's' press
```

---

## How It Works

1. **Capture** — PiCamera2 @ 640×480, ~15 FPS
2. **Preprocess** — Resize 160×120, RGB→HSV, Gaussian blur 5×5 (σ=1.8)
3. **Dominant colors** — Mask S < 25, quantize into 4 Hue × 8 Sat × 8 Val = 256 bins, take top-3
4. **Feature** — 17-d vector per frame (see [Feature Vector](#feature-vector-17-dimensions))
5. **Buffer** — Sliding window of 12 frames
6. **Infer** — `StandardScaler` → GRU → 16-class softmax
7. **Smooth** — Majority vote over last 5 cycles, display only if confidence > 35%

---

## The 16 Composite Emotions

| ID | Name | Anchor Hue | Basis |
| :-: | :--- | :-: | :--- |
| 0 | Joyful Energy | 45° | warm high-sat |
| 1 | Calm Serenity | 210° | cool low-sat |
| 2 | Melancholy Blue | 220° | dark desaturated |
| 3 | Angry Red | 0° | high-arousal red |
| 4 | Peaceful Green | 130° | balanced mid-value |
| 5 | Anxious Yellow | 55° | high-contrast yellow-green |
| 6 | Romantic Pink | 330° | soft warm |
| 7 | Neutral Gray | — | low-sat equilibrium |
| 8 | Energetic Orange | 20° | high-sat activation |
| 9 | Sad Purple | 280° | dark cool |
| 10 | Fearful Gray | 170° | cold desaturated |
| 11 | Surprised Gold | 40° | bright sudden |
| 12 | Disgusted Green | 100° | sickly yellow-green |
| 13 | Trustworthy Blue | 200° | stable sky blue |
| 14 | Anticipation Teal | 175° | moderate sat |
| 15 | Contempt Violet | 270° | cool dark |

> **Note:** If several profiles share near-identical anchor HSV + variance, the synthetic generator will produce overlapping classes and the model may collapse to a few dominant labels. Keep anchors well separated.

---

## System Requirements

### Hardware
- Raspberry Pi 5 (4 GB+ recommended)
- PiCamera2 (CSI)
- 5V 5A USB-C power supply

### Software
- Raspberry Pi OS Bookworm 64-bit
- Python 3.11+
- APT packages: `python3-picamera2`, `python3-opencv`, `python3-numpy`, `python3-sklearn`, `python3-pandas`

---

## Installation

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv \
    python3-numpy python3-sklearn python3-pandas

cd ~/Desktop/UROP\ 3200/ai_model/hsv_emotion_classifier
python3 -m venv venv --system-site-packages
source venv/bin/activate

pip install torch --index-url https://download.pytorch.org/whl/cpu
mkdir -p trained_model toy_dataset captured_frames
```

---

## Usage

### 1. Generate Data

Outputs `toy_dataset/X_seq.npy` and `y_labels.npy` (~30–60 s on Pi 5).

```bash
python3 generate_dataset.py
```

### 2. Train Model

Saves `trained_model/gru_mood_model.pth` and `trained_model/scaler.pkl` (~2–5 min on CPU).

```bash
python3 train_model.py
```

### 3. Live Inference

```bash
python3 camera_infer.py
```

---

## Camera Controls

| Key | Action |
| :-: | :--- |
| `q` | Quit |
| `r` | Reset buffer |
| `d` | Toggle debug probability bars |
| `s` | Save current frame |

Saved file format: `captured_frames/frame_YYYYMMDD_HHMMSS_ms_<Emotion>_conf0pXX.jpg`

---

## Feature Vector (17 Dimensions)

Input shape to model: `(batch, 12, 17)`

| Index | Feature | Range |
| :-: | :--- | :--- |
| 0–3 | C1 H / S / V / ratio | H: `0–179`, S/V: `0–255` |
| 4–7 | C2 H / S / V / ratio | H: `0–179`, S/V: `0–255` |
| 8–11 | C3 H / S / V / ratio | H: `0–179`, S/V: `0–255` |
| 12 | `color_entropy` | `0–1` |
| 13 | `saturation_avg` | `0–1` |
| 14 | `area_imbalance` | `≥ 1` |
| 15 | `hue_shift` | `0–180` |
| 16 | `motion_color_change` | `0–1` |

---

## Model Architecture

```text
Input (B, 12, 17)
  └── GRU(hidden=128, layers=2, batch_first=True)
        └── Last hidden state
              └── Dropout(0.4)
                    └── Linear(128 → 64) + ReLU
                          └── Dropout(0.3)
                                └── Linear(64 → 16) → Logits
```

- **Loss:** CrossEntropyLoss
- **Optimizer:** Adam (`lr=1e-3`)
- **Batch Size:** 512
- **Epochs:** 150 (+ `ReduceLROnPlateau`, early stopping)
- **Parameters:** ~135k

---

## Performance Notes

### Expected FPS (Raspberry Pi 5)
- **Debug OFF:** 8–12 FPS
- **Debug ON:** 6–9 FPS

### Accuracy Reality Check
- Trained on **synthetic** HSV profiles, not real-world labeled data.
- Works best under neutral white light with stable white balance (AWB).
- Strong ambient color casts will bias predictions toward nearby hue classes.
- Low-saturation scenes often result in `"Neutral Gray"` or sub-35% rejection.

### Demo Suitability
- ✅ Good for demonstrating real-time CV pipelines and live color response.
- ⚠️ Not a validated emotion recognizer.
- If predictions stick to 3–4 classes only, check anchor separation in `emotion_profiles.py` and regenerate data.

### Usage Tips
1. Ensure even lighting and avoid hard shadows.
2. Wait 2–3 seconds after launch for Auto White Balance (AWB) to settle.
3. Hold a color sample steady for at least 1 second.
4. Press `r` to reset the temporal buffer upon major scene changes.

---

## Troubleshooting

- **Camera initialization failed**
  Check the CSI ribbon cable connection and test with `libcamera-hello`.

- **Qt plugin error**
  Install missing Qt dependencies:
  ```bash
  sudo apt install -y libqt5gui5 qt5-qmake
  ```

- **Model not found**
  Ensure you run `python3 train_model.py` before running `camera_infer.py`.

- **Low FPS**
  Lower the capture resolution to `320×240` or increase `frame_interval`.

- **Only "Neutral Gray" / Low confidence**
  Caused by gray scenes, low saturation, or unsettled white balance. Press `r` to reset.

- **Always predicts the same 3–4 emotions**
  Likely caused by class collapse (anchors too close in HSV space or generator variance too high). Edit `emotion_profiles.py` to spread out hues/saturation bands, then regenerate data and retrain.

- **`ENOSPC` error on camera**
  Reboot the Pi or kill other processes occupying `/dev/video0`.

---

## License & Disclaimer

Educational use permitted with attribution (**UROP 3200, HKUST**).

- Not a facial or biometric recognition system.
- Not intended for clinical or diagnostic use.
- Outputs represent color-psychology associations learned from synthetic training data, not measured human emotion.
