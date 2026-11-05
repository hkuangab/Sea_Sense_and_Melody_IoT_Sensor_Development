# HSV Emotion Classifier

Real-time HSV color sequence → composite emotion classifier for Raspberry Pi 5.

> This classifies **color patterns**, NOT facial expressions.
> It maps temporal sequences of dominant HSV colors to composite mood profiles
> based on color-psychology priors.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology (HKUST)
Email: hkuangab@connect.ust.hk
Date: October 2026

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
9. [Feature Vector (17 Dimensions)](#feature-vector)
10. [Model Architecture](#model-architecture)
11. [Performance Notes](#performance-notes)
12. [Troubleshooting](#troubleshooting)
13. [License & Disclaimer](#license--disclaimer)

---

## Overview

The HSV Emotion Classifier is built for the UROP 3200 program at HKUST.
A Raspberry Pi 5 + PiCamera2 captures live video, extracts the dominant HSV
colors of each frame, and feeds a 12-frame temporal window into a GRU network
that outputs one of 16 composite emotional states.

**What it actually does**
- Watches the *scene palette* (ambient color), not faces
- Converts per-frame dominant colors into a 17-d feature vector
- Uses sequence context (12 frames ≈ 0.8 s) to stabilize prediction

**What it does NOT do**
- No facial expression analysis
- No person identification
- No claim of physiological/emotional ground truth

Intended uses:
- Mood-responsive ambient lighting
- Art / installation feedback
- Color-psychology teaching demos
- Interactive media

---

## Project Structure

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
│   ├── X_seq.npy           # (N, 12, 17)
│   └── y_labels.npy        # (N,)
│
└── captured_frames/         # created on first 's' press

---

## How It Works

1. **Capture** — PiCamera2 @ 640×480, ~15 FPS
2. **Preprocess** — resize 160×120, RGB→HSV, Gaussian blur 5×5 σ=1.8
3. **Dominant colors** — mask S<25, quantize into
   4 Hue × 8 Sat × 8 Val = 256 bins, take top-3
4. **Feature** — 17-d vector per frame (see below)
5. **Buffer** — sliding window of 12 frames
6. **Infer** — StandardScaler → GRU → 16-class softmax
7. **Smooth** — majority vote over last 5 cycles,
   display only if confidence > 35%

---

## The 16 Composite Emotions

| ID | Name | Anchor Hue | Basis |
|----|------|------------|-------|
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

> Note: if several profiles share near-identical anchor HSV + variance,
> the synthetic generator will produce overlapping classes and the model
> may collapse to a few dominant labels. Keep anchors separated.

---

## System Requirements

Hardware
- Raspberry Pi 5 (4 GB+ recommended)
- PiCamera2 (CSI)
- 5V 5A USB-C supply

Software
- Raspberry Pi OS Bookworm 64-bit
- Python 3.11+
- apt packages:
  python3-picamera2 python3-opencv python3-numpy
  python3-sklearn python3-pandas

---

## Installation
bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv \
python3-numpy python3-sklearn python3-pandas
cd ~/Desktop/UROP\ 3200/ai_model/hsv_emotion_classifier
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
mkdir -p trained_model toy_dataset captured_frames
---

## Usage

### 1. Generate data
bash
python3 generate_dataset.py
Outputs `toy_dataset/X_seq.npy`, `y_labels.npy`.
~30–60 s on Pi 5.

### 2. Train
bash
python3 train_model.py
Saves `gru_mood_model.pth` + `scaler.pkl`.
~2–5 min on CPU.

### 3. Inference
bash
python3 camera_infer.py
---

## Camera Controls

| Key | Action |
|-----|--------|
| q | quit |
| r | reset buffer |
| d | toggle debug prob bars |
| s | save frame |

Saved file:
`frame_YYYYMMDD_HHMMSS_ms_<Emotion>_conf0pXX.jpg`

---

## Feature Vector

| idx | feature | range |
|-----|---------|-------|
| 0–3 | C1 H/S/V/ratio | H 0–179, S/V 0–255 |
| 4–7 | C2 H/S/V/ratio | |
| 8–11 | C3 H/S/V/ratio | |
| 12 | color_entropy | 0–1 |
| 13 | saturation_avg | 0–1 |
| 14 | area_imbalance | ≥1 |
| 15 | hue_shift | 0–180 |
| 16 | motion_color_change | 0–1 |

Input to model: `(batch, 12, 17)`

---

## Model Architecture
Input (B,12,17)
→ GRU(hidden=128, layers=2, batch_first)
→ last hidden state
→ Dropout(0.4)
→ Linear(128→64) + ReLU
→ Dropout(0.3)
→ Linear(64→16)
→ logits
- Loss: CrossEntropy
- Optim: Adam lr=1e-3
- Batch: 512
- Epochs: 150 (+ ReduceLROnPlateau, early stop)
- Params: ~135k

---

## Performance Notes

Expected FPS (Pi 5):
- debug off: 8–12
- debug on: 6–9

Accuracy reality check:
- Trained on **synthetic** HSV profiles, not real labels
- Works best under neutral white light, stable WB
- Strong color cast → bias toward nearby hue class
- Low-saturation scene → often "Neutral Gray" or sub-35% reject

Demo suitability:
- ✅ Good for showing pipeline + live color response
- ⚠️ Not a validated emotion recognizer
- If predictions stick to 3–4 classes only, check anchor
  separation in `emotion_profiles.py` and regenerate data

Tips:
1. Even lighting, avoid hard shadows
2. Wait 2–3 s after launch for AWB
3. Hold color sample ≥1 s
4. `r` to reset on scene change

---

## Troubleshooting

**Camera init fail**
Check ribbon, run `libcamera-hello`.

**Qt plugin error**
bash
sudo apt install -y libqt5gui5 qt5-qmake
**Model not found**
Run `train_model.py` first.

**Low FPS**
Lower res to 320×240, raise `frame_interval`.

**Only "Neutral Gray" / low conf**
Gray scene, low sat, WB not settled → press `r`.

**Always same 3–4 emotions**
Likely class collapse: anchors too close in HSV space
or generator variance too high. Edit `emotion_profiles.py`,
spread hues / sat bands, regenerate + retrain.

**ENOSPC on camera**
Reboot; kill other `/dev/video0` users.

---

## License & Disclaimer

Educational use permitted with attribution (UROP 3200, HKUST).

Not a facial / biometric system.
Not for clinical or diagnostic use.
Outputs are color-psychology associations from synthetic training,
not measured human emotion.