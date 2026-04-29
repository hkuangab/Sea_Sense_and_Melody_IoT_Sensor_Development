# ==================== Mobilenet V3 目标识别 ====================

# ==================== 导入必要的库 ====================
import cv2
import threading
import ctypes
import inspect
# 注意：已移除JupyterLab依赖库，代码兼容标准Python环境

# ==================== 线程终止函数 ====================
def _async_raise(tid, exctype):
    """
    通过抛出异常来安全终止指定线程
    参数：
        tid: 线程ID
        exctype: 异常类型
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
    参数：
        thread: 要停止的线程对象
    """
    _async_raise(thread.ident, SystemExit)

# ==================== 加载目标检测模型 ==================== # COCO数据集的80个类别，是已经被训练好的模型
# 模型配置文件路径
config_file = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'
# 预训练模型权重文件路径
frozen_model = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/frozen_inference_graph.pb'

# 创建SSD MobileNet V3目标检测模型对象
# cv2.dnn_DetectionModel: 创建深度学习检测模型
model = cv2.dnn_DetectionModel(frozen_model, config_file)

# ==================== 加载类别标签文件 ====================
classLabels = []  # 存储80个COCO数据集类别名称
filename = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/labels.txt'

# 读取标签文件，每行一个类别
with open(filename, 'rt', encoding='utf-8') as spt:
    classLabels = spt.read().rstrip('\n').split('\n')
    # 注意：添加encoding='utf-8'避免编码问题

# ==================== 设置模型预处理参数 ====================
# 设置输入图像尺寸为320x320
# 注意：尺寸越大精度越高但速度越慢
model.setInputSize(320, 320)

# 设置输入缩放比例
# 将像素值从[0,255]缩放到[-1,1]
model.setInputScale(1.0/127.5)

# 设置输入均值，用于归一化
model.setInputMean((127.5, 127.5, 127.5))

# 将BGR通道顺序转换为RGB
# OpenCV默认读取为BGR，但模型需要RGB输入
model.setInputSwapRB(True)

# ==================== 视频输入输出设置 ====================
# 打开输入视频文件
# cv2.VideoCapture: 读取视频文件或摄像头
cap = cv2.VideoCapture('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/test_video.mp4')

# 读取第一帧获取视频尺寸
ret, frame = cap.read()
if not ret:
    print("Error: Cannot read video file")
    exit()

# 定义视频编码器
# 'mp4v'支持MP4格式，兼容性较好
fourcc = cv2.VideoWriter_fourcc(*'mp4v')

# 初始化视频写入器
# 参数：输出文件名、编码器、帧率(25fps)、帧尺寸
video = cv2.VideoWriter('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/tvideo.avi', 
                         fourcc, 25, (frame.shape[1], frame.shape[0]))

# 设置字体用于绘制文本
font = cv2.FONT_HERSHEY_PLAIN

# ==================== 视频处理函数 ====================
def Video_display():
    """
    视频处理主函数
    在线程中持续读取视频帧，进行目标检测，绘制结果并保存
    """
    while True:
        ret, frame = cap.read()  # 读取一帧视频
        
        if not ret:  # 视频结束或读取失败
            print("Video ended or failed to read frame.")
            break
        
        # ==================== 目标检测 ====================
        # 使用模型检测当前帧中的目标
        # confThreshold=0.65: 置信度阈值，只显示65%以上置信度的检测结果
        classIndex, confidence, bbox = model.detect(frame, confThreshold=0.65)
        
        # ==================== 绘制检测结果 ====================
        # 如果检测到目标，绘制边界框和标签
        if len(classIndex) != 0:
            for classInd, boxes in zip(classIndex.flatten(), bbox):
                # 绘制蓝色边界框
                # 参数：图像、左上角坐标、右下角坐标、颜色(BGR)、线宽
                cv2.rectangle(frame, boxes, (255, 0, 0), 2)
                
                # 在框上方绘制类别标签
                # 参数：图像、文本、位置、字体、字号、颜色、线宽
                cv2.putText(frame, classLabels[classInd-1], 
                           (boxes[0] + 10, boxes[1] + 40), 
                           font, fontScale=1, color=(0, 255, 0), thickness=2)
        
        # ==================== 保存和显示结果 ====================
        # 将处理后的帧写入输出视频
        video.write(frame)
        
        # 显示实时检测结果
        cv2.imshow('Object Detection', frame)
        
        # ==================== 退出检测 ====================
        # 检测按键，按下'q'键退出循环
        # cv2.waitKey(1): 等待1ms并检测键盘输入
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("User interrupted the video processing.")
            break

# ==================== 启动视频处理线程 ====================
# 创建并启动视频处理线程
# threading.Thread: 创建新线程执行指定函数
t = threading.Thread(target=Video_display)
t.setDaemon(True)  # 设置为守护线程，主线程结束时自动终止
t.start()  # 启动线程

# ==================== 主线程控制 ====================
# 等待处理线程完成
try:
    t.join()  # 主线程等待子线程结束
except KeyboardInterrupt:
    # 捕获Ctrl+C键盘中断信号
    print("Keyboard interrupt detected, stopping thread.")
    stop_thread(t)  # 安全终止线程
except Exception as e:
    print(f"Error occurred: {e}")

# ==================== 释放资源 ====================
# 关闭视频捕获对象
cap.release()

# 关闭视频写入器
video.release()

# 销毁所有OpenCV创建的窗口
cv2.destroyAllWindows()

print("Video processing completed. Output saved as 'tvideo.avi'.")