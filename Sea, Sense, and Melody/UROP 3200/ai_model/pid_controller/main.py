#!/usr/bin/env python3
"""
Persistent HSV tuning with live mask and PID-based tracking.
- Separate window with sliders for H, S, V (first range).
- Separate window showing binary mask (white = detected).
- Main window shows bounding box and optional overlay.
- Largest object within HSV range is tracked and centred.
- Median filter on centroid to reject outlier jumps.
- PID controller for smooth, robust servo movement.
- Slew-rate limiter prevents abrupt angle changes.
- Deadband, EMA, and manual keyboard override.

Keys:
  q   – quit
  m   – toggle mask overlay
  w/a/s/d or arrows – manual pan/tilt adjustment
  r   – reset to centre (90°, 90°)

Author: KUANG, Haozhe
Affiliation: HKUST
Email: hkuangab@connect.ust.hk
Version: 4.0.0
"""

import cv2
import signal
import sys
import time
import numpy as np
from collections import deque

from camera_module import Camera
from detector_module import ColorDetector
from servo_module import ServoController
from pid_controller import PIDController


class TrackingSystem:
    def __init__(self):
        self.camera = Camera(width=320, height=240)
        self.servo = ServoController(invert_pan=True, invert_tilt=True)
        print(f"[SERVO] Hardware available: {self.servo.available}")

        if self.servo.available:
            print("[TEST] Sweeping servos...")
            self.servo.set_angles(45, 90); time.sleep(0.5)
            self.servo.set_angles(135, 90); time.sleep(0.5)
            self.servo.set_angles(90, 90); time.sleep(0.3)
            print("[TEST] Done.")

        # Get initial HSV thresholds from user
        hsv_params = self._get_hsv_from_user()
        self.detector = ColorDetector(**hsv_params)

        # Store thresholds for live update
        self.hsv_lower = np.array(hsv_params.get('hsv_lower', [0,0,0]))
        self.hsv_upper = np.array(hsv_params.get('hsv_upper', [179,255,255]))
        self.hsv_lower2 = np.array(hsv_params.get('hsv_lower2', [0,0,0])) if hsv_params.get('hsv_lower2') else None
        self.hsv_upper2 = np.array(hsv_params.get('hsv_upper2', [179,255,255])) if hsv_params.get('hsv_upper2') else None
        self.min_area = hsv_params.get('min_area', 400)

        # Flag to rebuild detector only when thresholds change
        self._thresholds_changed = False

        # ---- Robustness enhancements ----
        # Median filter buffer for centroid (length 5)
        self.cx_buffer = deque(maxlen=5)
        self.cy_buffer = deque(maxlen=5)

        # EMA filter (still used after median)
        self.ema_alpha = 0.6
        self.filtered_cx = None
        self.filtered_cy = None

        # Deadband for servo commands (pixels)
        self.deadband_px = 12

        # Slew-rate limiter (max degrees per frame)
        self.max_angle_change = 3.0  # degrees

        # PID controllers for pan and tilt
        self.pid_pan = PIDController(kp=0.04, ki=0.003, kd=0.008,
                                     integral_min=-20, integral_max=20)
        self.pid_tilt = PIDController(kp=0.035, ki=0.002, kd=0.007,
                                      integral_min=-20, integral_max=20)

        self.pan_angle = 90.0
        self.tilt_angle = 90.0
        self.show_mask_overlay = True
        self.running = False
        signal.signal(signal.SIGINT, self._signal_handler)

        # Create persistent tuning window
        self._create_tuning_window()

        # --- Store hovered pixel info for overlay ---
        self._hover_bgr = None
        self._hover_hsv = None
        self._hover_pos = (0, 0)

        # --- Manual control step size (degrees) ---
        self.manual_step = 5

    # ------------------------------------------------------------------
    # HSV input from user (direct HSV entry, no RGB)
    # ------------------------------------------------------------------
    def _get_hsv_from_user(self):
        print("\n=== HSV Threshold Setup ===")
        print("Enter lower HSV bound (H 0-179, S 0-255, V 0-255).")
        print("Example for skin tone: 0 0 130")
        while True:
            inp = input("Lower HSV: ").strip()
            if inp == "":
                lower = [0, 0, 145]
                print(f"Using default lower: {lower}")
                break
            try:
                vals = list(map(int, inp.split()))
                if len(vals) != 3 or vals[0]<0 or vals[0]>179 or vals[1]<0 or vals[1]>255 or vals[2]<0 or vals[2]>255:
                    print("Must be three integers: H 0-179, S 0-255, V 0-255.")
                    continue
                lower = vals
                break
            except:
                print("Invalid input.")

        print("\nEnter upper HSV bound (same format). Example: 25 65 235")
        while True:
            inp = input("Upper HSV: ").strip()
            if inp == "":
                upper = [40, 85, 245]
                print(f"Using default upper: {upper}")
                break
            try:
                vals = list(map(int, inp.split()))
                if len(vals) != 3 or vals[0]<0 or vals[0]>179 or vals[1]<0 or vals[1]>255 or vals[2]<0 or vals[2]>255:
                    print("Must be three integers: H 0-179, S 0-255, V 0-255.")
                    continue
                upper = vals
                break
            except:
                print("Invalid input.")

        # Optional second range (for red wrap-around)
        print("\nOptional: second HSV range for red wrap-around (press Enter to skip).")
        lower2, upper2 = None, None
        inp = input("Lower2 HSV (or empty): ").strip()
        if inp:
            try:
                lower2 = list(map(int, inp.split()))
                if len(lower2)!=3: raise ValueError
                inp2 = input("Upper2 HSV: ").strip()
                upper2 = list(map(int, inp2.split()))
                if len(upper2)!=3: raise ValueError
            except:
                print("Invalid second range, ignoring.")
                lower2 = upper2 = None

        print("\nMinimum contour area (pixels)? Default 400.")
        inp = input("Min area: ").strip()
        min_area = 400
        if inp:
            try:
                min_area = int(inp)
                if min_area < 1: min_area = 400
            except:
                pass

        params = {
            'hsv_lower': lower,
            'hsv_upper': upper,
            'min_area': min_area
        }
        if lower2 is not None and upper2 is not None:
            params['hsv_lower2'] = lower2
            params['hsv_upper2'] = upper2
        else:
            params['hsv_lower2'] = None
            params['hsv_upper2'] = None

        print(f"\nInitial HSV thresholds:")
        print(f"  Range1: [{lower[0]},{lower[1]},{lower[2]}] -> [{upper[0]},{upper[1]},{upper[2]}]")
        if lower2:
            print(f"  Range2: [{lower2[0]},{lower2[1]},{lower2[2]}] -> [{upper2[0]},{upper2[1]},{upper2[2]}]")
        print(f"  Min area: {min_area}\n")
        return params

    def _signal_handler(self, signum, frame):
        print("\n[SYSTEM] Interrupt received.")
        self.running = False

    # ------------------------------------------------------------------
    # Persistent tuning window (non‑blocking)
    # ------------------------------------------------------------------
    def _create_tuning_window(self):
        """Create a window with trackbars for first HSV range and min area."""
        self.tune_win = "HSV Tuning"
        cv2.namedWindow(self.tune_win, cv2.WINDOW_NORMAL)
        cv2.createTrackbar("H Low", self.tune_win, int(self.hsv_lower[0]), 179, lambda x:None)
        cv2.createTrackbar("H High", self.tune_win, int(self.hsv_upper[0]), 179, lambda x:None)
        cv2.createTrackbar("S Low", self.tune_win, int(self.hsv_lower[1]), 255, lambda x:None)
        cv2.createTrackbar("S High", self.tune_win, int(self.hsv_upper[1]), 255, lambda x:None)
        cv2.createTrackbar("V Low", self.tune_win, int(self.hsv_lower[2]), 255, lambda x:None)
        cv2.createTrackbar("V High", self.tune_win, int(self.hsv_upper[2]), 255, lambda x:None)
        cv2.createTrackbar("Min Area", self.tune_win, self.min_area, 5000, lambda x:None)

        cv2.setWindowProperty(self.tune_win, cv2.WND_PROP_TOPMOST, 1)

        self.mask_win = "Mask Preview"
        cv2.namedWindow(self.mask_win)

        print("[INFO] Click on the 'HSV Tuning' window to use the sliders.")

    def _read_trackbars(self):
        """Read slider positions, enforce High >= Low, update thresholds if changed."""
        hl = cv2.getTrackbarPos("H Low", self.tune_win)
        hh = cv2.getTrackbarPos("H High", self.tune_win)
        sl = cv2.getTrackbarPos("S Low", self.tune_win)
        sh = cv2.getTrackbarPos("S High", self.tune_win)
        vl = cv2.getTrackbarPos("V Low", self.tune_win)
        vh = cv2.getTrackbarPos("V High", self.tune_win)
        ma = cv2.getTrackbarPos("Min Area", self.tune_win)

        # Enforce High >= Low for each channel
        if hh < hl:
            hl, hh = hh, hl
            cv2.setTrackbarPos("H Low", self.tune_win, hl)
            cv2.setTrackbarPos("H High", self.tune_win, hh)
        if sh < sl:
            sl, sh = sh, sl
            cv2.setTrackbarPos("S Low", self.tune_win, sl)
            cv2.setTrackbarPos("S High", self.tune_win, sh)
        if vh < vl:
            vl, vh = vh, vl
            cv2.setTrackbarPos("V Low", self.tune_win, vl)
            cv2.setTrackbarPos("V High", self.tune_win, vh)

        new_lower = np.array([hl, sl, vl])
        new_upper = np.array([hh, sh, vh])

        # Check if anything changed
        if not np.array_equal(new_lower, self.hsv_lower) or \
           not np.array_equal(new_upper, self.hsv_upper) or \
           ma != self.min_area:
            self.hsv_lower = new_lower
            self.hsv_upper = new_upper
            self.min_area = ma
            self._thresholds_changed = True

    def _apply_new_thresholds(self):
        """Rebuild detector with current thresholds (only if changed)."""
        if self._thresholds_changed:
            self.detector = ColorDetector(
                hsv_lower=self.hsv_lower.tolist(),
                hsv_upper=self.hsv_upper.tolist(),
                hsv_lower2=self.hsv_lower2.tolist() if self.hsv_lower2 is not None else None,
                hsv_upper2=self.hsv_upper2.tolist() if self.hsv_upper2 is not None else None,
                min_area=self.min_area
            )
            self._thresholds_changed = False
            print(f"[THRESH] H:[{self.hsv_lower[0]},{self.hsv_upper[0]}]  "
                  f"S:[{self.hsv_lower[1]},{self.hsv_upper[1]}]  "
                  f"V:[{self.hsv_lower[2]},{self.hsv_upper[2]}]  "
                  f"MinArea:{self.min_area}")

    # ------------------------------------------------------------------
    # Mask computation
    # ------------------------------------------------------------------
    def _compute_mask(self, hsv_frame):
        mask1 = cv2.inRange(hsv_frame, self.hsv_lower, self.hsv_upper)
        if self.hsv_lower2 is not None:
            mask2 = cv2.inRange(hsv_frame, self.hsv_lower2, self.hsv_upper2)
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            mask = mask1
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask

    # ------------------------------------------------------------------
    # Mouse callback – stores hovered pixel values for overlay
    # ------------------------------------------------------------------
    def _mouse_callback(self, event, x, y, flags, param):
        """Store HSV value of the pixel under the cursor."""
        if event == cv2.EVENT_MOUSEMOVE:
            if hasattr(self, '_last_frame_bgr') and self._last_frame_bgr is not None:
                bgr = self._last_frame_bgr[y, x]
                hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
                self._hover_bgr = bgr
                self._hover_hsv = hsv
                self._hover_pos = (x, y)

    # ------------------------------------------------------------------
    # Keyboard manual control handler
    # ------------------------------------------------------------------
    def _handle_manual_key(self, key):
        """Adjust pan/tilt based on keyboard input. Returns True if manual command issued."""
        moved = False
        if key == ord('w') or key == 82:      # W or Up arrow
            self.tilt_angle = np.clip(self.tilt_angle + self.manual_step, 0, 180)
            moved = True
        elif key == ord('s') or key == 84:     # S or Down arrow
            self.tilt_angle = np.clip(self.tilt_angle - self.manual_step, 0, 180)
            moved = True
        elif key == ord('a') or key == 81:     # A or Left arrow
            self.pan_angle = np.clip(self.pan_angle - self.manual_step, 0, 180)
            moved = True
        elif key == ord('d') or key == 83:     # D or Right arrow
            self.pan_angle = np.clip(self.pan_angle + self.manual_step, 0, 180)
            moved = True
        elif key == ord('r') or key == ord('R'):
            self.pan_angle = 90.0
            self.tilt_angle = 90.0
            # Reset PID states when manually centering
            self.pid_pan.reset()
            self.pid_tilt.reset()
            moved = True
            print("[MANUAL] Reset to centre (90°, 90°).")

        if moved:
            self.servo.set_angles(self.pan_angle, self.tilt_angle)
            print(f"[MANUAL] Pan={self.pan_angle:.1f}  Tilt={self.tilt_angle:.1f}")
        return moved

    # ------------------------------------------------------------------
    # Slew-rate limiter for smooth angle transitions
    # ------------------------------------------------------------------
    def _apply_slew_rate(self, target_pan, target_tilt):
        """Limit angle change per frame to prevent jerkiness."""
        pan_delta = np.clip(target_pan - self.pan_angle,
                            -self.max_angle_change, self.max_angle_change)
        tilt_delta = np.clip(target_tilt - self.tilt_angle,
                             -self.max_angle_change, self.max_angle_change)
        self.pan_angle = np.clip(self.pan_angle + pan_delta, 0, 180)
        self.tilt_angle = np.clip(self.tilt_angle + tilt_delta, 0, 180)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def setup(self):
        self.camera.start()
        print("[SYSTEM] Ready. Keys: q=quit, m=mask, w/a/s/d or arrows=manual, r=reset.")
        self.running = True

    def run(self):
        if not self.running:
            self.setup()

        cv2.namedWindow('Tracking')
        cv2.setMouseCallback('Tracking', self._mouse_callback)

        frame_counter = 0
        while self.running:
            try:
                frame_rgb = self.camera.capture_frame()
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                frame_counter += 1

                self._last_frame_bgr = frame_bgr.copy()

                self._read_trackbars()
                self._apply_new_thresholds()

                hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
                mask = self._compute_mask(hsv)
                cv2.imshow(self.mask_win, mask)

                found, cx, cy, bbox = self.detector.detect(frame_bgr, blur_kernel=7)

                # ---------- DEBUG: print detection status ----------
                if not found:
                    if frame_counter % 30 == 0:
                        print("[DEBUG] No target detected. Check HSV thresholds and mask.")
                else:
                    if frame_counter % 10 == 0:
                        print(f"[DEBUG] Target FOUND at ({cx},{cy}), area={bbox[2]*bbox[3]}")

                display_frame = frame_bgr.copy()
                if self.show_mask_overlay:
                    mask_colour = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                    mask_colour[:,:,1] = mask
                    display_frame = cv2.addWeighted(display_frame, 0.7, mask_colour, 0.3, 0)

                if found and bbox is not None:
                    x,y,w,h = bbox
                    cv2.rectangle(display_frame, (x,y), (x+w,y+h), (255,0,0), 3)

                    # ---- Step 1: Median filter to reject outlier jumps ----
                    self.cx_buffer.append(cx)
                    self.cy_buffer.append(cy)
                    median_cx = int(np.median(self.cx_buffer))
                    median_cy = int(np.median(self.cy_buffer))

                    # ---- Step 2: EMA filter for additional smoothing ----
                    if self.filtered_cx is None:
                        self.filtered_cx = float(median_cx)
                        self.filtered_cy = float(median_cy)
                    else:
                        self.filtered_cx = self.ema_alpha * self.filtered_cx + (1 - self.ema_alpha) * median_cx
                        self.filtered_cy = self.ema_alpha * self.filtered_cy + (1 - self.ema_alpha) * median_cy

                    filtered_cx_int = int(round(self.filtered_cx))
                    filtered_cy_int = int(round(self.filtered_cy))

                    cv2.drawMarker(display_frame, (filtered_cx_int, filtered_cy_int),
                                   (0,255,0), markerType=cv2.MARKER_CROSS, thickness=2)

                    img_cx = self.camera.width // 2
                    img_cy = self.camera.height // 2
                    err_x = filtered_cx_int - img_cx
                    err_y = filtered_cy_int - img_cy

                    # ---- Step 3: Deadband ----
                    if abs(err_x) <= self.deadband_px:
                        err_x = 0
                    if abs(err_y) <= self.deadband_px:
                        err_y = 0

                    # ---- Step 4: PID compute ----
                    pid_out_pan = self.pid_pan.compute(-err_x)   # negative because pan direction
                    pid_out_tilt = self.pid_tilt.compute(-err_y)

                    target_pan = self.pan_angle + pid_out_pan
                    target_tilt = self.tilt_angle + pid_out_tilt

                    # ---- Step 5: Slew-rate limiter ----
                    self._apply_slew_rate(target_pan, target_tilt)

                    # ---- Step 6: Send to servos ----
                    self.servo.set_angles(self.pan_angle, self.tilt_angle)

                    if frame_counter % 10 == 0:
                        print(f"[TRACK] Raw=({cx:3d},{cy:3d}) Med=({median_cx:3d},{median_cy:3d}) "
                              f"Filtered=({filtered_cx_int:3d},{filtered_cy_int:3d})  "
                              f"Pan={self.pan_angle:5.1f}  Tilt={self.tilt_angle:5.1f}  "
                              f"PID_pan={pid_out_pan:.2f}  PID_tilt={pid_out_tilt:.2f}")

                # Always show HSV overlay at top-left corner
                if self._hover_hsv is not None:
                    h,s,v = self._hover_hsv
                    text = f"HSV({h:3d},{s:3d},{v:3d})"
                    cv2.putText(display_frame, text, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                cv2.imshow('Tracking', display_frame)

                # Handle keyboard (both manual and standard keys)
                key = cv2.waitKey(10) & 0xFF
                if key == ord('q'):
                    self.running = False
                elif key == ord('m'):
                    self.show_mask_overlay = not self.show_mask_overlay
                    print(f"[UI] Mask overlay {'ON' if self.show_mask_overlay else 'OFF'}")
                else:
                    self._handle_manual_key(key)

            except Exception as e:
                print(f"[ERROR] Frame {frame_counter}: {e}")
                continue

        self.cleanup()

    def cleanup(self):
        try:
            self.servo.set_angles(90, 90)
            print("[SERVO] Centred.")
        except: pass
        self.camera.stop()
        cv2.destroyAllWindows()
        print("[SYSTEM] Cleanup done.")


def main():
    system = TrackingSystem()
    try:
        system.run()
    except Exception as e:
        print(f"[FATAL] {e}")
        system.cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()