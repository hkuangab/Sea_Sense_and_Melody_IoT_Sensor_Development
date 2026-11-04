#!/usr/bin/env python3
"""
PID Controller for pan/tilt servo tracking.

Implements a discrete PID controller with:
- Anti-windup (integral clamping)
- Derivative low-pass filter (to reduce noise amplification)
- Configurable sample time

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
License: MIT
Version: 1.1.0
"""

import time


class PIDController:
    """
    Discrete PID controller for real-time servo correction.

    Attributes:
        kp (float): Proportional gain.
        ki (float): Integral gain.
        kd (float): Derivative gain.
        dt (float): Sample time in seconds (auto-calculated if not fixed).
        integral_min (float): Lower clamp for integral term (anti-windup).
        integral_max (float): Upper clamp for integral term.
        _last_error (float): Previous error for derivative calculation.
        _last_output (float): Previous output for derivative filter.
        _last_time (float): Timestamp of last update.
    """

    def __init__(self, kp=0.03, ki=0.002, kd=0.01,
                 integral_min=-30, integral_max=30, dt=None):
        """
        Initialise PID gains and limits.

        Args:
            kp: Proportional gain (default 0.03).
            ki: Integral gain (default 0.002).
            kd: Derivative gain (default 0.01).
            integral_min: Minimum integral sum (anti-windup).
            integral_max: Maximum integral sum.
            dt: Fixed sample time in seconds. If None, computed from time differences.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.integral_min = integral_min
        self.integral_max = integral_max

        self._integral = 0.0
        self._last_error = 0.0
        self._last_output = 0.0
        self._last_time = time.time()

    def reset(self):
        """Reset integral and derivative states (call when target changes significantly)."""
        self._integral = 0.0
        self._last_error = 0.0
        self._last_output = 0.0
        self._last_time = time.time()

    def compute(self, error):
        """
        Compute PID output given the current error.

        Args:
            error: Difference between setpoint and measured value.

        Returns:
            float: Control output (to be added to current angle).
        """
        now = time.time()
        if self.dt is not None:
            dt = self.dt
        else:
            dt = now - self._last_time
            if dt <= 0.0:
                dt = 1e-6  # avoid division by zero

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup
        self._integral += error * dt
        self._integral = max(self.integral_min, min(self.integral_max, self._integral))
        i_term = self.ki * self._integral

        # Derivative term with low-pass filter (alpha = 0.2)
        derivative = (error - self._last_error) / dt
        alpha = 0.2  # filter coefficient
        # Filtered derivative: blend raw derivative with previous filtered value
        if self.kd != 0:
            # Approximate previous filtered derivative from last output
            prev_filtered_d = (self._last_output - p_term - i_term) / self.kd
        else:
            prev_filtered_d = 0.0
        d_term = self.kd * (alpha * derivative + (1 - alpha) * prev_filtered_d)

        # Sum terms
        output = p_term + i_term + d_term

        # Save state for next iteration
        self._last_error = error
        self._last_output = output
        self._last_time = now

        return output