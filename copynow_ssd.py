import os
import time
import shutil
import subprocess
import threading
import datetime
import argparse
from luma.core.interface.serial import spi
from luma.oled.device import sh1106
from luma.core.render import canvas
from PIL import ImageFont
import error_handler

# OLED fonts
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
SMALL_FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)

# Paths
SRC = "/mnt/src"
DST_ROOT = "/mnt/dst"
JUST_DST = os.path.join(DST_ROOT, "just-backup")
DATED_DST = os.path.join(DST_ROOT, "dated-backup")
LOG_FILE = "/backup-data/copy-log.csv"
MAX_LOG_ENTRIES = 10
SESSION_FILE = "/backup-data/session.lock"
# Globals
rsync_proc = None
stop_flag = False
copying_active = False

def check_mounts(device):
    return error_handler.check_mount_points(device)


def log_to_csv(start, end, size, duration, status):
    entries = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            entries = f.readlines()
    new = f"{start},{end},{size},{duration},{status}\n"
    entries.insert(0, new)
    entries = entries[:MAX_LOG_ENTRIES]
    with open(LOG_FILE, 'w') as f:
        f.writelines(entries)


def bytes_to_human(n):
    if n >= 1024**3:
        return f"{n/1024**3:.2f}GB"
    return f"{n/1024**2:.2f}MB"

def display_progress(device, percent, filename, count, total, mode, action=None):
    header = "Offload-SSD!" if mode == 'just' else "DatedCopy!"
    with canvas(device) as draw:
        # Header
        draw.rectangle((0,0,device.width,16), outline="white", fill="white")
        draw.text((4,2), header, font=FONT, fill="black")
        # Progress bar
        w = device.width - 10
        filled = int((percent/100)*w)
        draw.rectangle((5,20,5+w,30), outline="white", fill="black")
        draw.rectangle((5,20,5+filled,30), outline="white", fill="white")
        # Status info
        name = os.path.basename(filename) if filename else ""
        display_name = name[-14:] if len(name) > 14 else name
        status = f"{action}:{display_name}" if action else display_name
        draw.text((5,35), status, font=SMALL_FONT, fill="white")
        # Show both attempted and successful counts
        draw.text((5,50), f"{count}/{total}", font=SMALL_FONT, fill="white")

def check_space(device, src, dst, mode):
    total = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.startswith('.'): continue
            srcp = os.path.join(root, f)
            if mode == 'just':
                rel   = os.path.relpath(root, src)
                destp = os.path.join(dst, rel, f)
            else:  # dated mode
                date  = datetime.datetime.fromtimestamp(os.path.getmtime(srcp)).\
                        strftime("%m-%d-%Y")
                destp  = os.path.join(dst, date, f)
            if not os.path.exists(destp):
                try: total += os.path.getsize(srcp)
                except: pass
    # make sure dst folder exists so disk_usage() won’t blow up
    os.makedirs(dst, exist_ok=True)
    free = shutil.disk_usage(dst).free
    pending = bytes_to_human(total)
    free_hr = bytes_to_human(free)
    with canvas(device) as draw:
        draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
        draw.text((4,5), "Space Check", font=FONT, fill="white")
        draw.text((4,25), f"Pend: {pending}", font=SMALL_FONT, fill="white")
        draw.text((4,40), f"Free: {free_hr}", font=SMALL_FONT, fill="white")
    time.sleep(2)
    if total > free:
        error_handler.display_error(device, "Dst Space not enough")
        log_to_csv("Null", "Null", "Null", "Null", "Dst. Space Not Enough")
        return False
    return True

def monitor(device, mode):
    global rsync_proc, stop_flag
    while not stop_flag and copying_active:
        if not os.path.ismount(SRC):
            if rsync_proc:
                rsync_proc.terminate()
                try:
                    rsync_proc.wait(timeout=1)
                except:
                    rsync_proc.kill()
            stop_flag = "src"
            break

        if not os.path.ismount(DST_ROOT):
            if rsync_proc:
                rsync_proc.terminate()
                try:
                    rsync_proc.wait(timeout=1)
                except:
                    rsync_proc.kill()
            stop_flag = "dst"
            break

        time.sleep(1)


def rsync_file(device, srcp, destp, count, total, mode):
    global rsync_proc, stop_flag
    start_time = time.time()
    copying_active = True
    try:
        # Verify source and destination still exist
        if not os.path.exists(srcp):
            display_progress(device, (count/total)*100, srcp, count, total, mode, action="Missing!")
            time.sleep(0.5)
            return 1

        # Add destination mount check
        if not os.path.ismount(DST_ROOT):
            stop_flag = "dst"
            display_progress(device, (count/total)*100, "DESTINATION LOST!", count, total, mode)
            time.sleep(0.5)
            return 1

        cmd = ["rsync", "-a", "--partial", "--inplace",
               "--human-readable", "--info=progress2", "--exclude=.*", srcp, destp]
        rsync_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        try:
            while True:
                if stop_flag or (time.time() - start_time) > 30:  # 30sec timeout
                    rsync_proc.terminate()
                    return 1

                # Check destination mount periodically during copy
                if not os.path.ismount(DST_ROOT):
                    stop_flag = "dst"
                    rsync_proc.terminate()
                    return 1

                line = rsync_proc.stdout.readline()
                if not line:
                    break

                display_progress(device, (count/total)*100, srcp, count, total, mode, action="Copy")

        except Exception as e:
            return 1

        rsync_proc.wait()
    finally:
        copying_active = False
    return rsync_proc.returncode


