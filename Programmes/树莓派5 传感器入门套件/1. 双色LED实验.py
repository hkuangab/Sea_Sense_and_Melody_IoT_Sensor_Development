# 导入必要的库
from gpiozero import PWMLED
from time import sleep

# 定义颜色范围值
colors = [0xFF00, 0x00FF, 0x0FF0, 0xF00F]
makerobo_pins = (17, 18)  # PIN管脚字典，红色LED接GPIO17，绿色LED接GPIO18

# 实例化LED管脚
p_R = PWMLED(pin=makerobo_pins[0],initial_value = 0, frequency=2000)  # 设置频率为2KHz
p_G = PWMLED(pin=makerobo_pins[1],initial_value = 0, frequency=2000)  # 设置频率为2KHz

# 主程序
def makerobo_pwm_map(x, in_min, in_max, out_min, out_max):
	return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def makerobo_set_Color(col):   # 例如:col = 0x1122
	R_val = col  >> 8
	G_val = col & 0x00FF
	# 把0-255的范围同比例缩小到0-100之间
	R_val = makerobo_pwm_map(R_val, 0, 255, 0, 100)
	G_val = makerobo_pwm_map(G_val, 0, 255, 0, 100)
	
	p_R.value = (R_val)/100.0     # 改变占空比
	p_G.value = (G_val)/100.0     # 改变占空比

# 调用循环函数
def makerobo_loop():
	while True:
		for col in colors:
			makerobo_set_Color(col)
			sleep(0.5)
# 释放资源
def makerobo_destroy():
	p_G.close()
	p_R.close()

# 程序入口
if __name__ == "__main__":
	try:
		makerobo_loop()        # 调用循环函数
	except KeyboardInterrupt:  # 当按下Ctrl+C时，将执行destroy()子程序。
		makerobo_destroy()     # 释放资源
