# -*- coding: utf-8 -*-
"""
人脸检测与眼睛检测程序
适用于 Thonny IDE 运行版本
功能：使用 Haar 级联分类器检测人脸和眼睛，并在图像上绘制矩形框
"""

# ============================================================
# 1. 导入必要的库
# ============================================================
import numpy as np
import cv2

# ============================================================
# 2. 加载 Haar 级联分类器模型
# ============================================================
# cv2.CascadeClassifier() - 加载预训练的 Haar 特征分类器
# 参数：XML 模型文件的路径
# Haar 级联是一种基于机器学习的目标检测方法，通过提取图像的Haar-like特征来识别目标

# 这里加载了两个模型：人脸检测和眼睛检测
face_cascade = cv2.CascadeClassifier('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/haarcascade_eye.xml')

# ============================================================
# 3. 线程控制相关函数 
# ============================================================
import threading
import ctypes
import inspect

def _async_raise(tid, exctype):
    """
    异步向指定线程抛出异常
    
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

# ============================================================
# 4. 初始化树莓派摄像头 (Picamera2)
# ============================================================
import libcamera
from picamera2 import Picamera2

# 创建 Picamera2 实例
picamera = Picamera2()

# 创建预览配置
# main: 主图像流配置，RGB888 格式，分辨率 640x480
# raw: 原始图像流配置，SRGGB12 格式，分辨率 1920x1080
config = picamera.create_preview_configuration(
    main={"format": 'RGB888', "size": (640, 480)},
    raw={"format": "SRGGB12", "size": (1920, 1080)}
)

# 设置图像变换：水平翻转=0（不翻转），垂直翻转=1（翻转）
config["transform"] = libcamera.Transform(hflip=0, vflip=1)

# 应用配置到摄像头
picamera.configure(config)

# 启动摄像头，开始捕获图像
picamera.start()

# ============================================================
# 5. 图像编码函数（用于显示）
# ============================================================
def bgr8_to_jpeg(value, quality=75):
    """
    将 BGR 格式的图像数组编码为 JPEG 格式的字节数据
    
    参数:
        value: numpy数组，BGR格式的图像
        quality: JPEG压缩质量，范围1-100，默认75
    
    返回:
        bytes: JPEG编码后的字节数据
    """
    return bytes(cv2.imencode('.jpg', value)[0])

# ============================================================
# 6. 创建显示控件（使用 OpenCV 窗口替代 Jupyter 控件）
# ============================================================
# 由于移除了 Jupyter 依赖，这里改用 OpenCV 的原生窗口显示
print("Press 'q' to quit the program.")

# ============================================================
# 7. 视频显示与人脸检测主循环
# ============================================================
def Video_display():
    """
    视频捕获、人脸检测和显示的无限循环
    在独立线程中运行以实现实时处理
    
    本段代码使用 Haar 级联分类器进行人脸和眼睛检测
    
    【Haar 算法原理】
    1. Haar-like 特征：使用矩形区域计算像素差值
       - 白色区域：求和
       - 黑色区域：求负和
       - 特征值 = 白色区域和 - 黑色区域和
       
    2. 常用特征类型：
       - 边缘特征：检测水平/垂直边缘
       - 线特征：检测45°/135°线
       - 中心特征：检测中心亮点/暗点
       
    3. 积分图加速：
       - 预先计算积分图，使任意矩形区域的和可以在 O(1) 时间内计算
       - 积分图公式：ii(x,y) = sum of all pixels above and to the left of (x,y)
       
    4. AdaBoost 训练：
       - 从大量弱分类器中选择最有效的特征
       - 每个弱分类器只关注一个 Haar 特征
       - 强分类器 = 多个弱分类器的加权组合
       
    5. 级联结构：
       - 多级分类器串联
       - 前级快速排除非目标区域
       - 后级精细判断，提高准确率
       - 结构示意：
         [简单分类器1] -> [简单分类器2] -> ... -> [复杂分类器N]
              ↓                    ↓                        ↓
         快速排除90%        再排除9%                精确判断1%
    """
    while True:      
        # picamera.capture_array() - 从摄像头捕获一帧图像
        # 返回 numpy 数组，格式为 RGB
        frame = picamera.capture_array()
        
        # cv2.flip() - 图像翻转函数
        # 参数1: 输入图像
        # 参数2: 翻转方式
        #   - 0: 绕X轴垂直翻转
        #   - 1: 绕Y轴水平翻转（镜像效果，常用于自拍）
        #   - -1: 同时水平和垂直翻转
        img = cv2.flip(frame, 1)
        
        # cv2.cvtColor() - 颜色空间转换函数
        # 将 RGB 图像转换为灰度图像
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ============================================================
        # Haar 级联人脸检测核心函数
        # 通过计算图像中特定矩形区域内像素灰度值的差值，来捕捉目标的局部结构特征
        # ============================================================
        # face_cascade.detectMultiScale() - Haar 级联多尺度目标检测函数
        # 
        # 【算法流程】
        # 1. 图像金字塔：不断缩小图像，实现多尺度检测
        # 2. 滑动窗口：在不同位置和尺度上移动检测窗口
        # 3. 特征计算：在每个窗口位置计算 Haar 特征值
        # 4. 级联分类：用多个 AdaBoost 分类器依次判断
        # 5. 非极大值抑制：合并重叠的检测框
        #
        # 参数详解：detectMultiScale
        # ------------------------------------------------------------
        # 参数1: image (gray)
        #   - 输入图像，必须是单通道灰度图
        #   - 原因：Haar 特征基于像素强度计算，与颜色无关
        #
        # 参数2: scaleFactor (1.3)
        #   - 图像金字塔的缩放比例
        #   - 含义：每次图像缩小的倍数
        #   - 计算过程：
        #     原始图像 640x480
        #     第1次：640/1.3 ≈ 492x369
        #     第2次：492/1.3 ≈ 378x291
        #     第3次：378/1.3 ≈ 291x224
        #     ... 直到小于 minSize
        #   - 取值影响：
        #     - 较小值（1.05）：检测更精细，能检测更小的人脸
        #       但计算量大，速度慢
        #     - 较大值（1.5）：检测速度快，但可能漏检
        #       或无法检测较小的人脸
        #   - 经验值：1.1 ~ 1.4 之间
        #
        # 参数3: minNeighbors (5， KNN)
        #   - 每个候选矩形需要保留的最小邻居数
        #   - 原理：同一个目标可能被多次检测到
        #     通过"投票"机制确定最终检测结果
        #   - 计算过程：
        #     1. 检测到一个候选框
        #     2. 在周围搜索相似框
        #     3. 如果相似框数量 >= minNeighbors，则保留
        #     4. 否则认为是误检，丢弃
        #   - 取值影响：
        #     - 较小值（1-2）：误检多，容易出现假阳性 -> False Positive
        #     - 较大值（5-6）：误检少，但可能漏检
        #   - 经验值：3 ~ 6 之间
        #
        # 其他常用参数（未在此代码中使用）：
        # ------------------------------------------------------------
        # minSize: 最小检测目标尺寸
        #   - 例如 (30, 30) 表示小于30x30的区域不检测
        #   - 用于排除过小的噪声
        #
        # maxSize: 最大检测目标尺寸
        #   - 例如 (300, 300) 表示大于300x300的区域不检测
        #   - 用于排除过大的区域
        #
        # flags: 检测标志
        #   - cv2.CASCADE_SCALE_IMAGE: 默认值
        #   - 已废弃，新版本中忽略此参数
        #
        # 返回值: faces
        #   - 检测到的目标矩形列表
        #   - 每个元素为 (x, y, w, h)
        #     - x, y: 矩形左上角坐标
        #     - w, h: 矩形的宽度和高度
        #   - 如果未检测到，返回空元组 ()
        # ------------------------------------------------------------
        faces = face_cascade.detectMultiScale(
            gray,           # 输入灰度图像
            scaleFactor=1.15,  # 图像金字塔缩放比例
            minNeighbors=2   # 最小邻居数，用于过滤误检
        )
        
        # 遍历所有检测到的人脸
        for (x, y, w, h) in faces:
            # cv2.rectangle() - 在图像上绘制矩形
            # 参数详解：
            #   img: 要绘制的图像
            #   (x, y): 矩形左上角坐标
            #   (x+w, y+h): 矩形右下角坐标
            #   (255, 0, 0): 矩形颜色，BGR格式
            #     - 蓝色 = (255, 0, 0)
            #     - 绿色 = (0, 255, 0)
            #     - 红色 = (0, 0, 255)
            #   thickness: 线宽
            #     - 正数：线宽（像素）
            #     - -1：填充整个矩形
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
            
            # ============================================================
            # 提取感兴趣区域 (ROI - Region of Interest)
            # ============================================================
            # ROI 是图像中我们真正关心的部分
            # 在人脸区域内检测眼睛，可以：
            #   1. 减少计算量（只在人脸区域搜索）
            #   2. 提高准确率（避免在非人脸区域误检）
            #
            # 切片语法：image[y1:y2, x1:x2]
            #   - 第一个范围：行的范围（y 方向，从上到下）
            #   - 第二个范围：列的范围（x 方向，从左到右）
            #   - 注意：OpenCV 中坐标是 (x, y)，但数组索引是 [y, x]
            # ------------------------------------------------------------
            # 在灰度图中提取人脸区域，用于眼睛检测
            # 眼睛检测只需要形状信息，不需要颜色
            roi_gray = gray[y:y + h, x:x + w]
            
            # 在彩色图中提取人脸区域，用于绘制眼睛框
            # 需要彩色信息才能画出彩色的眼睛框
            roi_color = img[y:y + h, x:x + w]
            
            # 打印人脸中心坐标
            # 计算方式：
            #   center_x = x + w/2 （左上角x + 一半宽度）
            #   center_y = y + h/2 （左上角y + 一半高度）
            # 用途：可用于：
            #   - 机器人跟踪人脸
            #   - 计算头部姿态
            #   - 统计人脸位置分布
            print(int(x + w / 2), int(y + h / 2))
            
            # eye_cascade.detectMultiScale() - 在人脸区域内检测眼睛
            # 参数与人脸检测相同，但可以使用不同的参数值
            # 因为眼睛比人脸小，所以：
            #   - scaleFactor 可以稍大（1.1~1.2）
            #   - minNeighbors 可以稍小（2~3）
            # 这样可以提高对小目标的检测灵敏度
            eyes = eye_cascade.detectMultiScale(roi_gray)
            
            # 遍历所有检测到的眼睛
            for (ex, ey, ew, eh) in eyes:
                # 在彩色人脸区域上绘制眼睛的绿色矩形框
                # 注意坐标转换：
                #   - 眼睛在 roi_color 中的坐标是 (ex, ey)
                #   - 但 roi_color 是 img 的一个子区域
                #   - 所以实际在 img 中的坐标是 (x+ex, y+ey)
                # 这里直接对 roi_color 绘制，省去坐标转换
                cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)
        
        # 在窗口中显示处理后的图像
        # cv2.imshow() - 创建窗口并显示图像
        # 参数1: 窗口名称（字符串）
        # 参数2: 要显示的图像（numpy数组）
        # 注意：必须先创建窗口，再调用 waitKey
        cv2.imshow('Face Detection', img)
        
        # cv2.waitKey() - 等待键盘输入
        # 参数: 等待时间（毫秒）
        #   - 0: 无限等待，直到有按键
        #   - 1: 等待1毫秒，然后继续执行
        # 返回值: 按下的键的 ASCII 码
        #   - 如果期间没有按键，返回 -1
        # & 0xFF: 取低8位
        #   - 在某些系统上，waitKey 返回32位值
        #   - 0xFF 是 255，二进制为 11111111
        #   - 与运算确保只取低8位
        # ord('q'): 返回字符 'q' 的 ASCII 码（113）
        # 整体逻辑：
        #   - 如果按下了 'q' 键，退出循环
        #   - 否则继续下一帧
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 释放资源
    # 停止摄像头
    picamera.stop()
    
    # cv2.destroyAllWindows() - 关闭所有 OpenCV 创建的窗口
    # 注意：必须在循环结束后调用
    # 如果放在循环内，会导致窗口一闪而过
    cv2.destroyAllWindows()

# ============================================================
# 8. 启动检测线程
# ============================================================
# 创建线程，目标函数为 Video_display
t = threading.Thread(target=Video_display)

# setDaemon(True) - 设置为守护线程
# 当主程序退出时，守护线程会自动终止
t.setDaemon(True)

# start() - 启动线程
t.start()

# ============================================================
# 9. 等待用户输入以退出程序
# ============================================================
# 由于使用了守护线程，主程序会立即继续执行到这里
# 为了让程序持续运行直到用户手动中断，添加一个无限循环
try:
    while True:
        pass  # 空循环，保持主线程存活
except KeyboardInterrupt:
    # 捕获 Ctrl+C 中断信号
    print("\nProgram interrupted by user.")
    # 停止线程
    stop_thread(t)
    # 清理资源
    picamera.stop()
    cv2.destroyAllWindows()
    print("Program ended successfully.")