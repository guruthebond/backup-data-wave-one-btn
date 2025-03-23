import time
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import smbus2  # To interface with I2C for SH1106
from luma.core.interface.serial import spi
from luma.oled.device import sh1106  # Use this for SH1106 1.3 OLED display
import signal
import sys
import os

## Allowed CPU Serial Numbers
#ALLOWED_SERIALS = ["000000004d754df1", "000000004d754df2", "000000004d754df3", "9f26d72973077df"]

## Get Raspberry Pi's CPU Serial Number
#def get_cpu_serial():
#    try:
#        with open("/proc/cpuinfo", "r") as f:
#            for line in f:
#                if line.startswith("Serial"):
#                    return line.strip().split(":")[1].strip()
#    except Exception as e:
#        print(f"Error reading CPU serial: {e}")
#    return None

## Function to shutdown system if unauthorized
#def unauthorized_shutdown():
#    print("Unauthorized device detected! Shutting down in 10 seconds...")
#    
#    # Display message on OLED screen
#    image = Image.new('1', (128, 64), 0)  # Black background
#    draw = ImageDraw.Draw(image)
#    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
#    
#    text = "STOP!\nHardware Changed\nContact Support \nShutting Down"
#    text_x, text_y = (5, 5)
#    draw.text((text_x, text_y), text, font=font, fill=255)
#    
#    oled.display(image)
#    oled.show()
#    
#    time.sleep(10)
#    
#    # Shutdown system
#    subprocess.run(["sudo", "shutdown", "-h", "now"])

# Initialize OLED display
serial = spi(port=0, device=0, gpio=None)
oled = sh1106(serial, width=128, height=64)
oled.clear()
oled.show()

## Check CPU Serial
#cpu_serial = get_cpu_serial()
#if cpu_serial not in ALLOWED_SERIALS:
#    unauthorized_shutdown()
#    sys.exit(1)  # Exit script after shutdown command

## Continue with normal execution if authorized
#print("Device authorized, continuing startup...")

# Load GIF file
gif_path = '/backup-data/media/catzzs.gif'  # Path to your GIF file
gif = Image.open(gif_path)

# Function to resize images while maintaining aspect ratio
def resize_image(image, width, height):
    img_ratio = image.width / image.height
    target_ratio = width / height
    
    if img_ratio > target_ratio:
        new_width = width
        new_height = int(width / img_ratio)
    else:
        new_height = height
        new_width = int(height * img_ratio)
    
    return image.resize((new_width, new_height), Image.LANCZOS)

# Resize the GIF frames to fit the screen
frames = [resize_image(frame.copy(), 128, 64) for frame in ImageSequence.Iterator(gif)]
frame_delay = gif.info.get("duration", 1000) / 1000.0  # Convert ms to seconds

# Load font for the text
font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)

def display_for_5_seconds():
    start_time = time.time()

    while time.time() - start_time < 4:
        for frame in frames:
            image = Image.new('1', (128, 64), 0)
            draw = ImageDraw.Draw(image)
            text = "PurrfectBackup"
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_x = (128 - (bbox[2] - bbox[0])) // 2
            text_y = 2
            draw.text((text_x, text_y), text, font=font_large, fill=255)
            frame_resized = frame.resize((128, 64), Image.LANCZOS).convert('1')
            image.paste(frame_resized, (0, 16))
            oled.display(image)
            oled.show()
            time.sleep(frame_delay)
            if time.time() - start_time > 4:
                break

    oled.clear()
    oled.show()
    time.sleep(1)
    print("Launching main.py...")
    global process
    # Check which file exists
    if os.path.exists("/backup-data/main.pyc"):
        main_script = "/backup-data/main.pyc"
    elif os.path.exists("/backup-data/main.py"):
        main_script = "/backup-data/main.py"
    else:
        print("Error: Neither main.py nor main.pyc found.")
        exit(1)

    # Launch the appropriate script
    try:
        process = subprocess.Popen(["/backup-data/myenv/bin/python3", main_script])
    except Exception as e:
        print(f"Error launching {main_script}: {e}")

def handle_exit(signum, frame):
    print("\nExiting gracefully...")
    oled.clear()
    oled.show()
    try:
        if process and process.poll() is None:
            process.terminate()
            process.wait()
            print("main.py terminated")
    except NameError:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

if __name__ == "__main__":
    try:
        display_for_5_seconds()
    except KeyboardInterrupt:
        handle_exit(None, None)
