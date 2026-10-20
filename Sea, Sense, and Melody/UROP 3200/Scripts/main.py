import webbrowser
import time

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
from ..ai_model.hsv_emotion_classifier.camera_infer import *


#Create queue for sensor data to prevent dropping of data 
message_queue = queue.Queue()



BASE_DIR = Path(__file__).parent.parent
HTML_FILE = BASE_DIR  / "3js" / "3jsTest" / "index5.html"

JSONL_FILE_PATH = BASE_DIR / "sensor_box" / "sensor_box.jsonl"

# Initiaise the emotion classifier app and run it
camera_app = EmotionClassifier()
camera_app.createQueue()

#Class for managing websocket connection
class ConnectionManager:
    #Create list of clients/websites connected to python program
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    #Asynchronously connect clients and add to websocket connectons 
    async def connect(self, socket: WebSocket):
        await socket.accept()
        self.active_connections.append(socket)

    #remove client from websocket connections
    def disconnect(self, socket: WebSocket):
        if socket in self.active_connections:
            self.active_connections.remove(socket)

    #Send information to clients via json
    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

#Intiialise connection manager
manager = ConnectionManager()

#run every frame of the website
async def game_loop():

    while True:

        #Get inference from camera app
        camera_data = camera_app.get_current_state()
        #delay to allow for processing time
        await asyncio.sleep(0.05)

        #intialise sensor data to 0
        current_data = (0,0,0)
        try:
            #attempt to retrieve message data from queue, returns exception if empty
            current_data = message_queue.get_nowait()
        except queue.Empty:
            pass
   
        chosen_color = camera_data["color"]
        
        await manager.broadcast({"type": "SENSOR_DATA",
                                  "sound_energy": current_data[0], 
                                  "brightness": current_data[1],
                                  "touch_frequency" : current_data[2],
                                  "color": chosen_color, 
                                  "prediction": camera_data['prediction'], 
                                  "confidence": camera_data['confidence']})



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

#Automatically open website 
def open_browser():
  # Wait a short moment for the server to start listening
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:8000/static/3jsTest/index.html")


def tail_sensor_log():
   # """Continuously reads new lines from the C program's JSONL output and pushes them to the queue."""
    print(f"[INFO] Starting sensor log reader for: {JSONL_FILE_PATH}")
    
    # Wait until the file is created by the C program
    while not os.path.exists(JSONL_FILE_PATH):
        time.sleep(0.5)
        
    with open(JSONL_FILE_PATH, "r") as f:
        # Move to the end of the file so we only read new live data
        f.seek(0, os.SEEK_END)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)  # Sleep briefly if no new line is ready
                continue
                
            try:
                data = json.loads(line.strip())
                
                # Extract the metrics you want to send to the web app
                # For example, using sound energy and light brightness
                sound_energy = data.get("sound", {}).get("energy", 0.0)
                light_brightness = data.get("light", {}).get("brightness", 0.0)
                touch_frequency = data.get("touch", {}).get("freq", 0.0)
                
                # Push a tuple into your message_queue (e.g., (humidity/sensor_val, ratio/modifier))
                message_queue.put((sound_energy, light_brightness, touch_frequency))
                
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"[ERROR] Error parsing sensor log line: {e}")

if __name__ == "__main__":
    #Run the camera inference app in a separate thread since it has its own loop and blocking calls
    camera_thread = threading.Thread(target=camera_app.run,args=(camera_app.queue,), daemon=True)
    camera_thread.start()

    #Log the sensor data in a separate thread
    sensor_thread = threading.Thread(target=tail_sensor_log, daemon=True)
    sensor_thread.start()

    #Create the server on local host to run the website
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)