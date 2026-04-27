# -*- coding: utf-8 -*-
"""
OpenCV 颜色空间转换与颜色物体追踪
适用于 Thonny IDE 运行版本
"""

# ============================================================
# 1. 颜色空间转换 - 查看所有可用的颜色转换标志
# ============================================================
import cv2 

# 获取所有以'COLOR_'开头的属性，这些是OpenCV支持的颜色转换方式
flags = [i for i in dir(cv2) if i.startswith('COLOR_')]
print(flags)

# ============================================================
# 1.1 把BGR转换为HSV颜色空间
# ============================================================
import sys
import numpy as np
import cv2

# 获取用户输入的BGR值
print("Please enter blue:")
blue = int(input())
print("Please enter green:")
green = int(input())
print("Please enter red:")
red = input()
red = int(red)

# 创建BGR颜色数组，注意OpenCV使用BGR格式而非RGB
# np.uint8确保数据类型为8位无符号整数（0-255范围）
color = np.uint8([[[blue, green, red]]])

# cv2.cvtColor() - OpenCV颜色空间转换函数
# COLOR_BGR2HSV 表示从BGR颜色空间转换到HSV颜色空间
# HSV颜色空间更适合颜色检测，因为色相(Hue)分离出来便于设定范围
hsv_color = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)

# 提取色相(Hue)值，用于后续设置颜色检测范围
hue = hsv_color[0][0][0]

# 输出颜色检测的下限和上限范围
# 色相范围通常设置为 hue±10，饱和度和明度设为100-255
print("Lower bound is :")
print("[" + str(hue-10) + ", 100, 100]\n")

print("Upper bound is :")
print("[" + str(hue + 10) + ", 255, 255]")


# ============================================================
# 1.2 OpenCV颜色检测 - 读取图片并进行颜色过滤
# ============================================================
import cv2
import numpy as np

# 定义图像编码函数，将numpy数组转换为JPEG格式字节流
def bgr8_to_jpeg(value, quality=75):
    """
    将BGR格式的图像数组编码为JPEG格式的字节数据
    
    参数:
        value: numpy数组，BGR格式的图像
        quality: JPEG压缩质量，范围1-100，默认75
    
    返回:
        bytes: JPEG编码后的字节数据
    """
    return bytes(cv2.imencode('.jpg', value)[1])

# 读取图像文件
# cv2.imread() - 读取图像文件
# 参数1: 文件路径
# 参数2: 读取模式，1表示彩色模式(BGR)，0表示灰度模式，-1表示包含alpha通道
img = cv2.imread('./images/makerobo.jpg', 1)

# 检查图像是否成功加载
if img is None:
    print("Error: Could not load image './images/makerobo.jpg'")
    print("Please make sure the image file exists.")
else:
    # cv2.resize() - 调整图像大小
    # (0,0)表示自动计算新尺寸
    # fx=0.2, fy=0.2 表示宽高都缩小为原来的20%
    img = cv2.resize(img, (0, 0), fx=0.2, fy=0.2)
    
    # cv2.cvtColor() - 颜色空间转换
    # 将BGR图像转换为HSV图像，便于进行颜色检测
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 定义要检测的颜色范围（这里检测的是绿色）
    # 下限: [H-10, 100, 100] 色相略低，饱和度和明度较低
    # 上限: [H+10, 255, 255] 色相略高，饱和度和明度较高
    lower_range = np.array([24, 100, 100], dtype=np.uint8) # 给出上下限，相当于直接说明想要留下什么颜色
    upper_range = np.array([44, 255, 255], dtype=np.uint8)

    # cv2.inRange() - 颜色阈值分割函数
    # 将图像中在指定范围内的像素设为255（白色），范围外的设为0（黑色）
    # 生成一个二值化的掩码图像
    mask = cv2.inRange(hsv, lower_range, upper_range) # 将指定的颜色换成白色，剩下全部变成黑色

    # 使用OpenCV窗口显示原图和掩码图
    # cv2.imshow() - 在指定窗口中显示图像
    cv2.imshow('Original Image', img)
    cv2.imshow('Mask', mask)
    
    # cv2.waitKey() - 等待键盘输入
    # 参数0表示无限等待，直到有按键按下
    # 按任意键关闭窗口
    print("Press any key to close windows...")
    cv2.waitKey(0)
    
    # cv2.destroyAllWindows() - 关闭所有OpenCV创建的窗口
    cv2.destroyAllWindows()

# ============================================================
# 2. OpenCV 中颜色物体追踪 - 实时摄像头追踪
# ============================================================
from collections import deque
import numpy as np
import argparse
import imutils
import cv2

# 线程控制相关函数
import threading
import ctypes
import inspect

def _async_raise(tid, exctype):
    """
    异步抛出异常到指定线程
    
    参数:
        tid: 线程ID
        exctype: 要抛出的异常类型
    """
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
    """
    停止指定线程
    
    参数:
        thread: 要停止的线程对象
    """
    _async_raise(thread.ident, SystemExit)
    
