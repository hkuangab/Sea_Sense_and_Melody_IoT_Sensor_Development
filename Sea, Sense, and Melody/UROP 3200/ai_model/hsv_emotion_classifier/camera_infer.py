#!/usr/bin/env python3
"""
camera_infer.py — CSV-driven 26-D emotion inference, sends label string to C
============================================================================

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Reads the newest row of sensor_box.csv (written by main_camera.c every
    second), builds the 26-D feature vector the GRU was trained on, keeps a
    12-row sliding window, runs inference, and pushes the **emotion label text**
    (e.g. "Embarrassed Fluster") into the POSIX queue "/sensor_box_infer" —
    which main_camera.c drains every 5 ms, draws on the SDL camera window,
    and writes into the next CSV row.

    Message queue is used through ctypes + librt (mq_open/mq_send directly).
    posix_ipc is NOT required.

Run:
    sudo python camera_infer.py
"""

import os
import sys
import time
import math
import pickle
import select
import threading
import ctypes
import warnings
from collections import deque
from datetime import datetime

warnings.filterwarnings('ignore')

import numpy as np
import torch
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mood_model import load_model, INPUT_DIM, NUM_CLASSES, WINDOW_SIZE
from emotion_profiles import EMOTION_PROFILES, EMOTION_COLOR_PROFILES

# ---------------------------------------------------------------------------
# Paths — this file lives in <UROP>/ai_model/hsv_emotion_classifier,
# the CSV lives in <UROP>/sensor_box/sensor_box.csv
# ---------------------------------------------------------------------------
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
UROP_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
MODELS_DIR = os.path.join(BASE_DIR, 'trained_model')

CONFIG = {
    'model_path':  os.path.join(MODELS_DIR, 'gru_mood_model.pth'),
    'scaler_path': os.path.join(MODELS_DIR, 'scaler.pkl'),
    'csv_path':    os.path.join(UROP_ROOT, 'sensor_box', 'sensor_box.csv'),
    'window_size': WINDOW_SIZE,          # 12
    'prediction_smoothing': 5,
    'poll_interval': 0.5,
}

MQ_NAME = "/sensor_box_infer"     # must match INFER_MQ_NAME in sensor_box.h

EMOTION_LABELS = {
    pid: info['name'].replace('_', ' ').title()
    for pid, info in EMOTION_PROFILES.items()
}


EMOTION_DISPLAY_COLORS = {}
for pid, info in EMOTION_COLOR_PROFILES.items():
    base = info['colors'][0]
    # Standard HSV: H in [0, 360], S and V in [0, 255]
    h = base['h'] % 360
    s = min(max(base['s'], 0), 255) / 255.0
    v = min(max(base['v'], 0), 255) / 255.0

    # Pure Python HSV to RGB conversion
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    # Scale back to 0-255 integers
    EMOTION_DISPLAY_COLORS[pid] = (
        int((r + m) * 255),
        int((g + m) * 255),
        int((b + m) * 255)
    )


# 26-D feature order — must match FEATURE_COLS the scaler/model were fit on
FEATURE_COLS = [
    'light_raw', 'light_brightness', 'light_trend', 'light_variance',
    'light_is_daylight', 'light_flicker_freq',
    'sound_raw', 'sound_energy', 'sound_speech_rate', 'sound_continuity',
    'sound_spike', 'sound_human_presence',
    'touch_irq', 'touch_count', 'touch_freq', 'touch_intent',
    'cam_top_count',
    'cam_top1_h', 'cam_top1_s', 'cam_top1_v',
    'cam_top2_s', 'cam_top2_v',
    'cam_top3_h', 'cam_top3_s', 'cam_top3_v',
]
# touch_pattern is a string in the CSV ("random"/"rhythmic") -> encoded
# and appended as the 17th column (index 16), matching training order.
assert len(FEATURE_COLS) + 1 == INPUT_DIM, "feature order mismatch"


