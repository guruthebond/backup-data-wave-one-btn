import report_dated
import os
import time
import subprocess
import signal
import threading
from luma.core.render import canvas
from PIL import ImageFont
import datetime
import argparse

# Load custom fonts
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

# Global variables
output_lines = []
update_event = threading.Event()

def log_to_csv(start_time, end_time, data_copied, time_taken, status):
    """Log the copy details to copy-log.csv and keep only the last 5 entries."""
    log_file = "/backup-data/copy-log.csv"  # Adjust the path if needed
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
    else:
        lines = []
    new_entry = f"{start_time},{end_time},{data_copied},{time_taken},{status}\n"
    lines.insert(0, new_entry)
    # Keep only the last 5 entries
    lines = lines[:5]
    with open(log_file, "w") as f:
        f.writelines(lines)

def get_file_modification_date(file_path):
    """Return modification date in 'mm-dd-yyyy' format."""
    modification_time = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(modification_time).strftime('%m-%d-%Y')

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
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
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
    Update the OLED with:
      - Header: "Dated Copy!" in a white box.
      - Progress Bar: a bar with the current percentage centered.
      - Action Line: displays "Copy:" or "Skip:" along with the last part of the filename.
      - File Count Line: displays the number of files processed (e.g., "Files: 4002/5504").
    """
    with canvas(device) as draw:
        # 1. Header (white background with black text)
        header_text = "Dated Copy!"
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
        text_y = y_bar + (bar_height - 12) // 2
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            draw.text((text_x + dx, text_y + dy), percentage_text, font=font, fill="black")
        draw.text((text_x, text_y), percentage_text, font=font, fill="white")
        
        # 3. Action Line: "Copy:" or "Skip:" with truncated file name
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


def round_size(size):
    """Format size in bytes to MB or GB."""
    if size > (1024 * 1024 * 1024):
        return f"{size / (1024 * 1024 * 1024):.2f}GB"
    else:
        return f"{size / (1024 * 1024):.2f}MB"

def is_mount_accessible(mount_path):
    """Check if a mount point is accessible."""
    try:
        if not os.path.exists(mount_path):
            return False
        if not os.access(mount_path, os.R_OK):
            return False
        with os.scandir(mount_path) as it:
            next(it)
        return True
    except (OSError, StopIteration):
        return False

def unmount_path(mount_path):
    """Attempt to unmount the given mount path."""
    try:
        subprocess.run(["sudo", "umount", mount_path], check=True)
    except subprocess.CalledProcessError:
        try:
            subprocess.run(["sudo", "umount", "-l", mount_path], check=True)
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["sudo", "umount", "-f", mount_path], check=True)
            except subprocess.CalledProcessError as e:
                try:
                    subprocess.run(["sudo", "fuser", "-k", "-m", mount_path], check=True)
                    subprocess.run(["sudo", "umount", mount_path], check=True)
                except subprocess.CalledProcessError:
                    print(f"Failed to unmount {mount_path}: {e}")

def check_mount_points(device):
    """Ensure /mnt/src and /mnt/dst are mounted and accessible."""
    src_mounted = os.path.ismount("/mnt/src")
    dst_mounted = os.path.ismount("/mnt/dst")
    src_phantom = src_mounted and not is_mount_accessible("/mnt/src")
    dst_phantom = dst_mounted and not is_mount_accessible("/mnt/dst")
    if src_phantom and dst_phantom:
        display_message(device, "Re-plug Source & Dest. n Restart")
        unmount_path("/mnt/src")
        unmount_path("/mnt/dst")
        return
    elif src_phantom:
        display_message(device, "Re-plug Source Drive n Restart")
        unmount_path("/mnt/src")
        return
    elif dst_phantom:
        display_message(device, "Re-plug Dest. Drive n Restart")
        unmount_path("/mnt/dst")
        return
    elif not src_mounted and not dst_mounted:
        display_message(device, "Source / Dest Drives Unavailable")
        return
    elif not src_mounted:
        display_message(device, "Source Drive Unavailable")
        return
    elif not dst_mounted:
        display_message(device, "Dest. Drive Unavailable")
        return

def generate_new_files_list(device, src, dst, total_files):
    """
    Walk the source tree, compare with destination (based on creation date folders),
    and generate a list of new files to copy.
    Updates the OLED progress bar as each file is processed.
    """
    new_files = []
    files_processed = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            files_processed += 1
            file_path = os.path.join(root, file)
            creation_date = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m-%d-%Y')
            backup_subdir = os.path.join(dst, creation_date)
            dst_file = os.path.join(backup_subdir, file)
            progress = round((files_processed / total_files) * 100)
            if os.path.exists(dst_file):
                display_progress(device, progress, file, "Skip", files_processed, total_files)
                print(f"Skipping: {file}")
            else:
                new_files.append(file_path)
                display_progress(device, progress, file, "Copy", files_processed, total_files)
                print(f"Copying: {file}")
    return new_files, files_processed

def run_rsync_with_filelist(device, file_list, dst, total_files):
    """
    Write the new file list to a temporary file and run rsync with --files-from.
    During rsync, update the progress bar.
    
    overall_total is defined as:
       overall_total = total_files (from scanning) + new_files_count
    Progress during copying:
       overall_progress = (total_files + new_files_copied) / overall_total * 100
    """
    new_files_count = len(file_list)
    new_files_copied = 0
    overall_total = total_files + new_files_count

    list_file = "/tmp/new_files.txt"
    with open(list_file, "w") as f:
        for file_path in file_list:
            f.write(f"{file_path}\n")

    command = [
        "rsync", "-a", "--human-readable", "--info=progress2",
        "--exclude=.*", "--itemize-changes", "--files-from", list_file, "/", dst
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               bufsize=1, universal_newlines=True)
    for line in iter(process.stdout.readline, ""):
        line = line.strip()
        if line.startswith(">f"):
            new_files_copied += 1
            overall_progress = round(((total_files + new_files_copied) / overall_total) * 100)
            file_name = line.split()[-1]
            display_progress(device, overall_progress, file_name, "Copying", total_files + new_files_copied, overall_total)
            print(f"Copied: {file_name}")
    process.stdout.close()
    stderr_output = process.stderr.read()
    if stderr_output:
        print("Error during rsync:", stderr_output)
        display_error(device, stderr_output.splitlines()[0])
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        log_to_csv(current_time, current_time, "N/A", "N/A", "Copy Failed")
    process.wait()
    return process.returncode

def rsync_copy_with_oled(device, file_path, backup_subdir, total_size, data_copied, files_processed, total_files):
    """
    For the validation == "Yes" case, run a single file copy via rsync while updating progress.
    total_size is the size of the current file.
    """
    command = [
        "rsync", "-a", "--human-readable", "--info=progress2",
        "--exclude=.*",  "--inplace",  "--itemize-changes", file_path, backup_subdir
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
            file_name = line.split()[-1]
            # Calculate progress based on files_processed already done
            progress_percentage = round((files_processed / total_files) * 100)
            # Update OLED display for this file copy
            display_progress(device, progress_percentage, file_name, "Copying", files_processed, total_files)
            print(line)
            update_event.set()
    process.stdout.close()
    stderr_output = process.stderr.read()
    if stderr_output:
        print("Error during rsync:", stderr_output)
        display_error(device, stderr_output.splitlines()[0])
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        log_to_csv(current_time, current_time, "N/A", "N/A", "Copy Failed")
    process.wait()
    return data_copied, process.returncode


def copy_files_based_on_date(device, src, dst, validate="No"):
    """
    Copy files from src to dst based on the validation mode.
    For validate=="No", new file list is generated and copied in one rsync call.
    For validate=="Yes", files are processed one-by-one with per-file progress updates.
    The progress bar is based on the total number of source files (including skipped files).
    """
    start_time = time.time()
    start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_files = sum(len(files) for root, dirs, files in os.walk(src)
                      if not any(f.startswith('.') for f in dirs))
    data_copied = 0

    if validate == "No":
        # Existing "No" branch: generate list and run rsync once.
        new_files, _ = generate_new_files_list(device, src, dst, total_files)
        if new_files:
            ret = run_rsync_with_filelist(device, new_files, dst, total_files)
            if ret != 0:
                raise Exception("rsync encountered an error copying new files.")
        else:
            print("No new files to copy.")
    else:
        # "Yes" branch: process each file one-by-one.
        files_processed = 0  # initialize counter for processed files
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.startswith('.'):
                    continue
                files_processed += 1
                file_path = os.path.join(root, file)
                creation_date = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%m-%d-%Y')
                backup_subdir = os.path.join(dst, creation_date)
                if not os.path.exists(backup_subdir):
                    os.makedirs(backup_subdir)
                dst_file = os.path.join(backup_subdir, file)
                # Calculate overall progress based on files processed.
                progress = round((files_processed / total_files) * 100)
                if os.path.exists(dst_file):
                    # File already exists: update display with "Skip"
                    display_progress(device, progress, file, "Skip", files_processed, total_files)
                    print(f"Skipping: {file}")
                else:
                    # File needs to be copied: update display then copy.
                    display_progress(device, progress, file, "Copy", files_processed, total_files)
                    print(f"Copying: {file}")
                    total_size = os.path.getsize(file_path)
                    data_copied, ret_code = rsync_copy_with_oled(device, file_path, backup_subdir,
                                                                 total_size, data_copied, files_processed, total_files)
                    if ret_code != 0:
                        raise Exception(f"Failed to copy file: {file_path}")

    # Final summary and logging.
    end_time = time.time()
    end_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_time = end_time - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes = remainder // 60
    seconds = int(remainder % 60)
    time_taken_str = f"{int(hours)}h {int(minutes)}m {seconds}s" if hours > 0 else f"{int(minutes)}m {seconds}s"
    if data_copied > (1024 * 1024 * 1024):
        data_copied_str = f"{data_copied / (1024 * 1024 * 1024):.2f}GB"
    else:
        data_copied_str = f"{data_copied / (1024 * 1024):.2f}MB"
    log_to_csv(start_time_str, end_time_str, data_copied_str, time_taken_str, "Copy Success")
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        draw.text((6, device.height // 2 - 20), "Report Creation", font=font, fill="white")
        draw.text((6, device.height // 2), f"Please wait...", font=font, fill="white")
    report_dated.generate_reports()
    # Display final message on OLED and start reboot countdown.
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        draw.text((10, device.height // 2 - 30), "Going Back!!", font=font, fill="white")
        draw.text((10, device.height // 2 - 10), f"Time Taken: \n{time_taken_str}", font=font, fill="white")
    time.sleep(10)
    reboot_countdown(device)


def reboot_countdown(device, countdown_seconds=10):
    """Display a countdown on the OLED and then reboot (or exit)."""
    for remaining in range(countdown_seconds, 0, -1):
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, device.height//2 - 20), "Check History!", font=font, fill="white")
            draw.text((10, device.height//2), f"Going back.. {remaining}s", font=font, fill="white")
        time.sleep(1)
    unmount_before_reboot()

def unmount_before_reboot():
    """Unmount source and destination drives before rebooting."""
    subprocess.run("sudo umount /mnt/src", shell=True)
    subprocess.run("sudo umount /mnt/dst", shell=True)

def display_message(device, message, duration=10):
    """Display a message on the OLED screen for a set duration."""
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width, device.height), outline="white", fill="black")
        lines = []
        current_line = ""
        for word in message.split():
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
    time.sleep(duration)

def copy_now_dated(device, validate="No"):
    # Check that mounts are accessible
    check_mount_points(device)
    src = "/mnt/src"
    dst = "/mnt/dst/dated-backup"
    # Display startup animation
    animation_frames = ["Comparing.", "Comparing..", "Comparing..."]
    start_time_anim = time.time()
    animation_duration = 5
    animation_index = 0
    while time.time() - start_time_anim < animation_duration:
        with canvas(device) as draw:
            draw.rectangle((0, 5, device.width, 25), outline="white", fill="white")
            draw.text((10, 10), "Starting Now", font=font, fill="black")
            draw.text((10, 30), animation_frames[animation_index], font=font, fill="white")
            draw.text((10, 45), "Files Pls Wait...", font=font, fill="white")
        animation_index = (animation_index + 1) % len(animation_frames)
        time.sleep(0.5)
    try:
        copy_files_based_on_date(device, src, dst, validate)
    except Exception as e:
        display_error(device, str(e))
        return

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', type=str, required=True)
    parser.add_argument('--validate', type=str, default="No")
    args = parser.parse_args()
    # The device argument should be a valid OLED device object. Here we assume it is passed appropriately.
    device = args.device
    copy_now_dated(device, validate=args.validate)
