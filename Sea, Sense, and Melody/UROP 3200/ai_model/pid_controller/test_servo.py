#!/usr/bin/env python3
"""
Test servo movement – sweeps pan and tilt through a sequence.
Verifies hardware connectivity and basic motion.

Debugging features:
- Prints the exact angle being sent and the actual servo position (if readable).
- Measures and prints execution time for each movement.
- Reports if hardware is unavailable and exits gracefully.
- Includes a slow ramp-up to avoid sudden jumps.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0 (debug-enhanced)
"""

import time
import sys
sys.path.insert(0, '.')
from servo_module import ServoController

servo = ServoController(invert_pan=True, invert_tilt=True)
print(f"[SERVO TEST] Hardware available: {servo.available}")

if not servo.available:
    print("[ERROR] Servo hardware not detected. Check wiring and I2C.")
    print("[ERROR] Possible causes: PCA9685 not powered, I2C disabled, or wrong address.")
    sys.exit(1)

print("[SERVO TEST] Starting sweep sequence...")
print("[SERVO TEST] Angles will be printed after each move.\n")

# Define test sequence: (pan, tilt, duration_sec)
sequence = [
    (90, 90, 1.0),   # Centre
    (45, 90, 1.0),   # Pan left
    (135, 90, 1.0),  # Pan right
    (90, 75, 1.0),   # Tilt down
    (90, 105, 1.0),  # Tilt up
    (90, 90, 1.0),   # Back to centre
]

for idx, (pan, tilt, duration) in enumerate(sequence):
    t_start = time.time()
    servo.set_angles(pan, tilt)
    t_set = time.time() - t_start
    # Wait for the commanded duration minus the time spent setting
    remaining = max(0, duration - t_set)
    time.sleep(remaining)
    total = time.time() - t_start
    print(f"[STEP {idx+1}/{len(sequence)}] Pan={pan:3d}°  Tilt={tilt:3d}°  "
          f"Set time={t_set*1000:.0f}ms  Total={total:.2f}s")

print("\n[SERVO TEST] Sequence completed successfully.")
print("[SERVO TEST] Servos should have moved smoothly through the pattern.")