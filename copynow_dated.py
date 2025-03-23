import report_dated
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
import argparse
# OLED Display Setup
#serial = i2c(port=1, address=0x3C)  # Adjust the address if necessary
#serial = spi(port=0, device=0, gpio=None)
#device = sh1106(serial)   # Use this for sh1106 1.3  OLED display 
#device = ssd1306(serial)  # Use this of ssd1306 0.96 OLED display

# Load custom fonts
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

# Global variables
rsync_process = None
stop_monitoring = False
stop_progress_updates = False
output_lines = []
update_event = threading.Event()


def get_file_modification_date(file_path):
    """Get the modification date of a file and return it as 'mm-dd-yyyy'."""
    modification_time = os.path.getmtime(file_path)
    modification_date = datetime.datetime.fromtimestamp(modification_time).strftime('%m-%d-%Y')
    return modification_date


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


def display_progress(device, progress_percentage, file_name, data_copied):
    """Display progress bar, truncated file name, and total data copied on the OLED screen."""
    truncated_file_name = file_name[-7:]  # Keep the last 7 characters of the file name
    total_data_copied_str = round_size(data_copied)  # Format the data copied for display
    
    with canvas(device) as draw:
        # Draw the top message with a highlighted box (white box with black text)
        message = "Dated Copy!"
        box_padding = 4
        box_height = 16
        draw.rectangle((0, 0, device.width, box_height), outline="white", fill="white")  # White box
        draw.text((box_padding, 2), message, font=font, fill="black")  # Black text inside the box

        # Draw the progress bar below the message
        bar_width = device.width - 10
        bar_height = 10
        progress_width = int((progress_percentage / 100) * bar_width)

        # Draw background (empty bar)
        draw.rectangle((5, box_height + 5, bar_width + 5, box_height + 5 + bar_height), outline="white", fill="black")
        
        # Draw the progress (filled bar)
        draw.rectangle((5, box_height + 5, progress_width + 5, box_height + 5 + bar_height), outline="white", fill="white")
        
        # Show progress text
        draw.text((5, box_height + bar_height + 10), f"{progress_percentage}% Completed", font=font, fill="white")

        # Show the file name and total data copied below the progress bar
        raw_output_y_position = box_height + bar_height + 25
        draw.text((5, raw_output_y_position), f"..{truncated_file_name} | {total_data_copied_str}", font=small_font, fill="white")


def round_size(size):
    """Format size in bytes to MB or GB."""
    if size > (1024 * 1024 * 1024):
        return f"{size / (1024 * 1024 * 1024):.2f}GB"  # Convert bytes to GB
    else:
        return f"{size / (1024 * 1024):.2f}MB"  # Convert bytes to MB


