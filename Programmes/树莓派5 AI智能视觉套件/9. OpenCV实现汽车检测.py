"""
汽车检测程序
适用于 Thonny IDE 运行版本
功能：使用 Haar 级联分类器检测视频中的汽车，并在图像上绘制矩形框
"""

# ============================================================================
# 第一部分：导入必要的库
# ============================================================================
import cv2          # OpenCV库，用于图像处理和计算机视觉
import time         # 时间库，用于控制帧率和延迟
import numpy as np  # NumPy库，用于数组操作
import tkinter as tk  # Tkinter库，用于创建GUI界面
from PIL import Image, ImageTk  # PIL库，用于图像格式转换
import threading    # 线程库，用于多线程处理
import os           # 操作系统库，用于文件路径操作
import sys          # 系统库，用于程序退出

# ============================================================================
# 第二部分：加载 Haar 级联分类器
# 功能：加载训练好的汽车检测模型
# ============================================================================
car_classifier_path = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/haarcascade_car.xml'

# 检查分类器文件是否存在
if os.path.exists(car_classifier_path):
    car_classifier = cv2.CascadeClassifier(car_classifier_path)
    print("INFO: Loading custom car classifier from file")
else:
    # 如果自定义分类器不存在，使用OpenCV内置的分类器
    print(f"WARNING: Custom classifier file not found: {car_classifier_path}")
    print("INFO: Using default OpenCV car classifier")
    car_classifier = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_car.xml')

# 检查分类器是否加载成功
if car_classifier.empty():
    print("ERROR: Failed to load classifier")
    sys.exit(1)
else:
    print("INFO: Car classifier loaded successfully")

# ============================================================================
# 第三部分：打开视频文件
# 功能：打开视频文件或摄像头，准备读取视频流
# ============================================================================
video_path = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/cars.avi'

# 尝试打开视频文件
cap = cv2.VideoCapture(video_path)

# 如果视频文件打不开，尝试使用摄像头
if not cap.isOpened():
    print(f"WARNING: Unable to open video file: {video_path}")
    print("INFO: Trying to use webcam instead")
    cap = cv2.VideoCapture(0)  # 参数0表示使用默认摄像头
    
    # 如果摄像头也打不开，退出程序
    if not cap.isOpened():
        print("ERROR: Unable to open webcam")
        sys.exit(1)
    else:
        print("INFO: Webcam opened successfully")
else:
    print("INFO: Video file opened successfully")

# ============================================================================
# 第四部分：定义全局变量
# 功能：用于在不同线程之间共享数据
# ============================================================================
running = True           # 程序运行控制标志
current_frame = None     # 当前处理的视频帧
current_car_count = 0    # 当前帧检测到的汽车数量
frame_count = 0          # 处理的总帧数

# ============================================================================
# 第五部分：创建 GUI 界面
# 功能：创建用户界面，显示检测结果和控制按钮
# ============================================================================
root = tk.Tk()
root.title("Car Detection System")
root.geometry("700x550")

# --------------------------------------------------------
# 创建图像显示区域
# --------------------------------------------------------
image_label = tk.Label(root)
image_label.pack()
print("INFO: Image display label created")

# --------------------------------------------------------
# 创建信息显示标签
# --------------------------------------------------------
info_label = tk.Label(root, text="Detecting cars...", font=("Arial", 12))
info_label.pack(pady=5)
print("INFO: Info label created")

# --------------------------------------------------------
# 创建统计信息标签
# --------------------------------------------------------
stats_label = tk.Label(root, text="Number of cars in current frame: 0", font=("Arial", 10))
stats_label.pack()
print("INFO: Statistics label created")

# --------------------------------------------------------
# 创建帧数显示标签
# --------------------------------------------------------
frame_label = tk.Label(root, text="帧数: 0", font=("Arial", 10))
frame_label.pack()
print("INFO: Frame counter label created")

# --------------------------------------------------------
# 创建按钮容器
# --------------------------------------------------------
button_frame = tk.Frame(root)
button_frame.pack(pady=10)
print("INFO: Button frame created")

