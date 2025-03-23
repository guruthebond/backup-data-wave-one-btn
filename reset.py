#!/backup-data/myenv/bin/python
import psutil
import sys
import time
import subprocess
from gpiozero import Button
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont

def is_main_running():
    for proc in psutil.process_iter(['cmdline']):
        cmd = proc.info.get('cmdline') or []
        if any("main.py" in part for part in cmd):
            return True
    return False

def monitor_main():
    monitor_start = time.time()
    detected_start = None

    while time.time() - monitor_start < 11:
        if is_main_running():
            if detected_start is None:
                detected_start = time.time()
            elif time.time() - detected_start >= 10:
                return True
        else:
            detected_start = None
        time.sleep(1)
    return False

if monitor_main():
    sys.exit(0)

# Initialize OLED
serial = spi(port=0, device=0, gpio=None)
device = sh1106(serial)

# Load fonts
font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
font_icons = ImageFont.truetype("lineawesome-webfont.ttf", 14)
font_heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)

# Setup buttons
button_up = Button(19, hold_time=2, bounce_time=0.3)
button_down = Button(6, hold_time=2, bounce_time=0.3)
button_select = Button(13, hold_time=2, bounce_time=0.3)


def display_menu(selected_index, menu_options):
    visible_items = 2  # Number of items to display at a time
    start_idx = max(0, min(selected_index, len(menu_options) - visible_items))
    end_idx = start_idx + visible_items

    with canvas(device) as draw:
        heading_text = "System Restore"
        text_width = draw.textlength(heading_text, font=font_heading)
        text_x = (device.width - text_width) // 2
        draw.text((text_x, 5), heading_text, font=font_heading, fill="white")
        draw.line((0, 20, device.width, 20), fill="white")
        
        for i, option in enumerate(menu_options[start_idx:end_idx]):
            y = 25 + (i * 15)
            if (start_idx + i) == selected_index:
                draw.rectangle((6, y - 1, device.width - 10, y + 13), outline="white", fill="white")
                draw.text((12, y), option, font=font_medium, fill="black")
            else:
                draw.text((12, y), option, font=font_medium, fill="white")
        
        # Draw arrows if there are more options above or below
        if start_idx > 0:
            draw.text((device.width - 10, 50), "▲", font=font_medium, fill="white")  # Up arrow
        if end_idx < len(menu_options):
            draw.text((device.width - 10, 50), "▼", font=font_medium, fill="white")  # Down arrow

def get_button_press():
    if button_up.is_pressed:
        time.sleep(0.2)
        return "UP"
    elif button_down.is_pressed:
        time.sleep(0.2)
        return "DOWN"
    elif button_select.is_pressed:
        time.sleep(0.2)
        return "SELECT"
    return None

def restore_backup():
    try:
        subprocess.run(["rsync", "-a", "/root/backup-data-stable/", "/backup-data/"], check=True)
        subprocess.run(["mkdir", "-p", "/etc/systemd/system/"], check=True)
        subprocess.run(["cp", "-r", "/root/backup-data-services/.", "/etc/systemd/system/"], check=True)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        
        for i in range(10, 0, -1):
            with canvas(device) as draw:
                draw.text((5, 20), "System Restored", font=font_medium, fill="white")
                draw.text((5, 40), f"Rebooting in {i}s...", font=font_medium, fill="white")
            time.sleep(1)
        reboot_system()
    except subprocess.CalledProcessError as e:
        print("Error during restore:", e)

def reboot_system():
    subprocess.run(["sudo", "reboot"])

def shutdown_system():
    subprocess.run(["sudo", "shutdown", "now"])

def show_reset_menu():
    menu_options = ["Restore Backup", "Reboot", "Shutdown"]
    selected = 0
    while True:
        display_menu(selected, menu_options)
        button = get_button_press()
        if button == "UP":
            selected = (selected - 1) % len(menu_options)
        elif button == "DOWN":
            selected = (selected + 1) % len(menu_options)
        elif button == "SELECT":
            if selected == 0:
                restore_backup()
            elif selected == 1:
                reboot_system()
            elif selected == 2:
                shutdown_system()
            break
        time.sleep(0.1)

def main():
    show_reset_menu()

if __name__ == "__main__":
    main()
