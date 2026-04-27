# 导入必要的库
import cv2
import threading  # 线程库
import ctypes
import inspect

# 线程终止函数
# 功能：通过抛出异常来安全地终止指定线程
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

# 加载模型和标签文件
# 功能：初始化目标检测模型并加载类别标签
config_file = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/ssd_mobilenet_v3_large_coco_2020_01_14.pbtxt'  # 模型配置文件路径
frozen_model = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/frozen_inference_graph.pb'  # 预训练模型权重文件路径
model = cv2.dnn_DetectionModel(frozen_model, config_file)  # 创建检测模型对象

# 读取类别标签文件
classLabels = []  # 存储类别名称的列表
filename = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/15.ssd+mobilenet+V3+目标检测/labels.txt'  # 标签文件路径
with open(filename, 'rt') as spt:
    classLabels = spt.read().rstrip('\n').split('\n')  # 按行读取并去除换行符

# 设置模型输入参数
model.setInputSize(320, 320)  # 设置输入图像尺寸，值越大结果越准确但速度越慢
model.setInputScale(1.0/127.5)  # 设置输入缩放比例
model.setInputMean((127.5, 127.5, 127.5))  # 设置输入均值
model.setInputSwapRB(True)  # 将BGR通道顺序转换为RGB

# 视频捕获和写入设置
# 功能：打开输入视频文件并初始化输出视频写入器
cap = cv2.VideoCapture('test_video.mp4')  # 打开视频文件进行读取
ret, frame = cap.read()  # 读取第一帧以获取视频尺寸

fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 定义视频编码器
# 初始化视频写入器，参数：输出文件名、编码器、帧率、帧尺寸
video = cv2.VideoWriter('video.avi', fourcc, 25, (frame.shape[1], frame.shape[0]))

# 字体设置用于绘制文本
font = cv2.FONT_HERSHEY_PLAIN

# 视频处理函数
# 功能：在线程中持续读取视频帧，进行目标检测，绘制结果并保存输出视频
def Video_display():
    while True:
        ret, frame = cap.read()  # 读取视频帧
        if not ret:  # 如果读取失败（如视频结束），则退出循环
            print("Video ended or failed to read frame.")  # 使用英语防止乱码
            break
        
        # 使用模型进行目标检测，confThreshold为置信度阈值
        classIndex, confidence, bbox = model.detect(frame, confThreshold=0.65)
        
        # 如果检测到目标，则绘制边界框和标签
        if len(classIndex) != 0:
            for classInd, boxes in zip(classIndex.flatten(), bbox):
                cv2.rectangle(frame, boxes, (255, 0, 0), 2)  # 绘制蓝色矩形框
                # 在框上方绘制类别标签
                cv2.putText(frame, classLabels[classInd-1], (boxes[0] + 10, boxes[1] + 40), 
                           font, fontScale=1, color=(0, 255, 0), thickness=2)
        
        video.write(frame)  # 将处理后的帧写入输出视频
        
        # 显示实时检测结果
        cv2.imshow('Object Detection', frame)  # 在窗口中显示当前帧
        
        # 检测按键，如果按下'q'键则退出循环
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("User interrupted the video processing.")  # 使用英语防止乱码
            break

# 启动视频处理线程
# 功能：在新线程中运行视频处理，避免阻塞主线程
t = threading.Thread(target=Video_display)
t.setDaemon(True)  # 设置为守护线程，主线程结束时自动终止
t.start()

# 主线程等待处理线程完成
try:
    t.join()  # 等待线程结束
except KeyboardInterrupt:
    print("Keyboard interrupt detected, stopping thread.")  # 使用英语防止乱码
    stop_thread(t)  # 安全终止线程

# 释放资源
# 功能：关闭视频捕获、写入器并销毁所有OpenCV窗口
cap.release()  # 释放视频捕获对象
video.release()  # 释放视频写入器
cv2.destroyAllWindows()  # 关闭所有OpenCV窗口
print("Video processing completed. Output saved as 'video.avi'.")  # 使用英语防止乱码