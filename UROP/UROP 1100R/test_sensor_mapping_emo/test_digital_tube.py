from RPLCD.i2c import CharLCD
import RPi.GPIO as GPIO
import time
import datetime

# ================== 液晶屏参数配置 ==================
LCD_I2C_PORT = 1
LCD_COLS = 16
LCD_ROWS = 2

# 常见 I2C 地址列表（自动探测）
POSSIBLE_ADDRESSES = [0x27, 0x3F, 0x20, 0x38, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F]

# ================== 数码管参数配置 ==================
SEG_PINS = [12, 22, 19, 16, 17, 13, 20, 18]
DIG_PINS = [6, 24, 23, 21]
TOUCH_PIN = 5

SEG_CODE = {
    0: [0,0,0,0,0,0,1,1],
    1: [1,0,0,1,1,1,1,1],
    2: [0,0,1,0,0,1,0,1],
    3: [0,0,0,0,1,1,0,1],
    4: [1,0,0,1,1,0,0,1],
    5: [0,1,0,0,1,0,0,1],
    6: [0,1,0,0,0,0,0,1],
    7: [0,0,0,1,1,1,1,1],
    8: [0,0,0,0,0,0,0,1],
    9: [0,0,0,0,1,0,0,1],
}

# ================== 全局变量 ==================
count = 0
last_trigger = 0
lcd_needs_update = False
lcd = None

# ================== 工具函数 ==================
def pad_text(text, width=LCD_COLS):
    return str(text).ljust(width)[:width]

# ================== 数码管函数 ==================
def show_one(pos, num):
    for d in DIG_PINS:
        GPIO.output(d, GPIO.LOW)
    code = SEG_CODE[num]
    for i in range(8):
        GPIO.output(SEG_PINS[i], code[i])
    GPIO.output(DIG_PINS[pos], GPIO.HIGH)

def show_num(val):
    val = max(0, min(9999, val))
    d0 = val // 1000
    d1 = (val % 1000) // 100
    d2 = (val % 100) // 10
    d3 = val % 10
    show_one(0, d0); time.sleep(0.003)
    show_one(1, d1); time.sleep(0.003)
    show_one(2, d2); time.sleep(0.003)
    show_one(3, d3); time.sleep(0.003)

# ================== 触摸中断回调 ==================
def on_touch(channel):
    global count, last_trigger, lcd_needs_update
    now = time.time()
    if now - last_trigger > 0.3:
        count = (count + 1) % 10000
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        print(f'[{timestamp}] Touch! Count = {count:04d}')
        last_trigger = now
        lcd_needs_update = True

# ================== 初始化 ==================
def makerobo_setup():
    global lcd

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for p in SEG_PINS:
        GPIO.setup(p, GPIO.OUT); GPIO.output(p, GPIO.HIGH)
    for p in DIG_PINS:
        GPIO.setup(p, GPIO.OUT); GPIO.output(p, GPIO.LOW)
    GPIO.setup(TOUCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.add_event_detect(TOUCH_PIN, GPIO.RISING, callback=on_touch, bouncetime=300)

    # 自动探测 I2C 地址
    print('Scanning for LCD1602 I2C address...')
    for addr in POSSIBLE_ADDRESSES:
        try:
            lcd = CharLCD(
                i2c_expander='PCF8574',
                address=addr,
                port=LCD_I2C_PORT,
                cols=LCD_COLS,
                rows=LCD_ROWS,
                dotsize=8
            )
            print(f'  ✅ LCD1602 found at I2C address 0x{addr:02X}')
            break
        except Exception:
            pass

    if lcd is None:
        print('  ❌ LCD1602 not found at any common I2C address')
        print('     Please check:')
        print('     1. VCC (5V) and GND are connected')
        print('     2. SDA -> Pin 3, SCL -> Pin 5')
        print('     3. All wires are firmly seated')
        print('     4. Run: i2cdetect -y -r 1')
        print('     Running in 7-seg display only mode.')
    else:
        # LCD 初始化成功
        lcd.backlight_enabled = True
        lcd.clear()
        welcome = "Counter Ready!"
        for i in range(len(welcome) + 1):
            lcd.cursor_pos = (0, 0)
            lcd.write_string(pad_text(welcome[:i]))
            time.sleep(0.1)
        lcd.cursor_pos = (1, 0)
        lcd.write_string(pad_text("Touch to start"))
        time.sleep(1.5)
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(pad_text("Count: 0000"))
        lcd.cursor_pos = (1, 0)
        lcd.write_string(pad_text("Touch to add"))

    print('Started | IRQ mode + 7-seg display')
    if lcd:
        print('LCD1602 enabled.')
    print('Touch sensor -> GPIO 5 (BCM)')
    print('Press Ctrl+C to exit and show final result')

# ================== 主循环 ==================
def makerobo_loop():
    global lcd_needs_update
    while True:
        show_num(count)
        if lcd_needs_update and lcd is not None:
            lcd.cursor_pos = (0, 7)
            lcd.write_string(f'{count:04d}')
            lcd_needs_update = False
        time.sleep(0.01)

# ================== 释放资源 ==================
def destroy():
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'\n{"="*30}')
    print(f'  FINAL RESULT: {count:04d}')
    print(f'  Exited at: {timestamp}')
    print(f'{"="*30}')

    if lcd is not None:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string(pad_text('Final Result:'))
        lcd.cursor_pos = (1, 0)
        lcd.write_string(pad_text(f'Count: {count:04d}'))
        print('LCD shows final result for 3 seconds.')

    for _ in range(30):
        show_num(count)
        time.sleep(0.1)

    if lcd is not None:
        lcd.clear()
        lcd.backlight_enabled = False
        lcd.close()

    GPIO.remove_event_detect(TOUCH_PIN)
    GPIO.cleanup()
    print('GPIO cleaned up. Goodbye!')

# ================== 程序入口 ==================
if __name__ == '__main__':
    try:
        makerobo_setup()
        makerobo_loop()
    except KeyboardInterrupt:
        destroy()