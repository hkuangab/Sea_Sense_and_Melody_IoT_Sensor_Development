# 导入必要的库
import cv2
import numpy as np
import subprocess
import tempfile
import os

# 读取图像
img = cv2.imread('/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/makecar.jpg', cv2.IMREAD_COLOR)

# 检查图像是否成功加载
if img is None:
    print("Error: Failed to load image")
    exit()

# 调整图像大小
img = cv2.resize(img, (600, 400))

# 将彩色图像转换为灰度图
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 应用双边滤波进行降噪处理
# 函数: cv2.bilateralFilter()
# 参数说明:
#   - gray: 输入图像（灰度图）
#   - 13: 滤波器的直径（必须为正奇数）
#   - 15: 颜色空间的标准差（控制颜色相似性的权重）
#   - 15: 坐标空间的标准差（控制空间距离的权重）
# 
# 双边滤波的工作原理（双边滤波是一种非线性滤波方法）：
# 1. 空间权重（Spatial Weighting）：
#    - 离中心像素越近的像素，权重越大
#    - 通过高斯函数计算：exp(-距离²/(2×σ_space²))
#    - σ_space = 15 控制权重随距离衰减的速度
#
# 2. 颜色权重（Color/Intensity Weighting）：
#    - 与中心像素灰度值越相似的像素，权重越大
#    - 通过高斯函数计算：exp(-颜色差异²/(2×σ_color²))
#    - σ_color = 15 控制权重随颜色差异衰减的速度
#
# 3. 组合权重：
#    - 总权重 = 空间权重 × 颜色权重
#    - 输出像素值 = Σ(邻域像素值×总权重) / Σ(总权重)
#
# 双边滤波的数学公式：
# BF[I](x,y) = Σ_{i,j∈Ω} w_s(i,j) × w_c(i,j) × I(i,j) / Σ_{i,j∈Ω} w_s(i,j) × w_c(i,j)
# 其中：
# w_s(i,j) = exp(-((i-x)²+(j-y)²)/(2σ_s²))  # 空间权重
# w_c(i,j) = exp(-(I(i,j)-I(x,y))²/(2σ_c²))  # 颜色权重
#
# 在车牌识别中为什么使用双边滤波而不是高斯滤波？
# 高斯滤波会模糊所有边缘，而双边滤波能在平滑噪声的同时保护车牌字符边缘。
# 这是因为字符边缘处颜色突变，颜色权重很小，从而保护了边缘。
gray = cv2.bilateralFilter(gray, 13, 15, 15)

# 边缘检测
# 函数: cv2.Canny()
# 参数说明:
#   - gray: 输入图像（经过双边滤波处理后的灰度图）
#   - 30: 低阈值（低于此值的像素点不被认为是边缘）
#   - 200: 高阈值（高于此值的像素点被认为是强边缘）
#
# Canny边缘检测的工作原理（四个步骤）：
# 步骤1: 噪声抑制（已由双边滤波完成）
#    - 理论上Canny的第一步是高斯滤波，但我们已使用更好的双边滤波
#
# 步骤2: 计算梯度强度和方向
#    - 使用Sobel算子计算x和y方向的梯度：
#      G_x = [[-1, 0, 1],   G_y = [[-1, -2, -1],
#             [-2, 0, 2],          [ 0,  0,  0],
#             [-1, 0, 1]]          [ 1,  2,  1]]
#    - 梯度大小: G = √(G_x² + G_y²)
#    - 梯度方向: θ = arctan(G_y / G_x) （角度范围0-180度）
#
# 步骤3: 非极大值抑制（NMS）
#    - 沿着梯度方向比较当前像素与相邻像素
#    - 只保留梯度值最大的像素，抑制非极大值
#    - 例如：梯度方向为90度（垂直），比较上下两个像素
#
# 步骤4: 双阈值检测和边缘连接
#    - 高阈值(200): 梯度值>200的像素 → 强边缘（肯定保留）
#    - 低阈值(30): 梯度值<30的像素 → 非边缘（丢弃）
#    - 30<梯度值<200的像素 → 弱边缘（有条件保留）
#    - 弱边缘只有连接到强边缘时才被保留
#
# 为什么选择30和200作为阈值？
# 1. 经验比例：高阈值:低阈值 ≈ 2:1 到 3:1
# 2. 30/200=1:6.7，更保守，减少噪声但可能丢失弱边缘
# 3. 可根据具体图像调整：噪声多则提高阈值，边缘弱则降低阈值
edged = cv2.Canny(gray, 30, 200)

