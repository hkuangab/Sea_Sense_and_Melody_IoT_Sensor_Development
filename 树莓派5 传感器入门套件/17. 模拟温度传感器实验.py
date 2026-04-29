# 导入必要的库文件
from gpiozero import Button, MCP3008
from signal import pause
from time import sleep, time
import math
from collections import deque
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd
import os
import openpyxl
from openpyxl import Workbook
from openpyxl.drawing.image import Image

# 数据记录配置
EXCEL_FILE = "temperature_data.xlsx"
PLOT_FILE = "temperature_chart.png"
MAX_DATA_POINTS = 1000  # 最大数据点数
DATA_RECORD_INTERVAL = 1  # 数据记录间隔（秒）

# 定义温度传感器使用通道和数字引脚
makerobo_DO = Button(17)  # 数字输出引脚，用于检测是否过热
makerobo_tempPin = MCP3008(channel=0)  # 模拟输入引脚，用于读取温度值

# 温度检测参数配置
COLD_THRESHOLD = 20.0    # 冷阈值
HOT_THRESHOLD = 30.0     # 热阈值
HYSTERESIS = 0.5         # 迟滞值

# 设置移动平均窗口大小
MOVING_AVG_WINDOW = 10   # 移动平均窗口大小（采样点数）

# 设置温度变化率检测参数
RATE_CHANGE_THRESHOLD = 0.5  # 摄氏度/秒，温度快速变化的阈值

# 初始化温度历史记录
temperature_history = deque(maxlen=MOVING_AVG_WINDOW)  # 存储温度历史记录
time_history = deque(maxlen=MOVING_AVG_WINDOW)         # 存储时间戳历史记录

# 数据记录相关变量
data_buffer = []  # 数据缓冲区
last_record_time = 0
data_counter = 0
excel_wb = None
excel_ws = None
excel_row = 1  # Excel行计数器

# 定义打印函数
def makerobo_Print(temp_category, temp_c, rate_of_change=None):
    """
    根据温度状态打印提示信息
    """
    if temp_category == 0:
        message = f"COLD! Temperature: {temp_c:.2f}°C"
    elif temp_category == 1:
        message = f"Normal Temperature: {temp_c:.2f}°C"
    else:
        message = f"HOT! Temperature: {temp_c:.2f}°C"
    
    if rate_of_change is not None:
        if rate_of_change > RATE_CHANGE_THRESHOLD:
            message += f" | Warming rapidly: {rate_of_change:.2f}°C/s"
        elif rate_of_change < -RATE_CHANGE_THRESHOLD:
            message += f" | Cooling rapidly: {abs(rate_of_change):.2f}°C/s"
    
    print(message)

# 计算移动平均温度
def calculate_moving_average(new_temp, new_time):
    """
    计算移动平均温度
    """
    temperature_history.append(new_temp)
    time_history.append(new_time)
    
    if len(temperature_history) < 2:
        return new_temp, 0.0
    
    avg_temp = sum(temperature_history) / len(temperature_history)
    
    if len(temperature_history) >= 3:
        recent_temps = list(temperature_history)[-3:]
        recent_times = list(time_history)[-3:]
        
        n = len(recent_temps)
        sum_xy = sum(recent_temps[i] * recent_times[i] for i in range(n))
        sum_x = sum(recent_times)
        sum_y = sum(recent_temps)
        sum_x2 = sum(t * t for t in recent_times)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator != 0:
            rate_of_change = (n * sum_xy - sum_x * sum_y) / denominator
        else:
            rate_of_change = 0.0
    else:
        rate_of_change = 0.0
    
    return avg_temp, rate_of_change

# 温度状态分类函数（带迟滞）
class TemperatureClassifier:
    def __init__(self, cold_thresh, hot_thresh, hysteresis):
        self.cold_thresh = cold_thresh
        self.hot_thresh = hot_thresh
        self.hysteresis = hysteresis
        self.current_state = 1
        self.last_print_state = 1
    
    def classify(self, temperature):
        if self.current_state == 0:
            if temperature > self.cold_thresh + self.hysteresis:
                self.current_state = 1
        elif self.current_state == 1:
            if temperature < self.cold_thresh - self.hysteresis:
                self.current_state = 0
            elif temperature > self.hot_thresh + self.hysteresis:
                self.current_state = 2
        else:
            if temperature < self.hot_thresh - self.hysteresis:
                self.current_state = 1
        
        return self.current_state

