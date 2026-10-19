🌊 Sea, Sense, and Melody — Multi-Modal IoT Emotion Classifier
> **Real-time 20-class emotion inference system** based on multi-modal sensor data, **Attentional-GRU model**, and **POSIX message queue** inter-process communication.
>
> 👤 **Author:** KUANG, Haozhe · 🏫 **HKUST** · 📅 **October 2026**
---
📌 Project Overview
This project implements an end-to-end real-time emotion classification pipeline for IoT multi-modal sensors (light, sound, touch, camera HSV features). It uses a single-layer GRU with temporal self-attention to recognize 20 distinct emotional states from 26-dimensional sensor time-series features.
🔄 System Workflow
C program `main_camera.c` writes sensor readings into `sensor_box.csv` every second.
Python `camera_infer.py` continuously polls the CSV file, maintains a 12-frame sliding-window feature buffer.
Pre-trained Attentional-GRU model performs sequence inference; prediction smoothing is applied to stabilize outputs.
Inferred human-readable emotion label is sent via POSIX message queue (`/sensor_box_infer`) back to the C application.
C program consumes the message queue, renders emotion text on SDL camera window and appends result into CSV log.
> ⚠️ **Note:** Training dataset is **fully synthetic**, generated from Gaussian emotion profiles defined in `emotion_profiles.py`. No real-world human sensor data is used for model training.
---
📁 Repository File Structure
```
ai_model/hsv_emotion_classifier/
├── camera_infer.py          # Real-time inference runtime
├── emotion_profiles.py       # 20 synthetic emotion profiles (mean/std for 26-D features)
├── generate_dataset.py       # Generate synthetic training dataset X_seq.npy / y_labels.npy
├── mood_model.py             # Attentional-GRU PyTorch model definition
├── train_model.py            # Training pipeline, saves model checkpoint & StandardScaler
├── toy_dataset/              # Auto-generated synthetic dataset output folder
│   ├── X_seq.npy
│   └── y_labels.npy
└── trained_model/            # Output artifacts after training
    ├── gru_mood_model.pth    # PyTorch model weights
    └── scaler.pkl            # Fitted StandardScaler for feature normalization
```
---
🛠️ Dependencies
```bash
pip install numpy pandas torch scikit-learn
```
✅ Python >= 3.8
✅ `ctypes`, `pickle` are built-in modules
🐧 Requires Linux OS with `librt` for POSIX message queue
🔑 `sudo` privilege required for running inference.
---
🚀 Quick Start
1️⃣ Generate Synthetic Dataset
```bash
python3 generate_dataset.py
```
> Output dataset saved to `toy_dataset/`, generates **62,500 sequences** with shape `(62500, 12, 26)`.
2️⃣ Train Attentional-GRU Classifier
```bash
python3 train_model.py
```
85% train / 15% validation split
Feature standard scaling
Best model and scaler saved under `trained_model/`
3️⃣ Start the C Sensor Program (MUST RUN FIRST) ⚠️
Open another terminal, launch the C sensor application, it creates POSIX message queue and writes sensor CSV file.
```bash
cd ~/Desktop/UROP\ 3200/sensor_box
sudo ./sensor_box
```
4️⃣ Launch Real-time Python Inference
Open new terminal under `ai_model/hsv_emotion_classifier` directory:
```bash
sudo python camera_infer.py
```
🎮 Runtime Keyboard Controls in Inference Terminal
Key	Action
`r`	Reset feature buffer and prediction smoothing history
`q`	Gracefully quit inference process
---
📥 Input & 📤 Output
Model Input
> Tensor shape: `(batch_size, WINDOW_SIZE=12, INPUT_DIM=26)`
26-D multi-modal feature groups:
💡 Light (6): `light_raw, light_brightness, light_trend, light_variance, light_is_daylight, light_flicker_freq`
🔊 Sound (6): `sound_raw, sound_energy, sound_speech_rate, sound_continuity, sound_spike, sound_human_presence`
👆 Touch (5+1 encoded): `touch_irq, touch_count, touch_freq, touch_intent, touch_pattern_enc`
🎥 Camera HSV (9): `cam_top_count, cam_top1_h, cam_top1_s, cam_top1_v, cam_top2_s, cam_top2_v, cam_top3_h, cam_top3_s, cam_top3_v`
20 Emotion Classes
Index	Emotion	Index	Emotion
0	Serene Bliss	10	Irritated Frustration
1	Joyful Exuberance	11	Peaceful Slumber
2	Melancholic Nostalgia	12	Exhilarating Thrill
3	Furious Rage	13	Wistful Longing
4	Anxious Trembling	14	Determined Grit
5	Calm Contentment	15	Bittersweet Reminiscence
6	Ecstatic Wonder	16	Awestruck Reverence
7	Gloomy Despair	17	Sullen Resignation
8	Playful Mischief	18	Radiant Hope
9	Tender Affection	19	Embarrassed Fluster
---
✅ Pros (Advantages)
🏗️ Full end-to-end prototype pipeline: synthetic dataset generation → GRU-attention training → real-time inference → cross-language IPC with C. Easy to reproduce.
⚙️ Uses raw `ctypes` for POSIX message queue without extra third-party IPC libraries.
🪟 Sliding-window buffer + prediction smoothing suppress single-frame noise for streaming sensor input.
🎯 Attention-enhanced GRU: model learns to focus on important time steps inside sequence.
🛡️ Defensive runtime logic: NaN value sanitization, auto-reconnect stale message queue fd, non-blocking terminal hot-keys.
🔒 Strict dimension assertion checks to avoid silent feature-order mismatch bugs.
📊 Rich console debug output: queue status, CSV status, confidence, sending statistics.
---
⚠️ Cons & Limitations
🧪 Training data is purely synthetic: sampled from hand-crafted Gaussian profiles. Large domain gap for real-world physical sensor data. Real-world generalization is unvalidated.
🐌 CSV polling design: reads entire CSV file just for latest row, inefficient for large log files; fixed polling interval introduces latency. No event-driven file watcher.
🐧 Linux-only: depends on POSIX message queue (`librt`); requires `sudo`. Cannot run natively on Windows/macOS.
⚖️ Simple majority-vote smoothing: low-confidence predictions have equal voting weight as high-confidence outputs.
🔄 No handling for fast emotion transitions inside 12-frame sliding window.
🚨 Lack of sensor anomaly detection: corrupted sensor frames only get NaN→zero replacement.
🖨️ Confidence and attention weights are only printed to console; no automatic disk logging.
🌊 Synthetic dataset noise simulation cannot fully replicate real-world sensor autocorrelation and noise characteristics.
---
📏 Important Constraints
The C sensor program must start before running `camera_infer.py` to create POSIX queue `/sensor_box_infer`.
Feature column ordering must be consistent across all scripts; re-ordering features will break inference.
`touch_pattern` string in CSV is encoded to binary value inside python inference code.
---
🚧 Future Improvements
📡 Collect real human-sensor interaction data to replace synthetic dataset; perform domain adaptation.
👁️ Use `inotify` event-driven file watching instead of periodic CSV polling.
⚖️ Implement confidence-weighted prediction smoothing.
💾 Auto-log inference confidence, attention weights and input features to disk.
🛡️ Add sensor anomaly detection for bad sensor readings.
🌐 Add cross-platform IPC fallback such as Unix domain socket.
🔀 Support detection of mixed / fast-transition emotion states inside sliding window.
---
📄 License
> **Academic UROP prototyping only.** Synthetic emotion profiles and model are for demonstration purpose. Real-world deployment requires calibration with real sensor data.
