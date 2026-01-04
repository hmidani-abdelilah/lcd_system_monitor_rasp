from RPLCD.i2c import CharLCD
import time
import psutil
import socket
import os
from datetime import datetime
from astral.sun import sun
from astral import LocationInfo
import pytz 
import requests 
import subprocess
import getpass
import RPi.GPIO as GPIO
# ===============================
# إعداد أزرار GPIO
# ===============================
PIN_NEXT = 23
PIN_PREV = 27
PIN_PAUSE = 22
PIN_SAVE = 24

# إعداد الأرجل كمداخل
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_NEXT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_PREV, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_PAUSE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(PIN_SAVE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# ===============================
# الموقع والشمس
# ===============================

def get_current_location():
    try:
       
        response = requests.get('http://ip-api.com/json/').json()
        
        if response['status'] == 'success':
            return LocationInfo(
                name=response['city'],
                region=response['country'],
                timezone=response['timezone'],
                latitude=response['lat'],
                longitude=response['lon']
            )
    except Exception as e:
        print(f"Erreur de détection : {e}")
    
    
    return LocationInfo("Fes", "Maroc", "Africa/Casablanca", 34.033333, -5.0)

city = get_current_location()

s = sun(city.observer, date=datetime.today())
tz = pytz.timezone(city.timezone)

sunrise = s['sunrise'].astimezone(tz)
sunset = s['sunset'].astimezone(tz)



# إعداد الشاشة
lcd_columns = 16
lcd_rows = 2

lcd = CharLCD('PCF8574', 0x27, cols=lcd_columns, rows=lcd_rows)

# النصوص
first_text = "System Monitor"
second_text = "Raspberry Pi"

# مسح الشاشة
lcd.clear()

# ⏱️ حركة الساعة
blink = [
    0b00000,
    0b00100,
    0b00100,
    0b00000,
    0b00100,
    0b00100,
    0b00000,
    0b00000,
]


# 🌡️ سهم حرارة (↑ ↓)
arrow_up = [
    0b00100,
    0b01110,
    0b10101,
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b00000,
]

arrow_down = [
    0b00100,
    0b00100,
    0b00100,
    0b00100,
    0b10101,
    0b01110,
    0b00100,
    0b00000,
]

wifi_symbol = (
    0b00000, # .....
    0b01110, # .###.
    0b10001, # #...#
    0b00100, # ..#..
    0b01010, # .#.#.
    0b00000, # .....
    0b00100, # ..#..
    0b00000  # .....
)

ethernet_symbol = (
    0b00000, # (vide)
    0b11111, # ##### (barre supérieure)
    0b10101, # # . # . # (trois connecteurs)
    0b10101, # # . # . #
    0b01110, # . ### .
    0b00100, # .. # .. (base du câble)
    0b00100, # .. # ..
    0b00000  # (vide)
)

# ==================================================
# ICONS
# ==================================================
thermo = (0b00100,0b01010,0b01010,0b01110,0b01110,0b11111,0b11111,0b01110)
bar_empty = (0b10001,)*8
bar_full  = (0b11111,)*8
warn = (0b00100,0b00100,0b00100,0b00100,0b00100,0b00000,0b00100,0b00000)

lcd.create_char(0, thermo)
lcd.create_char(1, bar_empty)
lcd.create_char(2, bar_full)
lcd.create_char(3, wifi_symbol)
lcd.create_char(4, ethernet_symbol)


BAR_LEN = 10  # طول البار المناسب

def move_to_center_left(lcd, text, row=0, cols=16, delay=0.2):
    """تحريك النص من اليسار إلى المنتصف"""
    text_len = len(text)
    start_col = (cols - text_len) // 2
    # من العمود 0 إلى start_col
    for col in range(start_col + 1):
        lcd.cursor_pos = (row, 0)
        lcd.write_string(" " * cols)  # مسح السطر
        lcd.cursor_pos = (row, col)
        lcd.write_string(text)
        time.sleep(delay)

def move_to_center_right(lcd, text, row=1, cols=16, delay=0.2):
    """تحريك النص من اليمين إلى المنتصف"""
    text_len = len(text)
    start_col = (cols - text_len) // 2
    # من العمود الأخير إلى start_col
    for col in range(cols - text_len, start_col - 1, -1):
        lcd.cursor_pos = (row, 0)
        lcd.write_string(" " * cols)  # مسح السطر
        lcd.cursor_pos = (row, col)
        lcd.write_string(text)
        time.sleep(delay)

def center_text(lcd, text, row=0, delay=5):
    """يعرض النص في منتصف الشاشة ويبقيه ثابتاً لمدة delay ثانية"""
    lcd.cols = 16
    if len(text) > lcd.cols:
        text = text[:lcd.cols]  # تقليم النص إذا كان أطول من العرض
    # حساب المكان للتمركز
    start_col = (lcd.cols - len(text)) // 2
    lcd.cursor_pos = (row, start_col)
    lcd.write_string(text)
    time.sleep(delay)

def is_night_mode():
    #hour = datetime.now().hour
    hour = datetime.now(pytz.timezone(city.timezone)).hour
    #hour = 18  # اختبار الوضع الليلي
    if hour >= 0 and hour <= 7:
        lcd.backlight_enabled = False
    elif hour < sunrise.hour or hour >= sunset.hour:
        lcd.backlight_enabled = True
    else:
        lcd.backlight_enabled = False

def get_cpu_usage():
    return psutil.cpu_percent(interval=0.1)

CPU_usage = 'CPU: {} %'.format(get_cpu_usage())

def get_cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if "cpu_thermal" in temps:
            return round(temps["cpu_thermal"][0].current, 1)
    except:
        pass
    return None

def get_cpu_frequencies():
    freqs = psutil.cpu_freq()
    return round(freqs.current, 2), round(freqs.min, 2), round(freqs.max, 2)

def get_cpu_load():
    l1, l5, l15 = psutil.getloadavg()
    return round(l1, 2), round(l5, 2), round(l15, 2)

def get_cpu_times():
    times = psutil.cpu_times_percent(interval=0.1)
    return times.user, times.system, times.idle

def get_gpu_temperature():
    try:
        temp = os.popen("vcgencmd measure_temp").readline()
        return float(temp.replace("temp=", "").replace("'C\n", ""))
    except:
        return None

def get_ram_info():
    mem = psutil.virtual_memory()
    return mem.percent

def get_swap_info():
    swap = psutil.swap_memory()
    return swap.percent

def get_uptime():
    uptime = time.time() - psutil.boot_time()
    d = int(uptime // 86400)
    h = int((uptime % 86400) // 3600)
    m = int((uptime % 3600) // 60)
    return f"{d} d {h} h {m} m"
    
def get_ssid():
    result = subprocess.check_output(
        ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"]
    ).decode()

    for line in result.splitlines():
        if line.startswith("yes:"):
            return line.split("yes:")[1]

    return None
    
def get_ip(interface):
    try:
        for addr in psutil.net_if_addrs().get(interface, []):
            if addr.family == socket.AF_INET:
                return addr.address
    except:
        pass
    return None

# ==================================================
# NETWORK SPEED (NO BLOCKING)
# ==================================================

_last_net = psutil.net_io_counters()
_last_time = time.time()

def get_network_speed():
    global _last_net, _last_time

    now = time.time()
    current = psutil.net_io_counters()

    dt = now - _last_time
    if dt <= 0:
        return 0.0, 0.0

    rx = (current.bytes_recv - _last_net.bytes_recv) / dt
    tx = (current.bytes_sent - _last_net.bytes_sent) / dt

    _last_net = current
    _last_time = now
    
    return rx / 1024 , tx / 1024   # 1024 KB/s  # convert to MB/s * 2 for better display


def get_disk_percent():
    return psutil.disk_usage("/").percent


def get_media_percent():
    
    #raw_path = "/media/$USER/"
    #path = os.path.expandvars(raw_path)
    user = getpass.getuser()
    path = f"/media/{user}/"
    if not os.path.exists(path):
        return 'no path'
    media = os.listdir(path)
    usage = []
    for p in media:
        try:
            usage.append(psutil.disk_usage(path + p).percent)
        except:
            usage.append(None)
    return media, usage
  

# ==================================================
# function pages
# ==================================================

def page_is_night_mode():
    is_night_mode()
    # تحريك العربية من اليسار إلى المنتصف
    move_to_center_left(lcd, first_text, row=0, cols=lcd_columns, delay=0.6)
    # تحريك الإنجليزية من اليمين إلى المنتصف
    move_to_center_right(lcd, second_text, row=1, cols=lcd_columns, delay=0.6)
    # تثبيت النصوص في المنتصف 3 ثواني
    time.sleep(3)
    lcd.clear()
    date = datetime.now().strftime("%d/%m/%Y")
    center_text(lcd, date, row=1, delay=0)

def page_date_time():
    # ⏱️ الساعة
        now = datetime.now().strftime("%H:%M:%S")
        center_text(lcd, now, row=0, delay=0)

        lcd.cursor_pos = (0, 14)

def page_cpu_usage():
    center_text(lcd,'CPU: {} %'.format(get_cpu_usage()), row=0, delay=0)

def page_cpu_temperature(last_temp = 0):
    temp = float(get_cpu_temperature()) or 'N/A'
    lcd.cursor_pos = (1, 0)
    arrow = arrow_up if temp > last_temp else arrow_down
    lcd.create_char(0, arrow)
    lcd.cursor_pos = (1, 0)
    center_text(lcd, f"Temp: {temp:>3} {chr(223)}C ", row=1, delay=0)
    lcd.write_string(chr(0))
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return
    last_temp = temp

def page_cpu_frequency():
    center_text(lcd,'CPU Freq:', row=0, delay=0)
    center_text(lcd,f'{get_cpu_frequencies()[0]}  MHz', row=1, delay=0)
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return


def page_gpu_temperature(last_temp = 0):
    center_text(lcd,'GPU Temp:', row=0, delay=0)
    temp_gpu = get_gpu_temperature() or 'N/A'
    lcd.cursor_pos = (1, 0)
    arrow = arrow_up if temp_gpu > last_temp else arrow_down
    lcd.create_char(0, arrow)
    center_text(lcd,f'{get_gpu_temperature() or "N/A"} {chr(223)}C ', row=1, delay=0)
    lcd.write_string(chr(0))
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.2)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return
    last_temp = temp_gpu


def page_ram_usage():
    filled = int((get_ram_info() / 100) * BAR_LEN)
    lcd.clear()
    center_text(lcd,'Ram Usage:',row=0,delay=0)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f'{get_ram_info()}% ')
    for i in range(BAR_LEN):
        lcd.write_string(chr(2) if i < filled else chr(1))
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return

def page_swap_usage():
    filled = int((get_swap_info() / 100) * BAR_LEN)
    lcd.clear()
    center_text(lcd,'Swap Usage:', row=0, delay=0)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f'{get_swap_info()}% ')
    for i in range(BAR_LEN):
        lcd.write_string(chr(2) if i < filled else chr(1))
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return


def page_disk_usage():
    center_text(lcd,'Disk Usage:', row=0, delay=0)
    filled = int((get_disk_percent() / 100) * BAR_LEN)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(f'{get_disk_percent()}% ')
    for i in range(BAR_LEN):
        lcd.write_string(chr(2) if i < filled else chr(1))
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.2)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return

        
def page_wifi_info():
    move_to_center_left(lcd,'Config WiFi ',row=0,delay=0.2)
    lcd.cursor_pos = (0, 0)
    lcd.write_string(chr(3))  # Display WiFi icon
    time.sleep(0.3)
    move_to_center_right(lcd,'SSID:{}'.format(get_ssid() if get_ssid() != None else 'Not Found'),row=0,delay=0.3)
    ip = get_ip('wlan0')
    center_text(lcd,'{}'.format(ip or 'N/A'),row=1,delay=0.3)
    time.sleep(0.3)



