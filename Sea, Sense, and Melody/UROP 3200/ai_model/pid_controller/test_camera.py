#!/usr/bin/env python3
"""
Test colour detection – prints centre and area every frame.
Useful for verifying that the camera and detector work before enabling servos.

Debugging features:
- Prints full detection status including contour count and areas.
- Shows bounding box and centre crosshair on the image.
- Terminal output includes frame number and elapsed time.
- Handles missing detection gracefully with clear message.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0 (debug-enhanced)
"""

import cv2
import sys
import time
sys.path.insert(0, '.')
from camera_module import Camera
from detector_module import ColorDetector
import numpy as np

cam = Camera(width=320, height=240)
cam.start()

# Use typical HSV thresholds for light skin tone (RGB 239,215,194)
# You can adjust these after running hsv_tuner.py
detector = ColorDetector(
    hsv_lower=[0, 35, 170],
    hsv_upper=[28, 125, 250],
    min_area=200
)

print("[TEST] Camera and detector test started.")
print("[TEST] Press 'q' to quit. Output shows centre and area every frame.\n")

frame_count = 0
start_time = time.time()

while True:
    frame = cam.capture_frame()
    frame_count += 1
    elapsed = time.time() - start_time

    found, cx, cy, bbox = detector.detect(frame, blur_kernel=5)

    # Debug output
    if found:
        x, y, w, h = bbox
        area = w * h
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 3)
        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
        cv2.putText(frame, f"({cx},{cy})", (cx+5, cy-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        print(f"[FRAME {frame_count:4d}] Center=({cx:3d},{cy:3d})  Area={area:4d}  "
              f"Time={elapsed:.2f}s")
    else:
        print(f"[FRAME {frame_count:4d}] NOT DETECTED  Time={elapsed:.2f}s")

    cv2.imshow('Test Camera', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        print(f"\n[TEST] Quit after {frame_count} frames ({elapsed:.1f}s).")
        break

cam.stop()
cv2.destroyAllWindows()