# 查找轮廓
# 函数: cv2.findContours()
# 参数说明:
#   - edged.copy(): 输入二值图像（边缘检测结果）
#     使用copy()避免修改原始图像
#   - cv2.RETR_TREE: 轮廓检索模式
#     检索所有轮廓并建立完整的层次结构
#   - cv2.CHAIN_APPROX_SIMPLE: 轮廓近似方法
#     压缩水平、垂直和对角方向的点，只保留端点
#
# 轮廓查找的工作原理：
# 1. 扫描二值图像（0=黑色背景，255=白色边缘）
# 2. 边缘跟踪算法（如：Moore-Neighbor跟踪算法）：
#    a. 从左上角开始扫描，找到第一个白色像素（边缘起点）
#    b. 按照8-邻域方向搜索下一个白色像素
#    c. 记录像素坐标，形成轮廓
#    d. 标记已访问的像素，避免重复
# 3. 层次结构建立（RETR_TREE模式）：
#    - 每个轮廓可能有父子关系
#    - 例如：外层轮廓是父轮廓，内层轮廓是子轮廓
#    - 层次信息存储在数组中，每行包含4个值：
#      [next, previous, first_child, parent]
# 4. 轮廓压缩（CHAIN_APPROX_SIMPLE）：
#    - 删除冗余点，只保留轮廓的端点
#    - 例如：直线只需要起点和终点
#    - 大大减少内存使用
#
# 返回值说明：
#   - contours: 轮廓列表
#     每个轮廓是numpy数组，形状为(n,1,2)
#     表示n个点，每个点是(x,y)坐标
#   - _: 层次信息（这里用下划线忽略，因为当前任务不需要）
contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

# 按轮廓面积排序并获取前10个最大的轮廓
# 函数: sorted()
# 参数说明:
#   - contours: 轮廓列表
#   - key=cv2.contourArea: 排序键，按轮廓面积排序
#   - reverse=True: 降序排序（从大到小）
#   - [:10]: 切片，只取前10个
#
# 轮廓面积的计算原理：
# 使用格林公式（Green's theorem）计算多边形面积：
# A = 1/2 × |Σ_{i=0}^{n-1} (x_i × y_{i+1} - x_{i+1} × y_i)|
# 其中：
#   - (x_i, y_i) 是轮廓上第i个点的坐标
#   - (x_n, y_n) = (x_0, y_0) （闭合多边形）
#
# 为什么只取前10个最大的轮廓？
# 1. 车牌通常是图像中面积较大的四边形
# 2. 但不是最大的（最大的可能是整个车辆轮廓）
# 3. 前10个是计算效率和准确性的平衡：
#    - 太少（如前3个）可能漏检
#    - 太多（如前50个）增加不必要的计算
# 4. 每个轮廓都要进行多边形近似，比较耗时
contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

