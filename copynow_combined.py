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
    header = "JustCopy!" if mode == 'just' else "DatedCopy!"
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

        cmd = ["rsync", "-a", "--human-readable", "--info=progress2", "--exclude=.*", srcp, destp]
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



def copy_mode(device, mode):
    global stop_flag
    stop_flag = False

    dst = JUST_DST if mode == 'just' else DATED_DST
    if not os.path.ismount(DST_ROOT):
        stop_flag = "dst"
        display_progress(device, 100, "DST DISCONNECTED", 0, 0, mode)
        time.sleep(3)  # Wait for user to notice the message
        return

    if not check_mounts(device):
        return
    if not check_space(device, SRC, dst, mode):
        return

    all_files = []
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
                date = datetime.datetime.fromtimestamp(
                        os.path.getmtime(srcp)).strftime("%m-%d-%Y")
                destp = os.path.join(dst, date, f)
            # Log source and destination paths
            all_files.append((srcp, destp))

    total = len(all_files)
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

    for srcp, destp in all_files:
        if stop_flag:
            break

        # Check if source still exists before accessing it
        if not os.path.exists(srcp):
            stop_flag = "src"
            actual_copied = sum(1 for f in all_files[:all_files.index((srcp, destp))] 
                           if os.path.exists(f[0]))
            count = actual_copied
            break
        
        # Check if source is mounted (if it's a mountable device)
        if not os.path.ismount(SRC):
            stop_flag = "src"
            actual_copied = sum(1 for f in all_files[:all_files.index((srcp, destp))] 
                           if os.path.exists(f[0]))
            count = actual_copied
            break

        if not os.path.ismount(DST_ROOT):
            stop_flag = "dst"
            actual_copied = sum(1 for f in all_files[:all_files.index((srcp, destp))] 
                                if os.path.exists(f[0]))
            count = actual_copied
            break

        count += 1
        if (os.path.exists(destp) and
            os.path.getsize(destp) == os.path.getsize(srcp) and
            os.path.getmtime(destp) >= os.path.getmtime(srcp)):
            action = 'Skip'
        else:
            action = 'Copy'

        display_progress(device, (count/total)*100, srcp, count, total, mode, action=action)

        if action == 'Copy':
            if stop_flag or not os.path.ismount(DST_ROOT):
                stop_flag = "dst"
                break
            # Ensure destination folder exists and check for I/O errors
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
        actual_copied = sum(1 for srcp, _ in all_files[:count] if os.path.exists(srcp))
        log_to_csv(start_s, end.strftime("%Y-%m-%d %H:%M"), 
                 bytes_to_human(data_copied), dur_s, "Src Lost!")
        display_progress(device, 100, "SRC LOST!", actual_copied, total, mode)
        with canvas(device) as draw:
            draw.text((10, 20), "SRC LOST!", font=FONT, fill="white")
            draw.text((10, 40), f"{actual_copied}/{total} copied", font=SMALL_FONT, fill="white")
        time.sleep(3)
        return
    elif stop_flag == "dst":
        actual_copied = sum(1 for srcp, _ in all_files[:count] if os.path.exists(srcp))
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
        # Check the mode and import the corresponding report
        if mode == 'just':
            import report
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
                draw.text((6, device.height // 2 - 20), "Report Creation", font=FONT, fill="white")
                draw.text((6, device.height // 2), f"Please wait...", font=FONT, fill="white")
            report.generate_reports()
        elif mode == 'dated':
            import report_dated
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            with canvas(device) as draw:
                draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
                draw.text((6, device.height // 2 - 20), "Report Creation", font=FONT, fill="white")
                draw.text((6, device.height // 2), f"Please wait...", font=FONT, fill="white")
            report_dated.generate_reports()
        time.sleep(2)
        with canvas(device) as draw:
            draw.rectangle((0, 0, device.width - 1, device.height - 1), outline="white", fill="black")
            draw.text((10, 20), "Copy Done!", font=FONT, fill="white")
            draw.text((10, 40), f"{count}/{total} files", font=SMALL_FONT, fill="white")
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['just','dated'], required=True)
    parser.add_argument('--device', type=str, required=True)
    args = parser.parse_args()
    serial = spi(device=0, port=0)
    dev = sh1106(serial)
    copy_mode(dev, args.mode)

if __name__ == '__main__':
    main()
