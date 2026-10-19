#!/usr/bin/env python3
"""
Camera module for Pi Camera Module 2 using picamera2 + libcamera.

Provides a simple interface to capture frames in RGB888 format.
The camera is configured with a vertical flip to compensate for upside-down mounting.

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0
"""

import libcamera
from picamera2 import Picamera2
import time


class Camera:
    """
    Wrapper for Picamera2 with preset configuration.

    Attributes:
        width (int): Frame width in pixels.
        height (int): Frame height in pixels.
        framerate (int): Target frames per second (used for configuration).
        picamera (Picamera2 | None): Internal camera instance, created on start().
    """

    def __init__(self, width: int = 320, height: int = 240, framerate: int = 30):
        """
        Initialize camera parameters without starting the hardware.

        Args:
            width: Desired frame width (default 320).
            height: Desired frame height (default 240).
            framerate: Target FPS (default 30). Actual FPS depends on exposure.
        """
        self.width = width
        self.height = height
        self.framerate = framerate
        self.picamera = None  # Will be created in start()

    def start(self) -> None:
        """
        Initialize and start the camera pipeline.

        Creates a preview configuration with RGB888 format and applies a vertical flip
        transform. A short sleep allows auto-exposure to stabilise before first capture.
        """
        self.picamera = Picamera2()
        config = self.picamera.create_preview_configuration(
            main={"format": 'RGB888', "size": (self.width, self.height)},
            raw={"format": "SRGGB12", "size": (1920, 1080)}  # Raw stream for potential use
        )
        # Vertical flip to correct camera orientation (mount-dependent)
        config["transform"] = libcamera.Transform(hflip=0, vflip=1)
        self.picamera.configure(config)
        self.picamera.start()

        # Let auto-exposure settle (important for stable brightness)
        time.sleep(1.5)
        print(f"[CAMERA] Started: {self.width}x{self.height} @ {self.framerate}fps")

    def capture_frame(self):
        """
        Capture a single RGB frame from the camera.

        Returns:
            numpy.ndarray: Image array of shape (height, width, 3) with dtype uint8.

        Raises:
            RuntimeError: If the camera has not been started yet.
        """
        if self.picamera is None:
            raise RuntimeError("Camera not started. Call start() first.")
        return self.picamera.capture_array()

    def stop(self) -> None:
        """Stop the camera and release resources."""
        if self.picamera:
            self.picamera.stop()
            print("[CAMERA] Stopped")