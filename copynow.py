import report
import os
import time
import subprocess
import signal
import threading
from luma.core.interface.serial import spi
#from luma.core.interface.serial import i2c
#from luma.oled.device import ssd1306  # Use for 0.96" OLED
from luma.oled.device import sh1106   # Use for 1.3" OLED
from luma.core.render import canvas
from PIL import ImageFont
import re
import datetime
import argparse

# Load custom fonts
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

# Global variables
rsync_process = None
stop_monitoring = False

def truncate_text(draw, text, font, max_width):
    """Truncate text to fit within max_width."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    truncated_text = text
    while draw.textlength(truncated_text + "...", font=font) > max_width and truncated_text:
        truncated_text = truncated_text[:-1]
    return truncated_text + "..."

def display_error(device, error_message):
    """Display an error message on the OLED screen."""
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="white", fill="black")
        lines = []
        current_line = ""
        for word in error_message.split():
            test_line = current_line + " " + word if current_line else word
            if draw.textlength(test_line, font=font) <= device.width - 10:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        y_position = 5
        for line in lines:
            line = truncate_text(draw, line, font, device.width - 10)
            draw.text((5, y_position), line, font=font, fill="white")
            y_position += 15
            if y_position >= device.height:
                break
    time.sleep(5)

def display_progress(device, progress_percentage, file_name, action, files_processed, total_files):
    """
    Display progress in the style of copynow_dated.py:
      - A header ("Just Copy!") on a white background.
      - A progress bar (with inverted percentage text centered).
      - An action line (e.g. "Skip:" or "Copy:" followed by the last 10 characters of the file name).
      - A file count line ("Files: X/Y").
    """
    with canvas(device) as draw:
        # 1. Header
        header_text = "Just Copy!"
        header_height = 16
        draw.rectangle((0, 0, device.width, header_height), outline="white", fill="white")
        draw.text((4, 2), header_text, font=font, fill="black")
        
        # 2. Progress Bar
        bar_width = device.width - 10
        bar_height = 10
        x_bar = 5
        y_bar = header_height + 5
        draw.rectangle((x_bar, y_bar, x_bar + bar_width, y_bar + bar_height), outline="white", fill="black")
        progress_width = int((progress_percentage / 100) * bar_width)
        draw.rectangle((x_bar, y_bar, x_bar + progress_width, y_bar + bar_height), outline="white", fill="white")
        percentage_text = f"{progress_percentage}%"
        text_width = draw.textlength(percentage_text, font=font)
        text_x = x_bar + (bar_width - text_width) // 2
        text_y = y_bar + (bar_height - 12) // 2  # approx 12px text height
        for dx, dy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            draw.text((text_x + dx, text_y + dy), percentage_text, font=font, fill="black")
        draw.text((text_x, text_y), percentage_text, font=font, fill="white")
        
        # 3. Action Line: display "Skip:" or "Copy:" with file name (last 10 characters)
        truncated_file_name = file_name[-10:]
        action_text = f"{action}: {truncated_file_name}"
        y_action = y_bar + bar_height + 4
        draw.rectangle((0, y_action, device.width, y_action + 15), outline="black", fill="black")
        draw.text((4, y_action), action_text, font=small_font, fill="white")
        
        # 4. File Count Line: "Files: processed/total"
        count_text = f"Files: {files_processed}/{total_files}"
        y_count = y_action + 15
        draw.rectangle((0, y_count, device.width, y_count + 15), outline="black", fill="black")
        draw.text((4, y_count), count_text, font=small_font, fill="white")

def rsync_copy_with_oled(device, file_path, dest_file, total_size, data_copied, files_processed, total_files):
    """
    Copy a single file from file_path to dest_file using rsync.
    Update the OLED with progress (based on files_processed/total_files).
    """
    command = [
        "rsync", "-a", "--human-readable", "--info=progress2",
        "--exclude=.*", file_path, dest_file
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1, universal_newlines=True)
    for line in iter(process.stdout.readline, ""):
        line = line.strip()
        # We update OLED based on overall file count progress (not per-byte)
        if line.startswith(">f"):
            try:
                file_size = os.path.getsize(file_path)
                data_copied += file_size
            except OSError:
                pass
            file_name = os.path.basename(file_path)
            progress_percentage = round((files_processed / total_files) * 100)
            display_progress(device, progress_percentage, file_name, "Copy:", files_processed, total_files)
        print(line)
    process.stdout.close()
    stderr_output = process.stderr.read()
    if stderr_output:
        print("rsync stderr:", stderr_output)
        display_error(device, stderr_output.splitlines()[0])
    process.wait()
    return data_copied, process.returncode

def is_mount_accessible(mount_path):
    """Check if a mount point is accessible by listing its contents."""
    try:
        with os.scandir(mount_path) as it:
            next(it)
        return True
    except (OSError, StopIteration):
        return False

def unmount_path(mount_path):
    """Unmount a mount point using umount with retries."""
    try:
        subprocess.run(["sudo", "umount", mount_path], check=True)
        print(f"Unmounted {mount_path} successfully.")
    except subprocess.CalledProcessError:
        try:
            subprocess.run(["sudo", "umount", "-l", mount_path], check=True)
            print(f"Lazy unmount of {mount_path} successful.")
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["sudo", "umount", "-f", mount_path], check=True)
                print(f"Force unmount of {mount_path} successful.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to unmount {mount_path}: {e}")
                try:
                    subprocess.run(["sudo", "fuser", "-k", "-m", mount_path], check=True)
                    subprocess.run(["sudo", "umount", mount_path], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Failed to kill processes or unmount {mount_path}: {e}")

def check_mount_points(device):
    """Ensure /mnt/src and /mnt/dst are mounted and accessible."""
    src_mounted = os.path.ismount("/mnt/src")
    dst_mounted = os.path.ismount("/mnt/dst")
    src_phantom = src_mounted and not is_mount_accessible("/mnt/src")
    dst_phantom = dst_mounted and not is_mount_accessible("/mnt/dst")
    if src_phantom and dst_phantom:
        display_error(device, "Source & Dest Drives Unavailable. Re-plug and restart.")
        unmount_path("/mnt/src")
        unmount_path("/mnt/dst")
        return
    elif src_phantom:
        display_error(device, "Source Drive Unavailable. Re-plug and restart.")
        unmount_path("/mnt/src")
        return
    elif dst_phantom:
        display_error(device, "Dest Drive Unavailable. Re-plug and restart.")
        unmount_path("/mnt/dst")
        return

def monitor_mount_points(device):
    """Monitor /mnt/src and /mnt/dst every 5 seconds and terminate rsync if needed."""
    global rsync_process, stop_monitoring
    while not stop_monitoring:
        src_mounted = os.path.ismount("/mnt/src")
        dst_mounted = os.path.ismount("/mnt/dst")
        src_phantom = src_mounted and not is_mount_accessible("/mnt/src")
        dst_phantom = dst_mounted and not is_mount_accessible("/mnt/dst")
        if src_phantom and dst_phantom:
            display_error(device, "Source & Dest Drives Unavailable. Re-plug and restart.")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
        elif src_phantom:
            display_error(device, "Source Drive Unavailable. Re-plug and restart.")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
        elif dst_phantom:
            display_error(device, "Dest Drive Unavailable. Re-plug and restart.")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
        time.sleep(5)

def unmount_before_reboot():
    """Unmount /mnt/src and /mnt/dst before rebooting."""
    subprocess.run("sudo umount /mnt/src", shell=True)
    subprocess.run("sudo umount /mnt/dst", shell=True)

def reboot_countdown(device, countdown_seconds=10):
    """Display a countdown on the OLED and then reboot."""
    for remaining in range(countdown_seconds, 0, -1):
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height // 2 - 20), "Check History!", font=font, fill="white")
            draw.text((10, device.height // 2), f"Going back.. {remaining}s", font=font, fill="white")
        time.sleep(1)
    unmount_before_reboot()

def log_to_csv(start_time, end_time, data_copied, time_taken, status):
    """Log the copy details to copy-log.csv and keep only the last 5 entries."""
    log_file = "/backup-data/copy-log.csv"
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
    else:
        lines = []
    new_entry = f"{start_time},{end_time},{data_copied},{time_taken},{status}\n"
    lines.insert(0, new_entry)
    lines = lines[:5]
    with open(log_file, "w") as f:
        f.writelines(lines)

def rsync_copy_file(device, file_path, dest_file, total_size, data_copied, files_processed, total_files):
    """
    Copy a single file (plain copy) using rsync and update OLED progress.
    """
    # Use same rsync options as in copynow_dated.py for file copy
    command = [
        "rsync", "-a", "--human-readable", "--info=progress2",
        "--exclude=.*", file_path, dest_file
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1, universal_newlines=True)
    for line in iter(process.stdout.readline, ""):
        line = line.strip()
        if line.startswith(">f"):
            try:
                file_size = os.path.getsize(file_path)
                data_copied += file_size
            except OSError:
                pass
            file_name = os.path.basename(file_path)
            progress_percentage = round((files_processed / total_files) * 100)
            display_progress(device, progress_percentage, file_name, "Copy", files_processed, total_files)
        print(line)
    process.stdout.close()
    stderr_output = process.stderr.read()
    if stderr_output:
        print("rsync stderr:", stderr_output)
        display_error(device, stderr_output.splitlines()[0])
    process.wait()
    return process.returncode

def rsync_copy_file(device, file_path, dest_file, files_processed, total_files):
    """
    Copy a single file using rsync and update OLED progress.
    Returns exit code only (0 = success)
    """
    command = [
        "rsync", "-a", "--human-readable", "--info=progress2",
        "--exclude=.*", file_path, dest_file
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1, universal_newlines=True)
    # OLED update logic (unchanged)
    for line in iter(process.stdout.readline, ""):
        line = line.strip()
        file_name = os.path.basename(file_path)
        progress_percentage = round((files_processed / total_files) * 100)
        display_progress(device, progress_percentage, file_name, "Copy", files_processed, total_files)
        print(line)
    process.stdout.close()
    stderr_output = process.stderr.read()
    if stderr_output:
        print("rsync stderr:", stderr_output)
        display_error(device, stderr_output.splitlines()[0])
    process.wait()
    return process.returncode

def bytes_to_human_readable(bytes_size):
    """Convert bytes to human-readable format matching copynow_dated.py (e.g., 1024 → '1.00MB')."""
    if bytes_size >= (1024 * 1024 * 1024):
        return f"{bytes_size / (1024 * 1024 * 1024):.2f}GB"
    else:
        return f"{bytes_size / (1024 * 1024):.2f}MB"

def copy_now(device, validate="Yes"):
    global rsync_process, stop_monitoring
    check_mount_points(device)
    src = "/mnt/src"
    dst = "/mnt/dst/just-backup"
    
    # Calculate total files (unchanged)
    total_files = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        total_files += len([f for f in files if not f.startswith('.')])

    files_processed = 0
    data_copied = 0  # Now tracked using file sizes

    # Startup animation (unchanged)
    # ... [keep original animation code] ...

    start_time = time.time()
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Mount monitoring thread (unchanged)
    monitor_thread = threading.Thread(target=monitor_mount_points, args=(device,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Main copy loop - MODIFIED SECTION
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        rel_path = os.path.relpath(root, src)
        dest_folder = os.path.join(dst, rel_path)
        
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)
            
        for file in files:
            if file.startswith('.'):
                continue
            files_processed += 1
            file_path = os.path.join(root, file)
            dest_file = os.path.join(dest_folder, file)
            progress = round((files_processed / total_files) * 100)
            
            if os.path.exists(dest_file):
                # Unchanged OLED skip display
                display_progress(device, progress, file, "Skip", files_processed, total_files)
                print(f"Skipping: {file}")
            else:
                # NEW: Get size BEFORE copying
                try:
                    file_size = os.path.getsize(file_path)
                except OSError as e:
                    print(f"Error getting size for {file}: {e}")
                    file_size = 0
                
                # Unchanged OLED copy display
                display_progress(device, progress, file, "Copy", files_processed, total_files)
                print(f"Copy: {file}")
                
                # Copy file and check result
                ret_code = rsync_copy_file(device, file_path, dest_file, files_processed, total_files)
                
                if ret_code == 0:
                    data_copied += file_size  # Accumulate AFTER success
                else:
                    raise Exception(f"Failed to copy file: {file_path}")

    # Finalization (unchanged except data_copied)
    end_time = time.time()
    end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_time = end_time - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes = remainder // 60
    seconds = int(remainder % 60)
    time_taken_str = f"{int(hours)}h {int(minutes)}m {seconds}s" if hours > 0 else f"{int(minutes)}m {seconds}s"
    
    # Log CORRECT data_copied value
    log_to_csv(start_time_str, end_time_str, bytes_to_human_readable(data_copied), time_taken_str, "Copy Success")
    

    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        draw.text((6, device.height // 2 - 20), "Report Creation", font=font, fill="white")
        draw.text((6, device.height // 2), f"Please wait...", font=font, fill="white")
    report.generate_reports()
    # Clear display and show final message
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
    with canvas(device) as draw:
        if True:  # if result_code was 0 (successful)
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height // 2 - 30), "Going Back!!", font=font, fill="white")
            draw.text((10, device.height // 2 - 10), f"Time Taken:\n{time_taken_str}", font=font, fill="white")
        else:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height // 2 - 10), "Copy Failed!", font=font, fill="white")
    time.sleep(10)
    stop_monitoring = True
    monitor_thread.join()
    reboot_countdown(device)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, required=True)
    args = parser.parse_args()
    device = args.device
    copy_now(device)
