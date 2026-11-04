import webbrowser
import time
import sys

import uvicorn
import asyncio
import random
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

import os
import json
import queue
import threading

parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# ----------------------------------------------------------------------
# DEBUG: Ensure the base directory resolves correctly.
# If your project structure is:
#   /home/.../UROP 3200/
#       ├── Scripts/
#       │   └── main.py
#       └── sensor_box/
#           └── sensor_box.jsonl
# then BASE_DIR should be /home/.../UROP 3200
#
# Using .resolve() avoids symlink or relative-path pitfalls.
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
print(f"[DEBUG] BASE_DIR = {BASE_DIR}")                     # Debug: verify path

# Create queue for sensor data to prevent dropping of data
message_queue = queue.Queue()

HTML_FILE = BASE_DIR / "3js" / "3jsTest" / "index5.html"

JSONL_FILE_PATH = BASE_DIR / "sensor_box" / "sensor_box.jsonl"
print(f"[DEBUG] JSONL_FILE_PATH = {JSONL_FILE_PATH}")       # Debug: verify path

# ======================== NEW: Shared emotion file ========================
SHARED_EMOTION_FILE = '/tmp/emotion_label.json'
current_emotion = {
    'prediction': -1,
    'confidence': 0.0,
    'color': (0, 0, 0),
    'label': 'Unknown'
}

def update_emotion_from_file():
    """Read the latest emotion data written by camera_infer.py."""
    global current_emotion
    if os.path.exists(SHARED_EMOTION_FILE):
        try:
            with open(SHARED_EMOTION_FILE, 'r') as f:
                data = json.load(f)
            current_emotion.update(data)
        except (json.JSONDecodeError, IOError):
            pass
# ========================================================================

# Class for managing websocket connection
class ConnectionManager:
    # Create list of clients/websites connected to python program
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    # Asynchronously connect clients and add to websocket connections
    async def connect(self, socket: WebSocket):
        await socket.accept()
        self.active_connections.append(socket)

    # Remove client from websocket connections
    def disconnect(self, socket: WebSocket):
        if socket in self.active_connections:
            self.active_connections.remove(socket)

    # Send information to clients via json
    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


# Initialise connection manager
manager = ConnectionManager()


# Run every frame of the website
async def game_loop():
    while True:
        # ==================== MODIFIED: Use shared file instead of camera_app ====================
        update_emotion_from_file()
        camera_data = current_emotion
        # =========================================================================================

        # Delay to allow for processing time
        await asyncio.sleep(0.05)

        # Initialise sensor data to 0
        current_data = (0, 0, 0)
        try:
            # Attempt to retrieve message data from queue, returns exception if empty
            current_data = message_queue.get_nowait()
        except queue.Empty:
            pass

        chosen_color = camera_data["color"]

        await manager.broadcast({
            "type": "SENSOR_DATA",
            "sound_energy": current_data[0],
            "brightness": current_data[1],
            "touch_frequency": current_data[2],
            "color": chosen_color,
            "prediction": camera_data['prediction'],
            "confidence": camera_data['confidence']
        })


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(game_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


@app.websocket("/ws/game")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    finally:
        manager.disconnect(ws)


# Automatically open website
def open_browser():
    # Wait a short moment for the server to start listening
    time.sleep(3.0)
    webbrowser.open("http://127.0.0.1:8000/static/3js/3jsTest/index5.html")


def tail_sensor_log():
    """
    Continuously reads new lines from the C program's JSONL output
    and pushes them to the queue.
    """
    print(f"[INFO] Starting sensor log reader for: {JSONL_FILE_PATH}")

    # ------------------------------------------------------------------
    # DEBUG: Check if the file exists right away.
    # If this prints False, the path is wrong or the C program hasn't
    # created the file yet (but you said it already exists).
    # ------------------------------------------------------------------
    print(f"[DEBUG] File exists initially: {os.path.exists(JSONL_FILE_PATH)}")

    # Wait until the file is created by the C program
    while not os.path.exists(JSONL_FILE_PATH):
        time.sleep(0.5)
        print("[DEBUG] Still waiting for file...")   # Debug: stuck here?

    print(f"[INFO] File found. Opening...")

    # ------------------------------------------------------------------
    # DEBUG: Open the file and print its size to confirm it's readable.
    # Also check if the file is owned by root but permissions allow read.
    # ------------------------------------------------------------------
    file_size = os.path.getsize(JSONL_FILE_PATH)
    print(f"[DEBUG] File size: {file_size} bytes")

    with open(JSONL_FILE_PATH, "r") as f:
        # Move to the end of the file so we only read new live data
        f.seek(0, os.SEEK_END)
        print(f"[DEBUG] Current file position after seek to end: {f.tell()}")

        line_count = 0
        json_error_count = 0  # 新增：记录 JSON 解析错误次数

        while True:
            line = f.readline()
            if not line:
                # No new line available; sleep briefly before retrying
                time.sleep(0.1)
                continue

            stripped_line = line.strip()
            # Skip empty lines immediately
            if not stripped_line:
                continue

            line_count += 1
            # ------------------------------------------------------------------
            # DEBUG: Print every raw line (first few lines to avoid flooding).
            # Comment out after confirming data arrives.
            # ------------------------------------------------------------------
            if line_count <= 5:
                print(f"[DEBUG] Raw line #{line_count}: {repr(stripped_line[:120])}...")

            try:
                data = json.loads(stripped_line)
                # ------------------------------------------------------------------
                # DEBUG: Print the parsed dictionary to see its structure.
                # This helps verify that keys like "sound", "light", "touch" exist.
                # ------------------------------------------------------------------
                print(f"[DEBUG] Parsed JSON: {data}")

                # Extract the metrics you want to send to the web app
                sound_energy = data.get("sound", {}).get("energy", 0.0)
                light_brightness = data.get("light", {}).get("brightness", 0.0)
                touch_frequency = data.get("touch", {}).get("freq", 0.0)

                # ------------------------------------------------------------------
                # DEBUG: Print extracted values to see if they are non-zero.
                # If they are all zero, either the JSON keys don't match or
                # the C program writes zeros.
                # ------------------------------------------------------------------
                print(f"[DEBUG] Extracted -> sound_energy={sound_energy}, "
                      f"brightness={light_brightness}, touch_frequency={touch_frequency}")

                # Push a tuple into your message_queue
                message_queue.put((sound_energy, light_brightness, touch_frequency))

            except json.JSONDecodeError as e:
                # ========== 修改点：降低日志级别并限制打印次数 ==========
                json_error_count += 1
                if json_error_count <= 5:
                    print(f"[WARN] JSON decode error #{json_error_count}: {e}")
                    print(f"[WARN] Offending line (first 200 chars): {repr(stripped_line[:200])}")
                continue
            except Exception as e:
                print(f"[ERROR] Unexpected error parsing sensor log line: {e}")
                continue


if __name__ == "__main__":
    # ==================== REMOVED: camera_app initialization and thread ====================
    # camera_app = EmotionClassifier()
    # camera_app.createQueue()
    # camera_thread = threading.Thread(
    #     target=camera_app.run, args=(camera_app.queue,), daemon=True
    # )
    # camera_thread.start()
    # =======================================================================================

    # Log the sensor data in a separate thread
    sensor_thread = threading.Thread(target=tail_sensor_log, daemon=True)
    sensor_thread.start()

    # Create the server on localhost to run the website
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    open_browser()