# 导入必要的库文件
from gpiozero import MCP3008
from time import sleep, time, strftime, localtime
import pandas as pd
import matplotlib.pyplot as plt
import os

# 定义传感器通道
makerobo_PhotoPin = MCP3008(channel=0)

# 熟悉一下这段代码，

# 全局变量初始化
raw_data_buffer = {
    'Timestamp': [],
    'Time_passed_s': [],
    'Raw_Analog_Value': [],  # 原始模拟值（0.0-1.0）
    'Mapped_Value': []       # 映射后的值（0-255）
}
avg_data_buffer = {
    'Timestamp': [],
    'Time_passed_s': [],
    'Avg_Analog_Value': [],  # 平均原始值
    'Avg_Mapped_Value': []  # 平均映射值
}
WINDOW_SIZE = 10
DATA_FILE = "photo_data.xlsx"
start_time = 0

def MAP(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def moving_average(values, window_size):
    if len(values) < window_size:
        return sum(values) / len(values) if values else 0
    return sum(values[-window_size:]) / window_size

def save_to_excel():
    try:
        raw_df = pd.DataFrame({
            'Timestamp': raw_data_buffer['Timestamp'],
            'Time_passed_s': raw_data_buffer['Time_passed_s'],
            'Raw_Analog_Value': raw_data_buffer['Raw_Analog_Value'],
            'Mapped_Value': raw_data_buffer['Mapped_Value']
        })
        
        avg_df = pd.DataFrame({
            'Timestamp': avg_data_buffer['Timestamp'],
            'Time_passed_s': avg_data_buffer['Time_passed_s'],
            'Avg_Analog_Value': avg_data_buffer['Avg_Analog_Value'],
            'Avg_Mapped_Value': avg_data_buffer['Avg_Mapped_Value']
        })
        
        with pd.ExcelWriter(DATA_FILE, engine='openpyxl') as writer:
            raw_df.to_excel(writer, sheet_name='Raw_Data', index=False)
            avg_df.to_excel(writer, sheet_name='Average_Data', index=False)
        
        print(f"Data saved to {DATA_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

def makerobo_loop():
    global start_time
    recent_analog = []  # 存储原始模拟值
    recent_mapped = []  # 存储映射值
    
    start_time = time()
    
    print("Starting sensor data collection...")
    print("Press Ctrl+C to stop and save data.")
    
    try:
        while True:
            current_time = time()
            time_passed = current_time - start_time
            timestamp = strftime("%Y-%m-%d %H:%M:%S", localtime(current_time))
            
            # 读取原始模拟值
            analog_value = makerobo_PhotoPin.value
            
            # 计算映射值
            mapped_value = round(MAP(analog_value, 0, 1, 0, 255))
            
            # 存储原始数据
            raw_data_buffer['Timestamp'].append(timestamp)
            raw_data_buffer['Time_passed_s'].append(round(time_passed, 1))
            raw_data_buffer['Raw_Analog_Value'].append(round(analog_value, 3))
            raw_data_buffer['Mapped_Value'].append(mapped_value)
            
            # 更新最近值列表
            recent_analog.append(analog_value)
            recent_mapped.append(mapped_value)
            if len(recent_analog) > WINDOW_SIZE:
                recent_analog.pop(0)
                recent_mapped.pop(0)
            
            # 计算移动平均值
            avg_analog = moving_average(recent_analog, WINDOW_SIZE)
            avg_mapped = moving_average(recent_mapped, WINDOW_SIZE)
            
            # 存储平均数据
            avg_data_buffer['Timestamp'].append(timestamp)
            avg_data_buffer['Time_passed_s'].append(round(time_passed, 1))
            avg_data_buffer['Avg_Analog_Value'].append(avg_analog)
            avg_data_buffer['Avg_Mapped_Value'].append(avg_mapped)
                       
            # 打印两种值
            print(f'Time: {time_passed:.1f}s, Raw: {analog_value:.3f}, Mapped: {mapped_value}')
            
            if len(raw_data_buffer['Timestamp']) % 50 == 0:
                save_to_excel()
            
            sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nData collection stopped by user.")
        if raw_data_buffer['Timestamp']:
            save_to_excel()
        else:
            print("No data collected.")

if __name__ == "__main__":
    try:
        makerobo_loop()
    except Exception as e:
        print(f"Unexpected error: {e}")