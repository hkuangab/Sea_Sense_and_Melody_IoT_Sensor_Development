#!/usr/bin/env python3
"""
Servo controller module for pan/tilt mechanism.
Supports PCA9685 via adafruit_servokit; falls back to display-only mode if hardware unavailable.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.0.0
"""

import logging

# Attempt to import hardware library; if it fails (no board, no I2C), set flag
try:
    from adafruit_servokit import ServoKit
    HARDWARE_AVAILABLE = True
except (ImportError, OSError):
    HARDWARE_AVAILABLE = False

logger = logging.getLogger(__name__)


class ServoController:
    """
    Controls two servos (pan and tilt) using PCA9685 via Adafruit ServoKit.

    Provides a unified interface regardless of whether hardware is present.
    When hardware is absent, the class stores angles internally and reports
    availability via the `available` attribute.

    Attributes:
        invert_pan (bool): Whether to reverse the pan direction.
        invert_tilt (bool): Whether to reverse the tilt direction.
        _pan_angle (float): Current pan angle (internal, 0–180).
        _tilt_angle (float): Current tilt angle (internal, 0–180).
        available (bool): True if servo hardware was successfully initialised.
        kit (ServoKit | None): Hardware interface (only when available).
    """

    def __init__(self, invert_pan=False, invert_tilt=False):
        """
        Initialise servo controller.

        Args:
            invert_pan: Set to True if pan servo moves opposite to expected direction.
            invert_tilt: Set to True if tilt servo moves opposite to expected direction.
        """
        self.invert_pan = invert_pan
        self.invert_tilt = invert_tilt
        self._pan_angle = 90.0   # Start at centre
        self._tilt_angle = 90.0
        self.available = HARDWARE_AVAILABLE

        if self.available:
            try:
                # Create ServoKit instance (16 channels for PCA9685)
                self.kit = ServoKit(channels=16)
                # Assume pan on channel 0, tilt on channel 1
                self.kit.servo[0].angle = self._pan_angle
                self.kit.servo[1].angle = self._tilt_angle
                logger.info("Servo hardware initialised.")
            except Exception as e:
                logger.warning(f"Failed to init servos: {e}. Entering display-only mode.")
                self.available = False
        else:
            logger.info("No servo hardware detected. Running in display-only mode.")

    @property
    def pan_angle(self):
        """Return the current pan angle (without inversion applied)."""
        return self._pan_angle

    @property
    def tilt_angle(self):
        """Return the current tilt angle (without inversion applied)."""
        return self._tilt_angle

    def set_angles(self, pan, tilt):
        """
        Set both servo angles. Values are clamped to [0, 180].

        If `invert_pan` or `invert_tilt` is True, the angle is mirrored
        (180 - angle) before sending to the hardware.

        Args:
            pan: Desired pan angle (0–180).
            tilt: Desired tilt angle (0–180).
        """
        # Clamp inputs to valid range
        pan = max(0, min(180, pan))
        tilt = max(0, min(180, tilt))

        # Apply inversion if requested
        actual_pan = 180 - pan if self.invert_pan else pan
        actual_tilt = 180 - tilt if self.invert_tilt else tilt

        # Store the logical (non-inverted) angles
        self._pan_angle = pan
        self._tilt_angle = tilt

        # Send to hardware if available
        if self.available:
            try:
                self.kit.servo[0].angle = actual_pan
                self.kit.servo[1].angle = actual_tilt
            except Exception as e:
                logger.error(f"Failed to set servo angles: {e}")
                self.available = False  # Disable further hardware attempts