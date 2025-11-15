from copynow_combined import copy_mode
import time
import os
import subprocess
from gpiozero import Button
#from luma.core.interface.serial import i2c
from luma.core.interface.serial import spi
#from luma.oled.device import ssd1306  # Use this for ssd1306 0.96 OLED display 
from luma.oled.device import sh1106  # Use this of sh1106 1.3 OLED display
from luma.core.render import canvas
from PIL import ImageFont, ImageDraw
import csv
import smbus
#bus = smbus.SMBus(1)
import qrcode  # QR code library
import socket
from PIL import Image
import shutil
from datetime import datetime
import re
import gpiozero.pins.lgpio
import lgpio
import pytz
import datetime as dt
import hashlib
import base64
import json
import sys
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256


# Add these near the top with other global variables
last_main_menu_index = 0
last_settings_menu_index = 0
current_brightness = 128  # Default brightness (0-255)
brightness_states = [32, 64, 128, 192, 255]  # Different brightness levels
brightness_index = 2  # Start at middle brightness (128)

def __patched_init(self, chip=None):
    gpiozero.pins.lgpio.LGPIOFactory.__bases__[0].__init__(self)
    chip = 0
    self._handle = lgpio.gpiochip_open(chip)
    self._chip = chip
    self.pin_class = gpiozero.pins.lgpio.LGPIOPin

gpiozero.pins.lgpio.LGPIOFactory.__init__ = __patched_init

# Load custom fonts
font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
font_icons = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/lineawesome-webfont.ttf", 14)
font_massive = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
font_con = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/dejavu-sans.condensed.ttf",10)

font_heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)

help_texts = {}

def load_help_text():
    global help_texts
    try:
        with open("/backup-data/help.txt", "r") as f:
            content = f.read()
            entries = content.split("\n")  # Split by new lines
            key = None
            value = []
            for line in entries:
                if ":" in line:  # New key found
                    if key:  # Save previous entry
                        help_texts[key.strip()] = "\n".join(value).replace("\\n", "\n").strip()
                    key, value_part = line.split(":", 1)
                    key = key.strip()
                    value = [value_part.strip()]
                else:  # Continuation of previous value
                    value.append(line.strip())

            if key:  # Save last entry
                help_texts[key] = "\n".join(value).replace("\\n", "\n").strip()
    except FileNotFoundError:
        help_texts = {}

# Call this function at the start
load_help_text()



def clean_menu_item(menu_item):
    """Remove non-alphanumeric characters except spaces."""
    return re.sub(r"[^\w\s]", "", menu_item).strip()

def show_help(menu_item):
    menu_item = clean_menu_item(menu_item)
    help_text = help_texts.get(menu_item, "No help available for this item.")
    
    # Wrap the text properly
    wrapped_lines = []
    paragraphs = help_text.split('\n')
    for para in paragraphs:
        wrapped_lines.extend(textwrap.wrap(para, width=16))  # Wrap each paragraph
    
    index = 0  # Tracks which line we're starting from
    max_lines = 5  # Number of lines that fit on screen
    
    while True:
        # Display current portion of text
        with canvas(device) as draw:
            y = 0
            for i in range(index, min(index + max_lines, len(wrapped_lines))):
                draw.text((0, y), wrapped_lines[i], font=font_medium, fill="white")
                y += 12  # Line height
            
            # Show scroll indicators if needed
            if index > 0:
                draw.text((120, 0), "↑", font=font_medium, fill="white")
            if index + max_lines < len(wrapped_lines):
                draw.text((120, 52), "↓", font=font_medium, fill="white")
        
        # Wait for button press
        button = None
        while not button:
            button = get_button_press()
            time.sleep(0.05)  # Small delay to prevent CPU overload
        
        # Handle button press
        if button == "UP":
            index = max(0, index - 1)  # Move up one line
        elif button == "DOWN":
            index = min(len(wrapped_lines) - max_lines, index + 1)  # Move down one line
        elif button == "LEFT":
            return  # Exit help immediately when LEFT is pressed

import textwrap

import textwrap

def display_help_text(help_text, index):
    max_width = 128   # OLED screen width
    max_height = 64   # OLED screen height
    max_lines = 5     # Maximum visible lines
    line_height = 12  # Approximate height per line

    # Create a blank image
    image = Image.new("1", (max_width, max_height), 0)
    draw = ImageDraw.Draw(image)

    # Preserve explicit `\n` and wrap long lines
    paragraphs = help_text.split("\n")
    lines = []
    for paragraph in paragraphs:
        lines.extend(textwrap.wrap(paragraph, width=16))  # Wrap to OLED width

    total_lines = len(lines)

    # Display selected portion of text (5 lines per screen)
    y = 0
    for i in range(index, min(index + max_lines, total_lines)):
        draw.text((0, y), lines[i], font=font_medium, fill=255)
        y += line_height

    # Draw up/down arrows if scrolling is available
    if index > 0:
        draw.text((118, 0), "↑", font=font_medium, fill=255)
    if index + max_lines < total_lines:
        draw.text((118, max_height - 12), "↓", font=font_medium, fill=255)

    # Send image to display
    device.display(image)


def get_button_press():
    """Detect which button is pressed and return its name."""
    if button_up.is_pressed:
        time.sleep(0.2)  # Debounce
        return "UP"
    elif button_down.is_pressed:
        time.sleep(0.2)  # Debounce
        return "DOWN"
    elif button_left.is_pressed:
        time.sleep(0.2)  # Debounce
        return "LEFT"
    elif button_right.is_pressed:
        time.sleep(0.2)  # Debounce
        return "RIGHT"
    elif button_key1.is_pressed:
        time.sleep(0.2)
        return "KEY1"
    elif button_key2.is_pressed:
        time.sleep(0.2)
        return "KEY2"
    elif button_key3.is_pressed:
        time.sleep(0.2)
        return "KEY3"
    return None

# I2C setup for OLED display
#serial = i2c(port=1, address=0x3C) 
serial = spi(port=0, device=0, gpio=None)
#serial = spi(port=0, device=0, gpio=None)
device = sh1106(serial)   # Use this for sh1106 1.3  OLED display 
#device = ssd1306(serial)  # Use this of ssd1306 0.96 OLED display

# Set up buttons
#button_up = Button(17, hold_time=2, bounce_time=0.3)
#button_down = Button(27, hold_time=2, bounce_time=0.3)
#button_select = Button(22, bounce_time=0.3)

# Set up buttons
button_up = Button(19, hold_time=2, bounce_time=0.3)
button_down = Button(6, hold_time=2, bounce_time=0.3)
button_select = Button(13, hold_time=2, bounce_time=0.3)
button_left = Button(26, hold_time=2, bounce_time=0.3)
button_right = Button(5, hold_time=2, bounce_time=0.3)
button_key3 = Button(21, bounce_time=0.3)  # KEY1 for brightness control
button_key2 = Button(20, bounce_time=0.3)  # KEY2 for reporting/WebUI
button_key1 = Button(16, bounce_time=0.3)  # KEY3 for settings menu


def check_sd_card_binding():
    """
    Check for master test license or hardware-bound license
    """
    master_license_file = "/backup-data/master_test.lic"
    hardware_license_file = "/backup-data/license.lic"
    current_hardware_id = get_hardware_id()
    
    # First, check if hardware-bound license exists (highest priority)
    if os.path.exists(hardware_license_file):
        if validate_license(hardware_license_file, current_hardware_id):
            return True  # Hardware-bound license valid
        else:
            return handle_license_mismatch()  # Use new handler with replace option
    
    # Second, check for master test license
    if os.path.exists(master_license_file):
        if validate_master_license(master_license_file):
            display_message("MASTER TEST MODE", "Unlimited testing")
            time.sleep(2)
            return True  # Master test license valid
    
    # No valid license found - must activate
    return require_activation(current_hardware_id)

def get_hardware_id():
    """
    Get unique hardware ID from Pi serial
    """
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    return hashlib.sha256(serial.encode()).hexdigest()[:32]
    except:
        pass
    return "unknown"

def validate_license(license_file, current_hardware_id):
    """
    Validate hardware-bound license
    """
    try:
        with open(license_file, 'r') as f:
            license_data = json.load(f)
        
        # Check if it's a hardware-bound license
        if license_data.get('type') != 'hardware_bound':
            return False
        
        public_key = RSA.import_key(license_data['public_key'])
        signature = base64.b64decode(license_data['signature'])
        stored_hardware_id = license_data['hardware_id']
        
        # Verify signature
        h = SHA256.new(stored_hardware_id.encode())
        pkcs1_15.new(public_key).verify(h, signature)
        
        # Verify hardware ID matches
        return stored_hardware_id == current_hardware_id
        
    except:
        return False

def validate_master_license(master_license_file):
    """
    Validate master test license (works on any hardware)
    """
    try:
        with open(master_license_file, 'r') as f:
            license_data = json.load(f)
        
        # Check if it's a master license
        if license_data.get('type') != 'master_test':
            return False
        
        public_key = RSA.import_key(license_data['public_key'])
        signature = base64.b64decode(license_data['signature'])
        master_key = license_data['master_key']
        
        # Verify signature
        h = SHA256.new(master_key.encode())
        pkcs1_15.new(public_key).verify(h, signature)
        
        return True
        
    except:
        return False

def require_activation(current_hardware_id):
    """
    No license found - offer activation options with serial display
    """
    hardware_serial = get_hardware_serial()
    options = ["Activate Hardware", "Use Test Mode", "Shutdown"]
    selected_index = 0
    
    while True:
        with canvas(device) as draw:
            # Show hardware serial at top
            draw.text((2, 0), f"{hardware_serial}", font=font_small, fill="white")
            draw.text((2, 12), "Use this for license", font=font_small, fill="white")
            
            y = 25
            for i, option in enumerate(options):
                if i == selected_index:
                    draw.rectangle((2, y-1, device.width-2, y+11), outline="white", fill="white")
                    draw.text((4, y), option, font=font_small, fill="black")
                else:
                    draw.text((4, y), option, font=font_small, fill="white")
                y += 13
        
        if button_up.is_pressed:
            selected_index = (selected_index - 1) % len(options)
            time.sleep(0.2)
        elif button_down.is_pressed:
            selected_index = (selected_index + 1) % len(options)
            time.sleep(0.2)
        elif button_select.is_pressed:
            if selected_index == 0:  # Activate Hardware License
                success = activate_hardware_license(current_hardware_id)
                if success:
                    return True  # Activation successful, system will reboot
                else:
                    continue  # Activation failed, show menu again
            elif selected_index == 1:  # Use Master Test Mode
                return check_for_master_license()
            elif selected_index == 2:  # Shutdown
                os.system("sudo shutdown now")
                return False
        elif button_left.is_pressed:
            return check_for_master_license()  # Quick test mode
        elif button_right.is_pressed:
            success = activate_hardware_license(current_hardware_id)  # Quick activation
            if success:
                return True
        
        time.sleep(0.1)

def activate_hardware_license(current_hardware_id):
    """
    Activate with hardware-bound license by checking USB drives
    """
    hardware_license_file = "/backup-data/license.lic"
    
    # Check if hardware license already exists and is valid
    if os.path.exists(hardware_license_file):
        if validate_license(hardware_license_file, current_hardware_id):
            display_message("HARDWARE LICENSE", "Already Activated!")
            time.sleep(2)
            return True
    
    # Search for license.lic on USB drives
    display_message("Searching USB", "for license.lic...")
    
    # Get USB partitions
    partitions = get_usb_partitions(exclude_disk="mmcblk")
    
    if not partitions:
        display_message("No USB drives", "found for activation")
        time.sleep(2)
        return False
    
    license_found = False
    license_path = None
    
    # Search each USB partition for license.lic
    for partition in partitions:
        try:
            # Create temporary mount point
            temp_mount = f"/mnt/temp_license_{partition[0]}"
            if not os.path.exists(temp_mount):
                os.makedirs(temp_mount)
            
            # Mount the partition
            mount_partition(partition[0], temp_mount)
            
            # Check for license.lic in root directory
            potential_license = os.path.join(temp_mount, "license.lic")
            if os.path.exists(potential_license):
                license_found = True
                license_path = potential_license
                break
            
            # Unmount before next iteration
            unmount_partition(temp_mount)
            
        except Exception as e:
            print(f"Error checking partition {partition[0]}: {e}")
            # Try to unmount if there was an error
            if os.path.ismount(temp_mount):
                unmount_partition(temp_mount)
    
    if not license_found:
        display_message("License not found", "on any USB drive")
        time.sleep(2)
        return False
    
    # Copy license file to /backup-data/
    try:
        shutil.copy2(license_path, hardware_license_file)
        # ADD THIS: Also copy to reset location
        reset_license_file = "/root/backup-data-stable/license.lic"
        shutil.copy2(license_path, reset_license_file)
        display_message("License copied", "Validating...")
        
        # Validate the copied license
        if validate_license(hardware_license_file, current_hardware_id):
            display_message("ACTIVATION", "SUCCESS!")
            time.sleep(2)
            
            # Clean up - unmount the partition where license was found
            unmount_partition(temp_mount)
            
            # Option 1: Reboot automatically
            display_message("Rebooting", "in 3 seconds...")
            time.sleep(3)
            os.system("sudo reboot")
            return True
        else:
            # License validation failed - remove invalid license
            if os.path.exists(hardware_license_file):
                os.remove(hardware_license_file)
            display_message("INVALID LICENSE", "Wrong hardware")
            time.sleep(2)
            return False
            
    except Exception as e:
        print(f"Error copying license: {e}")
        display_message("Activation failed", "Error copying license")
        time.sleep(2)
        return False