def page_ethernet_info():
    lcd.cursor_pos = (0, 0)
    lcd.write_string(chr(4))  # Display Ethernet icon
    lcd.cursor_pos = (0, 1)
    lcd.write_string('Config Ethernet')
    time.sleep(1)
    ip_eth = get_ip('eth0')
    move_to_center_left(lcd,'Eth0 IP :',row=0,delay=0.3)
    center_text(lcd,'{}'.format(ip_eth if ip_eth else 'Disconnected'),row=1,delay=0.3)
    time.sleep(1)
    
def page_network_speed():
    lcd.cursor_pos = (0, 0)
    lcd.create_char(0, arrow_up)
    lcd.write_string(chr(0))
    lcd.cursor_pos = (0, 15)
    lcd.create_char(6, arrow_down)
    lcd.write_string(chr(6))
    center_text(lcd,'Net Speed', row=0, delay=0)
    for _ in range(6):  # 6 * 0.5 = 3 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return
    lcd.clear()
    rx, tx = get_network_speed()
    center_text(lcd,f'Dow: {round(rx,1)} KB/s', row=0, delay=0.1)
    center_text(lcd,f'Up: {round(tx,1)} KB/s', row=1, delay=0.1)
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return

    
def page_uptime():
    center_text(lcd,'Uptime:', row=0, delay=0)
    center_text(lcd,get_uptime(), row=1, delay=0)
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return
    
