# ============================================================
# 树莓派5 AI智能视觉套件 - 摄像头与视频处理综合示例
# 运行环境：Thonny + 树莓派桌面环境（需接显示器）
# ============================================================

# -------------------------------
# 0. 统一导入所有需要用到的库
# -------------------------------
import cv2                          # OpenCV：图像处理、显示、视频读写的核心库
import numpy as np                   # NumPy：数组操作（OpenCV 底层依赖，用于矩阵运算）
import time                         # time：延时、计时（用于等待摄像头稳定）
import threading                     # threading：多线程（原代码中有线程逻辑，这里保留备用）
import ctypes                       # ctypes：底层线程操作（用于强制结束线程）
import inspect                       # inspect：获取线程信息（配合 ctypes 使用）
import libcamera                    # libcamera：树莓派新一代摄像头接口（取代旧的 raspistill）
from picamera2 import Picamera2      # Picamera2：控制 CSI 摄像头的高级封装（更易用）

# 【学习提示】
# 在 Python 中，import 语句通常放在文件最开头，这样代码结构清晰，便于管理依赖。


# -------------------------------
# 1. 公共函数：将 BGR 图像编码为 JPEG 字节
# -------------------------------
def bgr8_to_jpeg(value, quality=75):
    """
    将 OpenCV 的 BGR 图像（NumPy 数组）编码为 JPEG 格式的字节数据
    
    参数：
        value: BGR 图像（NumPy 数组，shape 为 [高度, 宽度, 3]）
        quality: JPEG 压缩质量，范围 0-100，默认 75（数值越高质量越好，文件越大）
    
    返回：
        JPEG 编码后的字节数据（可用于网络传输或保存为 .jpg 文件）
    """
    return bytes(cv2.imencode('.jpg', value, [int(cv2.IMWRITE_JPEG_QUALITY), quality])[1])


# 【学习提示】
# cv2.imencode() 会将图像编码为指定格式（这里是 .jpg），返回一个元组：(成功标志, 字节数据)
# 我们只需要字节数据部分，所以用 [1] 取出。


# -------------------------------
# 2. 摄像头实时预览（原代码中的"动态显示摄像头视频"）
# -------------------------------
def camera_preview():
    """
    功能：打开 CSI 摄像头，实时预览画面
    说明：这是最常用的功能，用于调试摄像头是否正常工作
    """
    # 创建 Picamera2 对象，用于控制 CSI 摄像头
    picamera = Picamera2()

    # 配置预览流参数：
    # - main：主预览流，RGB888 格式（OpenCV 兼容），分辨率 2000x2000
    # - raw：原始数据流，SRGGB12 格式（拜耳），分辨率 1920x1080
    # 【注意】main 分辨率设为 2000x2000 可能会导致性能下降，建议先用 640x480 测试
    config = picamera.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)},
        raw={"format": "SRGGB12", "size": (1920, 1080)}
    )

    # 设置图像变换：hflip=0 不水平翻转，vflip=1 垂直翻转
    # 如果摄像头装反了，可以调整这两个参数
    # 例如：hflip=1, vflip=1 表示同时水平和垂直翻转
    config["transform"] = libcamera.Transform(hflip=0, vflip=1)

    # 应用配置，让设置生效
    picamera.configure(config)

    # 启动摄像头，开始采集图像
    picamera.start()

    # 等待 2 秒，让自动曝光（AE）和自动白平衡（AWB）稳定
    # 如果不加延时，前几帧可能会过暗或过曝
    time.sleep(2)

    # 创建显示窗口，名称为 "Camera Preview"，允许手动调整大小
    cv2.namedWindow("Camera Preview", cv2.WINDOW_NORMAL)

    try:
        # 进入无限循环，持续捕获和显示图像
        while True:
            # 从摄像头捕获一帧图像（main 流，RGB888 格式）
            # 返回的是一个 NumPy 数组，形状为 (高度, 宽度, 3)
            frame = picamera.capture_array("main")

            # 在窗口中实时显示当前帧
            cv2.imshow("Camera Preview", frame)

            # 检测按键：
            # - waitKey(1)：等待 1 毫秒
            # - 0xFF == ord('q')：如果按下 'q' 键
            # 按下 'q' 键后退出循环
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("检测到 'q' 键，退出摄像头预览")
                break

    except KeyboardInterrupt:
        # 捕获 Ctrl+C 中断（用户手动中断程序）
        print("用户通过 Ctrl+C 中断了摄像头预览")

    finally:
        # 无论是否发生异常，都释放资源
        picamera.stop()               # 停止摄像头
        cv2.destroyAllWindows()       # 关闭所有 OpenCV 窗口
        print("摄像头已停止，窗口已关闭")


# 【学习提示】
# try...except...finally 是 Python 的异常处理结构：
# - try：尝试执行代码
# - except：如果发生错误，执行这里的代码
# - finally：无论是否发生错误，都会执行这里的代码（用于清理资源）


