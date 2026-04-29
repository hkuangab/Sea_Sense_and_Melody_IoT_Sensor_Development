"""
dlib人脸检测技术原理：
1. HOG特征提取：计算图像的梯度方向直方图
2. 滑动窗口检测：在不同尺度和位置检测人脸
3. 线性SVM分类：区分人脸和非人脸区域
4. 非极大值抑制：去除重叠的检测框
"""

# 人脸识别脚本 - 使用dlib替代face_recognition

# 块1: 导入必要的库
import dlib
import cv2
import numpy as np
import os

# 线程相关库
import threading
import ctypes
import inspect

# 块2: 线程结束函数
# 用于强制停止线程的函数
def _async_raise(tid, exctype):
    """
    异步引发异常以停止线程
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
    thread: 线程对象
    """
    _async_raise(thread.ident, SystemExit)

# 块3: 使用dlib进行人脸识别和显示
def load_image_with_dlib(image_path):
    """
    使用dlib加载图片
    """
    # 使用OpenCV读取图片
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"无法加载图片: {image_path}")
    
    # 转换为RGB格式（dlib需要RGB）
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    return rgb_image, image  # 返回RGB和BGR图像

def detect_faces_with_dlib(rgb_image):
    """
    使用dlib检测人脸
    """
    # 创建HOG人脸检测器
    detector = dlib.get_frontal_face_detector()
    
    # 检测人脸
    # 参数1: 上采样次数，可以提高对小脸部的检测
    faces = detector(rgb_image, 1)
    
    # 转换为人脸位置列表
    face_locations = []
    for face in faces:
        # dlib返回的是(left, top, right, bottom)
        left, top, right, bottom = face.left(), face.top(), face.right(), face.bottom()
        # 转换为(top, right, bottom, left)格式，与face_recognition保持一致
        face_locations.append((top, right, bottom, left))
    
    return face_locations

# 主程序
def main():
    # 加载图像文件
    image_path = '/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/peds_0.jpg'  # 图像文件路径
    
    # 检查文件是否存在
    if not os.path.exists(image_path):
        # 如果找不到文件，创建一个测试图片
        print(f"Warning: Cannot find image file: {image_path}")
        print("Creating a test image...")
        
        # 创建一个包含测试人脸的图片
        test_image = np.ones((300, 400, 3), dtype=np.uint8) * 255
        
        # 绘制两个"人脸"区域
        # 人脸1
        cv2.rectangle(test_image, (50, 50), (200, 200), (100, 100, 100), -1)
        # 人脸2
        cv2.rectangle(test_image, (250, 100), (350, 250), (150, 150, 150), -1)
        
        # 保存测试图片
        cv2.imwrite('test_face.jpg', test_image)
        image_path = 'test_face.jpg'
    
    try:
        # 加载图片
        rgb_image, bgr_image = load_image_with_dlib(image_path)
        print(f"Successfully loaded image: {image_path}")
        
        # 使用dlib检测人脸
        print("Detecting faces with dlib...")
        face_locations = detect_faces_with_dlib(rgb_image)
        
        # 打印检测到的人脸位置，使用英文输出
        print(f"Number of faces detected: {len(face_locations)}")
        print("Face locations:", face_locations)
        
        if len(face_locations) > 0:
            # 在检测到的人脸周围绘制矩形
            # face_locations格式为(top, right, bottom, left)
            for i, (top, right, bottom, left) in enumerate(face_locations):
                # 绘制红色矩形
                cv2.rectangle(bgr_image, (left, top), (right, bottom), (0, 0, 255), 2)
                # 添加标签
                cv2.putText(bgr_image, f"Face {i+1}", (left, top-10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # 显示图像
        cv2.imshow('Face Detection (dlib)', bgr_image)
        print("Press any key to close the window...")
        # 等待按键，0表示无限等待直到按下任意键
        cv2.waitKey(0)
        # 销毁所有OpenCV窗口
        cv2.destroyAllWindows()
        print("Face detection completed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Please check the image path and try again.")

# 运行主程序
if __name__ == "__main__":
    main()