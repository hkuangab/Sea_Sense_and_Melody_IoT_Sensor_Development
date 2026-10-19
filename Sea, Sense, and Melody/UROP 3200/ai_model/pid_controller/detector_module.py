#!/usr/bin/env python3
"""
HSV colour detector module.

Detects objects based on configurable HSV threshold ranges.
Supports dual-range masking for colours that wrap around the hue circle (e.g., red).
Includes optional Gaussian blur and morphological operations to reduce noise.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 2.1.0
"""

import cv2
import numpy as np


class ColorDetector:
    """
    Detects coloured blobs using HSV thresholds.

    Detection pipeline:
        1. (Optional) Apply Gaussian blur.
        2. Convert to HSV.
        3. Apply one or two inRange masks (combined via bitwise OR).
        4. Morphological opening/closing to remove noise.
        5. Find external contours and select the largest above min_area.
        6. Return its bounding box and centre coordinates.

    Attributes:
        lower1 (np.ndarray): Lower HSV bound for primary mask.
        upper1 (np.ndarray): Upper HSV bound for primary mask.
        lower2 (np.ndarray | None): Lower bound for secondary mask (optional).
        upper2 (np.ndarray | None): Upper bound for secondary mask.
        min_area (int): Minimum contour area (in pixels) to be considered valid.
        morph_kernel_size (int): Kernel size for morphological operations (default 7).
    """

    def __init__(self, hsv_lower: list, hsv_upper: list,
                 hsv_lower2: list = None, hsv_upper2: list = None,
                 min_area: int = 50, morph_kernel_size: int = 7):
        """
        Initialise detector with HSV ranges.

        Args:
            hsv_lower: Lower bound [H, S, V] for primary mask (list of three ints).
            hsv_upper: Upper bound [H, S, V] for primary mask.
            hsv_lower2: Lower bound for secondary mask (use for red or hue-wrap colours).
            hsv_upper2: Upper bound for secondary mask.
            min_area: Minimum contour area to accept a detection (default 50 px²).
            morph_kernel_size: Size of morphological kernel (odd, default 7).
        """
        self.lower1 = np.array(hsv_lower, dtype=np.uint8)
        self.upper1 = np.array(hsv_upper, dtype=np.uint8)
        self.lower2 = np.array(hsv_lower2, dtype=np.uint8) if hsv_lower2 else None
        self.upper2 = np.array(hsv_upper2, dtype=np.uint8) if hsv_upper2 else None
        self.min_area = min_area
        self.morph_kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)

    def detect(self, frame: np.ndarray, blur_kernel: int = 0):
        """
        Detect the largest coloured region in the frame.

        Args:
            frame: Input image in BGR format (as returned by OpenCV).
            blur_kernel: Kernel size for Gaussian blur (must be odd positive integer).
                         Set to 0 or 1 to disable blurring (default 0).

        Returns:
            tuple: (found_flag, center_x, center_y, bounding_box)
                - found_flag (bool): True if a valid object was detected.
                - center_x (int | None): X-coordinate of the blob centre.
                - center_y (int | None): Y-coordinate of the blob centre.
                - bounding_box (tuple | None): (x, y, w, h) rectangle of the blob.
        """
        # --- Step 1: Optional Gaussian blur for noise reduction ---
        if blur_kernel > 1 and blur_kernel % 2 == 1:
            processed = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)
        else:
            processed = frame

        # --- Step 2: Convert to HSV colour space ---
        hsv = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)

        # --- Step 3: Create primary mask ---
        mask = cv2.inRange(hsv, self.lower1, self.upper1)

        # Combine with secondary mask if provided (useful for red hues)
        if self.lower2 is not None:
            mask2 = cv2.inRange(hsv, self.lower2, self.upper2)
            mask = cv2.bitwise_or(mask, mask2)

        # --- Step 4: Morphological operations to clean up the mask ---
        # Opening removes small white noise; closing fills holes inside the object
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.morph_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.morph_kernel)

        # --- Step 5: Find external contours ---
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return False, None, None, None

        # Select the largest contour
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        # Reject detections smaller than the minimum area
        if area < self.min_area:
            return False, None, None, None

        # --- Step 6: Compute bounding box and centre ---
        x, y, w, h = cv2.boundingRect(largest)
        center_x = x + w // 2
        center_y = y + h // 2
        return True, center_x, center_y, (x, y, w, h)