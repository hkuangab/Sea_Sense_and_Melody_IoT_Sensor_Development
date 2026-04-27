"""
行人检测与眼睛检测程序
适用于 Thonny IDE 运行版本
功能：使用 Haar 级联分类器检测行人的身体，并在图像上绘制矩形框
"""

# 载入必要的库
import cv2
import numpy as np

# 创建我们的身体分类器
# 使用OpenCV的Haar级联分类器来检测人体
body_classifier = cv2.CascadeClassifier('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/haarcascade_fullbody.xml')

# 为视频文件启动视频捕获
# 从指定路径读取视频文件
# 如果视频文件不存在，则尝试打开摄像头
if not cap.isOpened():
    print("Failed to open video file, trying to open camera...")
    cap = cv2.VideoCapture(0)

# 线程函数操作库
import threading  # 用于创建和管理多线程
import ctypes
import inspect

# 使用线程的主要原因：
#
# 1. 防止视频处理阻塞主程序
#    - 视频读取、人体检测、图像显示都是耗时操作
#    - 如果放在主线程中顺序执行，程序会"卡住"，无法响应用户操作
#    - 使用单独的线程处理视频，主程序可以继续执行其他任务
#
# 2. 实现实时显示效果
#    - 视频需要连续不断地读取和处理每一帧
#    - 线程可以让这个过程在"后台"持续运行
#    - 用户可以看到流畅的视频画面，而不是等待处理完成
#
# 3. 提高程序响应性
#    - 主线程可以处理用户输入（如点击按钮、输入命令等）
#    - 视频处理线程独立运行，互不干扰
#    - 例如：用户可以随时按Enter键停止视频，而不需要等待当前帧处理完

# 线程结束代码
# 该函数用于强制终止指定ID的线程
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

# 停止指定线程的函数
# 通过调用_async_raise来引发SystemExit异常从而终止线程
def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

# 将BGR图像转换为JPEG格式
# 参数value: BGR格式的numpy数组
# 参数quality: JPEG压缩质量，范围1-100，默认75
# 返回值: JPEG格式的字节数据
def bgr8_to_jpeg(value, quality=75):
    return bytes(cv2.imencode('.jpg', value)[1])

# ============================================
# Haar级联分类器算法：这部分区分颜色空间转换和图像预处理
# ============================================

# 读取视频帧并进行灰度化处理
# 将彩色BGR图像转换为灰度图以简化处理
# gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# ============================================
# 这一部分是将灰度图输入到人体检测器中进行识别
# ============================================

# 使用人体分类器检测图像中的人体
# detectMultiScale参数说明：
# - scaleFactor=1.2: 每次图像尺寸减小的比例
# - minNeighbors=3: 每个候选矩形需要保留的最小邻居数
# bodies = body_classifier.detectMultiScale(gray, 1.2, 3)

# ============================================
# 这一部分是在检测到的人体周围绘制边界框
# ============================================

# 遍历所有检测到的人体区域并在原图上绘制矩形框
# for (x, y, w, h) in bodies:
#     cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)

# 详细解释坐标计算公式：
# 
# detectMultiScale函数返回的检测结果是一个元组列表，每个元组包含4个值：
# - x: 边界框左上角的水平坐标（距离图像左边缘的像素数）
# - y: 边界框左上角的垂直坐标（距离图像顶部的像素数）
# - w: 边界框的宽度（像素）
# - h: 边界框的高度（像素）
#
# cv2.rectangle函数绘制矩形时需要两个对角点的坐标：
# - 第一个点 (x, y): 矩形的左上角
# - 第二个点 (x + w, y + h): 矩形的右下角

# ============================================
# 这一部分是将处理后的帧显示在GUI控件中
# ============================================

# 将BGR图像编码为JPEG后更新到显示控件
# Pedestrians_imge.value = bgr8_to_jpeg(frame)

# 主视频显示函数
# 持续读取视频帧，进行人体检测，并在窗口中显示结果
def Video_display():
    while cap.isOpened():
        ret, frame = cap.read() # 读取第一帧

        if not ret: 
            print("No more frames to read or error reading frame")
            break
        
        # 调整视频帧大小，缩小为原来的一半
        frame = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_LINEAR)
        
        # 将BGR颜色空间转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 将灰度图传入人体分类器进行检测
        bodies = body_classifier.detectMultiScale(gray, 1.2, 3)
        
        # 提取所有检测到的目标边界框并在图像上绘制
        for (x, y, w, h) in bodies:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            print("Person detected at position: x={}, y={}, w={}, h={}".format(x, y, w, h))
            
        # 将处理后的图像转换为JPEG格式并显示
        print("Frame processed and displayed")
    
    # 释放视频资源
    cap.release()
    print("Video capture released")

# 创建并启动视频处理线程
t = threading.Thread(target=Video_display)
t.daemon = True
t.start()

# 等待用户输入后停止线程
input("Press Enter to stop the video processing...")

# 结束线程
# 调用stop_thread函数安全停止视频处理线程
stop_thread(t)
print("Thread stopped successfully")