def page_cpu_load():
    l1, l5, l15 = get_cpu_load()
    center_text(lcd,'CPU Load Avg:', row=0, delay=0)
    center_text(lcd,'{} {} {}'.format(l1, l5, l15), row=1, delay=0)
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return
    
def page_cpu_times():
    center_text(lcd,'CPU Times:', row=0, delay=0)
    center_text(lcd,'U:{} S:{} I:{}'.format(*get_cpu_times()), row=1, delay=0)
    for _ in range(4):  # 4 * 0.5 = 2 seconds
        time.sleep(0.5)
        if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
            return

def page_media_usage():
    center_text(lcd,'Media Usage:', row=0, delay=0)
    lcd.clear()
    
    if get_media_percent() == 'no path':
        center_text(lcd,'PATH not exist',row=0 ,delay=0)
        for _ in range(4):  # 4 * 0.5 = 2 seconds
            time.sleep(0.5)
            if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
                return
    elif len(get_media_percent()[0]) == 0:
        center_text(lcd,'No Media mount',row=0 ,delay=0)
        for _ in range(4):  # 4 * 0.5 = 2 seconds
            time.sleep(0.5)
            if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
                return
    else :
        media, usage = get_media_percent()
        for m, u in zip(media, usage):
            filled = int((u / 100) * BAR_LEN)
            lcd.clear()
            center_text(lcd,'{}'.format(m if m is not None else 'N/A'), row=0, delay=0)
            lcd.cursor_pos = (1, 0)
            lcd.write_string('{}% '.format(u if u is not None else center_text(lcd,'N/A', row=1, delay=0)))
            for i in range(BAR_LEN):
                lcd.write_string(chr(2) if i < filled else chr(1))
            for _ in range(10):  # 10 * 0.5 = 5 seconds
                time.sleep(0.5)
                if GPIO.input(PIN_NEXT) == 0 or GPIO.input(PIN_PREV) == 0 or GPIO.input(PIN_SAVE) == 0 or GPIO.input(PIN_PAUSE) == 0:
                    return

