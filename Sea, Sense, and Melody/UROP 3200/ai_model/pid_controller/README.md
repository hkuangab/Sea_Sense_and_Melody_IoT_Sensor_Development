l (Robust PID Version)

Real‑time colour‑based object tracking using a Raspberry Pi Camera Module 2 (or compatible) and two servos (pan/tilt).  
The system captures video, detects a coloured blob via HSV thresholds, and drives servos to centre the object in the frame.  
If the servo hardware (PCA9685 + Adafruit ServoKit) is unavailable, the program runs in a display‑only mode for testing.

**This version (v4.0.0) introduces major robustness improvements:**

- **PID controller** (with anti‑windup and derivative filter) for smooth, accurate tracking
- **Median filter** (buffer length 5) to reject outlier centroid jumps
- **EMA filter** (α=0.6) for additional temporal smoothing
- **Slew‑rate limiter** (max 3°/frame) to prevent jerky servo movements
- **Deadband** (12 px) to avoid micro‑oscillations when target is nearly centred
- **Persistent HSV tuning window** with trackbars (live update, auto‑swap High/Low)
- **Manual keyboard override** (W/A/S/D or arrows, R to reset, M to toggle mask overlay)

## Features

- Modular design: `camera_module`, `detector_module`, `servo_module`, `pid_controller`
- HSV colour detection with optional dual‑range masking (for colours near the hue wrap)
- PID control replaces simple proportional gains
- Median + EMA filtering for jitter suppression
- Slew‑rate limiting for smooth physical motion
- Graceful fallback to display‑only mode when servos are missing
- Interactive HSV tuner (`hsv_tuner.py`) for easy parameter adjustment
- Real‑time visualisation: bounding box, centre point, mask overlay, status overlay
- Keyboard manual control always available (even when no target detected)

## Project Structure
├── camera_module.py # PiCamera2 wrapper (capture frames)
├── detector_module.py # HSV colour detector (find largest blob)
├── hsv_tuner.py # Interactive slider tool to find HSV values
├── main.py # Main tracking loop (PID, filters, UI) – v4.0.0
├── pid_controller.py # Discrete PID controller with anti‑windup
├── rgb_to_hsv_range.py # Utility: convert RGB to HSV threshold range
├── servo_module.py # Servo controller (PCA9685 / fallback)
├── test_camera.py # Standalone camera + detector test
├── test_servo.py # Standalone servo sweep test
├── requirements.txt # Python dependencies
└── README.md # This file
## Requirements

- Raspberry Pi (tested on Pi 4 / Pi 5)
- Raspberry Pi Camera Module 2 (or any camera supported by libcamera/picamera2)
- (Optional) PCA9685 PWM driver board + two servos (pan/tilt)
- Python 3.9+

Install dependencies:
bash
pip install -r requirements.txt
> **Note:** `picamera2` and `libcamera` are part of Raspberry Pi OS (Bullseye or later). On other systems you may need to build them manually.

## Usage

### 1. Tune HSV Parameters

Run the tuner to find the best HSV range for your target object:
bash
python hsv_tuner.py
Adjust the six trackbars until only the desired object appears white in the mask window.  
Press `q` to exit – the final HSV values will be printed to the terminal.

Alternatively, use the built‑in tuning window inside `main.py` (see step 2).

### 2. Run Tracking
bash
python main.py
The program will prompt you to enter HSV thresholds (you can paste the values from the tuner).  
Then the main window opens:

- **Main window ("Tracking")**: Shows camera feed with bounding box, centre crosshair, and optional mask overlay.
- **HSV Tuning window**: Six trackbars to adjust H, S, V thresholds in real time. Also a `Min Area` slider.
- **Mask Preview window**: Binary mask (white = detected pixels).

**Keyboard controls (always active):**

| Key | Action |
|-----|--------|
| `W` / `Up Arrow` | Tilt up (+5°) |
| `S` / `Down Arrow` | Tilt down (-5°) |
| `A` / `Left Arrow` | Pan left (-5°) |
| `D` / `Right Arrow` | Pan right (+5°) |
| `R` | Reset to centre (90°, 90°) |
| `M` | Toggle mask overlay on/off |
| `Q` | Quit |

When a target is detected, the PID controller automatically adjusts pan/tilt to centre it. Manual commands override temporarily; automatic control resumes as soon as the target is re‑detected.

### 3. Display‑Only Mode

If the PCA9685 board is not connected or the `adafruit-circuitpython-servokit` library fails to load, the program automatically switches to display‑only mode.  
All tracking logic still runs (angles are updated internally but no physical movement occurs). The terminal shows `[SERVO] Hardware available: False`.

## Configuration

### Resolution

Change `width` and `height` in `main.py` (inside `TrackingSystem.__init__`):
python
self.camera = Camera(width=320, height=240)
### PID Gains

Edit the `PIDController` initialisations in `main.py`:
python
self.pid_pan = PIDController(kp=0.04, ki=0.003, kd=0.008,
integral_min=-20, integral_max=20)
self.pid_tilt = PIDController(kp=0.035, ki=0.002, kd=0.007,
integral_min=-20, integral_max=20)
### Deadband

Modify `self.deadband_px` (default 12 pixels).

### Slew‑Rate Limit

Modify `self.max_angle_change` (default 3.0 degrees per frame).

### EMA Alpha

Modify `self.ema_alpha` (default 0.6).

### Servo Inversion

Pass `invert_pan=True, invert_tilt=True` to `ServoController` if your servos are mounted opposite direction.

## Author

**KUANG, Haozhe**  
The Hong Kong University of Science and Technology  
[hkuangab@connect.ust.hk](mailto:hkuangab@connect.ust.hk)

## License

This project is licensed under the MIT License – see the header of each source file for details.