# ---------------------------------------------------------------------------
# POSIX message queue via ctypes + librt  (no posix_ipc needed)
# ---------------------------------------------------------------------------
class MQSendError(Exception):
    """
    Custom exception raised when the POSIX message queue cannot be opened
    or when sending fails unrecoverably.
    """
    pass


class InferQueue:
    """
    Minimal mq_open()/mq_send() wrapper using librt directly.

    Provides a simple interface to open a POSIX message queue for writing
    and send byte payloads without requiring the posix_ipc package.

    Attributes:
        name (str): Name of the POSIX message queue (e.g., "/sensor_box_infer").
        fd (int): File descriptor of the opened queue, -1 if closed.
        librt (ctypes.CDLL): Loaded librt shared library handle.
    """

    O_WRONLY = 1

    def __init__(self, name):
        """
        Initialize the InferQueue object.

        Attempts to load librt (librt.so.1, librt.so, or libc.so.6) and
        sets up ctypes bindings for mq_open, mq_send, and mq_close.

        Args:
            name (str): Name of the POSIX message queue (must start with '/').

        Raises:
            MQSendError: If no suitable librt library can be loaded.
        """
        self.name = name
        self.fd = -1
        self.librt = None
        for lib in ('librt.so.1', 'librt.so', 'libc.so.6'):
            try:
                self.librt = ctypes.CDLL(lib, use_errno=True)
                break
            except OSError:
                continue
        if self.librt is None:
            raise MQSendError("cannot load librt")

        self.librt.mq_open.restype = ctypes.c_int
        self.librt.mq_open.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.librt.mq_send.restype = ctypes.c_int
        self.librt.mq_send.argtypes = [ctypes.c_int, ctypes.c_char_p,
                                       ctypes.c_size_t, ctypes.c_uint]
        self.librt.mq_close.argtypes = [ctypes.c_int]

    def open(self):
        """
        Open the POSIX message queue for write-only access.

        Returns:
            bool: True if the queue is now available for writing (either
                  already open or successfully opened), False otherwise.
        """
        if self.fd >= 0:
            return True
        fd = self.librt.mq_open(self.name.encode(), self.O_WRONLY)
        if fd < 0:
            self.fd = -1
            return False
        self.fd = fd
        return True

    def send(self, payload: bytes):
        """
        Send a byte payload to the POSIX message queue.

        If the queue handle is stale (e.g., C program restarted), it will
        attempt to close and reopen the queue once before giving up.

        Args:
            payload (bytes): The data to send (typically an emotion label string).

        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if self.fd < 0 and not self.open():
            return False
        r = self.librt.mq_send(self.fd, payload, len(payload), 0)
        if r != 0:
            # stale handle (C restarted / queue unlinked) -> drop and retry once
            self.librt.mq_close(self.fd)
            self.fd = -1
            if self.open():
                r = self.librt.mq_send(self.fd, payload, len(payload), 0)
        return r == 0

    def close(self):
        """
        Close the POSIX message queue if currently open.
        """
        if self.fd >= 0:
            self.librt.mq_close(self.fd)
            self.fd = -1

    def status(self):
        """
        Return a human-readable connection status string.

        Returns:
            str: "connected" if the queue is open or can be opened,
                 "not available" otherwise.
        """
        return "connected" if (self.fd >= 0 or self.open()) else "not available"


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
def _num(v, default=0.0):
    """
    Safely convert a value to float, returning a default on failure.

    Args:
        v: Input value (any type convertible to float).
        default (float): Value to return if conversion fails or NaN.

    Returns:
        float: Numeric representation of v, or default.
    """
    try:
        if v is None:
            return default
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def build_features(row):
    """
    Build a 26-D feature vector from a single CSV row dictionary.

    The feature order matches FEATURE_COLS plus the encoded touch_pattern
    inserted at index 16 (after touch_intent). All values are converted to
    float32 and NaN's are replaced with 0.0.

    Args:
        row (dict): A dictionary representing one row of sensor_box.csv,
                    with keys corresponding to FEATURE_COLS plus 'touch_pattern'.

    Returns:
        np.ndarray: A 1-D array of shape (26,) with dtype float32.
    """
    vals = [_num(row.get(c)) for c in FEATURE_COLS]

    # touch_pattern: CSV keeps the string; training used an encoded value
    pat = str(row.get('touch_pattern', 'random')).strip().strip('"').lower()
    pat_enc = 0.0 if pat == 'random' else 1.0

    # insert pattern_enc after touch_intent -> position 16
    vals = vals[:16] + [pat_enc] + vals[16:]

    vec = np.asarray(vals, dtype=np.float64)
    return np.nan_to_num(vec, nan=0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Terminal input (raw mode, keeps ONLCR so output stays flush-left)
# ---------------------------------------------------------------------------
class TerminalInputHandler:
    """
    Handles non-blocking keyboard input in raw terminal mode.

    Runs a background daemon thread that reads single keystrokes and stores
    the latest command (lowercased) for retrieval by the main loop.

    Attributes:
        command (str or None): Most recent character read.
        lock (threading.Lock): Protects concurrent access to command.
        running (bool): Flag to control the reader thread.
        thread (threading.Thread): Daemon thread reading stdin.
    """

    def __init__(self):
        """
        Initialize the handler and start the background reader thread.
        """
        self.command = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._read_stdin, daemon=True)
        self.thread.start()

    def _read_stdin(self):
        """
        Background thread method: reads single characters from stdin in raw mode.
        Keeps ONLCR flag to preserve proper line endings on output.
        Stores each character (lowercased) into self.command.
        """
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            new = termios.tcgetattr(fd)
            new[1] |= termios.ONLCR          # keep \n -> \r\n
            new[3] |= termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, new)
            while self.running:
                if select.select([sys.stdin], [], [], 0.08)[0]:
                    ch = sys.stdin.read(1)
                    with self.lock:
                        self.command = ch.lower()
        except Exception:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def get_command(self):
        """
        Atomically retrieve and clear the most recent keyboard command.

        Returns:
            str or None: The last pressed key (lowercased), or None if none.
        """
        with self.lock:
            c, self.command = self.command, None
            return c

    def stop(self):
        """
        Signal the reader thread to exit.
        """
        self.running = False


def print_login_info(queue_status, csv_exists, csv_rows):
    """
    Print a formatted startup banner showing configuration, status, and all
    emotion categories for the "Sea, Sense, and Melody" project.

    Args:
        queue_status (str): Connection status of the message queue.
        csv_exists (bool): Whether the CSV file was found.
        csv_rows (int): Number of data rows in the CSV (excluding header).
    """
    print()
    print('=' * 82)
    print('Sea, Sense, and Melody — IoT Sensor Development')
    print('Real-time Emotion Classification from Multi-Modal Sensors')
    print('=' * 82)
    print()
    print('  Author:       KUANG, Haozhe')
    print('  Affiliation:  HKUST')
    print('  Date:         {}'.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print('  Python:       {}'.format(sys.version.split()[0]))
    print()
    print('  CSV file:     {}'.format(CONFIG['csv_path']))
    print('                {}'.format("found, {} rows".format(csv_rows) if csv_exists else "NOT FOUND"))
    print('  Model dim:    {}   Classes: {}   Window: {}'.format(INPUT_DIM, NUM_CLASSES, WINDOW_SIZE))
    print('  Send queue:   {}  [{}]'.format(MQ_NAME, queue_status))
    print()
    print('  Controls: r = reset buffer, q = quit')
    print()
    print('  ── Emotion Categories ────────────────────────────────')
    for pid in range(NUM_CLASSES):
        label = EMOTION_LABELS.get(pid, 'Unknown')
        print('    [{:2d}] {}'.format(pid, label))
    print('  ──────────────────────────────────────────────────────')
    print()
    print('=' * 83)
    print()


class EmotionClassifier:
    """
    Main inference engine that polls the CSV, maintains a sliding window,
    runs the GRU model, and sends predictions via the POSIX queue.

    Attributes:
        running (bool): Control flag for the main loop.
        feature_buffer (deque): Rolling window of up to 12 feature vectors.
        prediction_history (deque): Last N smoothed predictions.
        probability_history (deque): Confidence values corresponding to predictions.
        current_prediction (int): Latest smoothed class ID (-1 if none).
        current_confidence (float): Average confidence of smoothed predictions.
        _last_ts (str): Timestamp of the last processed CSV row.
        _sent_count (int): Count of successful messages sent.
        input_handler (TerminalInputHandler): For keyboard commands.
        device (torch.device): CPU or CUDA device.
        model (nn.Module): Loaded GRU model in eval mode.
        scaler (StandardScaler): Fitted scaler for feature normalization.
    """

    def __init__(self):
        """
        Initialize the classifier: set up buffers, terminal input, and load
        model/scaler artifacts.
        """
        self.running = True
        self.feature_buffer = deque(maxlen=CONFIG['window_size'])
        self.prediction_history = deque(maxlen=CONFIG['prediction_smoothing'])
        self.probability_history = deque(maxlen=CONFIG['prediction_smoothing'])
        self.current_prediction = -1
        self.current_confidence = 0.0
        self._last_ts = None
        self._sent_count = 0

        self.input_handler = TerminalInputHandler()
        self._load_artifacts()

    def _load_artifacts(self):
        """
        Load the pre-trained model and StandardScaler from disk.

        Checks existence of both files, loads them onto the appropriate device,
        and validates that the scaler's feature count matches INPUT_DIM.

        Raises:
            SystemExit: If any artifact file is missing or dimensionality mismatches.
        """
        for p in (CONFIG['model_path'], CONFIG['scaler_path']):
            if not os.path.exists(p):
                sys.exit(f'[FATAL] missing: {p}')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = load_model(CONFIG['model_path'], self.device)
        self.model.eval()
        with open(CONFIG['scaler_path'], 'rb') as f:
            self.scaler = pickle.load(f)

        n_feat = getattr(self.scaler, 'n_features_in_', None)
        if n_feat is not None and n_feat != INPUT_DIM:
            sys.exit(f'[FATAL] scaler expects {n_feat} features, model uses {INPUT_DIM}')

    def _read_latest_row(self):
        """
        Read the most recent row from the CSV file.

        Returns:
            dict or None: The last row as a dictionary, or None if the file
                          is empty, missing, or inaccessible.
        """
        try:
            df = pd.read_csv(CONFIG['csv_path'])
            return df.iloc[-1].to_dict() if len(df) else None
        except (FileNotFoundError, pd.errors.EmptyDataError, PermissionError):
            return None

    def _run_inference(self):
        """
        Perform inference on the current feature buffer.

        Stacks the buffered feature vectors into a (12, 26) tensor, normalizes
        with the scaler, feeds through the GRU model, applies softmax, and
        records the predicted class and confidence into the smoothing histories.

        Returns:
            bool: True if enough predictions have been accumulated to produce
                  a smoothed result (i.e., history length equals smoothing window),
                  False otherwise.
        """
        seq = np.stack(list(self.feature_buffer), axis=0)          # (12, 26)
        flat = seq.reshape(-1, INPUT_DIM)
        norm = self.scaler.transform(flat).reshape(1, WINDOW_SIZE, INPUT_DIM)
        x = torch.tensor(norm, dtype=torch.float32).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)
            conf, pred = torch.max(probs, dim=1)
        self.prediction_history.append(pred.item())
        self.probability_history.append(conf.item())

        if len(self.prediction_history) == CONFIG['prediction_smoothing']:
            self.current_prediction = max(set(self.prediction_history),
                                          key=self.prediction_history.count)
            self.current_confidence = float(np.mean(self.probability_history))
            return True
        return False

    def handle_terminal_commands(self):
        """
        Check for keyboard input and execute commands:
            'q' : Stop the main loop.
            'r' : Reset all buffers and counters.
        """
        cmd = self.input_handler.get_command()
        if cmd == 'q':
            self.running = False
        elif cmd == 'r':
            self.feature_buffer.clear()
            self.prediction_history.clear()
            self.probability_history.clear()
            self.current_prediction = -1
            self.current_confidence = 0.0
            self._sent_count = 0
            print('\n[INFO] Buffer reset.')
    def createQueue(self):
        try:
            self.queue = InferQueue(MQ_NAME)
            self.q_status = self.queue.status()
        except MQSendError as e:
            print(f'[FATAL] message queue unavailable: {e}')
            sys.exit(1)
    def get_current_state(self) -> dict:
        """Return current prediction, confidence, probabilities, and color in RGB."""
        if self.current_prediction in EMOTION_DISPLAY_COLORS:
            bgr = EMOTION_DISPLAY_COLORS[self.current_prediction]
            rgb = (bgr[2], bgr[1], bgr[0])  # Convert BGR to RGB
        else:
            rgb = (0, 0, 0)  # Default fallback if no valid prediction yet

        return {
            'prediction': self.current_prediction,
            'confidence': self.current_confidence,
            'color': rgb
        }

    def run(self, queue):
        """
        Main inference loop: poll CSV, fill buffer, run inference, send label.

        Args:
            queue (InferQueue): An initialized InferQueue instance for sending
                                emotion labels to the C process.
        """
        try:
            while self.running:
                self.handle_terminal_commands()
                if not self.running:
                    break

                row = self._read_latest_row()
                if row is None:
                    print('\rWaiting for CSV...   ', end='', flush=True)
                    time.sleep(CONFIG['poll_interval'])
                    continue

                ts = str(row.get('ts', ''))
                if ts == self._last_ts:
                    time.sleep(CONFIG['poll_interval'])
                    continue
                self._last_ts = ts

                self.feature_buffer.append(build_features(row))
                n = len(self.feature_buffer)

                if n < CONFIG['window_size']:
                    print(f'\rfilling window {n}/{CONFIG["window_size"]}  '
                          f'ts={ts}   ', end='', flush=True)
                    time.sleep(CONFIG['poll_interval'])
                    continue

                ready = self._run_inference()

                if not ready:
                    print(f'\rsmoothing {len(self.prediction_history)}/'
                          f'{CONFIG["prediction_smoothing"]}   ',
                          end='', flush=True)
                else:
                    # Get the emotion label string
                    label = EMOTION_LABELS.get(self.current_prediction, 'Unknown')
                    # Send as plain UTF-8 string (no binary struct)
                    payload = label.encode('utf-8')
                    ok = queue.send(payload)
                    if ok:
                        self._sent_count += 1
                    state = 'sent to C' if ok else 'queue NOT ready (start sensor_box)'
                    print(f'\r[{ts}] Emotion: {label} '
                          f'[id={self.current_prediction}] '
                          f'({self.current_confidence:.0%})  -> {state}'
                          f'   (sent {self._sent_count})   ',
                          end='', flush=True)

                time.sleep(CONFIG['poll_interval'])
        except KeyboardInterrupt:
            pass
        finally:
            self.input_handler.stop()
            queue.close()
            print('\n[INFO] Shutdown complete.')


def main():
    """
    Entry point: check CSV existence, initialize the InferQueue, print login
    info, and start the EmotionClassifier loop.
    """
    csv_exists = os.path.exists(CONFIG['csv_path'])
    csv_rows = 0
    if csv_exists:
        try:
            csv_rows = max(0, sum(1 for _ in open(CONFIG['csv_path'])) - 1)
        except OSError:
            csv_rows = 0

    try:
        queue = InferQueue(MQ_NAME)
        q_status = queue.status()
    except MQSendError as e:
        print(f'[FATAL] message queue unavailable: {e}')
        sys.exit(1)

    print_login_info(q_status, csv_exists, csv_rows)

    if q_status != 'connected':
        print('[WARN] /sensor_box_infer not found -- start the C program first:\n'
              '       cd "~/Desktop/UROP 3200/sensor_box" && sudo ./sensor_box\n')

    EmotionClassifier().run(queue)


if __name__ == '__main__':
    main()