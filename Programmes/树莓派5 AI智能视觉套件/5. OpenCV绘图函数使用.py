# 载入库
import cv2
import numpy as np
from matplotlib import pyplot as plt

# ============================================================
# 第一部分：绘制英国国旗 (Union Jack)
# ============================================================

# 创建一个512x512的蓝色画布
image = np.full((512, 512, 3), (255, 0, 0), np.uint8)

# 定义常用颜色的BGR值
white = (255, 255, 255)  # 白色
red = (0, 0, 255)        # 红色

# 画白色对角线十字
cv2.line(image, (0, 0), (512, 512), white, 80)
cv2.line(image, (512, 0), (0, 512), white, 80)

# 画红色对角线十字
cv2.line(image, (0, 0), (512, 512), red, 50)
cv2.line(image, (512, 0), (0, 512), red, 50)

# 画白色水平十字
cv2.line(image, (0, 256), (512, 256), white, 80)
cv2.line(image, (256, 0), (256, 512), white, 80)

# 画红色水平十字
cv2.line(image, (0, 256), (512, 256), red, 50)
cv2.line(image, (256, 0), (256, 512), red, 50)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 使用matplotlib显示图像
plt.figure(figsize=(10, 7))
plt.imshow(image)
plt.title('Union Jack\nBritish Flag Created Using OpenCV', fontsize=18)
plt.xticks([]), plt.yticks([])
plt.tight_layout()
plt.show(block=False)
plt.pause(2)
plt.close()

# ============================================================
# 第二部分：绘制彩虹色同心矩形 (Rainbow Concentric Rectangles)
# ============================================================

# 创建一个512x512的黑色画布
image = np.zeros((512, 512, 3), np.uint8)

# 绘制多个同心矩形
num_rectangles = 20

for i in range(num_rectangles):
    offset = i * 12
    top_left = (offset, offset)
    bottom_right = (512 - offset, 512 - offset)
    
    if top_left[0] < bottom_right[0]:
        # 彩虹渐变颜色计算
        ratio = i / num_rectangles  # 0.0 ~ 1.0
        
        if ratio < 0.17:  # 红色 -> 橙色 (0.0 ~ 0.17)
            r, g, b = 255, int(255 * (ratio / 0.17)), 0
        elif ratio < 0.33:  # 橙色 -> 黄色 (0.17 ~ 0.33)
            r, g, b = 255, 255, int(255 * ((ratio - 0.17) / 0.16))
        elif ratio < 0.50:  # 黄色 -> 绿色 (0.33 ~ 0.50)
            r, g, b = int(255 * (1 - (ratio - 0.33) / 0.17)), 255, 0
        elif ratio < 0.67:  # 绿色 -> 青色 (0.50 ~ 0.67)
            r, g, b = 0, 255, int(255 * ((ratio - 0.50) / 0.17))
        elif ratio < 0.83:  # 青色 -> 蓝色 (0.67 ~ 0.83)
            r, g, b = 0, int(255 * (1 - (ratio - 0.67) / 0.16)), 255
        else:              # 蓝色 -> 紫色 (0.83 ~ 1.0)
            r, g, b = int(128 * ((ratio - 0.83) / 0.17)), 0, 255
        
        color = (b, g, r)  # 转换为 BGR 格式
        
        cv2.rectangle(image, top_left, bottom_right, color, -1)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 显示图像
plt.figure(figsize=(8, 8))
plt.imshow(image)
plt.title('Rainbow Concentric Rectangles', fontsize=14)
plt.xticks([]), plt.yticks([])
plt.show(block=False)
plt.pause(2)
plt.close()

# ============================================================
# 第三部分：绘制精确的奥林匹克五环 (带交叉效果)
# ============================================================

# 创建一个512x512的白色画布
image = np.ones((512, 512, 3), np.uint8) * 255  # 白色背景

# 定义五环的颜色 (BGR格式)
blue = (255, 0, 0)       # 蓝色
yellow = (0, 255, 255)   # 黄色
black = (0, 0, 0)       # 黑色
green = (0, 255, 0)     # 绿色
red = (0, 0, 255)       # 红色

# 五环的参数
ring_radius = 45
ring_thickness = 10
center_y_top = 180
center_y_bottom = 250

# 圆心坐标
centers = {
    'blue': (100, center_y_top),
    'black': (150, center_y_top),
    'red': (200, center_y_top),
    'yellow': (125, center_y_bottom),
    'green': (175, center_y_bottom)
}