def is_mount_accessible(mount_path):
    """Check if a mount point is accessible by attempting to list its contents."""
    try:
        # Check if the mount point directory exists
        if not os.path.exists(mount_path):
            return False
        
        # Check if the mount point is readable
        if not os.access(mount_path, os.R_OK):
            return False
        
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
        unmount_path("/mnt/src")
        unmount_path("/mnt/dst")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif src_phantom:
        display_message(device, "Re-plug Source Drive n Restart")
        unmount_path("/mnt/src")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif dst_phantom:
        display_message(device, "Re-plug Dest. Drive n Restart")
        unmount_path("/mnt/dst")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not src_mounted and not dst_mounted:
        display_message(device, "Source / Dest Drives Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not src_mounted:
        display_message(device, "Source Drive Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script
    elif not dst_mounted:
        display_message(device, "Dest. Drive Unavailable")
        return
        #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script


def rsync_copy_with_oled(device, file_path, backup_subdir, total_files, files_copied, data_copied, total_size, validate="No"):
    """Perform rsync copy and display output on OLED."""
    # Choose rsync command based on validation
    if validate == "Yes":
        command = [
            "rsync", "-a", "--human-readable", "--info=progress2", "--exclude=.*", "--itemize-changes", file_path, backup_subdir
        ]
    else:
        command = [
            "rsync", "-a", "--human-readable", "--info=progress2", "--exclude=.*", "--itemize-changes", "--ignore-existing", file_path, backup_subdir
        ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)

    global output_lines
    max_lines = device.height // 12  # Calculate the maximum number of lines that fit on the screen

    for line in iter(process.stdout.readline, ""):
        line = line.strip()

        if line.startswith(">f"):  # Check for successfully copied files (e.g., >f+++++++++)
            try:
                file_size = os.path.getsize(file_path)  # Get file size for copied files
                data_copied += file_size  # Update data copied
            except OSError:
                pass  # Ignore errors if file size can't be determined

        # Update progress only for successfully copied files
        if line:
            output_lines.append(line)
            if len(output_lines) > max_lines:
                output_lines.pop(0)

            # Extract the file name from the line
            if line.startswith(">f"):
                file_name = line.split()[-1]  # Get the file name from the line

                # Calculate progress based on total size copied
                progress_percentage = round((data_copied / total_size) * 100)  # Convert to percentage

                # Ensure progress doesn't exceed 100%
                progress_percentage = min(progress_percentage, 100)

                display_progress(device, progress_percentage, file_name, data_copied)

                update_event.set()  # Trigger the display update
                print(line)  # Log progress to the terminal

    # Close the output stream
    process.stdout.close()

    # Capture stderr to check for errors
    stderr_output = process.stderr.read()
    if stderr_output:
        print("Error during rsync:", stderr_output)

        # Check for specific error messages
        if "Input/output error" in stderr_output:
            display_error(device, "Not able to access Source or Dest. Disk! Re-try")
            process.terminate()
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Input/output error")
            return
            #os.kill(os.getpid(), signal.SIGTERM)
            return files_copied, data_copied, -1  # Return error code
        elif "No space left on device" in stderr_output:
            display_error(device, "No space left on Dest. Drive")
            process.terminate()
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Dst Disk Full")
            time.sleep(10)  # Display the error message for 10 seconds
            return
            #os.kill(os.getpid(), signal.SIGTERM)  # Kill the script immediately
            return files_copied, data_copied, -1  # Return error code
        elif "Invalid argument" in stderr_output:
            display_error(device, "Invalid argument: Check paths")
            process.terminate()
            log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Invalid argument")
            return
            #os.kill(os.getpid(), signal.SIGTERM)
            return files_copied, data_copied, -1  # Return error code
        else:
            # Display the first line of the error output
            error_lines = stderr_output.splitlines()
            if error_lines:
                display_error(device, error_lines[0])
                process.terminate()
                log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Copy Failed")
                return
                #os.kill(os.getpid(), signal.SIGTERM)
                return files_copied, data_copied, -1  # Return error code

    # Wait for the process to finish
    process.wait()

    return files_copied, data_copied, process.returncode

def copy_files_based_on_date(device, src, dst, validate="No"):
    """Copy files from src to dst based on creation date with progress display."""
    start_time = time.time()
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")  # Log start time without seconds
    total_files = sum([len(files) for _, dirs, files in os.walk(src) if not any(f.startswith('.') for f in dirs)])  # Count total files in the source directory, ignoring hidden files/folders
    files_copied = 0  # Track the number of files copied
    data_copied = 0  # Track the size of data copied

    # Determine the total size of all files to be copied
    total_size = sum([os.path.getsize(os.path.join(root, file)) for root, _, files in os.walk(src) for file in files if not file.startswith('.')])

    for root, dirs, files in os.walk(src):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]  # Modify dirs in-place to exclude hidden directories

        for file in files:
            # Skip hidden files
            if file.startswith('.'):
                continue

            file_path = os.path.join(root, file)
            creation_time = os.path.getctime(file_path)
            creation_date = datetime.datetime.fromtimestamp(creation_time).strftime('%m-%d-%Y')
            backup_subdir = os.path.join(dst, creation_date)

            if not os.path.exists(backup_subdir):
                os.makedirs(backup_subdir)

            # Pass the current count of copied files and total files for progress update
            files_copied, data_copied, result_code = rsync_copy_with_oled(device,file_path, backup_subdir, total_files, files_copied, data_copied, total_size, validate)
            if result_code != 0:
                raise Exception(f"Failed to copy file: {file_path}")  # Raise an exception if rsync fails

    end_time = time.time()
    end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")  # Log end time without seconds
    total_time = end_time - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes = remainder // 60
    time_taken_str = f"{int(hours)}h {int(minutes)}m" if hours > 0 else f"{int(minutes)}m {int(remainder % 60)}s"
    if data_copied > (1024 * 1024 * 1024):
        data_copied_str = f"{data_copied / (1024 * 1024 * 1024):.2f}GB"  # Convert bytes to GB
    else:
        data_copied_str = f"{data_copied / (1024 * 1024):.2f}MB"  # Convert bytes to MB

    # Log the copy details to CSV
    log_to_csv(start_time_str, end_time_str, data_copied_str, time_taken_str, "Copy Success")
    report_dated.generate_reports()

    # Clear the display after copying completes
    with canvas(device) as draw:
        pass

    # Display the "Time Taken" screen
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        draw.text((10, device.height // 2 - 30), "Going Back!!", font=font, fill="white")
        draw.text((10, device.height // 2 - 10), f"Time Taken: \n{time_taken_str}", font=font, fill="white")

    # Ensure the "Time Taken" screen shows for 10 seconds
    time.sleep(10)

    # Start the reboot countdown
    reboot_countdown(device)

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

def unmount_before_reboot():
    """Unmount /mnt/src and /mnt/dst before rebooting."""
    subprocess.run("sudo umount /mnt/src", shell=True)
    subprocess.run("sudo umount /mnt/dst", shell=True)


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

def copy_now_dated(device, validate="No"):
    global rsync_process, stop_monitoring

    # Check if /mnt/src and /mnt/dst are mounted and accessible
    check_mount_points(device)

    src = "/mnt/src"
    dst = "/mnt/dst/dated-backup"  # Updated destination path

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

    try:
        copy_files_based_on_date(device, src, dst, validate)
    except Exception as e:
        display_error(device, str(e))
        log_to_csv(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "N/A", "N/A", "Copy Failed")
        return

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, required=True)
    args = parser.parse_args()

    # Use the device object passed from the command line
    device = args.device
    copy_now_dated(device)