# ============================================================================
# 第六部分：定义按钮功能函数
# 功能：定义GUI按钮的回调函数
# ============================================================================
def stop_program():
    """
    功能：停止检测程序
    说明：设置running标志为False，视频处理线程会检测到这个变化并停止
    """
    global running
    running = False
    info_label.config(text="Halting the programme...")
    print("INFO: Stopping program...")

def exit_program():
    """
    功能：完全退出程序
    说明：停止所有线程，释放资源，关闭窗口
    """
    global running
    running = False
    time.sleep(0.5)  # 等待线程安全结束
    root.quit()
    root.destroy()
    sys.exit(0)
    print("INFO: Exiting program...")

# --------------------------------------------------------
# 创建控制按钮
# --------------------------------------------------------
stop_btn = tk.Button(button_frame, text="Stop detection", command=stop_program, 
                    bg="red", fg="white", width=15, height=2)
stop_btn.pack(side=tk.LEFT, padx=5)
print("INFO: Stop button created")

exit_btn = tk.Button(button_frame, text="Exit", command=exit_program,
                    bg="blue", fg="white", width=15, height=2)
exit_btn.pack(side=tk.LEFT, padx=5)
print("INFO: Exit button created")

# ============================================================================
# 第七部分：视频处理函数
# 功能：在子线程中处理视频帧，检测汽车
# ============================================================================
def process_video():
    """
    功能：视频处理主循环
    说明：在独立线程中运行，不断读取视频帧，检测汽车，更新全局变量
    """
    global running, current_frame, current_car_count, frame_count
    
    print("INFO: Video processing thread started")
    
    # --------------------------------------------------------
    # 主处理循环
    # --------------------------------------------------------
    while running:
        # 读取一帧视频
        ret, frame = cap.read()
        
        # 如果读取失败（视频结束），重置到开头
        if not ret:
            print("INFO: Video ended, restarting from beginning")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        frame_count += 1
        
        # --------------------------------------------------------
        # 图像预处理：调整大小
        # --------------------------------------------------------
        height, width = frame.shape[:2]
        if height > 480 or width > 640:
            scale = min(480/height, 640/width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            frame = cv2.resize(frame, (new_width, new_height))
            print(f"DEBUG: Frame resized to {new_width}x{new_height}")
        
        # --------------------------------------------------------
        # 颜色空间转换：BGR 转 灰度
        # 说明：Haar检测通常在灰度图像上进行，可以提高检测速度
        # --------------------------------------------------------
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        
        # ========== Haar 级联分类器原理与参数详解 ==========
        # 1. Haar 特征：
        #    基于图像的像素亮度差异，计算矩形区域内亮暗区域的差值。
        #    常见类型包括边缘特征、线特征和中心环绕特征，用于捕捉物体的轮廓与形状。
        #
        # 2. 级联结构（Cascade）：
        #    由多个弱分类器（决策树桩）组成，每一层逐步过滤掉非目标区域。
        #    早期层快速排除大量背景，后期层精细判断，提高检测速度与准确率。
        #
        # 3. detectMultiScale 参数说明：
        #    - scaleFactor（缩放比例）：每次图像缩小的比例，例如 1.4 表示缩小到原来的约 71%。
        #      值越大检测越快，但可能漏检；值越小检测更细致，但速度变慢。
        #    - minNeighbors（最小邻居数）：每个候选矩形需要保留的邻近检测数量。
        #      数值越高误检越少，但可能漏检；数值过低会增加假阳性。
        #    - minSize / maxSize（可选）：限制检测目标的最小和最大尺寸，避免检测到过小或过大的区域。
        #
        # 4. 优缺点：
        #    优点：速度快，适合嵌入式设备（如树莓派）；无需GPU加速。
        #    缺点：对光照变化敏感，难以检测姿态变化大的目标。
        cars = car_classifier.detectMultiScale(gray, 1.4, 2, minSize=(30, 30))
        
        # --------------------------------------------------------
        # 绘制检测结果
        # 说明：在检测到的汽车周围绘制矩形框和标签
        # --------------------------------------------------------
        for (x, y, w, h) in cars:
            # 绘制黄色矩形框，线宽2像素
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
            # 在矩形框上方添加标签
            cv2.putText(frame, 'Car', (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # --------------------------------------------------------
        # 在图像上添加统计信息文本
        # --------------------------------------------------------
        cv2.putText(frame, f'Cars: {len(cars)}', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(frame, f'Frame: {frame_count}', (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # --------------------------------------------------------
        # 颜色空间转换：BGR 转 RGB
        # 说明：OpenCV使用BGR格式，PIL/Tkinter使用RGB格式
        # --------------------------------------------------------
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # --------------------------------------------------------
        # 更新全局变量
        # --------------------------------------------------------
        current_frame = frame_rgb
        current_car_count = len(cars)
        
        # 控制处理速度，避免CPU占用过高
        time.sleep(0.05)
    
    # --------------------------------------------------------
    # 清理资源
    # --------------------------------------------------------
    cap.release()
    print("INFO: Video processing thread ended, resources released")

# ============================================================================
# 第八部分：GUI更新函数
# 功能：在主线程中更新GUI显示
# ============================================================================
def update_gui():
    """
    功能：更新GUI界面显示
    说明：在主线程中运行，定期从全局变量获取最新数据并更新界面
    """
    global current_frame, current_car_count, frame_count
    
    if current_frame is not None:
        try:
            # --------------------------------------------------------
            # 图像格式转换：numpy数组 转 PIL图像
            # --------------------------------------------------------
            img = Image.fromarray(current_frame)
            
            # --------------------------------------------------------
            # 图像格式转换：PIL图像 转 Tkinter PhotoImage
            # --------------------------------------------------------
            imgtk = ImageTk.PhotoImage(image=img)
            
            # --------------------------------------------------------
            # 更新图像显示
            # 注意：必须保存对PhotoImage的引用，否则会被垃圾回收
            # --------------------------------------------------------
            image_label.imgtk = imgtk
            image_label.config(image=imgtk)
            
            # --------------------------------------------------------
            # 更新统计信息
            # --------------------------------------------------------
            stats_label.config(text=f"Count of cars in current frame: {current_car_count}")
            frame_label.config(text=f"Frame count: {frame_count}")
            
        except Exception as e:
            print(f"ERROR: Failed to update GUI: {e}")
    
    # --------------------------------------------------------
    # 安排下一次更新
    # 说明：如果程序还在运行，50毫秒后再次调用此函数
    # --------------------------------------------------------
    if running:
        root.after(50, update_gui)  # 每50毫秒更新一次
    else:
        info_label.config(text="检测已停止")
        print("INFO: GUI update stopped")

# ============================================================================
# 第九部分：启动线程
# 功能：启动视频处理线程和GUI更新
# ============================================================================
# 启动视频处理线程
video_thread = threading.Thread(target=process_video, daemon=True)
video_thread.start()
print("INFO: Video processing thread started")

# 启动GUI更新（100毫秒后开始）
root.after(100, update_gui)
print("INFO: GUI update scheduled")

# ============================================================================
# 第十部分：窗口关闭处理
# 功能：处理用户关闭窗口的操作
# ============================================================================
def on_closing():
    """
    功能：窗口关闭时的清理工作
    说明：释放资源，安全退出程序
    """
    global running
    running = False
    time.sleep(0.5)  # 等待线程安全结束
    root.quit()
    root.destroy()
    print("INFO: Window closed, program ending")

# 注册窗口关闭事件处理函数
root.protocol("WM_DELETE_WINDOW", on_closing)

# ============================================================================
# 第十一部分：主程序循环
# 功能：启动Tkinter主循环
# ============================================================================
print("INFO: Starting main loop...")
try:
    root.mainloop()
except Exception as e:
    print(f"ERROR: Program error: {e}")
finally:
    # --------------------------------------------------------
    # 最终清理
    # --------------------------------------------------------
    running = False
    if cap.isOpened():
        cap.release()
    print("INFO: Program completely stopped")
    print("INFO: Goodbye!")