def check_for_master_license():
    """
    Check for master test license
    """
    master_license_file = "/backup-data/master_test.lic"
    
    if os.path.exists(master_license_file):
        if validate_master_license(master_license_file):
            display_message("MASTER TEST MODE", "Activated!")
            time.sleep(2)
            return True
    
    # No master license found
    #display_message("Insert master_test.lic", "in /backup-data/")
    display_message("Master License", "Not Found")
    time.sleep(3)
    return require_activation(get_hardware_id())

def handle_license_mismatch():
    """
    Handle license violations with option to replace license and show hardware ID
    """
    current_hardware_id = get_hardware_id()
    hardware_serial = get_hardware_serial()  # Get the actual serial number
    
    options = ["Replace License", "Shutdown"]
    selected_index = 0
    
    while True:
        with canvas(device) as draw:
            # Title bar
            #draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            #draw.text((2, 1), "LICENSE VIOLATION", font=font_small, fill="black")
            
            # Display hardware information
            #draw.text((2, 18), f"HW Serial:", font=font_small, fill="white")
            draw.text((2, 1), f"{hardware_serial}", font=font_small, fill="white")
            draw.text((2, 15), "Unlicensed Hardware", font=font_small, fill="white")
            
            # Display options
            y = 32
            for i, option in enumerate(options):
                if i == selected_index:
                    draw.rectangle((2, y-1, device.width-2, y+11), outline="white", fill="white")
                    draw.text((4, y), option, font=font_small, fill="black")
                else:
                    draw.text((4, y+15), option, font=font_small, fill="white")
        
        # Handle button presses
        if button_up.is_pressed:
            selected_index = (selected_index - 1) % len(options)
            time.sleep(0.2)
        elif button_down.is_pressed:
            selected_index = (selected_index + 1) % len(options)
            time.sleep(0.2)
        elif button_select.is_pressed:
            if selected_index == 0:  # Replace License
                success = replace_license_from_usb(current_hardware_id)
                if success:
                    display_message("LICENSE REPLACED", "Rebooting...")
                    time.sleep(2)
                    os.system("sudo reboot")
                    return True
                else:
                    continue  # License replacement failed, show menu again
            elif selected_index == 1:  # Shutdown
                os.system("sudo shutdown now")
                return False
        
        time.sleep(0.1)

def get_hardware_serial():
    """
    Get the actual Raspberry Pi serial number (not hashed)
    """
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    return serial
    except:
        pass
    return "UNKNOWN"

def replace_license_from_usb(current_hardware_id):
    """
    Search for and replace license from USB drives
    """
    hardware_license_file = "/backup-data/license.lic"
    
    display_message("Searching USB", "for license.lic...")
    
    # Get USB partitions
    partitions = get_usb_partitions(exclude_disk="mmcblk")
    
    if not partitions:
        display_message("No USB drives", "found for license")
        time.sleep(2)
        return False
    
    license_found = False
    license_path = None
    temp_mount = None
    
    # Search each USB partition for license.lic
    for partition in partitions:
        try:
            # Create temporary mount point
            temp_mount = f"/mnt/temp_license_{partition[0]}"
            if not os.path.exists(temp_mount):
                os.makedirs(temp_mount)
            
            # Mount the partition
            mount_partition(partition[0], temp_mount)
            
            # Check for license.lic in root directory
            potential_license = os.path.join(temp_mount, "license.lic")
            if os.path.exists(potential_license):
                license_found = True
                license_path = potential_license
                break
            
            # Unmount before next iteration
            unmount_partition(temp_mount)
            temp_mount = None
            
        except Exception as e:
            print(f"Error checking partition {partition[0]}: {e}")
            # Try to unmount if there was an error
            if temp_mount and os.path.ismount(temp_mount):
                unmount_partition(temp_mount)
    
    if not license_found:
        display_message("License not found", "on any USB drive")
        time.sleep(2)
        return False
    
    # Remove old invalid license
    try:
        if os.path.exists(hardware_license_file):
            os.remove(hardware_license_file)
    except Exception as e:
        print(f"Error removing old license: {e}")
    
    # Copy new license file to /backup-data/
    try:
        shutil.copy2(license_path, hardware_license_file)
        display_message("License copied", "Validating...")
        
        # Validate the new license
        if validate_license(hardware_license_file, current_hardware_id):
            display_message("LICENSE VALID", "Replacement successful!")
            
            # Clean up - unmount the partition where license was found
            if temp_mount and os.path.ismount(temp_mount):
                unmount_partition(temp_mount)
            
            return True
        else:
            # New license validation failed - remove invalid license
            if os.path.exists(hardware_license_file):
                os.remove(hardware_license_file)
            display_message("INVALID LICENSE", "Wrong hardware")
            time.sleep(2)
            return False
            
    except Exception as e:
        print(f"Error copying license: {e}")
        display_message("Replacement failed", "Error copying license")
        time.sleep(2)
        return False
    finally:
        # Always try to unmount
        if temp_mount and os.path.ismount(temp_mount):
            unmount_partition(temp_mount)

def nvme_present():
    if os.path.exists("/dev/nvme0n1p2") or os.path.ismount("/mnt/nvme0n1p2"):
        return True
    return False

menu_items = [
    "\uf0c5 Just Copy",
    "\uf133 Dated Copy",
    "\uf1eb WebUI Backup",
    "\uf15c Copy History",
    "\uf1c0 Disk Info",
    "\uf7b9 Disk Check",
    "\uf013 Settings →"
]

# Conditionally add Built-in SSD submenu
if nvme_present():
    menu_items.insert(4, "\uf0a0 Built-in SSD →")  # Insert after Copy History

shutdown_menu_items = ["\uf28d Shutdown", "\uf021 Reboot", "\uf28d Cancel"]
settings_menu_items = ["\uf017 Date/Time", "\uf129 Version", "\uf56d Update", "\uf021 Reboot", "\uf28d Shutdown",  "\uf2f1 Factory Reset"]
selected_index = 0

# Built-in SSD submenu items
ssd_menu_items = [
    "\uf1c0 SSD Info",       # shows total/free space of nvme0n1p2
    "\uf019 Offload Data",   # copies data to USB drive (reuse existing copy logic)
    "\uf1f9 Format SSD",     # formats nvme0n1p2 in exFAT (double confirmation)
    #"\uf28d Back"            # go back to main menu
]

def display_current_datetime():
    """Display real-time updating date and time with navigation"""
    last_update = 0
    update_interval = 1  # Update every second
    
    while True:
        current_time = time.time()
        
        # Only update if at least 1 second has passed
        if current_time - last_update >= update_interval:
            # Get current date and time
            now = datetime.now()
            date_str = now.strftime("%d %b %Y")    # "04 Oct 2024"
            time_str = now.strftime("%H:%M:%S")    # "14:30:25" with seconds
            timezone_str = get_utc_offset()        # "UTC+5:30"
            
            # Shorten timezone if too long
            if len(timezone_str) > 8:
                timezone_str = timezone_str.replace("UTC", "")  # Just show "+5:30"
            
            with canvas(device) as draw:
                # Clear screen
                draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                
                # Display date centered (top section) - medium font
                date_width = draw.textlength(date_str, font=font_medium)
                date_x = (device.width - date_width) // 2
                draw.text((date_x, 6), date_str, font=font_medium, fill="white")
                
                # Display time centered (middle section) - medium font
                time_width = draw.textlength(time_str, font=font_medium)
                time_x = (device.width - time_width) // 2
                draw.text((time_x, 23), time_str, font=font_medium, fill="white")
                
                # Display timezone centered
                tz_width = draw.textlength(timezone_str, font=font_small)
                tz_x = (device.width - tz_width) // 2
                draw.text((tz_x, 40), timezone_str, font=font_small, fill="white")
                
                # Separator line above navigation
                draw.line((0, 52, device.width - 0, 52), fill="white", width=1)
                
                # Navigation hints at bottom
                draw.text((8, 52), "← Back", font=font_small, fill="white")
                draw.text((device.width - 35, 52), "Set →", font=font_small, fill="white")
                
            last_update = current_time
        
        # Check for LEFT button to exit
        if button_left.is_pressed:
            time.sleep(0.2)
            return
        
        # Check for RIGHT button to go to time settings
        if button_right.is_pressed:
            time.sleep(0.2)
            set_time_manually()  # Go to existing time setting function
            return
        
        time.sleep(0.1)  # Small delay to reduce CPU usage


def ssd_info_menu(device_path="/dev/nvme0n1p2"):
    """Display info for the built-in SSD"""
    mount_point = "/mnt/ssd_info"
    
    # Ensure mount point exists
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)
    
    # Unmount if already mounted
    if os.path.ismount(mount_point):
        unmount_partition(mount_point)
    
    try:
        # Mount the SSD partition
        device_name = device_path.split('/')[-1]  # Extract 'nvme0n1p2' from '/dev/nvme0n1p2'
        mount_partition(device_name, mount_point)
        
        # Get partition info
        total_size, free_size = get_partition_info(mount_point)
        label = get_partition_label(device_name)
        
        # Display the info
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
            draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            draw.text((2, 1), "SSD Info", font=font_small, fill="black")
            
            y = 20
            draw.text((2, y), f"Label: {label}", font=font_medium, fill="white")
            y += 16
            draw.text((2, y), f"Total: {total_size}", font=font_medium, fill="white")
            y += 16
            draw.text((2, y), f"Free: {free_size}", font=font_medium, fill="white")
        
        # Wait for LEFT button press with proper debouncing
        button_pressed = False
        
        while True:
            if button_left.is_pressed:
                if not button_pressed:
                    button_pressed = True
                    # Wait for button release
                    while button_left.is_pressed:
                        time.sleep(0.05)
                    break  # Exit after button is released
            else:
                button_pressed = False
                
            time.sleep(0.1)
        
    except Exception as e:
        display_message("SSD Info Error", f"Cannot read {device_path}")
        # Wait for LEFT button to dismiss error message
        button_pressed = False
        while True:
            if button_left.is_pressed:
                if not button_pressed:
                    button_pressed = True
                    while button_left.is_pressed:
                        time.sleep(0.05)
                    break
            else:
                button_pressed = False
            time.sleep(0.1)
    finally:
        # Always unmount before returning
        if os.path.ismount(mount_point):
            unmount_partition(mount_point)
        
        # Small delay to prevent immediate re-detection in calling function
        time.sleep(0.2)

def ssd_menu():
    global selected_index
    selected_index = 0

    while True:
        choice = navigate_menu_time(ssd_menu_items, title="← Built-in SSD", reset_position=True)

        # Process the choice
        if choice == "\uf1c0 SSD Info":
            ssd_info_menu("/dev/nvme0n1p2")
            # After returning from SSD Info, reset navigation state
            selected_index = 0
        
        elif choice == "\uf019 Offload Data":
            # Get actual SSD partition info instead of placeholders
            ssd_device = "nvme0n1p2"
    
            # Mount the SSD temporarily to get size info
            mount_point = "/mnt/ssd_temp"
            if not os.path.exists(mount_point):
                os.makedirs(mount_point)
    
            # Unmount if already mounted
            if os.path.ismount(mount_point):
                unmount_partition(mount_point)
    
            try:
                # Mount SSD to get actual size information
                mount_partition(ssd_device, mount_point)
        
                # Get actual partition info
                total_size, free_size = get_partition_info(mount_point)
                label = get_partition_label(ssd_device)
        
                # Create proper partition tuple with real data
                ssd_partition = (ssd_device, total_size, free_size, label)
        
                # Let user select destination only
                dest = select_partition('destination', exclude_disk="nvme")
                if dest is None:
                    # Cleanup before returning
                    unmount_partition(mount_point)
                    continue

                # Show summary/confirmation screen before proceeding
                result = display_summary_offload(ssd_partition, dest)
                if result == "Back to Main Menu":
                    # Cleanup before returning
                    unmount_partition(mount_point)
                    continue

                # Clean previous mounts
                if os.path.ismount("/mnt/src"): unmount_partition("/mnt/src")
                if os.path.ismount("/mnt/dst"): unmount_partition("/mnt/dst")

                # Mount SSD as source and destination as usual
                mount_partition(ssd_partition[0], "/mnt/src")
                mount_partition(dest[0], "/mnt/dst")

                # Use existing Just Copy logic
                copy_mode(device, mode="just", buttons=(button_up, button_down, button_select))

                # Cleanup
                unmount_partition("/mnt/src")
                unmount_partition("/mnt/dst")
        
            except Exception as e:
                print(f"Error in Offload Data: {e}")
                display_message("Offload Error", f"Cannot read SSD: {str(e)}")
                time.sleep(2)
            finally:
                # Always unmount the temp mount point
                if os.path.ismount(mount_point):
                    unmount_partition(mount_point)

        elif choice == "\uf1f9 Format SSD":
            selected_index = 0
            if confirm_format_nvme():
                selected_index = 0
                continue
            else:
                selected_index = 0
                continue

        elif choice == "\uf28d Back":
            # Reset selection and return to main menu
            selected_index = 0
            return