# 绘制所有五环
cv2.circle(image, centers['blue'], ring_radius, blue, ring_thickness)
cv2.circle(image, centers['yellow'], ring_radius, yellow, ring_thickness)
cv2.circle(image, centers['black'], ring_radius, black, ring_thickness)
cv2.circle(image, centers['green'], ring_radius, green, ring_thickness)
cv2.circle(image, centers['red'], ring_radius, red, ring_thickness)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 显示图像
plt.figure(figsize=(8, 8))
plt.imshow(image)
plt.title('Olympic Rings', fontsize=14)
plt.xticks([]), plt.yticks([])
plt.show(block=False)
plt.pause(2)
plt.close()

# ============================================================
# 第四部分：绘制花朵图案 (Flower Pattern)
# ============================================================

# 创建一个512x512的白色画布
image = np.ones((512, 512, 3), np.uint8) * 255  # 白色背景

# 绘制8个椭圆组成花朵形状
center = (256, 256)
colors = [
    (255, 0, 0),      # 红
    (0, 255, 0),      # 绿
    (0, 0, 255),      # 蓝
    (255, 255, 0),    # 黄
    (255, 0, 255),    # 品红
    (0, 255, 255),    # 青
    (255, 128, 0),    # 橙
    (128, 0, 255),    # 紫
]

for i in range(8):
    angle = i * 45  # 每45度一个椭圆
    color = colors[i]
    cv2.ellipse(image, center, (80, 40), angle, 0, 360, color, -1)

# 添加花心
cv2.circle(image, center, 25, (255, 255, 0), -1)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 显示图像
plt.figure(figsize=(8, 8))
plt.imshow(image)
plt.title('Flower Pattern', fontsize=14)
plt.xticks([]), plt.yticks([]) # 隐藏 x 轴和 y 轴上的刻度值
plt.show(block=False)
plt.pause(2)
plt.close()

# ============================================================
# 第五部分：绘制多边形 (Polygon)
# ============================================================

# 创建一个512x512的黑色画布
image = np.zeros((512, 512, 3), np.uint8)

# 定义多边形的四个顶点
# 每个点用 [x, y] 坐标表示
# 注意：OpenCV中坐标系原点(0,0)在左上角
# - x轴向右为正方向
# - y轴向下为正方向
pts = np.array([[10, 50],    # 点1：左上区域
                [400, 50],   # 点2：右上区域
                [90, 200],   # 点3：中间偏左
                [50, 500]],  # 点4：左下区域
               np.int32)     # 指定数据类型为32位整数

# 打印原始数组的形状
# 输出：(4, 2) 表示4个点，每个点有2个坐标值(x,y)
print(pts.shape)

# 将点的数组形状调整为 OpenCV 要求的格式
# reshape((-1, 1, 2)) 的作用：
# - -1：自动计算该维度的大小
# - 1：每个点作为一个单独的元素
# - 2：每个点包含2个坐标值
# 调整后形状为 (4, 1, 2)
# 这是 cv2.polylines() 函数要求的输入格式
pts = pts.reshape((-1, 1, 2))

# 打印调整后的数组形状
# 输出：(4, 1, 2) 表示4个点，每点1组坐标，每组2个值
print(pts.shape)

# 使用 cv2.polylines() 函数绘制多边形
# 参数说明：
# - image：要绘制的图像画布
# - [pts]：点的数组(需要用方括号括起来)
# - True：闭合多边形(True=首尾相连, False=不闭合)
# - (0, 0, 255)：线条颜色，BGR格式，这里是红色
# - 3：线条粗细，单位为像素
cv2.polylines(image, [pts], True, (0, 0, 255), 3)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 显示图像
plt.figure(figsize=(8, 8))
plt.imshow(image)
plt.title('Polygon', fontsize=14)
plt.xticks([]), plt.yticks([])
plt.show(block=False)
plt.pause(2)
plt.close()

# ============================================================
# 第六部分：绘制文字 (Text)
# ============================================================

# 创建一个512x512的黑色画布
image = np.zeros((512, 512, 3), np.uint8)

# 使用 cv2.putText() 函数在图像上绘制文字
# 参数说明：
# - image：要绘制的图像画布
# - 'Hello World!'：要绘制的文本内容
# - (75, 290)：文本的起始位置坐标(x, y)
# - cv2.FONT_HERSHEY_COMPLEX：字体类型，这是一种衬线字体
# - 2：字体缩放比例，数值越大字体越大
# - (100, 170, 0)：文字颜色，BGR格式，这里是橄榄绿色
# - 3：线条粗细，单位为像素
cv2.putText(image, 'Hello World!', (75, 290), cv2.FONT_HERSHEY_COMPLEX, 2, (100, 170, 0), 3)

# 将BGR颜色空间转换为RGB
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

# 显示图像
plt.figure(figsize=(8, 8))
plt.imshow(image)
plt.title('Hello World!', fontsize=14)
plt.xticks([]), plt.yticks([]) # 隐藏 x 轴和 y 轴上的刻度值
plt.show()