screenCnt = None
detected = 0
# 查找车牌（近似四边形）
# 遍历前10个最大的轮廓，寻找最可能的车牌轮廓
for c in contours:
    # 计算轮廓的周长
    # 函数: cv2.arcLength()
    # 参数说明:
    #   - c: 输入轮廓（一个numpy数组，包含轮廓上所有点的坐标）
    #   - True: 表示轮廓是闭合的（起点和终点相连）
    # 返回值: peri - 轮廓的周长（浮点数）
    # 
    # 周长计算原理:
    # 计算轮廓上相邻点之间的欧氏距离之和：
    # peri = Σ_{i=0}^{n-1} √((x_{i+1} - x_i)² + (y_{i+1} - y_i)²)
    # 其中n是轮廓上的点数，(x_i, y_i)是第i个点的坐标
    # 对于闭合轮廓，最后一个点与第一个点相连
    peri = cv2.arcLength(c, True)
    
    # 多边形近似
    # 函数: cv2.approxPolyDP()
    # 参数说明:
    #   - c: 输入轮廓
    #   - 0.018 * peri: 近似精度（epsilon值）
    #     表示原始曲线与近似多边形之间的最大距离
    #     epsilon是周长的百分比，0.018表示1.8%
    #   - True: 表示近似后的多边形应该是闭合的
    # 返回值: approx - 近似后的多边形顶点坐标
    #     approx是一个numpy数组，形状为(m,1,2)
    #     m是近似多边形的顶点数
    #
    # Douglas-Peucker算法原理（Ramer-Douglas-Peucker算法）：
    # 1. 在轮廓的起点A和终点B之间画一条直线
    # 2. 找到轮廓上离直线AB最远的点C
    # 3. 计算点C到直线AB的距离d
    # 4. 如果d > epsilon（这里的0.018*peri）：
    #      保留点C，并以点C为分界点，将轮廓分为AC和CB两段
    #      对每一段递归执行步骤1-4
    # 5. 如果d <= epsilon：
    #      丢弃中间所有点，只保留端点A和B
    #
    # 示例：一个复杂轮廓的近似过程
    # 原始轮廓: A---C1---C2---C3---C4-n--C5---B
    # 步骤1: 找到离直线AB最远的点C3
    # 步骤2: 如果距离>epsilon，保留C3，分割为AC3和C3B
    # 步骤3: 对AC3段，找到离直线AC3最远的点C1
    # 步骤4: 如果距离>epsilon，保留C1，分割为AC1和C1C3
    # ... 如此递归，直到所有点到对应直线的距离都<=epsilon
    #
    # 为什么选择0.018作为系数？
    # 这是一个经验值，平衡了准确性和通用性：
    # - 太小（如0.005）：多边形顶点数增加，可能检测到非矩形
    # - 太大（如0.05）：多边形顶点数减少，可能漏检车牌
    # 0.018（1.8%）在大多数车牌图像中表现良好
    approx = cv2.approxPolyDP(c, 0.018 * peri, True)
    
    # 检查近似多边形的顶点数是否为4
    # len(approx)返回近似多边形的顶点数
    # 为什么检查4个顶点？
    # 1. 车牌通常是矩形或接近矩形的四边形
    # 2. 四边形是平面投影下的常见形状
    # 3. 排除三角形、五边形等其他形状
    if len(approx) == 4:
        # 如果找到4个顶点的多边形，认为找到了车牌
        screenCnt = approx  # 保存近似结果
        detected = 1        # 设置检测标志
        break  # 跳出循环，不再检查其他轮廓
        
# 注意：这里只检查顶点的数量，没有检查其他特征
# 可能的误检情况：
# 1. 图像中其他四边形物体（如窗户、广告牌）
# 2. 透视变形严重的车牌（可能被近似为4个以上的顶点）
# 3. 部分遮挡的车牌（顶点数可能不是4个）

if screenCnt is None:
    detected = 0
    print("No contour detected")
else:
    detected = 1

