# 人脸身份识别脚本 - 使用dlib替代face_recognition
# 块1: 导入必要的库
import dlib
import cv2
import numpy as np
import os

# 打印OpenCV版本，使用英文防止乱码
print("OpenCV version:", cv2.__version__)

# 块2: 定义人脸识别相关函数
def load_face_encodings(image_path, predictor_path, face_rec_model_path):
    """
    使用dlib加载图片并提取人脸编码
    image_path: 图片文件路径
    predictor_path: 人脸特征点检测器路径
    face_rec_model_path: 人脸识别模型路径
    """
    # 加载图片
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot load image: {image_path}")
    
    # 转换为RGB格式
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # 创建人脸检测器
    detector = dlib.get_frontal_face_detector()
    
    # 创建人脸特征点检测器
    shape_predictor = dlib.shape_predictor(predictor_path)
    
    # 创建人脸识别模型
    face_recognizer = dlib.face_recognition_model_v1(face_rec_model_path)
    
    # 检测人脸
    faces = detector(rgb_image, 1)
    
    if len(faces) == 0:
        raise ValueError(f"No face detected in image: {image_path}")
    
    # 获取第一个人脸的特征点
    shape = shape_predictor(rgb_image, faces[0])
    
    # 提取人脸编码（128维向量）
    face_encoding = np.array(face_recognizer.compute_face_descriptor(rgb_image, shape))
    
    return face_encoding

def detect_and_recognize_faces(test_image_path, known_encodings, known_names, 
                               predictor_path, face_rec_model_path, distance_threshold=0.6):
    """
    检测并识别人脸
    test_image_path: 测试图片路径
    known_encodings: 已知人脸编码列表
    known_names: 已知人脸名称列表
    predictor_path: 人脸特征点检测器路径
    face_rec_model_path: 人脸识别模型路径
    distance_threshold: 距离阈值，小于此值认为是同一人
    """
    # 加载测试图片
    test_image = cv2.imread(test_image_path)
    if test_image is None:
        raise ValueError(f"Cannot load test image: {test_image_path}")
    
    # 转换为RGB格式
    rgb_image = cv2.cvtColor(test_image, cv2.COLOR_BGR2RGB)
    
    # 创建人脸检测器
    detector = dlib.get_frontal_face_detector()
    
    # 创建人脸特征点检测器
    shape_predictor = dlib.shape_predictor(predictor_path)
    
    # 创建人脸识别模型
    face_recognizer = dlib.face_recognition_model_v1(face_rec_model_path)
    
    # 检测测试图片中的人脸
    faces = detector(rgb_image, 1)
    
    print(f"Number of faces detected in test image: {len(faces)}")
    
    # 提取每个人脸的位置和编码
    face_locations = []
    face_encodings = []
    
    for face in faces:
        # 获取人脸位置
        left, top, right, bottom = face.left(), face.top(), face.right(), face.bottom()
        face_locations.append((top, right, bottom, left))
        
        # 获取特征点
        shape = shape_predictor(rgb_image, face)
        
        # 提取人脸编码
        face_encoding = np.array(face_recognizer.compute_face_descriptor(rgb_image, shape))
        face_encodings.append(face_encoding)
    
    return test_image, face_locations, face_encodings

def compare_faces(known_encodings, unknown_encoding, threshold=0.6):
    """
    比较人脸编码，返回匹配结果
    known_encodings: 已知人脸编码列表
    unknown_encoding: 未知人脸编码
    threshold: 距离阈值
    """
    # 计算与所有已知人脸的距离
    distances = []
    for known_encoding in known_encodings:
        # 使用欧氏距离
        distance = np.linalg.norm(known_encoding - unknown_encoding)
        distances.append(distance)
    
    # 找到最小距离
    min_distance = min(distances)
    min_index = distances.index(min_distance)
    
    # 判断是否匹配
    if min_distance < threshold:
        return True, min_index, min_distance
    else:
        return False, -1, min_distance

