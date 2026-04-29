# 导入必要的库
import cv2
import numpy as np
import time
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
# 假设utils模块中有visualize函数，用于可视化检测结果
import utils
from picamera2 import Picamera2
import threading
import ctypes
import inspect

# 全局变量用于计算FPS
COUNTER, FPS = 0, 0
START_TIME = time.time()

def run():
    """
    主函数：捕获摄像头视频流，运行对象检测，并显示结果。
    """
    # --- 初始化摄像头部分 ---
    picamera = Picamera2()
    # 创建预览配置：主流格式为XRGB8888，分辨率1280x720；原始流格式为SRGGB12，分辨率1920x1080
    config = picamera.create_preview_configuration(main={"format": 'XRGB8888', "size": (1280, 720)},
                                                   raw={"format": "SRGGB12", "size": (1920, 1080)})
    # 使用字典替代 libcamera.Transform，设置图像变换：水平不翻转，垂直翻转
    config["transform"] = {"hflip": 0, "vflip": 1}
    picamera.configure(config)
    picamera.start()  # 开启摄像头

    # --- 可视化参数设置 ---
    row_size = 50  # 像素，用于显示FPS文本的行高
    left_margin = 24  # 像素，文本左边距
    text_color = (0, 0, 0)  # 黑色
    font_size = 1
    font_thickness = 1
    fps_avg_frame_count = 10  # 计算FPS的平均帧数

    detection_frame = None
    detection_result_list = []

    def save_result(result: vision.ObjectDetectorResult, unused_output_image: mp.Image, timestamp_ms: int):
        """
        回调函数：处理检测结果，计算FPS。
        """
        global FPS, COUNTER, START_TIME
        # 计算FPS：每处理fps_avg_frame_count帧后更新一次FPS
        if COUNTER % fps_avg_frame_count == 0:
            FPS = fps_avg_frame_count / (time.time() - START_TIME)
            START_TIME = time.time()

        detection_result_list.append(result)
        COUNTER += 1

    # --- 初始化对象检测模型 ---
    base_options = python.BaseOptions(model_asset_path='efficientdet_lite0.tflite')
    options = vision.ObjectDetectorOptions(base_options=base_options,
                                         running_mode=vision.RunningMode.LIVE_STREAM,
                                         max_results=5, score_threshold=0.3,
                                         result_callback=save_result)
    detector = vision.ObjectDetector.create_from_options(options)

    # --- 主循环：连续捕获图像并运行推理 ---
    while True:
        # 捕获一帧图像
        frame = picamera.capture_array()
        # 水平翻转图像，以适应摄像头镜像（通常前置摄像头需要）
        image = cv2.flip(frame, 1)

        # --- 图像格式转换：从BGR转换为RGB，因为MediaPipe模型需要RGB格式 ---
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        # 异步运行对象检测
        detector.detect_async(mp_image, time.time_ns() // 1_000_000)

        # --- 在图像上显示FPS ---
        fps_text = 'FPS = {:.1f}'.format(FPS)
        text_location = (left_margin, row_size)
        current_frame = image
        cv2.putText(current_frame, fps_text, text_location, cv2.FONT_HERSHEY_DUPLEX,
                    font_size, text_color, font_thickness, cv2.LINE_AA)

        # 如果有检测结果，调用visualize函数可视化并显示
        if detection_result_list:
            current_frame = visualize(current_frame, detection_result_list[0])
            detection_frame = current_frame
            detection_result_list.clear()

        # --- 显示检测结果帧 ---
        if detection_frame is not None:
            cv2.imshow('Object Detection', detection_frame)

        # 检查按键，如果按下'q'则退出循环
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # --- 清理资源 ---
    detector.close()
    picamera.stop()
    cv2.destroyAllWindows()

# --- 线程控制函数（用于强制停止线程） ---
def _async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

# --- 主程序入口 ---
if __name__ == "__main__":
    # 创建并启动线程，运行run函数
    t = threading.Thread(target=run)
    t.setDaemon(True)  # 设置为守护线程，主程序退出时自动结束
    t.start()
    # 我已經裝好了

    # 等待线程结束（当run函数中按下'q'退出循环时，线程自然结束）
    t.join()