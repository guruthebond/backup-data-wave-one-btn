# error_handler.py
import os
import time
from luma.core.render import canvas
from PIL import ImageFont
import datetime

# Load fonts (same as in main scripts)
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

def log_error_to_csv(error_message, error_type="Runtime"):
    """Log errors to CSV with timestamp and error details"""
    log_file = "/backup-data/error-log.csv"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"{timestamp},{error_type},{error_message}\n"
    
    try:
        if os.path.exists(log_file):
            with open(log_file, "a") as f:
                f.write(entry)
        else:
            with open(log_file, "w") as f:
                f.write("Timestamp,ErrorType,ErrorMessage\n")
                f.write(entry)
    except Exception as e:
        print(f"Failed to log error: {e}")

def display_error(device, error_message, duration=5):
    """Display error on OLED and log it"""
    try:
        # Log the error first in case display fails
        log_error_to_csv(error_message)
        
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            
            # Split error message into lines that fit the display
            lines = []
            current_line = ""
            for word in error_message.split():
                test_line = f"{current_line} {word}" if current_line else word
                if draw.textlength(test_line, font=small_font) <= device.width - 10:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Display lines
            y_pos = 5
            for line in lines[:3]:  # Max 3 lines to fit on display
                draw.text((5, y_pos), line, font=small_font, fill="white")
                y_pos += 15
                if y_pos >= device.height - 10:
                    break
            
            # Add error header
            draw.text((5, device.height - 20), "ERROR OCCURRED", font=small_font, fill="white")
        
        time.sleep(duration)
    except Exception as e:
        print(f"Failed to display error: {e}")

def check_mount_points(device):
    """Check if mount points are accessible with error handling"""
    try:
        src_mounted = os.path.ismount("/mnt/src")
        dst_mounted = os.path.ismount("/mnt/dst")
        
        if not src_mounted and not dst_mounted:
            display_error(device, "Source & Dest not mounted")
            return False
        elif not src_mounted:
            display_error(device, "Source not mounted")
            return False
        elif not dst_mounted:
            display_error(device, "Dest not mounted")
            return False
        
        # Check if mounted but not accessible (phantom mounts)
        if not is_mount_accessible("/mnt/src") and not is_mount_accessible("/mnt/dst"):
            display_error(device, "Both drives unresponsive")
            return False
        elif not is_mount_accessible("/mnt/src"):
            display_error(device, "Source unresponsive")
            return False
        elif not is_mount_accessible("/mnt/dst"):
            display_error(device, "Dest unresponsive")
            return False
            
        return True
    except Exception as e:
        display_error(device, f"Mount check failed: {str(e)}")
        return False

def is_mount_accessible(mount_path):
    """Check if mount point is accessible"""
    try:
        with os.scandir(mount_path) as it:
            next(it)
        return True
    except (OSError, StopIteration):
        return False
