#!/usr/bin/env python3
"""
Convert a target RGB colour to an HSV threshold range suitable for colour detection.

Given an RGB value (e.g. from a colour picker), this script computes HSV bounds
with configurable tolerances to account for lighting variations.

Debugging features:
- Prints the intermediate HSV value of the input colour.
- Warns if the hue range wraps around (common for red/pink).
- Allows interactive input when run directly.

Returns:
    tuple: (primary_range, secondary_range)
        primary_range: (hsv_lower, hsv_upper) as two lists of three ints.
        secondary_range: None or (hsv_lower2, hsv_upper2) for hue-wrap colours.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0 (debug-enhanced)
"""

import cv2
import numpy as np


def rgb_to_hsv_range(r, g, b, hue_tol=10, sat_tol=40, val_tol=40, verbose=True):
    """
    Convert an RGB colour to HSV lower/upper bounds.

    Args:
        r, g, b: RGB values (0–255).
        hue_tol: Tolerance for H channel (degrees in OpenCV range 0–179).
        sat_tol: Tolerance for S channel (0–255).
        val_tol: Tolerance for V channel (0–255).
        verbose: If True, print debug information.

    Returns:
        tuple: (primary_range, secondary_range)
            primary_range: (hsv_lower, hsv_upper) as lists of three ints.
            secondary_range: None or (hsv_lower2, hsv_upper2) for hue-wrap colours.
    """
    # Convert single pixel to HSV
    rgb_arr = np.uint8([[[b, g, r]]])  # OpenCV uses BGR order
    hsv = cv2.cvtColor(rgb_arr, cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])

    if verbose:
        print(f"[DEBUG] Input RGB({r:3d},{g:3d},{b:3d}) -> HSV({h:3d},{s:3d},{v:3d})")

    # Compute lower and upper bounds
    h_low = max(0, h - hue_tol)
    h_high = min(179, h + hue_tol)
    s_low = max(0, s - sat_tol)
    s_high = min(255, s + sat_tol)
    v_low = max(0, v - val_tol)
    v_high = min(255, v + val_tol)

    # Check if the range crosses the 0/180 boundary
    if h_low > h_high:  # Wrap-around case (e.g., red)
        # Two ranges: [h_low, 179] and [0, h_high]
        lower1 = [h_low, s_low, v_low]
        upper1 = [179, s_high, v_high]
        lower2 = [0, s_low, v_low]
        upper2 = [h_high, s_high, v_high]
        if verbose:
            print("[DEBUG] Hue wraps around 0/180! Using two ranges.")
            print(f"  Range 1: H[{lower1[0]:3d}..{upper1[0]:3d}]")
            print(f"  Range 2: H[{lower2[0]:3d}..{upper2[0]:3d}]")
        return (lower1, upper1), (lower2, upper2)
    else:
        if verbose:
            print("[DEBUG] Single continuous hue range.")
        return ([h_low, s_low, v_low], [h_high, s_high, v_high]), None


if __name__ == "__main__":
    # Interactive mode
    print("=== RGB to HSV Range Converter ===\n")
    while True:
        try:
            inp = input("Enter RGB values separated by spaces (e.g., 239 215 194) or 'q' to quit: ")
            if inp.lower() == 'q':
                break
            parts = list(map(int, inp.strip().split()))
            if len(parts) != 3:
                print("Please enter exactly three numbers.")
                continue
            r, g, b = parts
            primary, secondary = rgb_to_hsv_range(r, g, b, verbose=True)
            print(f"\nPrimary range: lower={primary[0]}, upper={primary[1]}")
            if secondary:
                print(f"Secondary range: lower={secondary[0]}, upper={secondary[1]}")
            print("-" * 50)
        except ValueError:
            print("Invalid input. Use integers 0-255.")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break