# -------------------------------
# 3. 从文件播放视频
# -------------------------------
def play_video_file(video_path='/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/walking.avi'):
    """
    功能：播放本地视频文件
    参数：
        video_path: 视频文件路径，默认为 './images/walking.avi'
    说明：用于测试视频文件是否能正常播放，以及了解视频处理的基本流程
    """
    # 使用 cv2.VideoCapture 打开视频文件
    # 参数可以是文件路径，也可以是摄像头索引（如 0 表示默认摄像头）
    cap = cv2.VideoCapture(video_path)

    # 检查视频是否成功打开
    if not cap.isOpened():
        print(f"错误：无法打开视频文件 '{video_path}'，请检查路径是否正确！")
        return  # 如果打开失败，直接返回，不继续执行后面的代码

    # 创建显示窗口
    cv2.namedWindow("Video Playback", cv2.WINDOW_NORMAL)

    # 进入循环，逐帧读取视频
    while cap.isOpened():
        # 逐帧读取视频
        # ret: 布尔值，表示是否成功读取帧
        # frame: 读取到的图像（NumPy 数组）
        ret, frame = cap.read()

        # 如果 ret 为 False，表示无法读取帧（视频播放完毕或文件损坏）
        if not ret:
            print("视频播放完毕或无法读取帧，退出播放")
            break

        # 水平翻转视频帧
        # cv2.flip() 的第二个参数：0 表示垂直翻转，1 表示水平翻转，-1 表示同时翻转
        # 原代码中的 flip(frame, 4) 是错误的，flip 第二个参数只能是 0, 1, -1
        frame = cv2.flip(frame, 1)

        # 显示当前帧
        cv2.imshow("Video Playback", frame)

        # 按 'q' 键退出播放
        # waitKey(25)：等待 25 毫秒（约 40 帧/秒）
        if cv2.waitKey(25) & 0xFF == ord('q'):
            print("用户按下 'q' 键，停止播放视频")
            break

    # 释放资源
    cap.release()                  # 释放视频文件
    cv2.destroyAllWindows()        # 关闭窗口
    print("视频播放结束，资源已释放")


# 【学习提示】
# cv2.VideoCapture 是 OpenCV 中用于读取视频的类
# - cap.isOpened()：检查视频是否成功打开
# - cap.read()：读取一帧，返回 (成功标志, 帧数据)
# - cap.release()：释放视频资源，必须调用，否则可能导致资源泄漏


# -------------------------------
# 4. 保存摄像头视频
# -------------------------------
def record_camera_video(output_filename='output.avi'):
    """
    功能：从摄像头捕获视频并保存为文件
    参数：
        output_filename: 输出视频文件名，默认为 'output.avi'
    说明：用于记录摄像头画面，比如制作 timelapse 或保存实验数据
    """
    # 创建 Picamera2 对象
    picamera = Picamera2()

    # 配置预览流（与 camera_preview 函数相同）
    # 【注意】main 分辨率设为 5000x5000 可能会导致性能问题，建议先用 640x480
    config = picamera.create_preview_configuration(
        main={"format": 'RGB888', "size": (640, 480)},
        raw={"format": "SRGGB12", "size": (1920, 1080)}
    )
    config["transform"] = libcamera.Transform(hflip=0, vflip=1)
    picamera.configure(config)

    # 启动摄像头
    print("摄像头已经开启：")
    picamera.start()
    time.sleep(2)  # 等待曝光稳定

    # 定义视频编解码器并创建 VideoWriter 对象
    # fourcc: 四字符编码，'XVID' 是一种常用的 AVI 编码
    # 20.0: 帧率（每秒 20 帧）
    # (640, 480): 视频分辨率，必须与捕获的分辨率一致
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_filename, fourcc, 20.0, (640, 480))

    # 检查 VideoWriter 是否创建成功
    if not out.isOpened():
        print(f"错误：无法创建视频文件 '{output_filename}'，请检查编码器是否支持！")
        picamera.stop()
        return

    # 创建显示窗口
    cv2.namedWindow("Recording Preview", cv2.WINDOW_NORMAL)

    try:
        while True:
            # 捕获一帧
            frame = picamera.capture_array("main")

            # 水平翻转帧（与原代码保持一致）
            frame = cv2.flip(frame, 1)

            # 将帧写入视频文件
            out.write(frame)

            # 实时预览
            cv2.imshow("Recording Preview", frame)

            # 按 'q' 键停止录制
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"用户按下 'q' 键，停止录制，视频已保存到 '{output_filename}'")
                break

    except KeyboardInterrupt:
        print("用户通过 Ctrl+C 中断了录制")

    finally:
        # 释放资源
        picamera.stop()
        out.release()                 # 关闭视频文件
        cv2.destroyAllWindows()
        print("摄像头已停止，视频文件已保存")


# 【学习提示】
# cv2.VideoWriter 是 OpenCV 中用于保存视频的类
# - fourcc：编码格式，常见的有 'XVID'（AVI）、'MJPG'（AVI）、'MP4V'（MP4）
# - fps：帧率，每秒保存多少帧
# - frameSize：分辨率，必须与输入帧的分辨率一致


# -------------------------------
# 5. 主程序入口
# -------------------------------
if __name__ == "__main__":
    """
    主程序入口：当直接运行此脚本时，会执行这里的代码
    如果是被其他脚本 import，则不会执行这里的代码
    """
    print("========================================")
    print("树莓派5 AI智能视觉套件 - 视频处理演示")
    print("========================================")

    # 在这里选择要运行的功能，一次只运行一个
    # 注意：摄像头同一时间只能被一个程序占用，所以不能同时运行多个功能

    # 1. 摄像头实时预览
    # camera_preview()

    # 2. 播放本地视频
    play_video_file('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/walking.avi')

    # 3. 保存摄像头视频
    record_camera_video('output.avi')

    print("\n程序运行结束")