# Sea, Sense, and Melody -- Multi-Modal IoT Emotion Classifier

**Real-time 20-class emotion inference system based on multi-modal sensor data, Attentional-GRU model, and POSIX message queue inter-process communication.**

> **Author:** KUANG, Haozhe
> **Affiliation:** HKUST
> **Date:** October 2026

---

## Table of Contents

- [Project Overview](#project-overview)
- [System Workflow](#system-workflow)
- [Repository File Structure](#repository-file-structure)
- [Dependencies](#dependencies)
- [Quick Start](#quick-start)
- [Runtime Keyboard Controls](#runtime-keyboard-controls)
- [Input and Output Specification](#input-and-output-specification)
- [20 Emotion Classes](#20-emotion-classes)
- [Pros](#pros)
- [Cons and Limitations](#cons-and-limitations)
- [Important Constraints](#important-constraints)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Project Overview

This project implements an end-to-end real-time emotion classification pipeline for IoT multi-modal sensors (light, sound, touch, camera HSV features). It uses a single-layer GRU with temporal self-attention to recognize **20 distinct emotional states** from 26-dimensional sensor time-series features.

> **Note:** Training dataset is **fully synthetic**, generated from Gaussian emotion profiles defined in `emotion_profiles.py`. No real-world human sensor data is used for model training.

---

## System Workflow

```
+------------------+       +-----------------------+       +---------------------+
|  main_camera.c   |       |   camera_infer.py     |       |   main_camera.c     |
|  (C / SDL app)   |       |   (Python inference)  |       |   (C / SDL app)     |
+--------+---------+       +-----------+-----------+       +----------+----------+
         |                             |                              ^
         |  1. Write sensor_box.csv    |  2. Poll CSV, maintain      |
         |  (every 1 second)           |     12-frame sliding window  |
         +---------------------------->+                              |
         |                             |  3. Attentional-GRU inference |
         |                             |     + prediction smoothing    |
         |                             |                              |
         |                             |  4. Send label via POSIX     |
         |                             |     message queue             |
         |                             |     (/sensor_box_infer)       |
         |                             +----------------------------->+
         |                                                        |
         |  5. Render emotion on SDL window                       |
         |     + append result to CSV log                         |
         +<-------------------------------------------------------+
```

1. C program `main_camera.c` writes sensor readings into `sensor_box.csv` every second.
2. Python `camera_infer.py` continuously polls the CSV file, maintains a 12-frame sliding-window feature buffer.
3. Pre-trained Attentional-GRU model performs sequence inference; prediction smoothing is applied to stabilize outputs.
4. Inferred human-readable emotion label is sent via POSIX message queue (`/sensor_box_infer`) back to the C application.
5. C program consumes the message queue, renders emotion text on SDL camera window and appends result into CSV log.

---

## Repository File Structure

```
ai_model/hsv_emotion_classifier/
├── camera_infer.py            # Real-time inference runtime
├── emotion_profiles.py        # 20 synthetic emotion profiles (mean/std for 26-D features)
├── generate_dataset.py        # Generate synthetic training dataset X_seq.npy / y_labels.npy
├── mood_model.py              # Attentional-GRU PyTorch model definition
├── train_model.py             # Training pipeline, saves model checkpoint & StandardScaler
├── toy_dataset/               # Auto-generated synthetic dataset output folder
│   ├── X_seq.npy
│   └── y_labels.npy
└── trained_model/             # Output artifacts after training
    ├── gru_mood_model.pth     # PyTorch model weights
    └── scaler.pkl             # Fitted StandardScaler for feature normalization
```

---

## Dependencies

**Python packages:**

```bash
pip install numpy pandas torch scikit-learn
```

**System requirements:**

| Requirement       | Details                                              |
|-------------------|------------------------------------------------------|
| Python version    | `>= 3.8`                                             |
| Built-in modules  | `ctypes`, `pickle`                                   |
| Operating system  | Linux (requires `librt` for POSIX message queue)     |
| Privileges        | `sudo` required for running inference                |

---

## Quick Start

### Step 1: Generate Synthetic Dataset

```bash
python3 generate_dataset.py
```

- Output dataset saved to `toy_dataset/`.
- Generates **62,500 sequences** with shape `(62500, 12, 26)`.

### Step 2: Train Attentional-GRU Classifier

```bash
python3 train_model.py
```

- **85%** train / **15%** validation split.
- Feature standard scaling applied.
- Best model and scaler saved under `trained_model/`.

### Step 3: Start the C Sensor Program (MUST RUN FIRST)

Open another terminal, launch the C sensor application. It creates the POSIX message queue and writes the sensor CSV file.

```bash
cd ~/Desktop/UROP\ 3200/sensor_box
sudo ./sensor_box
```

### Step 4: Launch Real-time Python Inference

Open a new terminal under the `ai_model/hsv_emotion_classifier` directory:

```bash
sudo python camera_infer.py
```

---

## Runtime Keyboard Controls

Available in the inference terminal:

| Key   | Action                                         |
|-------|------------------------------------------------|
| `r`   | Reset feature buffer and prediction smoothing history |
| `q`   | Gracefully quit inference process              |

---

## Input and Output Specification

### Model Input

Tensor shape: `(batch_size, WINDOW_SIZE=12, INPUT_DIM=26)`

**26-D multi-modal feature groups:**

| Modality       | Dimension | Feature Names                                                                                                  |
|----------------|-----------|----------------------------------------------------------------------------------------------------------------|
| Light          | 6         | `light_raw`, `light_brightness`, `light_trend`, `light_variance`, `light_is_daylight`, `light_flicker_freq`   |
| Sound          | 6         | `sound_raw`, `sound_energy`, `sound_speech_rate`, `sound_continuity`, `sound_spike`, `sound_human_presence`    |
| Touch          | 5+1 enc.  | `touch_irq`, `touch_count`, `touch_freq`, `touch_intent`, `touch_pattern_enc`                                 |
| Camera HSV     | 9         | `cam_top_count`, `cam_top1_h`, `cam_top1_s`, `cam_top1_v`, `cam_top2_s`, `cam_top2_v`, `cam_top3_h`, `cam_top3_s`, `cam_top3_v` |

---

## 20 Emotion Classes

| Index | Emotion                  | Index | Emotion                    |
|-------|--------------------------|-------|----------------------------|
| 0     | Serene Bliss             | 10    | Irritated Frustration      |
| 1     | Joyful Exuberance        | 11    | Peaceful Slumber           |
| 2     | Melancholic Nostalgia    | 12    | Exhilarating Thrill        |
| 3     | Furious Rage             | 13    | Wistful Longing            |
| 4     | Anxious Trembling        | 14    | Determined Grit            |
| 5     | Calm Contentment         | 15    | Bittersweet Reminiscence   |
| 6     | Ecstatic Wonder          | 16    | Awestruck Reverence        |
| 7     | Gloomy Despair           | 17    | Sullen Resignation         |
| 8     | Playful Mischief         | 18    | Radiant Hope               |
| 9     | Tender Affection         | 19    | Embarrassed Fluster        |

---

## Pros

- **Full end-to-end prototype pipeline:** synthetic dataset generation, GRU-attention training, real-time inference, cross-language IPC with C. Easy to reproduce.
- **Raw `ctypes` for POSIX message queue:** no extra third-party IPC libraries required.
- **Sliding-window buffer + prediction smoothing:** suppresses single-frame noise for streaming sensor input.
- **Attention-enhanced GRU:** model learns to focus on important time steps inside sequence.
- **Defensive runtime logic:** NaN value sanitization, auto-reconnect stale message queue fd, non-blocking terminal hot-keys.
- **Strict dimension assertion checks:** avoids silent feature-order mismatch bugs.
- **Rich console debug output:** queue status, CSV status, confidence, sending statistics.

---

## Cons and Limitations

- **Synthetic training data only:** sampled from hand-crafted Gaussian profiles. Large domain gap for real-world physical sensor data. Real-world generalization is unvalidated.
- **CSV polling design:** reads entire CSV file just for latest row, inefficient for large log files; fixed polling interval introduces latency. No event-driven file watcher.
- **Linux-only:** depends on POSIX message queue (`librt`); requires `sudo`. Cannot run natively on Windows/macOS.
- **Simple majority-vote smoothing:** low-confidence predictions have equal voting weight as high-confidence outputs.
- **No handling for fast emotion transitions** inside 12-frame sliding window.
- **Lack of sensor anomaly detection:** corrupted sensor frames only get NaN-to-zero replacement.
- **Confidence and attention weights** are only printed to console; no automatic disk logging.
- **Synthetic dataset noise simulation** cannot fully replicate real-world sensor autocorrelation and noise characteristics.

---

## Important Constraints

1. The C sensor program **must start before** running `camera_infer.py` to create POSIX queue `/sensor_box_infer`.
2. Feature column ordering must be consistent across all scripts; re-ordering features will break inference.
3. `touch_pattern` string in CSV is encoded to binary value inside python inference code.

---

## Future Improvements

- Collect real human-sensor interaction data to replace synthetic dataset; perform domain adaptation.
- Use `inotify` event-driven file watching instead of periodic CSV polling.
- Implement confidence-weighted prediction smoothing.
- Auto-log inference confidence, attention weights and input features to disk.
- Add sensor anomaly detection for bad sensor readings.
- Add cross-platform IPC fallback such as Unix domain socket.
- Support detection of mixed / fast-transition emotion states inside sliding window.

---

## License

Academic UROP prototyping only. Synthetic emotion profiles and model are for demonstration purpose. Real-world deployment requires calibration with real sensor data.