# 初始化Excel文件
def initialize_excel_file():
    """
    初始化Excel工作簿并设置表头
    """
    global excel_wb, excel_ws, excel_row
    
    # 创建新的工作簿
    excel_wb = Workbook()
    excel_ws = excel_wb.active
    excel_ws.title = "Temperature Data"
    
    # 设置表头
    excel_ws['A1'] = "Timestamp"
    excel_ws['B1'] = "Empirical Temperature (°C)"
    excel_ws['C1'] = "Average Temperature (°C)"
    excel_ws['D1'] = "State"
    excel_ws['E1'] = "Rate of Change (°C/s)"
    excel_ws['F1'] = "Digital Sensor State"
    
    # 设置列宽
    excel_ws.column_dimensions['A'].width = 20
    excel_ws.column_dimensions['B'].width = 25
    excel_ws.column_dimensions['C'].width = 25
    excel_ws.column_dimensions['D'].width = 15
    excel_ws.column_dimensions['E'].width = 25
    excel_ws.column_dimensions['F'].width = 25
    
    # 设置表头样式
    for cell in ['A1', 'B1', 'C1', 'D1', 'E1', 'F1']:
        excel_ws[cell].font = openpyxl.styles.Font(bold=True)
        excel_ws[cell].fill = openpyxl.styles.PatternFill(start_color="CCCCCC", 
                                                          end_color="CCCCCC", 
                                                          fill_type="solid")
    
    excel_row = 2
    print(f"Excel file initialized: {EXCEL_FILE}")

# 记录数据到Excel文件
def record_data_to_excel(timestamp, raw_temp, avg_temp, state, rate_of_change, digital_state):
    """
    记录温度数据到Excel文件
    """
    global excel_wb, excel_ws, excel_row, data_buffer, data_counter
    
    # 将数据添加到缓冲区
    data_entry = {
        'timestamp': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
        'raw_temperature': raw_temp,
        'avg_temperature': avg_temp,
        'state': state,
        'rate_of_change': rate_of_change,
        'digital_state': digital_state
    }
    
    data_buffer.append(data_entry)
    data_counter += 1
    
    # 定期写入Excel文件
    if data_counter >= 10:  # 每10个数据点写入一次
        save_data_to_excel()
        data_counter = 0

# 保存数据到Excel文件
def save_data_to_excel():
    """
    将缓冲区中的数据保存到Excel文件
    """
    global excel_wb, excel_ws, excel_row, data_buffer
    
    if not data_buffer or excel_wb is None:
        return
    
    try:
        for entry in data_buffer:
            # 写入时间戳
            excel_ws.cell(row=excel_row, column=1, value=entry['timestamp'])
            
            # 写入经验温度
            excel_ws.cell(row=excel_row, column=2, value=float(entry['raw_temperature']))
            
            # 写入平均温度
            excel_ws.cell(row=excel_row, column=3, value=float(entry['avg_temperature']))
            
            # 写入状态
            state_names = ['Cold', 'Normal', 'Hot']
            excel_ws.cell(row=excel_row, column=4, value=state_names[entry['state']])
            
            # 写入变化率
            excel_ws.cell(row=excel_row, column=5, value=float(entry['rate_of_change']))
            
            # 写入数字传感器状态
            excel_ws.cell(row=excel_row, column=6, value=entry['digital_state'])
            
            # 设置数字格式
            for col in [2, 3, 5]:  # 温度列和变化率列
                excel_ws.cell(row=excel_row, column=col).number_format = '0.00'
            
            excel_row += 1
        
        # 保存Excel文件
        excel_wb.save(EXCEL_FILE)
        data_buffer = []  # 清空缓冲区
        print(f"Data saved to Excel file: {EXCEL_FILE} (Row: {excel_row-1})")
        
    except Exception as e:
        print(f"Error saving to Excel: {e}")

