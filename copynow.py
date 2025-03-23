import report
import os
import time
import subprocess
import signal
import threading
from luma.core.interface.serial import spi
#from luma.core.interface.serial import i2c
#from luma.oled.device import ssd1306  # Use this for ssd1306 0.96 OLED display 
from luma.oled.device import sh1106  # Use this of sh1106 1.3 OLED display
from luma.core.render import canvas
from PIL import ImageFont
import re
import datetime
#import gpiozero.pins.lgpio
#import lgpio
import argparse

# Parse command-line arguments
#parser = argparse.ArgumentParser()
#parser.add_argument('--device', type=str, required=True)
#args = parser.parse_args()

# Use the device object passed from main.py
#device = args.device


# OLED Display Setup
#serial = i2c(port=1, address=0x3C)  # Adjust the address if necessary
#serial = spi(port=0, device=0, gpio=None)
#serial = spi(port=0, device=0, bus_speed_hz=8000000, gpio_DC=24, gpio_RST=25)
#device = sh1106(serial)   # Use this for sh1106 1.3  OLED display 
#device = ssd1306(serial)  # Use this of ssd1306 0.96 OLED display
# Load custom fonts
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

# Global variables
rsync_process = None
stop_monitoring = False

def truncate_text(draw, text, font, max_width):
    """Truncate text to fit within the specified max_width."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    truncated_text = text
    while draw.textlength(truncated_text + "...", font=font) > max_width:
        truncated_text = truncated_text[:-1]
    return truncated_text + "..."

def display_error(device, error_message):
    """Display an error message on the OLED screen."""
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        
        # Split message into lines if it's too long
        lines = []
        current_line = ""
        for word in error_message.split():
            test_line = current_line + " " + word if current_line else word
            if draw.textlength(test_line, font=font) <= device.width - 10:  # 10px padding
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Display lines on the OLED
        y_position = 5
        for line in lines:
            line = truncate_text(draw, line, font, device.width - 10)  # Truncate if necessary
            draw.text((5, y_position), line, font=font, fill="white")
            y_position += 15  # Move down for the next line
            if y_position >= device.height:  # Stop if we run out of vertical space
                break

    time.sleep(5)  # Display the error message for 5 seconds

def display_progress(device, progress_percentage, raw_output):
    """Display progress bar and raw output on the OLED screen."""
    with canvas(device) as draw:
        # Draw the top message with a highlighted box (white box with black text)
        message = "Just Copy!"
        box_padding = 4
        box_height = 16
        draw.rectangle((0, 0, device.width, box_height), outline="white", fill="white")  # White box
        draw.text((box_padding, 2), message, font=font, fill="black")  # Black text inside the box

        # Draw the progress bar below the message
        bar_width = device.width - 10
        bar_height = 10
        progress_width = int((progress_percentage / 100) * bar_width)

        # Draw background (empty bar)
        draw.rectangle((5, device.height - bar_height - 15, bar_width + 5, device.height - 15), outline="white", fill="black")
        
        # Draw the progress (filled bar)
        draw.rectangle((5, device.height - bar_height - 15, progress_width + 5, device.height - 15), outline="white", fill="white")
        
        # Show progress text
        draw.text((5, device.height - bar_height - 30), f"{progress_percentage}% Completed", font=font, fill="white")

        # Display the raw output in the bottom row
        draw.text((5, device.height - bar_height - 5), raw_output, font=small_font, fill="white")

def display_message(device, message, duration=10):
    """Display a message on the OLED screen for a specified duration."""
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        
        # Split message into lines if it's too long
        lines = []
        current_line = ""
        for word in message.split():
            test_line = current_line + " " + word if current_line else word
            if draw.textlength(test_line, font=font) <= device.width - 10:  # 10px padding
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Display lines on the OLED
        y_position = 5
        for line in lines:
            line = truncate_text(draw, line, font, device.width - 10)  # Truncate if necessary
            draw.text((5, y_position), line, font=font, fill="white")
            y_position += 15  # Move down for the next line
            if y_position >= device.height:  # Stop if we run out of vertical space
                break

    time.sleep(duration)  # Wait for the specified duration before returning

def is_mount_accessible(mount_path):
    """Check if a mount point is accessible by attempting to list its contents."""
    try:
        # Attempt to list the contents of the mount point
        with os.scandir(mount_path) as it:
            next(it)  # Try to read the first entry
        return True
    except (OSError, StopIteration):
        # If an error occurs, the mount point is not accessible
        return False

def unmount_path(mount_path):
    """Unmount a mount point using the `umount` command with retries and force options."""
    try:
        # Try a normal unmount first
        subprocess.run(["sudo", "umount", mount_path], check=True)
        print(f"Unmounted {mount_path} successfully.")
    except subprocess.CalledProcessError:
        try:
            # If normal unmount fails, try a lazy unmount
            subprocess.run(["sudo", "umount", "-l", mount_path], check=True)
            print(f"Lazy unmount of {mount_path} successful.")
        except subprocess.CalledProcessError:
            try:
                # If lazy unmount fails, try a force unmount
                subprocess.run(["sudo", "umount", "-f", mount_path], check=True)
                print(f"Force unmount of {mount_path} successful.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to unmount {mount_path}: {e}")
                # Optionally, kill processes using the mount point
                try:
                    subprocess.run(["sudo", "fuser", "-k", "-m", mount_path], check=True)
                    print(f"Killed processes using {mount_path}.")
                    # Retry unmount after killing processes
                    subprocess.run(["sudo", "umount", mount_path], check=True)
                    print(f"Unmounted {mount_path} after killing processes.")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to kill processes or unmount {mount_path}: {e}")

def check_mount_points(device):
    """Check if /mnt/src and /mnt/dst are mounted and accessible."""
    src_mounted = os.path.ismount("/mnt/src")
    dst_mounted = os.path.ismount("/mnt/dst")

    src_phantom = src_mounted and not is_mount_accessible("/mnt/src")
    dst_phantom = dst_mounted and not is_mount_accessible("/mnt/dst")

    if src_phantom and dst_phantom:
        display_message(device, "Re-plug Source & Dest. n Restart")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Src/Dst Drv Unavailable")
        unmount_path("/mnt/src")
        unmount_path("/mnt/dst")
        retun
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif src_phantom:
        display_message(device, "Re-plug Source Drive n Restart")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Source Drv Unavailable")
        unmount_path("/mnt/src")
        retrun
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif dst_phantom:
        display_message(device, "Re-plug Dest. Drive n Restart")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Dest Drv Unavailable")
        unmount_path("/mnt/dst")
        retun
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not src_mounted and not dst_mounted:
        display_message(device, "Source / Dest Drives Unavailable")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Src/Dst Drv Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not src_mounted:
        display_message(device, "Source Drive Unavailable")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Source Drv Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not dst_mounted:
        display_message(device, "Dest. Drive Unavailable")
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Dest Drv Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script

def monitor_mount_points(device):
    """Monitor /mnt/src and /mnt/dst every 5 seconds and handle errors."""
    global rsync_process, stop_monitoring

    while not stop_monitoring:
        src_mounted = os.path.ismount("/mnt/src")
        dst_mounted = os.path.ismount("/mnt/dst")

        src_phantom = src_mounted and not is_mount_accessible("/mnt/src")
        dst_phantom = dst_mounted and not is_mount_accessible("/mnt/dst")

        if src_phantom and dst_phantom:
            display_message(device, "Re-plug Source & Dest. n Restart", duration=10)
            unmount_path("/mnt/src")
            unmount_path("/mnt/dst")
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Src/Dst Drv Unavailable")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
            #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
        elif src_phantom:
            display_message(device, "Re-plug Source Drive n Restart", duration=10)
            unmount_path("/mnt/src")
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Source Drv Unavailable")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
            #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
        elif dst_phantom:
            display_message(device, "Re-plug Dest. Drive n Restart", duration=10)
            unmount_path("/mnt/dst")
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Dest Drv Unavailable")
            if rsync_process:
                rsync_process.terminate()
            stop_monitoring = True
            return
            #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script

        time.sleep(5)  # Check every 5 seconds

def rsync_copy_with_oled(device, src, dst, validate="No"):
    """Perform rsync copy and display output on OLED with progress bar based on to-chk."""
    global rsync_process, stop_monitoring
    
    # Choose rsync command based on validation
    if validate == "Yes":
        command = [
            "rsync", "-a", "--human-readable", "--info=progress2", "--inplace", "--exclude=.*", src + "/", dst + "/"
        ]
    else:
        command = [
            "rsync", "-a", "--human-readable", "--info=progress2", "--inplace", "--ignore-existing", "--exclude=.*", src + "/", dst + "/"
        ]

    print(f"Running rsync command: {' '.join(command)}")  # Debugging: Print the rsync command
    rsync_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)

    total_files = 0  # To store total files count
    files_processed = 0  # To store number of processed files
    raw_output = ""  # Variable to hold the latest rsync output line
    data_copied = "N/A"  # Default value for data copied

    last_update_time = time.time()

    try:
        for line in iter(rsync_process.stdout.readline, ""):
            line = line.strip()
            print(f"rsync output: {line}")  # Debugging: Print rsync output

            # Step 2: Extract progress percentage from the rsync output
            match = re.search(r"(\d+)%", line)
            if match:
                progress_percentage = int(match.group(1))
                print(f"Progress: {progress_percentage}%")  # Debugging: Print progress percentage

                # Update the OLED display only if 1 second has passed
                current_time = time.time()
                if current_time - last_update_time >= 1:
                    display_progress(device, progress_percentage, raw_output)
                    last_update_time = current_time
            
            # Capture the raw output line to display it in the bottom row
            raw_output = line

            # Extract data copied size from rsync stats (look for lines containing "xfr#" or "to-chk=")
            if "xfr#" in line or "to-chk=" in line:
                # Extract the size from the line (assuming it's the first element)
                parts = line.split()
                if parts:
                    data_copied = parts[0]  # Get the first element which is the size
                    print(f"Data copied: {data_copied}")  # Debugging: Print data copied

    except Exception as e:
        print(f"Error in rsync_copy_with_oled: {e}")  # Debugging: Print any errors
        display_error(device, str(e))
        rsync_process.terminate()
        return -1, "Error"

    # Close the output stream
    rsync_process.stdout.close()

    # Capture stderr to check for errors
    stderr_output = rsync_process.stderr.read()
    if stderr_output:
        print(f"rsync stderr: {stderr_output}")  # Debugging: Print stderr output

        # Check for specific error messages
        if "Input/output error" in stderr_output:
            display_error(device, "Not able to access Source or Dest. Disk! Re-try")
            rsync_process.terminate()
            return -1, "Input/output error"
        elif "No space left on device" in stderr_output:
            display_error(device, "No space left on Dest. Drive")
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Dst Disk Full")
        elif "Invalid argument" in stderr_output:
            display_error(device, "Invalid argument: Check paths")
        else:
            # Display the first line of the error output
            error_lines = stderr_output.splitlines()
            if error_lines:
                display_error(device, error_lines[0])

    # Wait for the process to finish
    rsync_process.wait()
    report.generate_reports()

    return rsync_process.returncode, data_copied
def unmount_before_reboot():
    """Unmount /mnt/src and /mnt/dst before rebooting."""
    subprocess.run("sudo umount /mnt/src", shell=True)
    subprocess.run("sudo umount /mnt/dst", shell=True)

def reboot_countdown(device, countdown_seconds=10):
    """Display a countdown on the OLED and reboot after the countdown."""
    for remaining in range(countdown_seconds, 0, -1):
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height // 2 - 20), "Check History!", font=font, fill="white")
            draw.text((10, device.height // 2), f"Going back.. {remaining}s", font=font, fill="white")
        time.sleep(1)
    # Unmount src and dst just before rebooting
    unmount_before_reboot()
    return
    #os.kill(os.getpid(), signal.SIGTERM)  # This kills the current process (the script)

def log_to_csv(start_time, end_time, data_copied, time_taken, status):
    """Log the copy details to copy-log.csv and keep only the last 5 entries."""
    log_file = "/backup-data/copy-log.csv"  # Ensure this is the correct path

    # Read existing entries from CSV
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
    else:
        lines = []

    # Prepend the new entry
    new_entry = f"{start_time},{end_time},{data_copied},{time_taken},{status}\n"
    lines.insert(0, new_entry)

    # Keep only the last 5 entries
    lines = lines[:5]

    # Write back to the CSV file
    with open(log_file, "w") as f:
        f.writelines(lines)

def copy_now(device, validate="No"):
    global rsync_process, stop_monitoring

    # Check if /mnt/src and /mnt/dst are mounted and accessible
    check_mount_points(device)

    src = "/mnt/src"
    dst = "/mnt/dst/just-backup"  # Ensure destination exists or create it
    
    # Display "Starting Now" with animation for "Comparing"
    bar_height = 20
    animation_frames = ["Comparing.", "Comparing..", "Comparing..."]  # Frames for the loading effect
    animation_index = 0

    start_time = time.time()
    animation_duration = 5  # Run animation for 5 seconds before proceeding

    while time.time() - start_time < animation_duration:
        with canvas(device) as draw:
            # White bar for "Starting Now"
            draw.rectangle((0, 5, device.width, 5 + bar_height), outline="white", fill="white")
            draw.text((10, 10), "Starting Now", font=font, fill="black")  # Centered inside the bar

            # Animated "Comparing" text
            draw.text((10, 30), animation_frames[animation_index], font=font, fill="white")
            draw.text((10, 45), "Files Pls Wait...", font=font, fill="white")

        # Cycle through animation frames
        animation_index = (animation_index + 1) % len(animation_frames)
        time.sleep(0.5)  # Update every 0.5 seconds

    #with canvas(device) as draw:
    #    draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
    #    draw.text((10, device.height // 2 - 10), "Starting Copy...", font=font, fill="white")

    time.sleep(2)

    # Start timer
    start_time = time.time()
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Start the mount point monitoring thread
    monitor_thread = threading.Thread(target=monitor_mount_points, args=(device,))
    #monitor_thread = threading.Thread(target=monitor_mount_points(device))
    monitor_thread.daemon = True
    monitor_thread.start()

    try:
        result_code, data_copied = rsync_copy_with_oled(device, src, dst, validate)
    except Exception as e:
        display_error(device, str(e))
        log_to_csv(start_time_str, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Copy Failed")
        return

    # Stop the monitoring thread
    stop_monitoring = True
    monitor_thread.join()

    # Stop timer
    end_time = time.time()
    end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_time = end_time - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes = remainder // 60
    time_taken_str = f"{int(hours)}h {int(minutes)}m" if hours > 0 else f"{int(minutes)}m {int(remainder % 60)}s"

    # Clear the OLED display
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")

    # Display completion message and time taken
    with canvas(device) as draw:
        if result_code == 0:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height // 2 - 30), "Going Back!!", font=font, fill="white")
            draw.text((10, device.height // 2 - 10), f"Time Taken: \n{time_taken_str}", font=font, fill="white")
            # Log the details
            log_to_csv(start_time_str, end_time_str, data_copied, time_taken_str, "Copy Success")
        else:
            draw.text((10, device.height // 2 - 10), "Copy Failed!", font=font, fill="white")
            log_to_csv(start_time_str, end_time_str, "N/A", "N/A", "Copy Failed")

    time.sleep(10)

    # Start reboot countdown
    reboot_countdown(device)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, required=True)
    args = parser.parse_args()

    # Use the device object passed from the command line
    device = args.device
    copy_now(device)