# 模拟命令行参数解析
# 在实际运行时可以通过命令行传入参数
args = {
    "video": None,      # 视频文件路径
    "buffer": 64        # 轨迹点缓冲区大小
}

# 定义要追踪的"黄色/绿色对象"的HSV颜色范围
# 这些数值是通过实验确定的，适用于检测特定颜色的物体（皮肤颜色）
# B G R
colorLower = np.array([50, 40, 50])
colorUpper = np.array([200, 160, 200])

# deque - 双端队列，用于存储历史轨迹点
# maxlen参数限制队列最大长度，自动丢弃最旧的元素
pts = deque(maxlen=args["buffer"])

# 尝试导入树莓派相机库
try:
    import libcamera
    from picamera2 import Picamera2
    use_picamera = True
except ImportError:
    print("Picamera2 not available, using webcam instead.")
    use_picamera = False

# ============================================================
# 初始化摄像头
# ============================================================
if use_picamera:
    # 初始化Picamera2
    picamera = Picamera2()
    config = picamera.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)},
        raw={"format": "SRGGB12", "size": (1920, 1080)}
    )
    config["transform"] = libcamera.Transform(hflip=0, vflip=1)
    picamera.configure(config)
    picamera.start()
    camera_source = "picamera"
else:
    # 使用普通USB摄像头作为备选
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera!")
        exit()
    camera_source = "webcam"

# ============================================================
# 颜色追踪主循环
# ============================================================
def Video_display():
    """
    视频显示和颜色追踪的主循环函数
    在独立线程中运行以实现实时处理
    """
    while True:
        # 捕获一帧图像
        if camera_source == "picamera":
            frame = picamera.capture_array()
        else:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame!")
                break
        
        # imutils.resize() - 调整帧大小
        # 保持宽高比的同时将宽度调整为600像素
        frame = imutils.resize(frame, width=600)
        
        # 将BGR图像转换为HSV颜色空间
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 创建颜色掩码
        mask = cv2.inRange(hsv, colorLower, colorUpper)
        
        # cv2.erode() - 腐蚀操作
        # 去除小的噪点，收缩前景区域
        mask = cv2.erode(mask, None, iterations=2)
        
        # cv2.dilate() - 膨胀操作
        # 恢复被腐蚀掉的主要区域，填充小洞
        mask = cv2.dilate(mask, None, iterations=2)

        # cv2.findContours() - 查找轮廓
        # 参数1: 二值图像（掩码）
        # 参数2: 检索模式，RETR_EXTERNAL只检测外轮廓
        # 参数3: 近似方法，CHAIN_APPROX_SIMPLE压缩水平、垂直、对角线段
        # 返回值: 图像、轮廓列表、层次结构
        cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
        
        # 初始化物体中心坐标
        center = None

        # 如果检测到轮廓
        if len(cnts) > 0:
            # max() - 找到面积最大的轮廓
            # key=cv2.contourArea 表示按面积比较
            c = max(cnts, key=cv2.contourArea)
            
            # cv2.minEnclosingCircle() - 获取最小外接圆
            # 返回圆心坐标和半径
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            
            # cv2.moments() - 计算图像矩
            # 用于计算物体的质心（重心）
            M = cv2.moments(c)
            
            # 计算质心坐标
            # m10/m00 和 m01/m00 分别是质心的x和y坐标
            if M["m00"] != 0:
                center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

            # 如果半径大于10像素，认为检测到了有效物体
            if radius > 10:
                # cv2.circle() - 绘制圆形
                # 参数: 图像、圆心、半径、颜色(BGR)、线宽(-1表示填充)
                cv2.circle(frame, (int(x), int(y)), int(radius), (0, 255, 255), 2)
                
                # 绘制质心点
                cv2.circle(frame, center, 5, (0, 0, 255), -1)

        # 将当前中心点添加到轨迹队列
        pts.appendleft(center)

        # 绘制运动轨迹
        # 遍历所有轨迹点，用线条连接相邻的点
        for i in range(1, len(pts)):
            # 跳过无效点（None）
            if pts[i - 1] is None or pts[i] is None:
                continue

            # 计算线条粗细，越老的轨迹点线条越细
            thickness = int(np.sqrt(args["buffer"] / float(i + 1)) * 2.5)
            
            # cv2.line() - 绘制直线
            # 参数: 图像、起点、终点、颜色、线宽
            cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)

        # 显示处理后的帧
        cv2.imshow('Frame', frame)
        cv2.imshow('Mask', mask)
        
        # 检测按键，按'q'退出循环
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    # 释放资源
    if camera_source == "picamera":
        picamera.stop()
    else:
        cap.release()
    cv2.destroyAllWindows()

# ============================================================
# 启动追踪线程
# ============================================================
print("Starting color tracking...")
print("Press 'q' to quit.")

t = threading.Thread(target=Video_display)
t.setDaemon(True)  # 设置为守护线程，主程序结束时自动终止
t.start()

# 等待线程结束（实际上在线程内部通过按键退出）
try:
    t.join()
except KeyboardInterrupt:
    print("\nStopping...")
    stop_thread(t)