# 块3: 主程序
def main():
    # 设置模型文件路径
    # 注意：需要先下载dlib的预训练模型文件
    # 1. shape_predictor_5_face_landmarks.dat
    # 2. dlib_face_recognition_resnet_model_v1.dat
    predictor_path = "shape_predictor_5_face_landmarks.dat"
    face_rec_model_path = "dlib_face_recognition_resnet_model_v1.dat"
    
    # 检查模型文件是否存在
    if not os.path.exists(predictor_path):
        print(f"Error: Cannot find predictor file: {predictor_path}")
        print("Please download it from: http://dlib.net/files/shape_predictor_5_face_landmarks.dat.bz2")
        return
    
    if not os.path.exists(face_rec_model_path):
        print(f"Error: Cannot find face recognition model: {face_rec_model_path}")
        print("Please download it from: http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2")
        return
    
    # 块4: 加载已知人脸并提取编码
    print("Loading known faces and extracting encodings...")
    
    known_encodings = []
    known_names = []
    
    # 定义已知人脸文件列表
    known_faces = [
        ('./known/Donald Trump.jpg', 'The Donald'),
        ('./known/Nancy Pelosi.jpg', 'Nancy Pelosi'),
        ('./known/Mike Pence.jpg', 'Mike Pence'),
        ('./known/zhulin.jpg', 'zhulin')
    ]
    
    for face_file, name in known_faces:
        try:
            if not os.path.exists(face_file):
                print(f"Warning: Cannot find known face file: {face_file}")
                continue
                
            encoding = load_face_encodings(face_file, predictor_path, face_rec_model_path)
            known_encodings.append(encoding)
            known_names.append(name)
            print(f"  Loaded: {name} from {face_file}")
            
        except Exception as e:
            print(f"  Error loading {face_file}: {e}")
    
    if len(known_encodings) == 0:
        print("Error: No known faces loaded successfully.")
        return
    
    print(f"Successfully loaded {len(known_encodings)} known faces.")
    
    # 块5: 测试图片人脸识别
    test_image_path = './unknown/u13.jpg'
    
    if not os.path.exists(test_image_path):
        print(f"Error: Cannot find test image: {test_image_path}")
        
        # 创建测试目录和测试图片
        print("Creating test directory and image...")
        os.makedirs('./unknown', exist_ok=True)
        
        # 创建一个简单的测试图片
        test_image = np.ones((300, 400, 3), dtype=np.uint8) * 255
        # 绘制两个"人脸"区域
        cv2.rectangle(test_image, (50, 50), (200, 200), (100, 100, 100), -1)
        cv2.rectangle(test_image, (250, 100), (350, 250), (150, 150, 150), -1)
        cv2.imwrite(test_image_path, test_image)
        print(f"Created test image: {test_image_path}")
    
    print(f"Processing test image: {test_image_path}")
    
    try:
        # 检测和识别人脸
        test_image, face_locations, face_encodings = detect_and_recognize_faces(
            test_image_path, known_encodings, known_names, predictor_path, face_rec_model_path
        )
        
        # 块6: 识别和标注人脸
        print("Recognizing faces...")
        
        # 设置字体
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            # 默认标记为未知
            name = "Unknown Person"
            color = (0, 0, 255)  # 红色
            
            # 与已知人脸比较
            match, match_index, distance = compare_faces(known_encodings, face_encoding)
            
            if match:
                name = known_names[match_index]
                color = (0, 255, 0)  # 绿色
                print(f"  Face at ({left}, {top}, {right}, {bottom}): {name} (distance: {distance:.4f})")
            else:
                print(f"  Face at ({left}, {top}, {right}, {bottom}): Unknown (min distance: {distance:.4f})")
            
            # 绘制人脸框
            cv2.rectangle(test_image, (left, top), (right, bottom), color, 2)
            
            # 绘制名字标签
            label_y = top - 10 if top > 20 else top + 20
            cv2.putText(test_image, name, (left, label_y), font, 0.75, color, 2)
        
        # 块7: 显示结果
        cv2.imshow('Face Recognition Results', test_image)
        print("\nPress any key to close the window...")
        
        # 等待按键
        cv2.waitKey(0)
        
        # 销毁所有窗口
        cv2.destroyAllWindows()
        
        # 保存结果
        output_path = 'face_recognition_result.jpg'
        cv2.imwrite(output_path, test_image)
        print(f"\nResults saved to: {output_path}")
        
    except Exception as e:
        print(f"Error during face recognition: {e}")

# 块8: 运行主程序
if __name__ == "__main__":
    main()