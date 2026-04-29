import cv2
import numpy as np
import time
import libcamera # 载入 libcamera 用于设置高级属性
from picamera2 import Picamera2 # 载入 picamera2 操作 CSI 摄像头

print(cv2.__version__)

# 创建 Picamera2 对象，实例化摄像头
picamera = Picamera2()

# 配置预览流
config = picamera.create_preview_configuration(
    main={"format": "RGB888", "size": (2080, 2080)},
    raw={"format": "SRGGB12", "size": (1920, 1080)}
)
# 设置摄像头是否水平翻转或者垂直翻转
config["transform"] = libcamera.Transform(hflip=0, vflip=1)
# 让设置生效
picamera.configure(config)

# 启动摄像头
picamera.start()
time.sleep(2)  # 等待自动曝光和白平衡稳定

# 创建窗口
cv2.namedWindow("CSI Camera Preview", cv2.WINDOW_NORMAL)

try:
    while True:
        # 捕获一帧
        frame = picamera.capture_array("main")  # 明确指定 main stream

        # 用 OpenCV 显示
        cv2.imshow("CSI Camera Preview", frame)

        # 按 'q' 键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
except KeyboardInterrupt:
    print("用户中断")
finally:
    # 释放资源
    picamera.stop()
    cv2.destroyAllWindows()