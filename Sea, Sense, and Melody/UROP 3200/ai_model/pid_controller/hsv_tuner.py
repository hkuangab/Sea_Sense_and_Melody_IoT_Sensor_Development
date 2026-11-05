#!/usr/bin/env python3
"""
HSV Threshold Tuner with Trackbars.
Displays live camera feed, mask, and detection result.
Prints target center coordinates and current HSV range to terminal every frame.
After tuning, copy the final HSV values into main.py's ColorDetector.

Debugging features:
- Prints detection status (found/not found) every frame.
- Shows the exact HSV values being used in the terminal.
- Draws bounding box and center crosshair on the result window.
- Terminal output updates continuously for fine-tuning.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0 (debug-enhanced)
"""

import cv2
import os
import numpy as np
import sys
sys.path.insert(0, '.')

from camera_module import Camera


def nothing(x):
    """Empty callback for trackbar creation."""
    pass


def main():
    cam = Camera(width=320, height=240)
    cam.start()

    cv2.namedWindow('HSV Tuning')
    cv2.resizeWindow('HSV Tuning', 800, 600)

    # Initial sliders (adjust to your target color)
    cv2.createTrackbar('H Low', 'HSV Tuning', 100, 179, nothing)
    cv2.createTrackbar('H High', 'HSV Tuning', 140, 179, nothing)
    cv2.createTrackbar('S Low', 'HSV Tuning', 80, 255, nothing)
    cv2.createTrackbar('S High', 'HSV Tuning', 220, 255, nothing)
    cv2.createTrackbar('V Low', 'HSV Tuning', 60, 255, nothing)
    cv2.createTrackbar('V High', 'HSV Tuning', 230, 255, nothing)
    cv2.createTrackbar('Min Area', 'HSV Tuning', 300, 1000, nothing)

    print("[TUNER] Adjust sliders to isolate your target color.")
    print("[TUNER] Press 'q' to quit. Coordinates printed when detected.")
    print("[DEBUG] Terminal shows: center, area, and current HSV thresholds.\n")

    try:
        while True:
            frame = cam.capture_frame()
            hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

            # Read all trackbar values
            h_low = cv2.getTrackbarPos('H Low', 'HSV Tuning')
            h_high = cv2.getTrackbarPos('H High', 'HSV Tuning')
            s_low = cv2.getTrackbarPos('S Low', 'HSV Tuning')
            s_high = cv2.getTrackbarPos('S High', 'HSV Tuning')
            v_low = cv2.getTrackbarPos('V Low', 'HSV Tuning')
            v_high = cv2.getTrackbarPos('V High', 'HSV Tuning')
            min_area = cv2.getTrackbarPos('Min Area', 'HSV Tuning')

            # Build mask
            lower = np.array([h_low, s_low, v_low], dtype=np.uint8)
            upper = np.array([h_high, s_high, v_high], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower, upper)

            # Morphological cleaning
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)

            result = frame.copy()
            found = False
            debug_msg = "[DEBUG] NOT DETECTED"

            if contours:
                largest = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest)
                if area >= min_area:
                    x, y, w, h = cv2.boundingRect(largest)
                    cx = x + w // 2
                    cy = y + h // 2
                    cv2.rectangle(result, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.circle(result, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.putText(result, f"({cx},{cy})", (cx+5, cy-5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                    debug_msg = (f"[DEBUG] Center=({cx:3d},{cy:3d})  "
                                 f"Area={area:5.0f}  "
                                 f"H:[{h_low:3d}-{h_high:3d}]  "
                                 f"S:[{s_low:3d}-{s_high:3d}]  "
                                 f"V:[{v_low:3d}-{v_high:3d}]")
                    found = True

            # Print debug info every frame (suppress if not needed, but helpful)
            print(debug_msg)

            # Build display layout
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            top_row = np.hstack([frame, result])
            bottom_row = np.hstack([mask_bgr, np.zeros_like(mask_bgr)])
            display = np.vstack([top_row, bottom_row])

            status = "DETECTED" if found else "NOT DETECTED"
            cv2.putText(display, status, (10, 570),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 0) if found else (0, 0, 255), 2)

            cv2.imshow('HSV Tuning', display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n[TUNER] Final HSV values (copy these into main.py):")
                print(f"  hsv_lower=[{h_low}, {s_low}, {v_low}]")
                print(f"  hsv_upper=[{h_high}, {s_high}, {v_high}]")
                print(f"  min_area={min_area}")
                os._exit(0)

    except KeyboardInterrupt:
        print("\n[TUNER] Interrupted by user (Ctrl+C).")
    finally:
        cam.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()