if detected == 1:
    # 创建掩码并提取车牌区域
    # 目标：从原始图像中精确提取车牌区域，去除背景
    
    # 步骤1: 创建掩码（mask）
    # np.zeros()创建一个与原始灰度图像相同大小的全黑（0）矩阵
    # 参数说明：
    #   - gray.shape: 获取灰度图像的尺寸（高度, 宽度）
    #   - np.uint8: 指定数据类型为8位无符号整数（0-255）
    # 掩码的作用：定义图像中哪些区域应该被处理/提取
    # 初始状态：所有像素都是0（黑色），表示"不选择"
    mask = np.zeros(gray.shape, np.uint8)
    
    # 步骤2: 在掩码上绘制检测到的车牌轮廓
    # 函数: cv2.drawContours()
    # 参数说明：
    #   - mask: 目标图像（我们创建的掩码）
    #   - [screenCnt]: 要绘制的轮廓列表（必须放在列表中）
    #   - 0: 轮廓的索引（0表示绘制第一个轮廓）
    #   - 255: 轮廓的颜色（白色，表示"选择"）
    #   - -1: 线宽，-1表示填充轮廓内部
    #
    # 执行效果：
    # 在掩码上，车牌轮廓内部被填充为白色（255），外部保持黑色（0）
    # 相当于创建了一个"选择区域"，白色区域是我们要提取的车牌
    #
    # 示例：假设车牌轮廓是一个矩形
    # 掩码创建前：全黑图像
    # 掩码创建后：矩形内部为白色，其余为黑色
    new_image = cv2.drawContours(mask, [screenCnt], 0, 255, -1)
    
    # 步骤3: 使用掩码提取车牌区域
    # 函数: cv2.bitwise_and()
    # 参数说明：
    #   - img: 原始彩色图像
    #   - img: 第二个输入图像（这里用同一个）
    #   - mask=mask: 掩码，只对掩码为白色的区域进行操作
    #
    # 工作原理（按位与操作）：
    # 对于每个像素点(x,y)：
    #   如果 mask(x,y) != 0（即白色）: dst(x,y) = src1(x,y) & src2(x,y)
    #   如果 mask(x,y) == 0（即黑色）: dst(x,y) = 0
    #
    # 由于src1和src2是同一张图，所以按位与后像素值不变
    # 但受掩码影响：
    #   - 掩码白色区域：保留原始像素值
    #   - 掩码黑色区域：像素值变为0（黑色）
    #
    # 结果：new_image中只有车牌区域可见，其余区域为黑色
    new_image = cv2.bitwise_and(img, img, mask=mask)
    
    # 步骤4: 获取车牌的边界框
    # 目标：找到掩码中白色区域的精确坐标范围
    # 函数: np.where()
    # 作用：返回数组中满足条件的元素索引
    # 参数：mask == 255 找到所有值为255（白色）的像素
    # 返回值：
    #   - x: 包含所有白色像素行坐标（y坐标）的数组
    #   - y: 包含所有白色像素列坐标（x坐标）的数组
    # 注意：numpy数组索引是(行,列)，即(高度,宽度)，对应(y,x)
    (x, y) = np.where(mask == 255)
    
    # 步骤5: 计算边界框的坐标
    # 目标：找到包含所有白色像素的最小矩形区域
    # 函数: np.min() 和 np.max()
    # 计算逻辑：
    #   - topx: 所有白色像素的最小行坐标（y方向最小值，上边界）
    #   - topy: 所有白色像素的最小列坐标（x方向最小值，左边界）
    #   - bottomx: 所有白色像素的最大行坐标（y方向最大值，下边界）
    #   - bottomy: 所有白色像素的最大列坐标（x方向最大值，右边界）
    #
    # 示例：如果白色像素分布在行100-150，列200-300之间
    # 则：topx=100, topy=200, bottomx=150, bottomy=300
    (topx, topy) = (np.min(x), np.min(y))
    (bottomx, bottomy) = (np.max(x), np.max(y))
    
    # 步骤6: 裁剪车牌区域
    # 目标：从原始灰度图中提取车牌区域
    # 语法: gray[行范围, 列范围]
    # 参数说明：
    #   - topx:bottomx+1 → 行范围（高度方向），+1是因为Python切片是左闭右开
    #   - topy:bottomy+1 → 列范围（宽度方向），+1同上
    #
    # 注意：我们使用gray（灰度图）而不是img（彩色图）进行裁剪
    # 原因：1. OCR通常对灰度图效果更好
    #       2. 之前所有处理都是在灰度图上进行的
    Cropped = gray[topx:bottomx+1, topy:bottomy+1]
    
    # 创建临时文件保存裁剪的车牌图像
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        temp_image_path = tmp_file.name
        cv2.imwrite(temp_image_path, Cropped)
    
    try:
        # 通过命令行调用Tesseract OCR
        # 使用PSM 11模式：稀疏文本，以任意顺序查找尽可能多的文本
        result = subprocess.run(
            ['tesseract', temp_image_path, 'stdout', '--psm', '11'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 获取OCR识别结果
        text = result.stdout.strip()
        
        # 清理文本（只保留字母、数字和空格）
        cleaned_text = ''.join(c for c in text if c.isalnum() or c.isspace())
        
        print("License Plate Recognition Results")
        print("=" * 40)
        print(f"Detected license plate number: {cleaned_text}")
        print(f"Raw OCR output: {text}")
        
    except subprocess.CalledProcessError as e:
        print(f"Tesseract error: {e}")
        print(f"Error output: {e.stderr}")
    except FileNotFoundError:
        print("Error: tesseract command not found. Please install Tesseract OCR:")
        print("  sudo apt update")
        print("  sudo apt install tesseract-ocr")
    finally:
        # 清理临时文件
        if os.path.exists(temp_image_path):
            os.unlink(temp_image_path)
    
    # 调整图像大小以便显示
    img_display = cv2.resize(img, (500, 300))
    cropped_display = cv2.resize(Cropped, (400, 200))
    
    # 显示结果
    cv2.imshow('Original Image with License Plate Detection', img_display)
    cv2.imshow('Cropped License Plate', cropped_display)
    
    # 等待按键
    print("\nPress any key on the image window to exit...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
else:
    print("License plate not detected")
    cv2.imshow('Processed Image', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()