def display_summary_offload(source, dest):
    while True:
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")

            # Title Bar with White background
            draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            draw.text((2, 1), "Summary[Offload Data]", font=font_small, fill="black")

            # Display source and destination labels
            source_label = "PBSSD"  # Fixed label for SSD
            dest_label = dest[3][:5] if dest[3] != "NO-LBL" else "NO-LBL"

            # Display source and destination info
            # For SSD, we can show it as source without size, or get actual size
            draw.text((0, 27), f"\u2193 ", font=font_large, fill="white")
            draw.text((2, 20), f"  [{source_label}]-SSD", font=font_medium, fill="white")

            # Show destination size
            dest_size_rounded = round(float(dest[1].replace('GB', '')))
            draw.text((2, 35), f"  [{dest_label}]-{dest_size_rounded}GB", font=font_medium, fill="white")

            # Draw the "Select" text with inverse colors
            select_text = "[SELECT] to Offload".upper()
            text_width = draw.textlength(select_text, font=font_small)
            x = (device.width - text_width) // 2
            draw.rectangle((x - 2, device.height - 15, x + text_width + 2, device.height), outline="black", fill="white")
            draw.text((x, device.height - 15), select_text, font=font_small, fill="black")

        if button_left.is_pressed:
            time.sleep(0.2)
            return "Back to Main Menu"

        # Wait for Select button to proceed
        if button_select.is_pressed:
            time.sleep(0.2)  # Debounce
            return "Proceed with Offload"

        time.sleep(0.1)  # Avoid High CPU usage

