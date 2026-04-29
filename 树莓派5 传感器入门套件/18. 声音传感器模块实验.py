#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声音传感器检测程序 - 校准和记录模式
功能：1. 校准声音传感器确定合适阈值
      2. 等待用户按键盘后开始记录声音
      3. 将记录的声音数据保存到Excel文件
      4. 绘制声音曲线图
"""

# ============================ 导入必要的库 ============================
import sys
import time
import spidev
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from gpiozero import MCP3008
import os

# ============================ 全局变量定义 ============================
sensor = None
spi = None
use_spi_direct = False
calibrated = False
print_threshold = 60
detect_threshold = 90

# ============================ 参数设置 ============================
CALIBRATION_DURATION = 5      # 校准持续时间（秒）
RECORD_DURATION = 10          # 记录持续时间（秒）
RECORD_INTERVAL = 0.1         # 记录间隔（秒）
EXCEL_FILENAME = "sound_data.xlsx"  # Excel文件名
CHART_FILENAME = "sound_chart.png"  # 图表文件名
DEBOUNCE_TIME = 0.5           # 防抖动时间（秒）

# ============================ 检查SPI ============================
def check_spi():
    """
    检查SPI是否可用
    
    返回:
        bool: SPI是否可用
    """
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)  # 打开SPI设备，总线0，设备0
        spi.max_speed_hz = 1000000
        spi.close()
        print("SPI check passed")
        return True
    except Exception as e:
        print(f"SPI check failed: {e}")
        print("Please enable SPI in raspi-config:")
        print("1. Run 'sudo raspi-config'")
        print("2. Go to 'Interface Options'")
        print("3. Select 'SPI' and enable it")
        print("4. Reboot the Raspberry Pi")
        return False

# ============================ 映射函数定义 ============================
def MAP(x, in_min, in_max, out_min, out_max):
    """
    将输入值从一个范围映射到另一个范围
    
    参数:
        x: 输入值
        in_min: 输入最小值
        in_max: 输入最大值
        out_min: 输出最小值
        out_max: 输出最大值
        
    返回:
        映射后的值
    """
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# ============================ 手动读取MCP3008 ============================
def read_mcp3008_channel(channel, spi):
    """
    手动读取MCP3008指定通道的值
    
    参数:
        channel: 通道号 (0-7)
        spi: SPI设备对象
        
    返回:
        int: 读取到的值 (0-1023) 或 -1 表示错误
    """
    if channel < 0 or channel > 7:
        return -1
    
    # MCP3008读取命令
    cmd = 0b11000000 | (channel << 4)
    adc_data = spi.xfer2([cmd, 0])
    adc_value = ((adc_data[0] & 0x03) << 8) + adc_data[1]
    return adc_value

# ============================ 声音传感器初始化 ============================
def initialize_sensor():
    """
    初始化声音传感器
    
    返回:
        tuple: (sensor对象, spi对象, 是否使用直接SPI模式)
    """
    print("Initializing sound sensor...")
    
    try:
        # 尝试使用gpiozero的MCP3008
        makerobo_voiceValuePin = MCP3008(channel=0)
        print("MCP3008 initialized successfully with gpiozero")
        return makerobo_voiceValuePin, None, False
    except Exception as e:
        print(f"gpiozero MCP3008 failed: {e}")
        print("Falling back to manual SPI mode...")
        
        try:
            # 尝试手动初始化SPI
            spi = spidev.SpiDev()
            spi.open(0, 0)  # 总线0，设备0
            spi.max_speed_hz = 1000000
            spi.mode = 0
            print("Manual SPI initialized successfully")
            return None, spi, True
        except Exception as e2:
            print(f"Manual SPI also failed: {e2}")
            return None, None, False

# ============================ 读取声音值 ============================
def read_voice_value():
    """
    读取声音传感器的值
    
    返回:
        float: 声音传感器的值 (0-1范围)
    """
    global sensor, spi, use_spi_direct
    
    if use_spi_direct and spi is not None:
        # 使用手动SPI模式
        raw_value = read_mcp3008_channel(0, spi)
        if raw_value >= 0:
            # MCP3008是10位ADC，返回0-1023
            return raw_value / 1023.0
        else:
            return 0
    elif sensor is not None:
        # 使用gpiozero模式
        return sensor.value
    else:
        return 0

# ============================ 校准模式 ============================
def calibration_mode():
    """
    校准模式：帮助确定合适的阈值
    
    返回:
        tuple: (print_threshold, detect_threshold) 推荐的阈值
    """
    global print_threshold, detect_threshold, calibrated
    
    print("\n" + "="*60)
    print("CALIBRATION MODE")
    print("="*60)
    print("This mode will help you determine the right threshold values.")
    print("Please follow these steps:")
    print("1. Keep quiet for 2 seconds (measure ambient noise)")
    print("2. Then speak normally at 1 meter distance for 3 seconds")
    print(f"\nThe calibration will run for {CALIBRATION_DURATION} seconds.")
    print("="*60)
    
    values = []
    start_time = time.time()
    
    print("\nStarting calibration...")
    print("Time | Raw Value | Mapped Value")
    print("-" * 30)
    
    while time.time() - start_time < CALIBRATION_DURATION:
        try:
            raw_value = read_voice_value()
            mapped_value = round(MAP(raw_value, 0, 1, 0, 255))
            values.append(mapped_value)
            
            elapsed = time.time() - start_time
            print(f"{elapsed:5.1f}s | {raw_value:9.3f} | {mapped_value:13d}")
            
            time.sleep(0.1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(0.1)
    
    # 分析数据
    if values:
        min_val = min(values)
        max_val = max(values)
        avg_val = sum(values) / len(values)
        
        # 计算安静时的平均值（前2秒）
        quiet_values = values[:20] if len(values) >= 20 else values[:int(CALIBRATION_DURATION*10 * 0.4)]
        quiet_avg = sum(quiet_values) / len(quiet_values) if quiet_values else 0
        
        print("\n" + "="*60)
        print("CALIBRATION RESULTS")
        print("="*60)
        print(f"Minimum value: {min_val}")
        print(f"Maximum value: {max_val}")
        print(f"Average value: {avg_val:.1f}")
        print(f"Quiet ambient average: {quiet_avg:.1f}")
        print("\nRECOMMENDED SETTINGS:")
        print("-" * 30)
        
        # 根据数据推荐阈值
        if max_val - quiet_avg < 30:
            print("WARNING: Small difference between quiet and loud sounds.")
            print("You may need to speak louder or adjust sensor position.")
        
        # 推荐阈值
        print_threshold = max(quiet_avg + 10, 30)
        detect_threshold = max(quiet_avg + 30, 80)
        
        print(f"PRINT_THRESHOLD = {int(print_threshold)}")
        print(f"DETECT_THRESHOLD = {int(detect_threshold)}")
        print("\nThese thresholds will be used for recording.")
        print("="*60)
        
        calibrated = True
        return print_threshold, detect_threshold
    
    return 60, 90  # 默认值

# ============================ 记录模式 ============================
def record_mode():
    """
    记录模式：记录声音数据到Excel文件并绘制图表
    
    返回:
        bool: 记录是否成功
    """
    global print_threshold, detect_threshold
    
    print("\n" + "="*60)
    print("RECORDING MODE")
    print("="*60)
    print(f"Recording will start when you press Enter.")
    print(f"Recording duration: {RECORD_DURATION} seconds")
    print(f"Using thresholds - Print: {print_threshold}, Detect: {detect_threshold}")
    print("="*60)
    
    # 等待用户按Enter键开始
    input("Press Enter to start recording...")
    
    # 准备数据存储
    timestamps = []
    raw_values = []
    mapped_values = []
    timestamps_abs = []
    detection_counts = []
    
    start_time = time.time()
    record_count = 0
    detection_count = 0
    last_detection_time = 0
    
    print(f"\nRecording started at {datetime.now().strftime('%H:%M:%S')}")
    print("="*30)
    
    # 3秒倒计时
    for i in range(3, 0, -1):
        print(f"Recording starts in {i}...")
        time.sleep(1)
    
    print("\nRecording NOW! Make some sounds...")
    print("Time | Raw Value | Mapped Value | Status")
    print("-" * 50)
    
    while time.time() - start_time < RECORD_DURATION:
        try:
            # 读取声音值
            raw_value = read_voice_value()
            mapped_value = round(MAP(raw_value, 0, 1, 0, 255))
            
            # 计算相对时间
            elapsed_time = time.time() - start_time
            current_time = datetime.now()
            
            # 检测声音
            current_detection_time = time.time()
            is_detected = False
            
            if (mapped_value > detect_threshold and 
                (current_detection_time - last_detection_time) > DEBOUNCE_TIME):
                detection_count += 1
                last_detection_time = current_detection_time
                is_detected = True
            
            # 存储数据
            timestamps.append(elapsed_time)
            timestamps_abs.append(current_time)
            raw_values.append(raw_value)
            mapped_values.append(mapped_value)
            detection_counts.append(is_detected)
            record_count += 1
            
            # 显示当前值
            status = "Normal"
            if is_detected:
                status = f"DETECTED ({detection_count})"
            elif mapped_value > print_threshold:
                status = "Above Print"
            
            print(f"{elapsed_time:5.1f}s | {raw_value:9.3f} | {mapped_value:13d} | {status}")
            
            time.sleep(RECORD_INTERVAL)
            
        except KeyboardInterrupt:
            print("\nRecording stopped by user.")
            break
        except Exception as e:
            print(f"Error during recording: {e}")
            time.sleep(RECORD_INTERVAL)
    
    # 记录完成
    print(f"\nRecording complete. Recorded {record_count} samples.")
    print(f"Total detections: {detection_count}")
    
    if record_count > 0:
        # 保存数据到Excel
        if save_to_excel(timestamps_abs, timestamps, raw_values, mapped_values, detection_counts):
            # 绘制图表
            plot_recorded_data(timestamps, raw_values, mapped_values, detection_counts)
            print(f"\nData saved to '{EXCEL_FILENAME}'")
            print(f"Chart saved as '{CHART_FILENAME}'")
            return True
        else:
            return False
    else:
        print("No data recorded.")
        return False

# ============================ 保存数据到Excel ============================
def save_to_excel(timestamps_abs, timestamps_rel, raw_values, mapped_values, detection_counts):
    """
    将记录的数据保存到Excel文件
    
    参数:
        timestamps_abs: 绝对时间戳列表
        timestamps_rel: 相对时间戳列表
        raw_values: 原始声音值列表
        mapped_values: 映射后的声音值列表
        detection_counts: 检测状态列表
        
    返回:
        bool: 保存是否成功
    """
    try:
        # 创建DataFrame
        df = pd.DataFrame({
            'Timestamp': timestamps_abs,
            'Time_Seconds': timestamps_rel,
            'Raw_Value': raw_values,
            'Mapped_Value': mapped_values,
            'Detected': detection_counts
        })
        
        # 添加检测统计
        total_detections = sum(detection_counts)
        detection_rate = total_detections / len(detection_counts) if detection_counts else 0
        
        # 使用ExcelWriter创建多sheet的Excel文件
        with pd.ExcelWriter(EXCEL_FILENAME, engine='openpyxl') as writer:
            # 主数据表
            df.to_excel(writer, sheet_name='Sound Data', index=False)
            
            # 统计信息表
            stats_df = pd.DataFrame({
                'Statistic': ['Min', 'Max', 'Average', 'Std Dev', 'Total Detections', 'Detection Rate'],
                'Raw_Value': [df['Raw_Value'].min(), df['Raw_Value'].max(), 
                             df['Raw_Value'].mean(), df['Raw_Value'].std(), '', ''],
                'Mapped_Value': [df['Mapped_Value'].min(), df['Mapped_Value'].max(), 
                                df['Mapped_Value'].mean(), df['Mapped_Value'].std(), '', ''],
                'Detection': ['', '', '', '', total_detections, f'{detection_rate:.2%}']
            })
            stats_df.to_excel(writer, sheet_name='Statistics', index=False)
            
            # 元数据表
            metadata_df = pd.DataFrame({
                'Parameter': ['Recording Duration', 'Sample Interval', 'Total Samples',
                             'Start Time', 'End Time', 'Print Threshold', 'Detect Threshold',
                             'Debounce Time', 'Calibration Status'],
                'Value': [RECORD_DURATION, RECORD_INTERVAL, len(df),
                         timestamps_abs[0].strftime('%Y-%m-%d %H:%M:%S'),
                         timestamps_abs[-1].strftime('%Y-%m-%d %H:%M:%S'),
                         print_threshold, detect_threshold, DEBOUNCE_TIME,
                         'Calibrated' if calibrated else 'Default']
            })
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        print("Data successfully saved to Excel file.")
        return True
        
    except Exception as e:
        print(f"Error saving to Excel: {e}")
        return False

# ============================ 绘制记录数据 ============================
def plot_recorded_data(timestamps, raw_values, mapped_values, detection_counts):
    """
    绘制记录的声音数据图表
    
    参数:
        timestamps: 时间戳列表
        raw_values: 原始声音值列表
        mapped_values: 映射后的声音值列表
        detection_counts: 检测状态列表
    """
    try:
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # 标记检测点
        detection_times = [timestamps[i] for i, detected in enumerate(detection_counts) if detected]
        detection_values = [mapped_values[i] for i, detected in enumerate(detection_counts) if detected]
        
        # 绘制原始值图表
        ax1.plot(timestamps, raw_values, 'b-', linewidth=1, alpha=0.7, label='Raw Value')
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Raw Value (0-1)')
        ax1.set_title('Sound Sensor Raw Data')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # 绘制映射值图表
        ax2.plot(timestamps, mapped_values, 'r-', linewidth=1, alpha=0.7, label='Mapped Value')
        ax2.scatter(detection_times, detection_values, color='green', s=50, 
                   zorder=5, label='Detected Sounds')
        ax2.axhline(y=detect_threshold, color='g', linestyle='--', 
                   label=f'Detect Threshold ({detect_threshold})')
        ax2.axhline(y=print_threshold, color='orange', linestyle='--', 
                   label=f'Print Threshold ({print_threshold})')
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Mapped Value (0-255)')
        ax2.set_title('Sound Sensor Mapped Data with Detections')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        
        # 保存图表
        plt.savefig(CHART_FILENAME, dpi=100)
        plt.close()
        
        print("Chart successfully created and saved.")
        
    except Exception as e:
        print(f"Error creating chart: {e}")

# ============================ 主程序入口 ============================
def main():
    """
    主程序入口
    功能：运行校准，然后等待用户按键开始记录
    """
    global sensor, spi, use_spi_direct, print_threshold, detect_threshold
    
    print("=" * 60)
    print("SOUND SENSOR RECORDING PROGRAM")
    print("=" * 60)
    print("This program will:")
    print("1. Calibrate the sound sensor")
    print("2. Wait for you to press Enter")
    print("3. Record sound for 10 seconds")
    print("4. Save data to Excel and create a chart")
    print("=" * 60)
    
    # 检查SPI
    if not check_spi():
        print("SPI is not available. Attempting to continue anyway...")
    
    # 初始化传感器
    sensor, spi, use_spi_direct = initialize_sensor()
    
    if sensor is None and spi is None:
        print("ERROR: Could not initialize sensor. Exiting.")
        return
    
    if sensor is None and spi is not None:
        print("Using manual SPI mode")
    else:
        print("Using gpiozero MCP3008 mode")
    
    try:
        # 步骤1: 校准传感器
        print("\n" + "="*60)
        print("STEP 1: CALIBRATION")
        print("="*60)
        print_threshold, detect_threshold = calibration_mode()
        
        # 步骤2: 记录声音
        print("\n" + "="*60)
        print("STEP 2: RECORDING")
        print("="*60)
        
        # 询问是否重新校准
        recalibrate = input("\nDo you want to recalibrate? (y/n): ").strip().lower()
        if recalibrate == 'y':
            print_threshold, detect_threshold = calibration_mode()
        
        # 开始记录
        record_success = False
        while not record_success:
            record_success = record_mode()
            
            if not record_success:
                retry = input("\nRecording failed. Try again? (y/n): ").strip().lower()
                if retry != 'y':
                    break
            else:
                # 询问是否查看文件
                view_files = input("\nRecording complete! View files? (y/n): ").strip().lower()
                if view_files == 'y':
                    if os.path.exists(EXCEL_FILENAME):
                        print(f"\nExcel file created: {EXCEL_FILENAME}")
                        print(f"File size: {os.path.getsize(EXCEL_FILENAME)} bytes")
                    
                    if os.path.exists(CHART_FILENAME):
                        print(f"Chart file created: {CHART_FILENAME}")
                        print(f"File size: {os.path.getsize(CHART_FILENAME)} bytes")
        
        print("\n" + "="*60)
        print("PROGRAM COMPLETE")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
    except Exception as e:
        print(f"\nError in main program: {e}")
    finally:
        # 清理资源
        if spi is not None and use_spi_direct:
            spi.close()
            print("SPI connection closed")

# ============================ 程序执行 ============================
if __name__ == "__main__":
    main()