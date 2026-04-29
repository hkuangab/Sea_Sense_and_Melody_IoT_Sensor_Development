# ========================================
# 树莓派5 AI智能视觉套件 - OpenCV 图像读取与显示示例
# 运行环境：Thonny + 本地桌面环境（接显示器）
# ========================================

# 导入 OpenCV 库（用于图像处理）
import cv2

# 导入 NumPy 库（用于数组操作，OpenCV 依赖它）
import numpy as np

# -------------------------------
# 1. 读取图像文件
# -------------------------------
# 使用 cv2.imread() 从指定路径读取图像
# 参数：图像文件的完整路径
# 返回值：一个 NumPy 数组，表示图像的像素数据（BGR 格式）
input_image = cv2.imread("/home/hkuangab/Desktop/Tutorials/树莓派5 AI智能视觉套件/Images/CLBLOGO.jpg")

# 检查图像是否成功加载
if input_image is None:
    print("错误：无法读取图像，请检查文件路径是否正确！")
else:
    print("图像读取成功！")

    # -------------------------------
    # 转换为灰度图
    # -------------------------------
    gray_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
    print("彩色图已转换为灰度图！")

    # -------------------------------
    # 2. 显示图像（使用 OpenCV 窗口，适合 Thonny）
    # -------------------------------
    cv2.namedWindow("Original Image", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Gray Image", cv2.WINDOW_NORMAL)

    cv2.imshow("Original Image", input_image)
    cv2.imshow("Gray Image", gray_image)

    # -------------------------------
    # 3. 打印图像基本信息
    # -------------------------------
    print("\n【彩色图像信息】")
    print(f"   高度（Height）：{int(input_image.shape[0])} 像素")
    print(f"   宽度（Width）：{int(input_image.shape[1])} 像素")
    print(f"   通道数（Channels）：{int(input_image.shape[2])} （BGR 三通道）")

    print("\n【灰度图像信息】")
    print(f"   高度（Height）：{int(gray_image.shape[0])} 像素")
    print(f"   宽度（Width）：{int(gray_image.shape[1])} 像素")
    print(f"   通道数（Channels）：{len(gray_image.shape)} （灰度图为单通道）")

    # 额外：查看灰度图的像素值范围
    min_val = gray_image.min()
    max_val = gray_image.max()
    mean_val = gray_image.mean()
    print(f"   像素值范围：{min_val} ~ {max_val}")
    print(f"   平均亮度：{mean_val:.2f}")

    # -------------------------------
    # 4. 等待用户按键
    # -------------------------------
    print("\n按任意键关闭图像窗口...")
    key = cv2.waitKey(0)

    if key == ord('q'):
        print("用户按下了 'q' 键，程序退出。")
    else:
        print(f"用户按下了键：{chr(key)}，程序正常结束。")

    # 关闭所有 OpenCV 创建的窗口
    cv2.destroyAllWindows()

    # -------------------------------
    # 5. 保存图像
    # -------------------------------
    cv2.imwrite('output_color.jpg', input_image)
    cv2.imwrite('output_gray.jpg', gray_image)

    print("\n图像已保存为：")
    print("   - output_color.jpg（彩色原图）")
    print("   - output_gray.jpg（灰度图）")