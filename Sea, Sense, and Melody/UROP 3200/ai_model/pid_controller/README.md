# HSV Object Tracking & Pan-Tilt Control (Robust PID Version)

Real-time colour-based object tracking using a Raspberry Pi Camera Module 2 (or compatible) and two servos (pan/tilt).  
The system captures video, detects a coloured blob via HSV thresholds, and drives servos to centre the object in the frame.  
If the servo hardware (PCA9685 + Adafruit ServoKit) is unavailable, the program runs in a display-only mode for testing.

> **Version Highlights (v4.0.0):** This release introduces major robustness improvements for jitter suppression and smooth physical actuation:
> - **PID controller** (with anti-windup and derivative filter) for smooth, accurate tracking
> - **Median filter** (buffer length 5) to reject outlier centroid jumps
> - **EMA filter** (α = 0.6) for additional temporal smoothing
> - **Slew-rate limiter** (max 3°/frame) to prevent jerky servo movements
> - **Deadband** (`12 px`) to avoid micro-oscillations when target is nearly centred
> - **Persistent HSV tuning window** with trackbars (live update, auto-swap High/Low)
> - **Manual keyboard override** (`W`/`A`/`S`/`D` or arrows, `R` to reset, `M` to toggle mask overlay)

---

## Features

- **Modular design:** `camera_module`, `detector_module`, `servo_module`, `pid_controller`
- **HSV colour detection:** Optional dual-range masking (for colours near the hue wrap-around)
- **Advanced control & filtering:** PID control with Median + EMA filtering and slew-rate limiting
- **Graceful fallback:** Automatically switches to display-only mode when servos are missing
- **Interactive HSV tuner:** Standalone (`hsv_tuner.py`) and built-in trackbars for parameter adjustment
- **Real-time visualisation:** Bounding box, centre crosshair, binary mask overlay, and status HUD
- **Manual override:** Keyboard manual control is always available (even when no target is detected)

---

## Project Structure

```text
hsv_object_tracker/
│
├── camera_module.py      # PiCamera2 wrapper (capture frames)
├── detector_module.py    # HSV colour detector (find largest blob)
├── hsv_tuner.py          # Interactive slider tool to find HSV values
├── main.py               # Main tracking loop (PID, filters, UI) – v4.0.0
├── pid_controller.py     # Discrete PID controller with anti-windup
├── rgb_to_hsv_range.py   # Utility: convert RGB to HSV threshold range
├── servo_module.py       # Servo controller (PCA9685 / fallback)
├── test_camera.py        # Standalone camera + detector test
├── test_servo.py         # Standalone servo sweep test
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Requirements

- Raspberry Pi (tested on Pi 4 / Pi 5)
- Raspberry Pi Camera Module 2 (or any camera supported by `libcamera` / `picamera2`)
- *(Optional)* PCA9685 PWM driver board + two servos (pan/tilt)
- Python 3.9+

### Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `picamera2` and `libcamera` are pre-installed on Raspberry Pi OS (Bullseye or later). On other systems, you may need to build them manually.

---

## Usage

### 1. Tune HSV Parameters

Run the standalone tuner to find the best HSV range for your target object:

```bash
python hsv_tuner.py
```

Adjust the six trackbars until only the desired object appears white in the mask window. Press `q` to exit—the final HSV values will be printed to the terminal.

*(Alternatively, use the built-in tuning window inside `main.py` in Step 2.)*

### 2. Run Tracking

```bash
python main.py
```

The program will prompt you to enter HSV thresholds (you can paste the values from the tuner). Then the main windows open:

- **Main window (`Tracking`):** Shows the camera feed with bounding box, centre crosshair, and optional mask overlay.
- **HSV Tuning window:** Six trackbars to adjust H, S, V thresholds in real time, plus a `Min Area` slider.
- **Mask Preview window:** Binary mask (`white` = detected pixels).

#### Keyboard Controls (Always Active)

| Key | Action |
| :-: | :--- |
| `W` / `Up Arrow` | Tilt up (`+5°`) |
| `S` / `Down Arrow` | Tilt down (`-5°`) |
| `A` / `Left Arrow` | Pan left (`-5°`) |
| `D` / `Right Arrow` | Pan right (`+5°`) |
| `R` | Reset to centre (`90°`, `90°`) |
| `M` | Toggle mask overlay on/off |
| `Q` | Quit |

When a target is detected, the PID controller automatically adjusts pan/tilt to centre it. Manual commands override temporarily; automatic control resumes as soon as the target is re-detected.

### 3. Display-Only Mode

If the PCA9685 board is not connected or the `adafruit-circuitpython-servokit` library fails to load, the program automatically switches to display-only mode.  
All tracking logic still runs (angles are updated internally, though no physical movement occurs), and the terminal displays `[SERVO] Hardware available: False`.

---

## Configuration

All key control parameters can be adjusted inside `TrackingSystem.__init__` in `main.py`:

### Resolution

Change `width` and `height`:

```python
self.camera = Camera(width=320, height=240)
```

### PID Gains

Edit the `PIDController` initialisations:

```python
self.pid_pan = PIDController(kp=0.04, ki=0.003, kd=0.008,
                             integral_min=-20, integral_max=20)
self.pid_tilt = PIDController(kp=0.035, ki=0.002, kd=0.007,
                              integral_min=-20, integral_max=20)
```

### Tuning Parameters

- **Deadband:** Modify `self.deadband_px` (default: `12` pixels).
- **Slew-Rate Limit:** Modify `self.max_angle_change` (default: `3.0` degrees per frame).
- **EMA Alpha:** Modify `self.ema_alpha` (default: `0.6`).
- **Servo Inversion:** Pass `invert_pan=True, invert_tilt=True` to `ServoController` if your servos are mounted in the opposite direction.

---

## Author

- **Name:** KUANG, Haozhe
- **Affiliation:** The Hong Kong University of Science and Technology (HKUST)
- **Email:** [hkuangab@connect.ust.hk](mailto:hkuangab@connect.ust.hk)

---

## License

This project is licensed under the MIT License – see the header of each source file for details.