def page_cpu_warning():
    if get_cpu_temperature() and get_cpu_temperature() > 70:
        center_text(lcd,f"CPU {get_cpu_temperature()} {chr(223)}C!!", row=0, delay=0)
        for _ in range(4):
            lcd.backlight_enabled = False
            time.sleep(0.5)
            lcd.backlight_enabled = True
            time.sleep(0.5)


pages = [page_is_night_mode,
         page_date_time,
         page_cpu_usage,
         page_cpu_temperature,
         page_cpu_frequency,
         page_gpu_temperature,
         page_ram_usage,
         page_swap_usage,
         page_disk_usage,
         page_wifi_info,
         page_ethernet_info,
         page_network_speed,
         page_uptime,
         page_cpu_load,
         page_cpu_times,
         page_media_usage,
         page_cpu_warning
         ]

# ==================================================
# الدلة الرئيسة بحيت سقوم بتنفيذ الصفحات الواحدة تلو الاخرى ويمكنك التحكم بالازرار  و لم تضغط ل 10 توان يكمل عرض الصفحات 
# ==================================================

def check_buttons(index):
    """فحص الأزرار وإرجاع index الجديد وآخر وقت ضغط"""
    if not GPIO.input(PIN_NEXT):
        index = (index + 1) % len(pages)
        print("NEXT pressed")
        return index, time.time(), True

    if not GPIO.input(PIN_PREV):
        index = (index - 1) % len(pages)
        print("PREV pressed")
        return index, time.time(), True

    if not GPIO.input(PIN_PAUSE):
        print("PAUSE pressed")
        while GPIO.input(PIN_PAUSE):
            time.sleep(0.1)
        print("RESUME pressed")
        return index, time.time(), True

    if not GPIO.input(PIN_SAVE):
        with open("lcd_last_page.txt", "w") as f:
            f.write(str(index))
        print("SAVE pressed")
        return index, time.time(), True
    
    return index, time.time(), False

def main_loop():
    index = 0
    last_button_time = time.time()
    PAUSE_DELAY = 10  # ثواني
    page_start_time = time.time()

    while True:
        # فحص الأزرار أثناء تنفيذ الصفحة
        new_index, new_time, button_pressed = check_buttons(index)
        
        if button_pressed:
            index = new_index
            last_button_time = new_time
            page_start_time = time.time()
            time.sleep(0.3)  # Debounce
            lcd.clear()
            continue

        # إذا انتهت المهلة الزمنية، انتقل للصفحة التالية
        if time.time() - last_button_time > PAUSE_DELAY:
            index = (index + 1) % len(pages)
            last_button_time = time.time()
            page_start_time = time.time()
            lcd.clear()
        
        pages[index]()

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        lcd.clear()
        GPIO.cleanup()