def confirm_format_nvme():
    confirmations = 0
    device_path = "/dev/nvme0n1p2"
    last_button_time = 0
    button_cooldown = 0.3

    messages = ["Format SSD?", "Really Sure?"]
    options = ["Cancel", "Confirm"]
    
    while confirmations < 2:
        index = 0
        prev_index = -1

        while True:
            current_time = time.time()
            
            if index != prev_index:
                with canvas(device) as draw:
                    # Clear screen
                    draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                    
                    # Centered heading
                    heading_text = messages[confirmations]
                    text_width = draw.textlength(heading_text, font=font_heading)
                    text_x = (device.width - text_width) // 2
                    draw.text((text_x, 10), heading_text, font=font_heading, fill="white")
                    
                    # Line below heading
                    draw.line((0, 25, device.width, 25), fill="white")
                    
                    # Options with proper spacing and highlighting
                    option_y_start = 30
                    option_spacing = 15
                    
                    for i, option in enumerate(options):
                        y = option_y_start + (i * option_spacing)
                        if i == index:
                            # Highlight selected option
                            draw.rectangle((6, y - 1, device.width - 5, y + 13), outline="white", fill="white")
                            draw.text((12, y), option, font=font_medium, fill="black")
                        else:
                            draw.text((12, y), option, font=font_medium, fill="white")
                
                prev_index = index

            # Handle button presses
            if button_up.is_pressed and current_time - last_button_time > button_cooldown:
                last_button_time = current_time
                index = (index - 1) % 2
                time.sleep(0.2)
            elif button_down.is_pressed and current_time - last_button_time > button_cooldown:
                last_button_time = current_time
                index = (index + 1) % 2
                time.sleep(0.2)
            elif button_select.is_pressed and current_time - last_button_time > button_cooldown:
                last_button_time = current_time
                if index == 0:  # Cancel
                    return False
                else:
                    confirmations += 1
                    break
            elif button_left.is_pressed and current_time - last_button_time > button_cooldown:
                time.sleep(0.2)
                return False
            
            time.sleep(0.1)

    # Formatting process
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
        draw.text((2, 1), "Formatting SSD", font=font_small, fill="black")
        draw.text((10, 25), "Quick Formatting...", font=font_medium, fill="white")
        draw.text((10, 40), "Please wait", font=font_medium, fill="white")

    # Unmount and format
    subprocess.run(["sudo", "umount", device_path], stderr=subprocess.DEVNULL)
    result = subprocess.run(
        ["sudo", "mkfs.exfat", device_path, "-n", "PBSSD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1)

    success = (result.returncode == 0)

    # Show result briefly (2 seconds) and then return automatically
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
        
        if success:
            draw.text((2, 1), "Format Complete", font=font_small, fill="black")
            draw.text((10, 30), "SSD Formatted!", font=font_medium, fill="white")
            draw.text((10, 45), "Label: PBSSD", font=font_medium, fill="white")
        else:
            draw.text((2, 1), "Format Failed", font=font_small, fill="black")
            draw.text((10, 30), "exFAT format failed!", font=font_medium, fill="white")

    # Show result for 2 seconds and then return automatically
    time.sleep(2)
    
    return success

def handle_brightness_control():
    global current_brightness, brightness_index

    last_press_time = time.time()
    timeout = 1  # seconds before auto-exit

    total_blocks = len(brightness_states)
    block_size = 10
    block_spacing = 4
    total_width = total_blocks * block_size + (total_blocks - 1) * block_spacing
    blocks_x = (device.width - total_width) // 2
    blocks_y = 42

    while True:
        now = time.time()

        if button_key1.is_pressed:
            while button_key1.is_pressed:
                time.sleep(0.05)
            brightness_index = (brightness_index + 1) % total_blocks
            current_brightness = brightness_states[brightness_index]
            device.contrast(current_brightness)
            last_press_time = now

        # Date, time, UTC
        now_dt = datetime.now()
        date_str = now_dt.strftime("%d %b %Y")
        time_str = now_dt.strftime("%H:%M:%S")
        offset_str = get_utc_offset()
        time_line = f"{time_str}  {offset_str}"

        with canvas(device) as draw:
            # Top white rectangle
            draw.rectangle((0, 0, device.width, 26), outline="white", fill="white")

            # Centered date
            date_x = (device.width - draw.textlength(date_str, font=font_small)) // 2
            draw.text((date_x, 2), date_str, font=font_small, fill="black")

            # Centered time + zone
            time_x = (device.width - draw.textlength(time_line, font=font_small)) // 2
            draw.text((time_x, 14), time_line, font=font_small, fill="black")

            # Divider
            draw.line((0, 27, device.width, 27), fill="white")

            # Brightness squares (filled and empty)
            for i in range(total_blocks):
                x = blocks_x + i * (block_size + block_spacing)
                if i <= brightness_index:
                    draw.rectangle((x, blocks_y, x + block_size, blocks_y + block_size), fill="white")
                else:
                    draw.rectangle((x, blocks_y, x + block_size, blocks_y + block_size), outline="white", fill=None)

        if now - last_press_time > timeout:
            break

        time.sleep(0.1)

def handle_chkfile_mode():
    font_icons = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/lineawesome-webfont.ttf", 12)

    # Proceed as usual when disk is found
    ip_address = HARD_CODED_IP
    start_hostapd_service()
    display_message_wifi_oled("Connect Phone", " BackMeUp", " 11223344", "& Press WebUI", font_icons=font_icons)

    # Wait for KEY3 press and release to proceed
    while button_key3.is_pressed:
        time.sleep(0.1)
    while not button_key3.is_pressed:
        time.sleep(0.1)
    while button_key3.is_pressed:
        time.sleep(0.1)

    start_flask_service()
    display_qr_code(f"http://192.168.0.1", mode="checkfiles")

    # Wait for KEY3 again to exit
    while not button_key3.is_pressed:
        time.sleep(0.5)
    while button_key3.is_pressed:
        time.sleep(0.5)

    stop_flask_service()
    display_message_wifi_oled("WebUI", "Stopped", "Returning ...", font_icons=font_icons)
    time.sleep(2)
    while button_key3.is_pressed:
        time.sleep(0.5)
    time.sleep(1.0)


def confirm_reset():
    options = ["Cancel", "Confirm"]
    index = 0

    while True:
        with canvas(device) as draw:
            # Display heading centered
            heading_text = "System Reset"
            text_width = draw.textlength(heading_text, font=font_heading)
            text_x = (device.width - text_width) // 2
            draw.text((text_x, 10), heading_text, font=font_heading, fill="white")

            # Draw line below heading (full width)
            draw.line((0, 25, device.width, 25), fill="white")

            # Display options aligned to the left with better spacing
            option_y_start = 30  # Adjusted for better centering
            option_spacing = 15  # More spacing between options

            for i, option in enumerate(options):
                y = option_y_start + (i * option_spacing)
                if i == index:
                    # Highlight selected option with proper alignment
                    draw.rectangle((6, y - 1, device.width - 5, y + 13), outline="white", fill="white")
                    draw.text((12, y), option, font=font_medium, fill="black")  # Left aligned
                else:
                    draw.text((12, y), option, font=font_medium, fill="white")  # Left aligned

        # Handle button presses
        if button_up.is_pressed:
            index = (index - 1) % 2
            time.sleep(0.2)
        elif button_down.is_pressed:
            index = (index + 1) % 2
            time.sleep(0.2)
        elif button_select.is_pressed:
            if index == 1:
                reset_system()  # Proceed with factory reset
            time.sleep(0.2)
            return  # Exit the reset menu


def reset_system():
    display_message("System Reset", "Rebooting in 10s")
    time.sleep(2)
    os.system("rsync -a /root/backup-data-stable/ /backup-data/ && mkdir -p /etc/systemd/system/ && cp /root/backup-data-services/* /etc/systemd/system/ && systemctl daemon-reload")
    for i in range(10, 0, -1):
        display_message("System Reset", f"Rebooting in {i}s")
        time.sleep(1)
    os.system("reboot")

# Function to display help for a selected menu item
def display_help(menu_item):
    global selected_index
    help_items = list(help_text.items())
    help_index = 0

    while True:
        with canvas(device) as draw:
            draw.text((0, 0), help_items[help_index][0], font=font_small, fill="white")
            draw.text((0, 20), help_items[help_index][1], font=font_small, fill="white")
            draw.text((0, 50), "Press Select to go back", font=font_small, fill="white")

        if button_up.is_pressed:
            help_index = (help_index - 1) % len(help_items)
            time.sleep(0.2)  # Debounce delay
        elif button_down.is_pressed:
            help_index = (help_index + 1) % len(help_items)
            time.sleep(0.2)  # Debounce delay
        elif button_select.is_pressed:
            break


def get_version_from_file(file_path):
    """
    Extracts the version number from the filename.
    """
    match = re.search(r'backup-data\.tar\.v(\d+\.\d+)\.gpg', file_path)
    if match:
        return match.group(1)
    return None

def read_installed_version(version_file_path):
    """
    Reads the installed version from the version file.
    """
    try:
        with open(version_file_path, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith("Version"):
                    return line.strip().split(" ")[1]
    except Exception as e:
        print(f"Error reading version file: {e}")
    return None

def compare_versions(installed_version, update_version):
    """
    Compares two version strings and returns:
    - 0 if versions are equal
    - 1 if update_version is higher
    - -1 if update_version is lower
    """
    from packaging import version
    if version.parse(installed_version) == version.parse(update_version):
        return 0
    elif version.parse(installed_version) < version.parse(update_version):
        return 1
    else:
        return -1

def display_update_selection_menu(installed_version, update_version, options):
    """
    Displays the update selection menu on the OLED screen.
    Allows the user to navigate through options using Up/Down buttons.
    """
    selected_index = 0

    while True:
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
            draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            draw.text((2, 1), "Update Options", font=font_small, fill="black")

            # Display installed and update versions
            y = 20
            draw.text((2, y), f"Installed: {installed_version}", font=font_medium, fill="white")
            y += 14
            draw.text((2, y), f"Update: {update_version}", font=font_medium, fill="white")
            y += 14

            # Display the selected option
            draw.text((2, y + 1), f"> {options[selected_index]}", font=font_medium, fill="white")

            # Add arrows for scrolling if needed
            if selected_index > 0:
                draw.text((device.width - 10, y - 10), "▲", font=font_small, fill="white")
            if selected_index < len(options) - 1:
                draw.text((device.width - 10, y + 10), "▼", font=font_small, fill="white")

        # Handle button presses
        if button_up.is_pressed:
            selected_index = (selected_index - 1) % len(options)
            time.sleep(0.2)
        elif button_down.is_pressed:
            selected_index = (selected_index + 1) % len(options)
            time.sleep(0.2)
        elif button_select.is_pressed:
            time.sleep(0.2)
            return options[selected_index]  # Return the selected option


def copy_decrypt_extract(update_file_path, update_version):
    """
    Copies the update file to /tmp/update, decrypts it, extracts it, and moves the contents to /backup-data.
    """
    # Create /tmp/update directory if it doesn't exist
    if not os.path.exists("/tmp/update"):
        os.makedirs("/tmp/update")

    # Copy the update file to /tmp/update
    update_file_name = os.path.basename(update_file_path)
    tmp_update_file_path = os.path.join("/tmp/update", update_file_name)
    shutil.copy(update_file_path, tmp_update_file_path)
    print(f"Copied {update_file_name} to /tmp/update")

    # Decrypt the file
    decrypted_file_name = update_file_name.replace(".gpg", "")
    decrypted_file_path = os.path.join("/tmp/update", decrypted_file_name)
    gpg_command = [
        "gpg",
        "--batch",
        "--yes",
        "--passphrase", "Chan@123",
        "--output", decrypted_file_path,
        "--decrypt", tmp_update_file_path
    ]
    try:
        subprocess.run(gpg_command, check=True)
        print(f"Decrypted {update_file_name} to {decrypted_file_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error decrypting {update_file_name}: {e}")
        return False

    # Extract the decrypted tar file
    extract_folder = os.path.join("/tmp/update", update_version)
    if not os.path.exists(extract_folder):
        os.makedirs(extract_folder)
    tar_command = [
        "tar",
        "-xf", decrypted_file_path,
        "-C", extract_folder
    ]
    try:
        subprocess.run(tar_command, check=True)
        print(f"Extracted {decrypted_file_name} to {extract_folder}")
    except subprocess.CalledProcessError as e:
        print(f"Error extracting {decrypted_file_name}: {e}")
        return False

    # NEW: Execute additional update commands
    print("Executing update commands...")
    if not execute_update_commands(update_version):
        print("Update commands execution failed")
        return False

    # Copy contents of extract_folder to /backup-data
    for item in os.listdir(extract_folder):
        src = os.path.join(extract_folder, item)
        dst = os.path.join("/backup-data", item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    print(f"Copied contents of {extract_folder} to /backup-data")

    # Clean up /tmp/update
    shutil.rmtree("/tmp/update")
    print("Cleaned up /tmp/update")

    return True

def update_version_file(version):
    """
    Updates the version file with the new version and current date/month.
    """
    version_file_path = "/backup-data/version"
    current_date = datetime.now().strftime("%b %Y")  # Format: "Feb 2025"
    try:
        with open(version_file_path, "w") as file:
            file.write(f"Version {version}\n")
            file.write(f"{current_date}\n")
        print(f"Updated version file with Version {version} and {current_date}")
    except Exception as e:
        print(f"Error updating version file: {e}")

def reboot_system():
    """
    Reboots the system after a 10-second countdown.
    """
    for i in range(10, 0, -1):
        display_message("Rebooting in", f"{i} seconds...")
        time.sleep(1)
    # Clear the OLED screen
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
    # Reboot the system
    subprocess.run(["reboot"])

def check_for_update():
    """
    Checks for updates on connected USB drives and displays the appropriate menu.
    If no USB drive is plugged in, displays a message and returns to the menu.
    If no update file is found, displays a message and cancels after 3 seconds.
    If multiple update files are found, displays a message and returns to the menu.
    """
    # Create /mnt/update directory if it doesn't exist
    if not os.path.exists("/mnt/update"):
        os.makedirs("/mnt/update")

    # Get USB partitions
    partitions = get_usb_partitions(exclude_disk="mmcblk")

    # Flag to track if an update file was found
    update_found = False

    # Initialize update_files
    update_files = []

    # Check if any USB partitions are found
    if not partitions:
        display_message("Plug USB drive", "with update file")
        time.sleep(3)
        return  # Exit the function and return to the previous menu

    for partition in partitions:
        try:
            # Unmount any existing mount at /mnt/update
            if os.path.ismount("/mnt/update"):
                unmount_partition("/mnt/update")
                print("Unmounted existing /mnt/update")

            # Mount the partition directly under /mnt/update
            mount_partition(partition[0], "/mnt/update")
            print(f"Mounted {partition[0]} to /mnt/update")

            # Search for the backup file in /mnt/update
            update_files = [file for file in os.listdir("/mnt/update") if file.startswith("backup-data.tar.v") and file.endswith(".gpg")]

            if len(update_files) > 1:
                # Multiple update files found
                display_message("Multiple update", "files found, keep just one")
                time.sleep(3)
                unmount_partition("/mnt/update")
                return  # Exit the function and return to the previous menu

            elif len(update_files) == 1:
                # Only one update file found
                update_file_path = os.path.join("/mnt/update", update_files[0])
                update_version = get_version_from_file(update_files[0])
                installed_version = read_installed_version("/backup-data/version")

                if installed_version and update_version:
                    comparison = compare_versions(installed_version, update_version)

                    if comparison == 0:
                        action_options = ["Re-install", "Cancel"]
                    elif comparison == 1:
                        action_options = ["Upgrade", "Cancel"]
                    else:
                        action_options = ["Downgrade", "Cancel"]

                    # Display the update selection menu
                    selected_action = display_update_selection_menu(installed_version, update_version, action_options)

                    if selected_action == "Cancel":
                        print("Update canceled. Returning to menu.")
                        unmount_partition("/mnt/update")
                        return  # Exit the function and return to the previous menu
                    else:
                        print(f"{selected_action} confirmed.")
                        # Perform the selected action
                        if copy_decrypt_extract(update_file_path, update_version):
                            print(f"{selected_action} completed successfully.")
                            # Update the version file
                            update_version_file(update_version)
                            # Display success message and reboot
                            display_message(f"{selected_action} complete", "Rebooting in 10 sec...")
                            reboot_system()
                            update_found = True  # Set flag to True to prevent "No update file found" message
                        else:
                            print(f"{selected_action} failed.")
                        break

            # Unmount the partition after processing
            unmount_partition("/mnt/update")
            print("Unmounted /mnt/update")

            # If an update file was found, exit the loop
            if update_found:
                break

        except Exception as e:
            print(f"Error mounting or processing {partition[0]}: {e}")
            # Unmount if an error occurs
            if os.path.ismount("/mnt/update"):
                unmount_partition("/mnt/update")

    # If no update file was found, display a message and cancel after 3 seconds
    if not update_found and not update_files:
        display_message("No Update in file found in USB", "Going Back ...")
        time.sleep(3)
        print("No update file found. Returning to menu.")
        return

def display_message(title, message, options):
    """
    Displays a message on the OLED screen with title, message, and options.
    """
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        draw.text((2, 2), title, font=font_small, fill="white")
        draw.text((2, 20), message, font=font_medium, fill="white")
        y = 40
        for i, option in enumerate(options):
            draw.text((2, y), f"{i+1}. {option}", font=font_medium, fill="white")
            y += 16

    # Wait for user input (e.g., button press) to handle selection
    while True:
        if button_select.is_pressed:
            selected_option = 1  # Placeholder for actual button logic
            time.sleep(0.2)
            return selected_option


def backup_data_version():
    """Display the version and date until the left button is pressed."""
    try:
        with open("version", "r") as file:
            lines = file.readlines()
            version = lines[0].strip()  # First line for version
            current_date = lines[1].strip()  # Second line for date
    except FileNotFoundError:
        version = "Version Unknown"
        current_date = "Date Unknown"

    while True:  # Keep displaying until the left button is pressed
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")

            # Logo text
            logo_text = "PerrfectBackup"
            logo_bbox = font_small.getbbox(logo_text)
            logo_height = logo_bbox[3] - logo_bbox[1]
            logo_y = 5  # Padding at the top

            # White background for the logo
            draw.rectangle((0, logo_y - 2, device.width, logo_y + logo_height + 2), fill="white")
            logo_x = (device.width - logo_bbox[2]) // 2
            draw.text((logo_x, logo_y), logo_text, font=font_small, fill="black")

            # Decorative line
            draw.line((1, logo_y + logo_height + 5, device.width - 1, logo_y + logo_height + 5), fill="white")

            # Positioning version and date
            version_bbox = font_large.getbbox(version)
            date_bbox = font_medium.getbbox(current_date)
            version_x = (device.width - (version_bbox[2] - version_bbox[0])) // 2
            version_y = logo_y + logo_height + 15
            date_x = (device.width - (date_bbox[2] - date_bbox[0])) // 2
            date_y = version_y + (version_bbox[3] - version_bbox[1]) + 5

            # Draw version and date
            draw.text((version_x, version_y), version, font=font_large, fill="white")
            draw.text((date_x, date_y), current_date, font=font_medium, fill="white")

        # Check if left button is pressed
        if button_left.is_pressed:
            time.sleep(0.2)  # Debounce delay
            return  # Return to settings menu



def get_time_zones():
    # Read the /usr/share/zoneinfo/zone.tab file
    time_zones = {}
    with open("/usr/share/zoneinfo/zone.tab", "r") as f:
        for line in f:
            if line.startswith("#"):  # Skip comments
                continue
            parts = line.strip().split()
            if len(parts) < 3:  # Skip invalid lines
                continue
            time_zone = parts[2]
            region = time_zone.split("/")[0]  # Extract region (e.g., Asia, Europe, America)
            if region not in time_zones:
                time_zones[region] = []
            time_zones[region].append(time_zone)

    # Sort regions alphabetically
    sorted_regions = sorted(time_zones.keys())
    sorted_time_zones = []
    for region in sorted_regions:
        # Sort time zones within each region alphabetically
        sorted_time_zones.extend(sorted(time_zones[region]))

    return sorted_time_zones

def is_leap_year(year):
    """Check if the given year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def get_utc_offset():
    """Get the current system timezone and convert it to UTC offset format (e.g., UTC+5:30)."""
    system_tz = os.popen("timedatectl show --property=Timezone --value").read().strip()
    tz = pytz.timezone(system_tz)
    now = datetime.now(tz)
    
    # Get UTC offset in hours and minutes
    offset_sec = now.utcoffset().total_seconds()
    hours = int(offset_sec // 3600)
    minutes = int((offset_sec % 3600) // 60)

    # Format as UTC+X:Y
    if minutes == 0:
        return f"UTC{hours:+d}"
    else:
        return f"UTC{hours:+d}:{abs(minutes):02d}"

def set_time_manually():
    # Get the list of time zones
    time_zones = get_time_zones()
    selected_time_zone = 0
    # Variables for accelerated scrolling
    scroll_delay = 0.1  # Initial delay between scrolls (in seconds)
    hold_threshold = 0.5  # Time (in seconds) after which scrolling accelerates
    accelerated_delay = 0.02  # Delay between scrolls after holding for hold_threshold
    skip_amount = 5  # Number of items to skip when holding the button
    last_button_press_time = None  # Timestamp of the last button press
    last_button_state = False  # Track the previous state of the button
    time.sleep(0.2)

    # Step 1: Select Time Zone
    while True:
        if button_left.is_pressed:
            time.sleep(0.2)
            return

        system_utc_offset = get_utc_offset()  # Get system timezone as UTC+X format
        current_time = datetime.now().strftime("%H:%M:%S")  # Get current time
        
        with canvas(device) as draw:
            # Title and separator
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
            draw.text((2, 2), "Select Time Zone", font=font_medium, fill="white")
            draw.line((0, 18, device.width, 18), fill="white")  # Line below the title

            # Display the selected time zone
            y = 25  # Position for the selected time zone
            text = time_zones[selected_time_zone]
            text_width = draw.textlength(text, font=font_medium)

            # Handle text wrapping if it exceeds the screen width
            if text_width > device.width - 4:  # 4 pixels padding
                # Split text into two lines
                mid = len(text) // 2
                line1 = text[:mid]
                line2 = text[mid:]
                draw.text((2, y), f"> {line1}", font=font_medium, fill="white")
                draw.text((2, y + 12), f"  {line2}", font=font_medium, fill="white")
            else:
                draw.text((2, y), f"> {text}", font=font_medium, fill="white")

            # Draw arrows if there are more options above or below
            if selected_time_zone > 0:
                draw.text((device.width - 10, y + 10), "▲", font=font_medium, fill="white")  # Up arrow
            if selected_time_zone < len(time_zones) - 1:
                draw.text((device.width - 10, y + 25), "▼", font=font_medium, fill="white")  # Down arrow
            # **Live Time Display at the Bottom with Current Timezone**
            draw.text((2, device.height - 12), f"{current_time}|{system_utc_offset}", font=font_con, fill="white")

        # Button handling for time zone selection
        if button_up.is_pressed:
            current_time = time.time()
            if not last_button_state:  # Button was just pressed
                last_button_press_time = current_time
                selected_time_zone = (selected_time_zone - 1) % len(time_zones)  # Normal scroll
            elif current_time - last_button_press_time > hold_threshold:
                # Accelerated scrolling: skip 10 items
                selected_time_zone = max(0, selected_time_zone - skip_amount)
                time.sleep(accelerated_delay)
            last_button_state = True
        elif button_down.is_pressed:
            current_time = time.time()
            if not last_button_state:  # Button was just pressed
                last_button_press_time = current_time
                selected_time_zone = (selected_time_zone + 1) % len(time_zones)  # Normal scroll
            elif current_time - last_button_press_time > hold_threshold:
                # Accelerated scrolling: skip 10 items
                selected_time_zone = min(len(time_zones) - 1, selected_time_zone + skip_amount)
                time.sleep(accelerated_delay)
            last_button_state = True
        else:
            last_button_state = False  # Reset button state when released

        if button_select.is_pressed:
            time.sleep(0.2)  # Debounce delay
            break  # Proceed to set date and time
        time.sleep(0.1)

    # Set the selected time zone
    os.system(f"sudo timedatectl set-timezone {time_zones[selected_time_zone]}")
    os.environ['TZ'] = time_zones[selected_time_zone]
    time.tzset()  # Reload timezone data for Python
    print(f"Time zone set to: {time_zones[selected_time_zone]}")

    # Step 2: Set Year First
    time_parts = ["Year", "Month", "Day", "Hour", "Minute"]
    current_values = [2023, 1, 1, 0, 0]  # Initial values

    for i, part in enumerate(time_parts):
        while True:
            with canvas(device) as draw:
                # Title and separator
                draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                draw.text((2, 2), f"Set {part}", font=font_medium, fill="white")
                draw.text((device.width - 10, y - 25), "↑", font=font_medium, fill="white")  # Up
                draw.text((device.width - 10, y + 0), "▶", font=font_medium, fill="white")  # Select 
                draw.text((device.width - 10, y + 25), "↓", font=font_medium, fill="white")  # Down 
                draw.line((0, 18, device.width, 18), fill="white")  # Line below the title

                # Display the current value
                y = 25  # Position for the value
                draw.text((2, y), f"> {current_values[i]}", font=font_medium, fill="white")

            # Button handling
            if button_up.is_pressed:
                current_values[i] += 1
                if part == "Year" and current_values[i] > 2099:  # Year (2023-2099)
                    current_values[i] = 2023
                elif part == "Month" and current_values[i] > 12:  # Month (1-12)
                    current_values[i] = 1
                elif part == "Day":
                    # Adjust day based on month and year
                    max_day = 31
                    if current_values[1] == 2:  # February
                        max_day = 29 if is_leap_year(current_values[0]) else 28
                    elif current_values[1] in {4, 6, 9, 11}:  # Months with 30 days
                        max_day = 30
                    if current_values[i] > max_day:
                        current_values[i] = 1
                elif part == "Hour" and current_values[i] > 23:  # Hour (0-23)
                    current_values[i] = 0
                elif part == "Minute" and current_values[i] > 59:  # Minute (0-59)
                    current_values[i] = 0
                time.sleep(0.2)

            if button_down.is_pressed:
                current_values[i] -= 1
                if part == "Year" and current_values[i] < 2023:  # Year (2023-2099)
                    current_values[i] = 2099
                elif part == "Month" and current_values[i] < 1:  # Month (1-12)
                    current_values[i] = 12
                elif part == "Day":
                    # Adjust day based on month and year
                    max_day = 31
                    if current_values[1] == 2:  # February
                        max_day = 29 if is_leap_year(current_values[0]) else 28
                    elif current_values[1] in {4, 6, 9, 11}:  # Months with 30 days
                        max_day = 30
                    if current_values[i] < 1:
                        current_values[i] = max_day
                elif part == "Hour" and current_values[i] < 0:  # Hour (0-23)
                    current_values[i] = 23
                elif part == "Minute" and current_values[i] < 0:  # Minute (0-59)
                    current_values[i] = 59
                time.sleep(0.2)

            if button_select.is_pressed:
                time.sleep(0.2)  # Debounce delay
                break  # Move to the next setting

    # Step 3: Confirmation screen
    confirmation_options = ["Confirm", "Restart", "Back"]
    selected_option = 0

    while True:
        with canvas(device) as draw:
            # Title and separator
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
            draw.text((2, 2), "Confirm Time", font=font_medium, fill="white")
            draw.line((0, 18, device.width, 18), fill="white")  # Line below the title
            draw.line((0, 42, device.width, 42), fill="white")  # Line below the title

            # Display the entered time
            entered_time = f"{current_values[0]:02d}-{current_values[1]:02d}-{current_values[2]} {current_values[3]:02d}:{current_values[4]:02d}"
            draw.text((2, 25), entered_time, font=font_medium, fill="white")

            # Display the selected option
            y = 45  # Position for the selected option
            option = confirmation_options[selected_option]
            draw.text((2, y), f"> {option}", font=font_medium, fill="white")

            # Draw arrows if there are more options above or below
            if selected_option > 0:
                draw.text((device.width - 10, y - 3), "▲", font=font_small, fill="white")  # Up arrow
            if selected_option < len(confirmation_options) - 1:
                draw.text((device.width - 10, y + 10), "▼", font=font_small, fill="white")  # Down arrow

        # Button handling for confirmation screen
        if button_up.is_pressed:
            selected_option = (selected_option - 1) % len(confirmation_options)
            time.sleep(0.2)

        if button_down.is_pressed:
            selected_option = (selected_option + 1) % len(confirmation_options)
            time.sleep(0.2)

        if button_select.is_pressed:
            time.sleep(0.2)  # Debounce delay
            if confirmation_options[selected_option] == "Confirm":
                # Set the system time
                #new_time = f"{current_values[2]}-{current_values[0]:02d}-{current_values[1]:02d} {current_values[3]:02d}:{current_values[4]:02d}:00"
                new_time = f"{current_values[0]:02d}-{current_values[1]:02d}-{current_values[2]} {current_values[3]:02d}:{current_values[4]:02d}:00"
                os.system(f"date -s '{new_time}'")
                os.system(f"sudo hwclock --systohc")
                os.system(f"sudo fake-hwclock save")
                #os.system("sudo timedatectl set-ntp false")
                # Update /etc/fake-hwclock.data
                #with open("/etc/fake-hwclock.data", "w") as f:
                #    f.write(new_time.replace("-", " "))  # Format: YYYY MM DD HH:MM:SS

                # Display confirmation message
                with canvas(device) as draw:
                    draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                    draw.text((2, 2), "Time Set!", font=font_medium, fill="white")
                    draw.text((2, 25), entered_time, font=font_small, fill="white")
                time.sleep(2)  # Show confirmation for 2 seconds
                break  # Return to the main menu

            elif confirmation_options[selected_option] == "Restart":
                return set_time_manually()  # Restart the time-setting process

            elif confirmation_options[selected_option] == "Back":
                break  # Return to the main menu without saving
        time.sleep(0.1) #Reduce High CPU Usage

def navigate_menu_time(menu_items, title="← Settings", reset_position=False):
    global selected_index, last_settings_menu_index
    
    # Reset position if requested or when entering settings menu
    if reset_position or (menu_items == settings_menu_items and reset_position):
        selected_index = 0
        last_settings_menu_index = 0

    # Restore last position when entering settings menu (original logic)
    if menu_items == settings_menu_items and not reset_position:
        selected_index = last_settings_menu_index

    max_visible_items = 2  # Number of items visible at once
    prev_index = -1  # Track previous index to avoid unnecessary redraws
    last_button_time = 0
    button_cooldown = 0.3  # 300ms cooldown

    while True:
        current_time = time.time()
        if selected_index != prev_index:  # Only redraw if selection changed
            with canvas(device) as draw:
                # Clear the screen
                draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")

                # Draw the title and line separator
                draw.text((2, 2), title, font=font_medium, fill="white")
                draw.line((0, 18, device.width, 18), fill="white")  # Line below the title

                # Calculate the start index for visible items
                start_index = selected_index - (selected_index % max_visible_items)

                # Draw visible menu items
                for i in range(max_visible_items):
                    if start_index + i >= len(menu_items):
                        break  # Stop if we exceed the menu items

                    y = 25 + i * 18  # Adjust y position and spacing
                    item = menu_items[start_index + i]
                    icon = item[0]  # Icon part
                    text = item[1:]  # Text part

                    # Highlight the selected item
                    if start_index + i == selected_index:
                        draw.rectangle((0, y - 1, device.width, y + 15), outline="white", fill="white")
                        draw.text((2, y), icon, font=font_icons, fill="black")  # Icon in black
                        draw.text((20, y), text, font=font_medium, fill="black")  # Text in black
                    else:
                        draw.text((2, y), icon, font=font_icons, fill="white")  # Icon in white
                        draw.text((20, y), text, font=font_medium, fill="white")  # Text in white

                # Draw navigation indicators
                if selected_index > 0:
                    draw.text((device.width // 2 + 50, device.height - 67), "▲", font=font_small, fill="white")
                if selected_index < len(menu_items) - 1:
                    draw.text((device.width // 2 + 50, device.height - 58), "▼", font=font_small, fill="white")

            prev_index = selected_index

        # Handle button presses with debouncing
        if button_up.is_pressed and current_time - last_button_time > button_cooldown:
            last_button_time = current_time
            selected_index = max(0, selected_index - 1)
            time.sleep(0.2)
        elif button_down.is_pressed and current_time - last_button_time > button_cooldown:
            last_button_time = current_time
            selected_index = min(len(menu_items) - 1, selected_index + 1)
            time.sleep(0.2)
        elif button_select.is_pressed and current_time - last_button_time > button_cooldown:
            last_button_time = current_time
            # Save the current position before exiting
            if menu_items == settings_menu_items:
                last_settings_menu_index = selected_index
            time.sleep(0.2)
            return menu_items[selected_index]
        elif button_left.is_pressed and current_time - last_button_time > button_cooldown:
            last_button_time = current_time
            # Save the current position before exiting
            if menu_items == settings_menu_items:
                last_settings_menu_index = selected_index
            time.sleep(0.2)
            return "\uf28d Back"

        time.sleep(0.1)  # Reduce CPU usage

def start_hostapd_service():
    """Start the hostapd service"""
    print("Starting hostapd service...")
    subprocess.run(['sudo', 'rfkill', 'unblock', 'wifi'], check=True)
    subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], check=True)

# Define Flask control functions
def start_flask_service():
    """Start the Flask service"""
    print("Starting Flask service...")
    subprocess.run(['sudo', 'systemctl', 'start', 'web-ui-flask-app.service'], check=True)

def stop_flask_service():
    """Stop the Flask & hostapd service and unmount USB drives if mounted"""
    print("Stopping Flask & hostapd service...")
    
    # Stop the Flask and hostapd services
    subprocess.run(['sudo', 'systemctl', 'stop', 'web-ui-flask-app.service'], check=True)
    subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], check=True)
    
    # Disable Wi-Fi
    subprocess.run(['sudo', 'rfkill', 'block', 'wifi'], check=True)

    subprocess.run(['sudo', 'umount', '/mnt/usb/source'])
    subprocess.run(['sudo', 'umount', '/mnt/usb/destination'])
    subprocess.run(['sudo', 'umount', '/mnt/usb/check'])

# Hardcoded IP address
HARD_CODED_IP = "192.168.0.1"

# Function to display multiple lines of text on the OLED screen
def display_message_wifi_oled(*lines, font_icons):
    """
    Display multiple lines of text on the OLED with a border, icons, and highlight.

    Args:
        *lines: Variable-length argument list containing the text lines to display.
        font_icons: The font used for rendering icons.
    """
    # Define icons using the Unicode from Line Awesome font
    phone_icon = "\uf10b"  # Phone icon
    wifi_icon = "\uf1eb"   # Wi-Fi icon
    lock_icon = "\uf023"   # Lock icon (password)

    # Set the font for regular text
    font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)

    with canvas(device) as draw:
        # Draw the outer border
        draw.rectangle((0, 0, 127, 63), outline="white", width=1)

        y_position = 0  # Starting y position for text
        line_spacing = 15  # Space between lines

        # Draw "Connect Phone" text inside a white highlight box
        if len(lines) > 0:
            connect_phone_text = lines[0]
            connect_phone_box_height = 15
            draw.rectangle((0, y_position, device.width, y_position + connect_phone_box_height), outline="white", fill="white")
            # Render icon with font_icons and text with font_medium
            draw.text((5, y_position + 3), phone_icon, font=font_icons, fill="black")  # Icon
            draw.text((20, y_position + 3), connect_phone_text, font=font_medium, fill="black")  # Text
            y_position += connect_phone_box_height + 1

            # Draw a thin line under the "Connect Phone" box
            draw.line((0, y_position, device.width, y_position), fill="white")
            y_position += 2  # Add some spacing after the line

        # Draw Wi-Fi text with icon
        if len(lines) > 1:
            wifi_text = lines[1]
            draw.text((5, y_position), wifi_icon, font=font_icons, fill="white")  # Icon
            draw.text((25, y_position), wifi_text, font=font_medium, fill="white")  # Text
            y_position += line_spacing

        # Draw Password text with icon
        if len(lines) > 2:
            password_text = lines[2]
            draw.text((5, y_position), lock_icon, font=font_icons, fill="white")  # Icon
            draw.text((25, y_position), password_text, font=font_medium, fill="white")  # Text
            y_position += line_spacing

        # Draw "SELECT" text in a white highlight box (width as wide as the text)
        if len(lines) > 3:
            select_text = lines[3]
            select_text_width = int(draw.textlength(select_text, font=font_medium))  # Convert to integer
            draw.rectangle((0, y_position , 5 + select_text_width + 30, y_position + 15), outline="white", fill="white")
            draw.text((15, y_position + 1), select_text, font=font_medium, fill="black")

def notify_incomplete_session(device):
    session_file = "/backup-data/session.lock"
    if os.path.exists(session_file):
        try:
            with open(session_file) as f:
                mode, timestamp = f.read().strip().split(",", 1)
        except:
            mode, timestamp = "unknown", "unknown"

        # Show simple notification
        with canvas(device) as draw:
            draw.rectangle((0,0,device.width,device.height), outline="black", fill="black")
            draw.text((2,2), "Last Copy Interrupted!", font=font_small, fill="white")
            draw.text((2,20), f"Mode: {mode} copy", font=font_small, fill="white")
            draw.text((2,35), "Please restart copy", font=font_small, fill="white")
            draw.text((2,50), "operation again...", font=font_small, fill="white")

        # Wait for any button press to dismiss
        while not (button_up.is_pressed or button_down.is_pressed or 
                   button_left.is_pressed or button_right.is_pressed or 
                   button_select.is_pressed or button_key1.is_pressed or 
                   button_key2.is_pressed or button_key3.is_pressed):
            time.sleep(0.1)

        # Clear session file so it won't nag again
        os.remove(session_file)


# Function to generate and display a borderless QR code
def display_qr_code(url, mode="wifi"):
    device.contrast(50)

    # Generate QR code once
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2,
        border=2
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white").convert("1")

    qr_w, qr_h = img.size
    qr_x = (device.width - qr_w) // 2
    qr_y = (device.height - 16 - qr_h) // 2

    font = font_small

    if mode == "wifi":
        labels = [
            'Conn Wifi "BackMeUp"',
            "Then Scan QR Code",
            "Backup via  WebUI"
        ]
    elif mode == "reporting":
        labels = [
            'Conn Wifi "BackMeUp"',
            "Then Scan QR Code",
            "Check Reports History"
        ]
    elif mode == "checkfiles":
        labels = [
            '1. Conn Wifi BackMeUp',
            "2. Then Scan QR Code",
            "To Access WebUI",
            "Press WebUI to Exit"
        ]
    else:
        labels = [
            'Conn Wifi "BackMeUp"',
            "Then Scan QR Code",
            "Backup via WebUI"
        ]

    label_index = 0
    last_toggle = time.time()
    current_label = labels[label_index]
    force_redraw = True
    flash_state = True
    last_flash = time.time()

    while not button_left.is_pressed:
        current_time = time.time()
        
        # Quick check if rsync copy is running
        copy_active = False
        try:
            result = subprocess.run(['pgrep', 'rsync'], capture_output=True, text=True)
            copy_active = (result.returncode == 0)
        except:
            pass

        if copy_active:
            # Flash "Copy-in-Progress"
            if current_time - last_flash > 0.5:  # Flash every 0.5 seconds
                flash_state = not flash_state
                last_flash = current_time
                force_redraw = True
            current_label = "Copy-in-Progress"
        else:
            # Normal rotating labels
            if current_time - last_toggle >= 2:
                label_index = (label_index + 1) % len(labels)
                current_label = labels[label_index]
                last_toggle = current_time
                force_redraw = True
            flash_state = True  # Always visible when not copying

        if force_redraw:
            with canvas(device) as draw:
                # Draw QR code
                for x in range(qr_w):
                    for y in range(qr_h):
                        if img.getpixel((x, y)) == 0:
                            draw.point((qr_x + x, qr_y + y), fill="white")

                # Draw text (flashing during copy)
                text_bbox = draw.textbbox((0, 0), current_label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_x = (device.width - text_width) // 2
                text_y = device.height - 12
                
                if flash_state:  # Only draw when visible
                    draw.text((text_x, text_y), current_label, font=font, fill="white")

            force_redraw = False

        time.sleep(0.05)

    device.contrast(128)

def get_partition_label(device):
    """
    Returns the label of the partition if it exists, otherwise returns 'No Label'.
    The label is trimmed to 5 characters.
    """
    label = None
    device_path = f"/dev/{device}"  # Ensure the full device path is used
    try:
        # Use blkid command to get the partition label
        label = os.popen(f"blkid -o value -s LABEL {device_path}").read().strip()
        print(f"blkid output for {device_path}: {label}")  # Debug print
        if not label:
            # Check if device appears in lsblk output with a label
            lsblk_output = os.popen(f"lsblk -no LABEL {device_path}").read().strip()
            print(f"lsblk output for {device_path}: {lsblk_output}")  # Debug print
            if lsblk_output:
                label = lsblk_output
    except Exception as e:
        print(f"Error fetching label for {device_path}: {e}")  # Debug print
        label = None
    return label[:5] if label else "No Label"


def get_partition_info(mount_point):
    """
    Retrieves total and free size for a given mount point.
    Returns sizes in GB as strings.
    """
    stat = os.statvfs(mount_point)
    total_size = (stat.f_blocks * stat.f_frsize) / (1024**3)  # Convert bytes to GB
    free_size = (stat.f_bavail * stat.f_frsize) / (1024**3)   # Available free space for unprivileged users
    return f"{total_size:.2f}GB", f"{free_size:.2f}GB"

def disk_info_menu():
    """
    Displays total and free sizes of mounted USB partitions with scrolling 
    and returns to the main menu upon Select or Left button press.
    """
    mounted_partitions = []
    partitions = get_usb_partitions(exclude_disk="mmcblk")  

    # Mount eligible partitions
    for partition in partitions:
        if float(partition[1].replace("GB", "")) >= 1:  # Only consider partitions >= 1GB
            mount_point = f"/mnt/{partition[0]}"
            mount_partition(partition[0], mount_point)
            total_size, free_size = get_partition_info(mount_point)
            label = get_partition_label(partition[0])  # Get label (max 5 chars)
            mounted_partitions.append((label, total_size, free_size, mount_point))

    # If no partitions found, show message and return
    if not mounted_partitions:
        display_message("No Eligible Disks", "Connect USB Disk")
        time.sleep(2)
        return

    selected_index = 0
    prev_index = -1  # Track previous selection

    while True:
        if selected_index != prev_index:  # Update display only if index changes
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
                draw.text((2, 1), "Disk Info", font=font_small, fill="black")

                # Display current partition info
                current_partition = mounted_partitions[selected_index]
                y = 20
                draw.text((2, y), f"Label: {current_partition[0]}", font=font_medium, fill="white")
                y += 16
                draw.text((2, y), f"Total: {current_partition[1]}", font=font_medium, fill="white")
                y += 16
                draw.text((2, y), f"Free: {current_partition[2]}", font=font_medium, fill="white")

                # Draw up/down arrows if scrolling is available
                if selected_index > 0:
                    draw.text((device.width - 10, 18), "▲", font=font_small, fill="white")
                if selected_index < len(mounted_partitions) - 1:
                    draw.text((device.width - 10, device.height - 10), "▼", font=font_small, fill="white")

            prev_index = selected_index  # Store last index update

        # Handle button presses
        if button_up.is_pressed and selected_index > 0:
            selected_index -= 1
            time.sleep(0.2)
        elif button_down.is_pressed and selected_index < len(mounted_partitions) - 1:
            selected_index += 1
            time.sleep(0.2)
        elif button_select.is_pressed or button_left.is_pressed:
            time.sleep(0.2)
            break  # Exit the menu

        time.sleep(0.1)  # Reduce CPU usage

    # Unmount partitions before returning to the menu
    for _, _, _, mount_point in mounted_partitions:
        unmount_partition(mount_point)


# Read and parse CSV log file
def read_and_parse_csv_log(log_file_path):
    if not os.path.exists(log_file_path):
        return None  # Return None if file doesn't exist
    
    logs = []
    with open(log_file_path, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) == 5:  # Assuming CSV has 4 columns: Start, End, Size, Time
                logs.append({
                    "start": row[0],
                    "end": row[1],
                    "size": row[2],
                    "time": row[3],
                    "Info": row[4]
                })
    return logs

# Display one log entry on the OLED screen
def display_log_entry(log_entry):
    with canvas(device) as draw:
        draw.text((1, 0), f"{log_entry['start']}", font=font_small, fill="white")
        draw.text((1, 12), f"{log_entry['end']}", font=font_small, fill="white")
        draw.text((1, 24), f"Size:{log_entry['size']}", font=font_small, fill="white")
        draw.text((1, 36), f"Time:{log_entry['time']}", font=font_small, fill="white")
        draw.text((1, 48), f"Info: {log_entry['Info']}", font=font_small, fill="white")

# Scroll through logs using the up and down buttons
def scroll_logs(logs):
    current_index = 0
    total_logs = len(logs)
    prev_index = -1  # Track previous index

    def display_log_entry_with_arrows(log_entry, index):
        with canvas(device) as draw:
            # Normal log entry display
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")

            draw.text((1, 0), f"{log_entry['start']}", font=font_small, fill="white")
            draw.text((1, 12), f"{log_entry['end']}", font=font_small, fill="white")
            draw.text((1, 24), f"Size: {log_entry['size']}", font=font_small, fill="white")
            draw.text((1, 36), f"Time: {log_entry['time']}", font=font_small, fill="white")

            # White background and black text for the 5th element
            draw.rectangle((0, 48, device.width, 60), outline="black", fill="white")
            draw.text((1, 48), f"{log_entry['Info']}", font=font_small, fill="black")

            # Add arrows for scrolling if needed
            if index > 0:
                draw.text((device.width - 10, 1), "▲", font=font_small, fill="white")
            if index < total_logs - 1:
                draw.text((device.width - 10, device.height - 54), "▼", font=font_small, fill="white")

    while True:
        if current_index != prev_index:  # Update only if index changes
            display_log_entry_with_arrows(logs[current_index], current_index)
            prev_index = current_index

        if button_up.is_pressed and current_index > 0:
            current_index -= 1
            time.sleep(0.2)
        elif button_down.is_pressed and current_index < total_logs - 1:
            current_index += 1
            time.sleep(0.2)
        elif button_left.is_pressed:
            time.sleep(0.2)
            return
        time.sleep(0.1)  # Reduce CPU usage


# Copy History menu logic
def copy_history_menu():
    log_file_path = 'copy-log.csv'  # Path to your CSV log file

    # Read and parse the log file
    logs = read_and_parse_csv_log(log_file_path)

    if logs is None or not logs:
        display_message("History not found", sub_message="Going back....")
        time.sleep(2)  # Display the message for 5 seconds
        return  # Automatically go back to the main menu after 5 seconds

    # Start scrolling through logs
    scroll_logs(logs)

def disk_check(partition):
    # Unmount the partition if it's mounted
    mount_point_src = "/mnt/src"
    mount_point_dst = "/mnt/dst"
    
    if os.path.ismount(mount_point_src):
        unmount_partition(mount_point_src)
    
    if os.path.ismount(mount_point_dst):
        unmount_partition(mount_point_dst)
    
    # Run the disk check
    print(f"Checking disk: /dev/{partition}")
    os.system(f"sudo fsck -y /dev/{partition}")
    display_message(f"Disk Check Complete", sub_message=f"/dev/{partition}")
    time.sleep(2)

def disk_check_menu():
    while True:
        partitions = get_usb_partitions(exclude_disk="mmcblk")  # Exclude Raspberry Pi's SD card
        if not partitions:
            display_message("No Disks Found", sub_message="Connect a Disk")
            time.sleep(2)
            return
        
        selected_index = 0
        while True:
            display_selection(partitions, selected_index, title="Select Disk to Check")
            if button_up.is_pressed:
                selected_index = (selected_index - 1) % len(partitions)
                time.sleep(0.2)
            if button_down.is_pressed:
                selected_index = (selected_index + 1) % len(partitions)
                time.sleep(0.2)
            if button_select.is_pressed:
                time.sleep(0.2)
                partition = partitions[selected_index][0]
                disk_check(partition)
                return
            if button_left.is_pressed:
                time.sleep(0.2)
                return

def display_menu(menu, title="PurrfectBackup"):
    global selected_index
    max_visible_items = 2  # Adjust based on the number of items you want to display at once
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        draw.text((2, 2), title, font=font_medium, fill="white")
        draw.line((0, 18, device.width, 18), fill="white")  # Line below the title

        start_index = selected_index - (selected_index % max_visible_items)
        for i in range(max_visible_items):
            if start_index + i >= len(menu):
                break
            y = 25 + i * 18  # Adjust y position and spacing
            item = menu[start_index + i]
            icon = item[0]  # Icon part
            text = item[1:]  # Text part

            text_width, text_height = draw.textbbox((0, 0), text, font=font_medium)[2:4]
            icon_width = draw.textbbox((0, 0), icon, font=font_icons)[2]  # Icon width
            padding = 1  # Add padding for better alignment

            if start_index + i == selected_index:
                draw.rectangle((0, y - padding, device.width, y + text_height + padding), outline="white", fill="white")
                draw.text((2, y), icon, font=font_icons, fill="black")  # Icon in black
                draw.text((icon_width + 5, y), text, font=font_medium, fill="black")  # Text in black
            else:
                draw.text((2, y), icon, font=font_icons, fill="white")  # Icon in white
                draw.text((icon_width + 5, y), text, font=font_medium, fill="white")  # Text in white
        # Debug: Draw arrows if needed
        show_up_arrow = selected_index > 0  # Check if we can scroll up
        show_down_arrow = selected_index + max_visible_items < len(menu) + 1   # Check if we can scroll down

        # Draw Up Arrow
        if show_up_arrow:
            draw.text((device.width // 2 + 50, device.height - 67), "▲", font=font_small, fill="white")

        # Draw Down Arrow
        if show_down_arrow:
            draw.text((device.width // 2 + 50, device.height - 58), "▼", font=font_small, fill="white")


def navigate_menu(menu, title="PurrfectBackup", check_special_buttons=True):
    global selected_index, last_main_menu_index
    
    # Restore last position if coming back to main menu
    if menu == menu_items:
        selected_index = last_main_menu_index
    
    prev_index = -1  # Store previous selection
    max_visible_items = 3  # Number of visible items
    last_button_check = time.time()
    
    # Double-tap tracking
    last_up_press_time = 0
    double_tap_threshold = 0.5  # 500ms for double-tap
    
    while True:
        # Check for special button presses every 100ms
        current_time = time.time()
        if current_time - last_button_check >= 0.1 and check_special_buttons:
            last_button_check = current_time
            
            if button_key1.is_pressed:
                handle_brightness_control()
                time.sleep(0.5)
                return "KEY1"
                
            if button_key2.is_pressed:
                disk_info_menu()
                time.sleep(0.5)
                selected_index = 0
                prev_index = -1
                
            if button_key3.is_pressed:
                time.sleep(0.5)
                return "KEY3"
        
        # Only update display if selection changed
        if selected_index != prev_index:
            display_menu(menu, title)
            prev_index = selected_index

        # Handle navigation buttons
        if button_up.is_pressed:
            current_time = time.time()
            
            # Check for double-tap on "Just Copy"
            if selected_index == 0 and menu == menu_items:
                if current_time - last_up_press_time < double_tap_threshold:
                    # Double-tap detected - show date/time
                    display_current_datetime()
                    # After returning from date/time, refresh the menu
                    prev_index = -1  # Force redraw
                    last_up_press_time = 0  # Reset double-tap timer
                else:
                    # Single tap - normal navigation or store time for potential double-tap
                    last_up_press_time = current_time
                    selected_index = max(0, selected_index - 1)  # Normal up navigation
            else:
                # Normal up navigation for other items
                selected_index = max(0, selected_index - 1)
            
            time.sleep(0.2)
                
        elif button_down.is_pressed:
            selected_index = min(len(menu) - 1, selected_index + 1)
            last_up_press_time = 0  # Reset double-tap timer on down press
            time.sleep(0.2)
            
        elif button_select.is_pressed:
            # Save position before leaving
            if menu == menu_items:
                last_main_menu_index = selected_index
            last_up_press_time = 0  # Reset double-tap timer
            time.sleep(0.2)
            return menu[selected_index]
            
        elif button_right.is_pressed and menu[selected_index] == "\uf013 Settings →":
            # Save position before leaving
            if menu == menu_items:
                last_main_menu_index = selected_index
            last_up_press_time = 0  # Reset double-tap timer
            time.sleep(0.2)
            return menu[selected_index]
            
        elif button_right.is_pressed and menu[selected_index] == "\uf0a0 Built-in SSD →":
            # Save position before leaving
            if menu == menu_items:
                last_main_menu_index = selected_index
            last_up_press_time = 0  # Reset double-tap timer
            time.sleep(0.2)
            return menu[selected_index]
            
        elif button_right.is_pressed:  # Help button
            last_up_press_time = 0  # Reset double-tap timer
            time.sleep(0.2)

        # Clear double-tap timer if too much time has passed
        if last_up_press_time > 0 and current_time - last_up_press_time > double_tap_threshold:
            last_up_press_time = 0

        time.sleep(0.1)  # Reduce CPU usage

def handle_shutdown_or_reboot(action):
    mount_point_src = "/mnt/src"
    mount_point_dst = "/mnt/dst"
    
    # Display message on OLED
    display_message("Ejecting Drives", sub_message=f"System {action.capitalize()}...")
    
    # Unmount drives if mounted
    if os.path.ismount(mount_point_src):
        unmount_partition(mount_point_src)
    
    if os.path.ismount(mount_point_dst):
        unmount_partition(mount_point_dst)
    
    time.sleep(3)  # Wait for 3 seconds to display the message
    
    # Clear screen
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
    
    # Perform the action (shutdown or reboot)
    if action == "shutdown":
        os.system("sudo shutdown now")
    elif action == "reboot":
        os.system("sudo reboot")


def clear_display():
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        time.sleep(0.5)


def navigate_shutdown_menu():
    global selected_index
    selected_index = 0

    while True:
        choice = navigate_menu(shutdown_menu_items, title="System Menu")
        if choice == "\uf28d Shutdown":
            clear_display()
            display_message("Ejecting Drives", sub_message="Shutdown...")
            time.sleep(3)
            #clear_display()  # Clear the display
            unmount_partition("/mnt/src")
            unmount_partition("/mnt/dst")
            os.system('sudo shutdown -h now')
            # Terminate the current script using signal
            os.kill(os.getpid(), signal.SIGTERM)  # Send SIGTERM to terminate the script
            #sys.exit()  # This will stop further execution of the script
        elif choice == "\uf021 Reboot":
            display_message("Ejecting Drives", sub_message="Rebooting...")
            time.sleep(3)
            clear_display()  # Clear the display
            unmount_partition("/mnt/src")
            unmount_partition("/mnt/dst")
            os.system('sudo reboot')
            os.kill(os.getpid(), signal.SIGTERM)  # Send SIGTERM to terminate the script
        elif choice == "\uf28d Cancel":
            return


def display_message(message, sub_message=None, icon=None):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)

    max_width = device.width
    max_height = device.height

    with canvas(device) as draw:
        draw.rectangle((0, 0, max_width, max_height), outline="black", fill="black")

        icon_height = 0
        if icon:
            icon_width, icon_height = icon.size
            icon_x = (max_width - icon_width) // 2
            draw.bitmap((icon_x, 0), icon, fill="white")

        lines = []
        words = message.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if draw.textlength(test_line, font=font) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        total_text_height = len(lines) * 12
        if sub_message:
            total_text_height += 10
        total_text_height += icon_height

        y = (max_height - total_text_height) // 2 + icon_height
        for line in lines:
            text_width = draw.textlength(line, font=font)
            x = (max_width - text_width) // 2
            draw.text((x, y), line, font=font, fill="white")
            y += 12

        if sub_message:
            sub_width = draw.textlength(sub_message, font=small_font)
            sub_x = (max_width - sub_width) // 2
            draw.text((sub_x, y), sub_message, font=small_font, fill="white")

        draw.line((0, max_height - 2, max_width, max_height - 2), fill="white", width=1)
        draw.line((0, icon_height, max_width, icon_height), fill="white", width=1)

def display_selection(partitions, selected_index, title="Select Partition"):
    with canvas(device) as draw:
        # Clear the display and draw the title bar
        draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
        draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
        draw.text((2, 1), title, font=font_small, fill="black")

        # Display two partitions at a time
        max_visible_items = 2  # Show only two partitions at a time
        start_index = (selected_index // max_visible_items) * max_visible_items  # Calculate the starting index for the pair

        # Iterate over the visible partitions
        for i, (name, size, free_space, label) in enumerate(partitions[start_index:start_index + max_visible_items]):
            y = 18 + (i * 20)  # Adjust spacing to fit multi-line entries
            # Display label (first 5 chars of label, or "NO-LBL" if no label exists)
            display_name = label[:5] if label != "NO-LBL" else "NO-LBL"

            if start_index + i == selected_index:
                # Highlight the selected partition
                draw.rectangle((0, y, device.width, y + 14), outline="white", fill="white")
                draw.text((2, y), f"> {display_name} {size}", font=font_medium, fill="black")
            else:
                # Display non-selected partitions
                draw.text((2, y), f"  {display_name} {size}", font=font_medium, fill="white")
                # Display navigation instructions at the bottom
                draw.text((2, device.height - 10), "▲  ▼ Select Disk", font=font_small, fill="white")

def get_usb_partitions(exclude_disk=None):
    result = os.popen('lsblk -o NAME,SIZE,TYPE,LABEL -nr').readlines()  # Ensure LABEL is included
    partitions = []
    for line in result:
        columns = line.strip().split()
        
        # If the line has 3 columns, add a placeholder for LABEL
        if len(columns) == 3:
            name, size, ptype = columns
            label = "NO-LBL"  # Default label if missing
        elif len(columns) == 4:
            name, size, ptype, label = columns
        else:
            continue  # Skip lines that don't match the expected number of columns

        if ptype == 'part' and not name.startswith('mmcblk'):
            if 'G' in size:
                size_float = float(size.replace('G', ''))
            elif 'T' in size:
                size_float = float(size.replace('T', '')) * 1024
            else:
                continue  # skip if size is not in GB or TB

            if exclude_disk and name.startswith(exclude_disk):
                continue

            # Get free space using 'df' command
            free_space = os.popen(f"df --output=avail -BG /dev/{name} | tail -1").read().strip().replace('G', '')
            try:
                free_space_float = float(free_space)
            except ValueError:
                free_space_float = 0.0

            # Add partition data with label (or "NO-LBL" if missing)
            partitions.append((name, f"{size_float:.2f}GB", f"{free_space_float:.2f}GB", label))
    
    return partitions


def wait_for_new_device(exclude_disk):
    display_message("Plug Destination", "Hard Drive")
    while True:
        if button_left.is_pressed:
            return None

        partitions = get_usb_partitions(exclude_disk=exclude_disk)
        if partitions:
            return partitions
        time.sleep(1)

def select_partition(mode, exclude_disk=None, allow_nvme_source=False):
    while True:
        # Check if left button is pressed to return to the main menu
        if button_left.is_pressed:
            # Wait for button release
            while button_left.is_pressed:
                time.sleep(0.05)
            return None

        partitions = get_usb_partitions(exclude_disk=exclude_disk)
        
        # ADD THIS FILTERING LOGIC:
        if mode == 'source' and not allow_nvme_source:
            partitions = [p for p in partitions if not p[0].startswith('nvme')]
        
        if not partitions:
            # Use the exact same display as before
            display_message(f"Plug {mode.capitalize()} Device!", "Disk or Card")
            
            # Wait for either LEFT button or new device detection with proper button handling
            last_check = time.time()
            button_pressed = False
            
            while True:
                # Check for LEFT button with press-and-release
                if button_left.is_pressed and not button_pressed:
                    button_pressed = True
                    while button_left.is_pressed:
                        time.sleep(0.05)
                    return None
                elif not button_left.is_pressed:
                    button_pressed = False
                
                # Check for new partitions every 1 second (same as before)
                current_time = time.time()
                if current_time - last_check > 1:
                    partitions = get_usb_partitions(exclude_disk=exclude_disk)
                    # Apply the same filter for new partitions
                    if mode == 'source' and not allow_nvme_source:
                        partitions = [p for p in partitions if not p[0].startswith('nvme')]
                    if partitions:
                        break  # Exit the waiting loop if device found
                    last_check = current_time
                
                time.sleep(0.1)
            continue  # Go back to main loop to process the new partitions

        if len(partitions) == 1:
            partition = partitions[0]
            print(f"Auto-selected {mode}: {partition[0]} {partition[1]}")
            return partition

        selected_index = 0
        button_pressed = False
        
        while True:
            # Display two partitions at a time (same as before)
            start = (selected_index // 2) * 2  # Calculate the starting index for the pair
            end = start + 2  # Display two partitions
            display_partitions = partitions[start:end]  # Get the current pair of partitions

            # Display the partitions with the existing layout (same as before)
            display_selection(display_partitions, selected_index % 2, f"{mode.upper()} DISK")

            # Handle button presses with press-and-release logic
            if button_left.is_pressed and not button_pressed:
                button_pressed = True
                while button_left.is_pressed:
                    time.sleep(0.05)
                return None

            elif button_up.is_pressed and not button_pressed:
                button_pressed = True
                while button_up.is_pressed:
                    time.sleep(0.05)
                selected_index = (selected_index - 1) % len(partitions)
                
            elif button_down.is_pressed and not button_pressed:
                button_pressed = True
                while button_down.is_pressed:
                    time.sleep(0.05)
                selected_index = (selected_index + 1) % len(partitions)
                
            elif button_select.is_pressed and not button_pressed:
                button_pressed = True
                while button_select.is_pressed:
                    time.sleep(0.05)
                return partitions[selected_index]
                
            else:
                button_pressed = False

            time.sleep(0.1) # Avoid High CPU

def mount_partition(partition, mount_point):
    ensure_mount_point_exists(mount_point)
    os.system(f"sudo mount /dev/{partition} {mount_point}")
    print(f"Mounted /dev/{partition} to {mount_point}")

def unmount_partition(mount_point):
    os.system(f"sudo umount {mount_point}")
    print(f"Unmounted {mount_point}")

def ensure_mount_point_exists(mount_point):
    if not os.path.exists(mount_point):
        os.makedirs(mount_point)

def display_summary(source, dest):
    while True:
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")

            # Title Bar with White background
            draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            draw.text((2, 1), "Summary[Just Copy]", font=font_small, fill="black")

            # Display source and destination labels (handle missing labels)
            source_label = source[3][:5] if source[3] != "NO-LBL" else "NO-LBL"  # First 5 chars of the label, or NO-LBL
            dest_label = dest[3][:5] if dest[3] != "NO-LBL" else "NO-LBL"

            # Display source and destination sizes
            source_size_rounded = round(float(source[1].replace('GB', '')))
            dest_size_rounded = round(float(dest[1].replace('GB', '')))
            draw.text((0, 27), f"\u2193 ", font=font_large, fill="white")
            draw.text((2, 20), f"  [{source_label}]-{source_size_rounded}GB ", font=font_medium, fill="white")
            draw.text((2, 35), f"  [{dest_label}]-{dest_size_rounded}GB", font=font_medium, fill="white")

            # Draw the "Select" text with inverse colors
            select_text = "[SELECT] to Copy".upper()
            text_width = draw.textlength(select_text, font=font_small)
            x = (device.width - text_width) // 2
            draw.rectangle((x - 2, device.height - 15, x + text_width + 2, device.height), outline="black", fill="white")
            draw.text((x, device.height - 15), select_text, font=font_small, fill="black")

        if button_left.is_pressed:
            time.sleep(0.2)
            return None

        # Wait for Select button to proceed
        if button_select.is_pressed:
            time.sleep(0.2)  # Debounce
            copy_mode(device, mode="just", buttons=(button_up, button_down, button_select))
            return

        time.sleep(0.1)  # Avoid High CPU usage


def display_summary_dated(source, dest):
    while True:
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")

            # Title Bar with White background
            draw.rectangle((0, 0, device.width, 15), outline="white", fill="white")
            draw.text((2, 1), "Summary[Dated Copy]", font=font_small, fill="black")

            # Display source and destination labels (handle missing labels)
            source_label = source[3][:5] if source[3] != "NO-LBL" else "NO-LBL"  # First 5 chars of the label, or NO-LBL
            dest_label = dest[3][:5] if dest[3] != "NO-LBL" else "NO-LBL"

            # Display source and destination sizes
            source_size_rounded = round(float(source[1].replace('GB', '')))
            dest_size_rounded = round(float(dest[1].replace('GB', '')))
            draw.text((0, 27), f"\u2193 ", font=font_large, fill="white")
            draw.text((2, 20), f"  [{source_label}]-{source_size_rounded}GB ", font=font_medium, fill="white")
            draw.text((2, 35), f"  [{dest_label}]-{dest_size_rounded}GB", font=font_medium, fill="white")

            # Draw the "Select" text with inverse colors
            select_text = "[SELECT] to Copy".upper()
            text_width = draw.textlength(select_text, font=font_small)
            x = (device.width - text_width) // 2
            draw.rectangle((x - 2, device.height - 15, x + text_width + 2, device.height), outline="black", fill="white")
            draw.text((x, device.height - 15), select_text, font=font_small, fill="black")

        if button_left.is_pressed:
            time.sleep(0.2)
            return None

        #Wait for Select button to proceed
        if button_select.is_pressed:
            time.sleep(0.2)  # Debounce
            copy_mode(device, "dated", (button_up, button_down, button_select))
            return
        
        time.sleep(0.1)  # Avoid High CPU usage

def execute_update_commands(update_version):
    """
    Execute additional commands after update extraction
    Looks for commands.json in the update folder and executes specified commands
    """
    commands_file = f"/tmp/update/{update_version}/commands.json"
    
    if not os.path.exists(commands_file):
        print("No additional commands to execute")
        return True
    
    try:
        with open(commands_file, 'r') as f:
            commands_data = json.load(f)
        
        # Execute DEB package commands (for Raspberry Pi)
        if 'deb_packages' in commands_data:
            for deb_action in commands_data['deb_packages']:
                if deb_action['action'] == 'install':
                    for deb_file in deb_action['files']:
                        deb_path = f"/tmp/update/{update_version}/{deb_file}"
                        if os.path.exists(deb_path):
                            print(f"Installing DEB package: {deb_file}")
                            result = subprocess.run(['sudo', 'dpkg', '-i', deb_path], 
                                                  capture_output=True, text=True)
                            if result.returncode != 0:
                                print(f"DEB install failed: {result.stderr}")
                                # Try to fix dependencies
                                subprocess.run(['sudo', 'apt-get', 'install', '-f', '-y'],
                                             capture_output=True)
                                return False
                
                elif deb_action['action'] == 'remove':
                    for package in deb_action['packages']:
                        print(f"Removing DEB package: {package}")
                        result = subprocess.run(['sudo', 'dpkg', '-r', package],
                                              capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"DEB remove failed: {result.stderr}")
                            # Don't fail on remove errors as package might not exist
        
        # Execute pip commands
        if 'pip' in commands_data:
            venv_path = "/backup-data/myenv/bin/activate"
            pip_path = "/backup-data/myenv/bin/pip"
            
            for pip_action in commands_data['pip']:
                if pip_action['action'] == 'install':
                    for package in pip_action['packages']:
                        print(f"Installing pip package: {package}")
                        # Check if it's a local wheel file or package name
                        if package.endswith('.whl'):
                            # Local wheel file
                            wheel_path = f"/tmp/update/{update_version}/{package}"
                            cmd = f"source {venv_path} && {pip_path} install {wheel_path}"
                        else:
                            # Package name (should be local wheel in update package)
                            cmd = f"source {venv_path} && {pip_path} install {package}"
                        
                        result = subprocess.run(['bash', '-c', cmd],
                                              capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"Pip install failed: {result.stderr}")
                            return False
                
                elif pip_action['action'] == 'uninstall':
                    for package in pip_action['packages']:
                        # Extract package name from wheel filename if needed
                        pkg_name = package.replace('.whl', '').split('-')[0]
                        print(f"Uninstalling pip package: {pkg_name}")
                        cmd = f"source {venv_path} && {pip_path} uninstall -y {pkg_name}"
                        result = subprocess.run(['bash', '-c', cmd],
                                              capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"Pip uninstall failed: {result.stderr}")
                            # Don't fail on uninstall errors
            
                elif pip_action['action'] == 'upgrade':
                    for package in pip_action['packages']:
                        print(f"Upgrading pip package: {package}")
                        cmd = f"source {venv_path} && {pip_path} install --upgrade {package}"
                        result = subprocess.run(['bash', '-c', cmd],
                                              capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"Pip upgrade failed: {result.stderr}")
                            return False
        
        # Execute shell commands
        if 'shell' in commands_data:
            for command in commands_data['shell']:
                print(f"Executing: {command}")
                result = subprocess.run(['bash', '-c', command],
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Shell command failed: {result.stderr}")
                    return False
        
        return True
        
    except Exception as e:
        print(f"Error executing update commands: {e}")
        return False

def main():
    global selected_index, current_brightness

    # Initialize display brightness
    device.contrast(current_brightness)

    # ✅ ADD THIS: Check license at startup
    license_valid = check_sd_card_binding()
    if not license_valid:
        return  # System will shutdown

    print("\nSystem Ready - Press KEY1-3 at any time!")
    notify_incomplete_session(device)
    while True:
        try:
            # Main menu navigation with special key handling
            choice = navigate_menu(menu_items, "PurrfectBackup", True)

            # --- Handle KEY1-3 shortcuts ---
            if choice == "KEY1":
                handle_brightness_control()
                continue
            elif choice == "KEY2":
                #handle_reporting_mode()
                disk_info_menu()
                # --- Debounce and cooldown ---
                while button_key2.is_pressed:
                    time.sleep(0.1)  # Wait for full release
                time.sleep(0.5)  # Prevent immediate reentry
                continue
            elif choice == "KEY3":
                handle_chkfile_mode()
                # --- Debounce and cooldown ---
                while button_key3.is_pressed:
                    time.sleep(0.1)  # Wait for full release
                time.sleep(0.5)  # Prevent immediate reentry
                continue

            # --- Handle regular menu choices ---
            if choice == "\uf0c5 Just Copy":
                print("Starting Just Copy...")
                source = select_partition('source', allow_nvme_source=False)  # ADD allow_nvme_source=False
                if source is None:
                    continue
                dest = select_partition('destination', exclude_disk=source[0][:3])
                if dest is None:
                    continue

                # Clean previous mounts
                if os.path.ismount("/mnt/src"): unmount_partition("/mnt/src")
                if os.path.ismount("/mnt/dst"): unmount_partition("/mnt/dst")

                # Mount and copy
                mount_partition(source[0], "/mnt/src")
                mount_partition(dest[0], "/mnt/dst")
                result = display_summary(source, dest)
                if result == "Back to Main Menu":
                    continue

                unmount_partition("/mnt/src")
                unmount_partition("/mnt/dst")

            elif choice == "\uf133 Dated Copy":
                print("Starting Dated Copy...")
                source = select_partition('source', allow_nvme_source=False)  # ADD allow_nvme_source=False
                if source is None:
                    continue
                dest = select_partition('destination', exclude_disk=source[0][:3])
                if dest is None:
                    continue

                if os.path.ismount("/mnt/src"): unmount_partition("/mnt/src")
                if os.path.ismount("/mnt/dst"): unmount_partition("/mnt/dst")

                mount_partition(source[0], "/mnt/src")
                mount_partition(dest[0], "/mnt/dst")
                result = display_summary_dated(source, dest)
                if result == "Back to Main Menu":
                    continue

                unmount_partition("/mnt/src")
                unmount_partition("/mnt/dst")

            elif choice == "\uf1eb WebUI Backup":
                print("Starting WebUI Backup...")
                ip_address = HARD_CODED_IP
                start_hostapd_service()

                font_icons = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/lineawesome-webfont.ttf", 12)
                display_message_wifi_oled("Connect Phone", " BackMeUp", " 11223344", "Then [Select]", font_icons=font_icons)
                cancelled = False
    
                # Wait for either SELECT to proceed or LEFT to cancel
                while True:
                    if button_select.is_pressed:
                        time.sleep(0.2)
                        break
                    elif button_left.is_pressed:
                        time.sleep(0.2)
                        stop_flask_service()
                        display_message_wifi_oled("Cancelled", "Returning to", "Main menu...", font_icons=font_icons)
                        time.sleep(2)
                        cancelled = True
                        break
                    time.sleep(0.1)

                # If cancelled, skip WebUI setup and return to main menu
                if cancelled:
                    # Clean up hostapd since we started it
                    stop_flask_service()  # This will also stop hostapd
                    continue  # Go back to main menu

                # Only proceed with WebUI if not cancelled
                time.sleep(0.5)
                start_flask_service()
                display_qr_code(f"http://{ip_address}", mode="wifi")

                while not button_left.is_pressed:
                    time.sleep(0.1)

                stop_flask_service()
                display_message_wifi_oled("WebUI Service", "Stopped", "Returning ...", font_icons=font_icons)
                time.sleep(2)

            elif choice == "\uf1c0 Disk Info":
                print("Showing Disk Info...")
                disk_info_menu()

            elif choice == "\uf7b9 Disk Check":
                print("Running Disk Check...")
                disk_check_menu()

            elif choice == "\uf0a0 Built-in SSD →":   # New SSD menu
                ssd_menu()

            elif choice == "\uf15c Copy History":
                print("Showing Copy History...")
                copy_history_menu()

            elif choice == "\uf013 Settings →":
                print("Entering Settings...")
                while True:
                    settings_choice = navigate_menu_time(settings_menu_items, reset_position=True)
                    if settings_choice == "\uf017 Date/Time":
                        print("Showing Current Date/Time...")
                        display_current_datetime()
                    elif settings_choice == "\uf28d Shutdown":
                        os.system("sudo shutdown now")
                        with canvas(device) as draw:
                            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                        return
                    elif settings_choice == "\uf021 Reboot":
                        os.system("sudo reboot")
                        with canvas(device) as draw:
                            draw.rectangle((0, 0, device.width, device.height), outline="black", fill="black")
                        return
                    elif settings_choice == "\uf28d Back":
                        break
                    elif settings_choice == "\uf129 Version":
                        backup_data_version()
                    elif settings_choice == "\uf2f1 Factory Reset":
                        confirm_reset()
                    elif settings_choice == "\uf56d Update":
                        check_for_update()

            elif choice == "System Menu":
                print("Entering System Menu...")
                navigate_shutdown_menu()

        except Exception as e:
            print(f"\nERROR in main loop: {str(e)}")
            import traceback
            traceback.print_exc()
            time.sleep(1)


if __name__ == "__main__":
    main()