def compare_files(src_files, dst_files):
    """Compare source and destination files, return duplicates and new files"""
    src_names = {os.path.basename(f[0]) for f in src_files}
    dst_names = {os.path.basename(f[1]) for f in dst_files}

    duplicates = src_names & dst_names
    new_files = src_names - dst_names

    return duplicates, new_files

def create_timestamped_filename(src_path):
    """Create a timestamped filename for duplicates (MM-DD-YYYY-HH-MM format)"""
    base, ext = os.path.splitext(os.path.basename(src_path))
    timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(src_path)).strftime("%m-%d-%Y-%H-%M")
    return f"{base}-{timestamp}{ext}"  # Changed from [timestamp] to -timestamp

def ssd_mode(device, mode, buttons=None, force_source=None):
    global stop_flag
    stop_flag = False
    
    # Handle buttons parameter
    if buttons:
        button_up, button_down, button_select = buttons
    else:
        # Default button objects if not provided (for backward compatibility)
        button_up = button_down = button_select = None
    
    # If force_source is provided, mount it as source automatically
    if force_source:
        print(f"Using forced source: {force_source}")
        # Clean previous mounts
        if os.path.ismount(SRC): 
            unmount_partition(SRC)
        if os.path.ismount(DST_ROOT): 
            unmount_partition(DST_ROOT)
        
        # Mount the forced source
        mount_partition(force_source, SRC)
    
    report_choice = ["Yes", "No"]
    selected = 0
    
    # Only show report selection if buttons are available (interactive mode)
    if buttons:
        while True:
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
                draw.text((2, 10), "Generate Report?", font=FONT, fill="white")
                for i,opt in enumerate(report_choice):
                    if i == selected:
                        draw.rectangle((5, 30 + i*15, device.width - 5, 30 + i*15 + 12),
                                       outline="white", fill="white")
                        draw.text((10, 30 + i*15), opt, font=SMALL_FONT, fill="black")
                    else:
                        draw.text((10, 30 + i*15), opt, font=SMALL_FONT, fill="white")

            if button_up.is_pressed or button_down.is_pressed:
                selected = (selected + 1) % len(report_choice)
                time.sleep(0.2)
            elif button_select.is_pressed:
                time.sleep(0.2)
                break
            time.sleep(0.1)
        generate_report = (report_choice[selected] == "Yes")
    else:
        generate_report = False  # Default to no report in non-interactive mode

    # Mark that a copy session started
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        f.write(f"{mode},{datetime.datetime.now().isoformat()}\n")
        f.flush()
        os.fsync(f.fileno())
    
    dst = JUST_DST if mode == 'just' else DATED_DST

    if not os.path.ismount(DST_ROOT):
        stop_flag = "dst"
        display_progress(device, 100, "DST DISCONNECTED", 0, 0, mode)
        time.sleep(3)
        return

    if not check_mounts(device):
        return
    if not check_space(device, SRC, dst, mode):
        return


    def has_duplicate_file(directory, target_size, target_mtime, filename):
        """Only skip if a file with *same name*, size, and mtime exists"""
        fpath = os.path.join(directory, filename)
        if os.path.exists(fpath):
            try:
                fsize = os.path.getsize(fpath)
                fmtime = os.path.getmtime(fpath)
                if fsize == target_size and fmtime == target_mtime:
                    return True
            except OSError:
                return False
        return False

    # First gather all source files
    src_files = []
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.startswith('.'):
                continue
            srcp = os.path.join(root, f)
            if mode == 'just':
                rel = os.path.relpath(root, SRC)
                destp = os.path.join(dst, rel, f)
            else:
                date = datetime.datetime.fromtimestamp(os.path.getmtime(srcp)).strftime("%m-%d-%Y")
                destp = os.path.join(dst, date, f)
            src_files.append((srcp, destp))

    total = len(src_files)
    if total == 0:
        display_progress(device, 100, "", 0, 0, mode)
        time.sleep(1)
        return

    mt = threading.Thread(target=monitor, args=(device, mode))
    mt.daemon = True
    mt.start()

    start = datetime.datetime.now()
    start_s = start.strftime("%Y-%m-%d %H:%M")
    data_copied = 0
    count = 0

    for srcp, destp in src_files:
        if stop_flag:
            break

        if not os.path.exists(srcp):
            stop_flag = "src"
            actual_copied = sum(1 for f in src_files[:src_files.index((srcp, destp))] 
                       if os.path.exists(f[0]))
            count = actual_copied
            break
        
        if not os.path.ismount(SRC):
            stop_flag = "src"
            actual_copied = sum(1 for f in src_files[:src_files.index((srcp, destp))] 
                       if os.path.exists(f[0]))
            count = actual_copied
            break

        if not os.path.ismount(DST_ROOT):
            stop_flag = "dst"
            actual_copied = sum(1 for f in src_files[:src_files.index((srcp, destp))] 
                            if os.path.exists(f[0]))
            count = actual_copied
            break

        count += 1
        
        # Get source file attributes
        try:
            src_size = os.path.getsize(srcp)
            src_mtime = os.path.getmtime(srcp)
        except OSError:
            action = 'Skip'
            display_progress(device, (count/total)*100, srcp, count, total, mode, action=action)
            continue
            
        dest_dir = os.path.dirname(destp)
        dest_file = os.path.basename(destp)
        
        # Check for existing file with same content
        if has_duplicate_file(dest_dir, src_size, src_mtime, dest_file):
            action = 'Skip'
        else:
            # Check if original destination exists and is different
            if os.path.exists(destp):
                try:
                    dst_size = os.path.getsize(destp)
                    dst_mtime = os.path.getmtime(destp)
                    if dst_size == src_size and dst_mtime == src_mtime:
                        action = 'Skip'
                    else:
                        # Generate unique filename
                        base, ext = os.path.splitext(dest_file)
                        timestamp = datetime.datetime.fromtimestamp(src_mtime).strftime("%m-%d-%Y-%H-%M")
                        new_file = f"{base}-{timestamp}{ext}"
                        counter = 1
                        while os.path.exists(os.path.join(dest_dir, new_file)):
                            new_file = f"{base}-{timestamp}-{counter}{ext}"
                            counter += 1
                        destp = os.path.join(dest_dir, new_file)
                        action = 'Copy'
                except OSError:
                    action = 'Copy'
            else:
                action = 'Copy'

        display_progress(device, (count/total)*100, srcp, count, total, mode, action=action)

        if action == 'Copy':
            if stop_flag or not os.path.ismount(DST_ROOT):
                stop_flag = "dst"
                break
            try:
                os.makedirs(os.path.dirname(destp), exist_ok=True)
            except OSError as e:
                print(f"Error creating directory {os.path.dirname(destp)}: {e}")
                stop_flag = "dst"
                break
            
            if stop_flag or not os.path.ismount(DST_ROOT):
                stop_flag = "dst"
                break
            ret = rsync_file(device, srcp, destp, count, total, mode)
            if ret == 0:
                data_copied += os.path.getsize(srcp)

    mt.join()

    end = datetime.datetime.now()
    dur_secs = int((end - start).total_seconds())
    mins, secs = divmod(dur_secs, 60)
    dur_s = f"{mins}m{secs}s"

    if stop_flag == "src":
        actual_copied = sum(1 for srcp, _ in src_files[:count] if os.path.exists(srcp))
        log_to_csv(start_s, end.strftime("%Y-%m-%d %H:%M"), 
                 bytes_to_human(data_copied), dur_s, "Src Lost!")
        display_progress(device, 100, "SRC LOST!", actual_copied, total, mode)
        with canvas(device) as draw:
            draw.text((10, 20), "SRC LOST!", font=FONT, fill="white")
            draw.text((10, 40), f"{actual_copied}/{total} copied", font=SMALL_FONT, fill="white")
        time.sleep(3)
        return
    elif stop_flag == "dst":
        actual_copied = sum(1 for srcp, _ in src_files[:count] if os.path.exists(srcp))
        log_to_csv(start_s, end.strftime("%Y-%m-%d %H:%M"),
                   bytes_to_human(data_copied), dur_s, "Dst Lost!")
        display_progress(device, 100, "DST LOST!", actual_copied, total, mode)
        with canvas(device) as draw:
             draw.text((10, 20), "DST LOST!", font=FONT, fill="white")
             draw.text((10, 40), f"{actual_copied}/{total} copied", font=SMALL_FONT, fill="white")
        time.sleep(3)
        return
    else:
        log_to_csv(start_s, end.strftime("%Y-%m-%d %H:%M"), bytes_to_human(data_copied), dur_s, "Success")
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")

        if generate_report:
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
                draw.text((10, 20), "Report Creation", font=FONT, fill="white")
                draw.text((10, 40), "Please wait...", font=SMALL_FONT, fill="white")
            if mode == 'just':
                import report
                report.generate_reports()
            else:
                 import report_dated
                 report_dated.generate_reports()
            time.sleep(2)
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, 20), "Copied Sucessfully!", font=SMALL_FONT, fill="white")
            draw.text((10, 40), f"{count}/{total} files", font=SMALL_FONT, fill="white")
        time.sleep(2)
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['just','dated'], required=True)
    parser.add_argument('--device', type=str, required=True)
    args = parser.parse_args()
    serial = spi(device=0, port=0)
    dev = sh1106(serial)
    ssd_mode(dev, args.mode)

if __name__ == '__main__':
    main()
