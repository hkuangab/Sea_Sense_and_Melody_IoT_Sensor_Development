# ==================== 摄像头目标识别实时识别 ====================
# 步骤1: 导入必要的库
import libcamera
from picamera2 import Picamera2
import threading
import cv2
import time
import numpy as np

# 步骤2: 相机初始化与配置
# 创建Picamera2实例，用于控制树莓派相机
picamera = Picamera2()

# 配置相机参数：
# 创建预览配置：
# - main流：格式为RGB888，分辨率320x240（用于处理和显示）
# - raw流：格式为SRGGB12，分辨率1920x1080（原始图像数据）
config = picamera.create_preview_configuration(
    main={"format": 'RGB888', "size": (1024, 1024)},
    raw={"format": "SRGGB12", "size": (1920, 1080)}
)

# 设置图像变换：水平不翻转(0)，垂直翻转(1)
# 适用于摄像头倒置安装的情况
config["transform"] = libcamera.Transform(hflip=0, vflip=1)

# 应用配置并启动相机
picamera.configure(config)
picamera.start()

# 步骤3: 定义全局变量
# 线程停止标志，用于安全停止视频处理线程
stop_thread_flag = False

# 加载SSD MobileNet V3模型
# 注意：你需要下载对应的模型文件
# 下载地址：https://github.com/opencv/opencv/wiki/TensorFlow-Object-Detection-API
print("INFO: Loading SSD MobileNet V3 model...")
# 模型配置文件路径
prototxt_path = "/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/config_files/MobileNetSSD_deploy.prototxt"
# 模型权重文件路径
model_path = "/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/config_files/MobileNetSSD_deploy.caffemodel"

try:
    # 加载模型
    net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
    print("INFO: Model loaded successfully")
except Exception as e:
    print(f"ERROR: Failed to load model: {e}")
    print("INFO: Please download the model files:")
    print("INFO: 1. MobileNetSSD_deploy.prototxt.txt")
    print("INFO: 2. MobileNetSSD_deploy.caffemodel")
    print("INFO: From: https://github.com/opencv/opencv/wiki/TensorFlow-Object-Detection-API")
    exit(1)

# SSD MobileNet V3的类别标签
classNames = ["background", "aeroplane", "bicycle", "bird", "boat",
              "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
              "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
              "sofa", "train", "tvmonitor"]

# 设置检测阈值
CONFIDENCE_THRESHOLD = 0.5  # 置信度阈值

# 步骤4: 将BGR格式图像转换为JPEG字节流
def bgr8_to_jpeg(frame, quality=85):
    """将BGR格式的numpy数组转换为JPEG字节流"""
    import io
    from PIL import Image
    
    # 转换颜色空间：BGR -> RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 创建PIL图像
    pil_image = Image.fromarray(rgb_frame)
    
    # 保存为JPEG字节流
    buffer = io.BytesIO()
    pil_image.save(buffer, format='JPEG', quality=quality)
    
    return buffer.getvalue()

# 步骤5: 目标检测函数
def detect_objects(frame, net, classNames, conf_threshold=0.5):
    """
    使用SSD MobileNet V3模型检测图像中的目标
    
    参数:
        frame: 输入图像帧
        net: 加载的神经网络模型
        classNames: 类别标签列表
        conf_threshold: 置信度阈值
        
    返回:
        绘制了检测结果的图像
    """
    (h, w) = frame.shape[:2]
    
    # 将图像转换为blob格式用于神经网络输入
    blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
    
    # 设置输入并前向传播
    net.setInput(blob)
    detections = net.forward()
    
    # 遍历所有检测结果
    for i in range(detections.shape[2]):
        # 获取当前检测的置信度
        confidence = detections[0, 0, i, 2]
        
        # 过滤掉置信度低于阈值的检测结果
        if confidence > conf_threshold:
            # 获取类别索引
            class_id = int(detections[0, 0, i, 1])
            
            # 跳过背景类别
            if class_id >= len(classNames):
                continue
                
            class_name = classNames[class_id]
            
            # 计算边界框坐标
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            
            # 确保边界框不超出图像范围
            startX = max(0, startX)
            startY = max(0, startY)
            endX = min(w, endX)
            endY = min(h, endY)
            
            # 在图像上绘制边界框
            color = (0, 255, 0)  # 绿色边界框
            cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
            
            # 准备标签文本
            label = f"{class_name}: {confidence:.2f}"
            
            # 计算标签文本的大小
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            
            # 绘制标签背景
            cv2.rectangle(frame, 
                          (startX, startY - label_size[1] - 10), 
                          (startX + label_size[0], startY), 
                          color, 
                          -1)
            
            # 绘制标签文本
            cv2.putText(frame, label, (startX, startY - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    
    return frame

# 步骤6: 实时视频处理函数
def PiVideo_display():
    """
    实时捕获视频帧并进行目标检测处理
    此函数将在独立线程中运行
    """
    global stop_thread_flag
    print("INFO: Starting video display thread...")
    
    # 创建OpenCV窗口
    cv2.namedWindow("SSD MobileNet V3 Object Detection", cv2.WINDOW_NORMAL)
    
    while not stop_thread_flag:
        # 捕获一帧图像
        frame = picamera.capture_array()
        
        # 转换颜色空间：RGB -> BGR（因为OpenCV使用BGR格式）
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # 使用模型进行目标检测
        processed_frame = detect_objects(frame_bgr, net, classNames, CONFIDENCE_THRESHOLD)
        
        # 在OpenCV窗口中显示处理后的图像
        cv2.imshow("SSD MobileNet V3 Object Detection", processed_frame)
        
        # 检查是否按下'q'键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop_thread_flag = True
            break
    
    # 关闭窗口
    cv2.destroyWindow("SSD MobileNet V3 Object Detection")
    print("INFO: Video display thread stopped.")

# 步骤7: 线程管理函数
def stop_thread(thread):
    """停止指定线程的函数"""
    global stop_thread_flag
    stop_thread_flag = True
    thread.join(timeout=2)  # 等待线程结束，最多等待2秒
    if thread.is_alive():
        print("WARNING: Thread did not stop in time, forcing termination.")
    else:
        print("INFO: Thread stopped successfully.")

# 步骤8: 主程序逻辑
def main():
    global stop_thread_flag
    
    print("INFO: Starting main program...")
    print("INFO: Press 'q' in the video window to quit.")
    print("INFO: Using SSD MobileNet V3 for object detection")
    print(f"INFO: Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"INFO: Detecting {len(classNames)} classes: {', '.join(classNames)}")
    
    # 创建并启动视频处理线程
    t1 = threading.Thread(target=PiVideo_display)
    t1.setDaemon(True)  # 设置为守护线程，主程序退出时自动结束
    t1.start()  # 启动线程
    
    try:
        # 主循环，等待线程完成
        while t1.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("INFO: Keyboard interrupt detected, stopping...")
    finally:
        # 停止线程
        stop_thread_flag = True
        stop_thread(t1)
        
        # 释放资源
        cv2.destroyAllWindows()
        picamera.stop()
        
        print("INFO: Camera stopped.")
        print("INFO: Program ended.")

# 步骤9: 程序入口
if __name__ == "__main__":
    main()