# 生成温度曲线图并嵌入到Excel
def generate_temperature_plot():
    """
    从Excel文件读取数据并生成温度曲线图
    """
    try:
        if not os.path.exists(EXCEL_FILE):
            print(f"No Excel file found: {EXCEL_FILE}")
            return
        
        # 读取Excel数据
        df = pd.read_excel(EXCEL_FILE, sheet_name=0)
        
        if len(df) < 2:
            print(f"Not enough data points ({len(df)}) to generate plot")
            return
        
        # 获取时间戳和温度数据
        timestamps = df.iloc[:, 0]  # 第一列是时间戳
        empirical_temp = df.iloc[:, 1]  # 第二列是经验温度
        avg_temp = df.iloc[:, 2]  # 第三列是平均温度
        
        # 创建图形
        plt.figure(figsize=(12, 8))
        
        # 绘制经验温度曲线
        plt.plot(timestamps, empirical_temp, 
                label=f'Empirical Temperature (Min: {empirical_temp.min():.1f}°C, Max: {empirical_temp.max():.1f}°C)',
                color='blue', linewidth=1.5, alpha=0.8, marker='o', markersize=3)
        
        # 绘制平均温度曲线
        plt.plot(timestamps, avg_temp, 
                label=f'Average Temperature (Min: {avg_temp.min():.1f}°C, Max: {avg_temp.max():.1f}°C)',
                color='red', linewidth=2, alpha=0.8, marker='s', markersize=3)
        
        # 添加阈值线
        plt.axhline(y=HOT_THRESHOLD, color='darkred', linestyle='--', alpha=0.6, 
                   label=f'Hot Threshold ({HOT_THRESHOLD}°C)')
        plt.axhline(y=COLD_THRESHOLD, color='darkblue', linestyle='--', alpha=0.6, 
                   label=f'Cold Threshold ({COLD_THRESHOLD}°C)')
        
        # 设置图表属性
        plt.xlabel('Time', fontsize=12, fontweight='bold')
        plt.ylabel('Temperature (°C)', fontsize=12, fontweight='bold')
        plt.title('Temperature Monitoring: Empirical vs Average Temperature', fontsize=14, fontweight='bold')
        plt.legend(loc='best', fontsize=10)
        plt.grid(True, alpha=0.3, linestyle='--')
        plt.xticks(rotation=45, ha='right')
        
        # 设置y轴范围
        temp_min = min(empirical_temp.min(), avg_temp.min(), COLD_THRESHOLD) - 2
        temp_max = max(empirical_temp.max(), avg_temp.max(), HOT_THRESHOLD) + 2
        plt.ylim(temp_min, temp_max)
        
        # 添加统计信息
        stats_text = f"Data Statistics:\n"
        stats_text += f"Total Measurements: {len(df)}\n"
        stats_text += f"Empirical Temp Range: {empirical_temp.min():.2f}°C to {empirical_temp.max():.2f}°C\n"
        stats_text += f"Average Temp Range: {avg_temp.min():.2f}°C to {avg_temp.max():.2f}°C\n"
        stats_text += f"Empirical Mean: {empirical_temp.mean():.2f}°C\n"
        stats_text += f"Average Mean: {avg_temp.mean():.2f}°C"
        
        plt.figtext(0.02, 0.02, stats_text, fontsize=9, 
                   bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8))
        
        # 自动调整布局
        plt.tight_layout()
        
        # 保存图表
        plt.savefig(PLOT_FILE, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 将图表插入到Excel文件中
        embed_plot_in_excel()
        
        print(f"Temperature plot saved to {PLOT_FILE}")
        print(f"Plot embedded in Excel file: {EXCEL_FILE}")
        
        # 在终端显示数据统计
        print("\n" + "="*60)
        print("TEMPERATURE DATA SUMMARY")
        print("="*60)
        print(f"Total data points: {len(df)}")
        print(f"Data collection period: {timestamps.iloc[0]} to {timestamps.iloc[-1]}")
        print(f"Empirical temperature range: {empirical_temp.min():.2f}°C to {empirical_temp.max():.2f}°C")
        print(f"Average temperature range: {avg_temp.min():.2f}°C to {avg_temp.max():.2f}°C")
        print(f"Empirical temperature mean: {empirical_temp.mean():.2f}°C")
        print(f"Average temperature mean: {avg_temp.mean():.2f}°C")
        print(f"Excel file saved to: {EXCEL_FILE}")
        print(f"Plot saved to: {PLOT_FILE}")
        print("="*60)
        
    except Exception as e:
        print(f"Error generating plot: {e}")

# 将图表嵌入到Excel文件中
def embed_plot_in_excel():
    """
    将生成的图表嵌入到Excel文件中
    """
    global excel_wb, excel_ws
    
    try:
        if not os.path.exists(PLOT_FILE) or excel_wb is None:
            return
        
        # 创建一个新的工作表用于图表
        if "Temperature Plot" in excel_wb.sheetnames:
            plot_sheet = excel_wb["Temperature Plot"]
        else:
            plot_sheet = excel_wb.create_sheet(title="Temperature Plot")
        
        # 清除现有内容
        plot_sheet.delete_rows(1, plot_sheet.max_row)
        
        # 添加标题
        plot_sheet['A1'] = "Temperature Monitoring Plot"
        plot_sheet['A1'].font = openpyxl.styles.Font(bold=True, size=14)
        
        # 插入图表图片
        img = Image(PLOT_FILE)
        
        # 调整图片大小
        img.width = 700
        img.height = 500
        
        # 将图片添加到工作表
        plot_sheet.add_image(img, 'A3')
        
        # 保存Excel文件
        excel_wb.save(EXCEL_FILE)
        
    except Exception as e:
        print(f"Error embedding plot in Excel: {e}")

# 主循环函数
def makerobo_loop():
    """
    主循环函数，包含数据记录功能
    """
    global last_record_time
    
    # 初始化Excel文件
    initialize_excel_file()
    
    # 初始化温度分类器
    temp_classifier = TemperatureClassifier(COLD_THRESHOLD, HOT_THRESHOLD, HYSTERESIS)
    makerobo_status = 1
    start_time = time()
    last_record_time = start_time
    
    print(f"Data will be recorded to Excel file: {EXCEL_FILE}")
    print(f"Temperature plot will be saved to: {PLOT_FILE}")
    print(f"Recording interval: {DATA_RECORD_INTERVAL} seconds")
    print(f"Temperature thresholds: Cold < {COLD_THRESHOLD}°C, Hot > {HOT_THRESHOLD}°C")
    print("-" * 60)
    
    while True:
        current_time = time()
        
        # 读取模拟温度传感器
        makerobo_analogVal = makerobo_tempPin.value
        makerobo_Vr = float(makerobo_analogVal * 3.3)
        
        # 计算电阻和温度
        makerobo_Rt = 10000 * makerobo_Vr / (3.3 - makerobo_Vr)
        makerobo_temp = 1 / (((math.log(makerobo_Rt / 10000)) / 3950) + (1 / (273.15 + 25)))
        temp_c = makerobo_temp - 273.15
        
        # 计算移动平均温度和变化率
        avg_temp, rate_of_change = calculate_moving_average(temp_c, current_time)
        
        # 使用分类器判断温度状态
        temp_state = temp_classifier.classify(avg_temp)
        
        # 读取数字温度传感器状态
        makerobo_tmp = not makerobo_DO.is_pressed
        digital_state_str = "Normal" if makerobo_tmp else "Hot"
        
        # 如果状态发生变化，则打印
        if temp_state != temp_classifier.last_print_state:
            makerobo_Print(temp_state, avg_temp, rate_of_change)
            temp_classifier.last_print_state = temp_state
        
        # 记录数据到Excel文件
        if current_time - last_record_time >= DATA_RECORD_INTERVAL:
            record_data_to_excel(current_time, temp_c, avg_temp, temp_state, 
                               rate_of_change, digital_state_str)
            last_record_time = current_time
        
        # 打印详细温度信息（每秒一次）
        if int(current_time) % 1 == 0:
            state_names = ['Cold', 'Normal', 'Hot']
            elapsed_time = current_time - start_time
            hours = int(elapsed_time // 3600)
            minutes = int((elapsed_time % 3600) // 60)
            seconds = int(elapsed_time % 60)
            
            print(f"Time: {hours:02d}:{minutes:02d}:{seconds:02d} | "
                  f"Empirical: {temp_c:.2f}°C | Average: {avg_temp:.2f}°C | "
                  f"Rate: {rate_of_change:+.2f}°C/s | State: {state_names[temp_state]} | "
                  f"Digital: {digital_state_str}")
            print("-" * 60)
        
        # 检测数字传感器的状态变化
        if makerobo_tmp != makerobo_status:
            print(f"Digital sensor state changed: {'Normal' if makerobo_tmp else 'Hot (Digital)'}")
            makerobo_status = makerobo_tmp
        
        # 短暂延时
        sleep(0.2)

# 程序入口
if __name__ == "__main__":
    print("="*60)
    print("TEMPERATURE MONITORING AND DATA LOGGING SYSTEM")
    print("="*60)
    print(f"Cold threshold: {COLD_THRESHOLD}°C")
    print(f"Hot threshold: {HOT_THRESHOLD}°C")
    print(f"Hysteresis: {HYSTERESIS}°C")
    print(f"Moving average window: {MOVING_AVG_WINDOW}")
    print(f"Rate change threshold: {RATE_CHANGE_THRESHOLD}°C/s")
    print(f"Data record interval: {DATA_RECORD_INTERVAL} second(s)")
    print("="*60)
    print("Starting temperature monitoring...")
    print("Press Ctrl+C to stop the program")
    print("="*60)
    
    try:
        makerobo_loop()
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("Program terminated by user.")
        print("Saving remaining data and generating plot...")
        print("="*60)
        
        # 保存剩余的数据
        if data_buffer:
            save_data_to_excel()
        
        # 生成温度曲线图
        generate_temperature_plot()
        
        print("\n" + "="*60)
        print("DATA LOGGING COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("Files generated:")
        print(f"1. Excel data file: {EXCEL_FILE}")
        print(f"   - Contains columns: Empirical Temperature, Average Temperature")
        print(f"   - Contains {excel_row-2} data points")
        print(f"2. Temperature plot: {PLOT_FILE}")
        print(f"   - Contains both Empirical and Average temperature curves")
        print("="*60)
        print("\nYou can now:")
        print("1. Open the Excel file to view all temperature data")
        print("2. View the temperature plot in the 'Temperature Plot' sheet")
        print("3. Analyze the temperature trends and statistics")
        print("="*60)