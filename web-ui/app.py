import report_webui
from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import json
import os
import threading
import time
import logging
from datetime import datetime
import shutil
from flask import Flask, session  # Import session
from flask_session import Session  # Import Flask-Session for better handling
from flask import send_file
import tempfile


logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Configure session to use filesystem (required for session persistence)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Required for session security

# Initialize Flask-Session
Session(app)

# Global variables to track mount status and copy progress
status = ""
copy_progress = "Not started"
overall_progress = 0
copy_complete = False
copied_files = []  # Initialize as an empty list
files_to_copy = []  # List of files to be copied, with their progress
currently_copying_files = []  # List of files currently being copied
LOG_DIR = 'log'  # Update with the actual log directory path

#@app.route('/logs')
#def logs():
#    try:
#        log_files = []
#        for filename in os.listdir(LOG_DIR):
#            if filename.endswith(".log"):
#                log_path = os.path.join(LOG_DIR, filename)
#                log_files.append({'name': filename, 'path': log_path})
#        return render_template('logs.html', logs=log_files)
#    except Exception as e:
#        return f"Error listing logs: {str(e)}"

@app.route('/chkfiles')
def check_files():
    partitions = get_available_partitions()
    return render_template('checkfiles.html', partitions=partitions)

@app.route('/mount_check', methods=['POST'])
def mount_check_drive():
    drive = request.form['drive']

    try:
        if os.path.ismount('/mnt/usb/check'):
            subprocess.run(['umount', '/mnt/usb/check'], check=True)

        subprocess.run(['mount', drive, '/mnt/usb/check'], check=True)
        return redirect(url_for('browse_check_folder', current_path='/mnt/usb/check'))
    except subprocess.CalledProcessError as e:
        return f"Failed to mount: {str(e)}", 400

@app.route('/browse_check')
def browse_check_folder():
    current_path = request.args.get('current_path', '/mnt/usb/check')

    # Prevent accessing outside the check folder
    if not current_path.startswith('/mnt/usb/check'):
        current_path = '/mnt/usb/check'

    # Get folder contents
    folders, files = list_folders_and_files(current_path)

    # Determine parent folder (if not at root)
    parent_folder = None
    if current_path != '/mnt/usb/check':
        parent_folder = os.path.dirname(current_path)

    display_path = current_path.replace('/mnt/usb/check', '')
    return render_template('checkfiles.html',
                         current_path=current_path,
                         display_path=display_path if display_path else '/',
                         folders=folders,
                         files=files,
                         parent_folder=parent_folder,
                         partitions=get_available_partitions())

from PIL import Image  # Add this at the top of your file

@app.route('/preview_raw')
def preview_raw():
    file_path = request.args.get('file')

    if not (
        file_path.startswith('/mnt/usb/source/')
        or file_path.startswith('/mnt/usb/destination/')
        or file_path.startswith('/mnt/usb/check/')
    ):
        return "Access denied", 403
    if not os.path.exists(file_path):
        return "File not found", 404

    temp_path = None
    try:
        # Create temp file for extracted preview
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_path = temp_file.name

        # Try PreviewImage
        result = subprocess.run(
            ['exiftool', '-b', '-PreviewImage', file_path],
            stdout=subprocess.PIPE
        )
        if result.stdout:
            with open(temp_path, 'wb') as f:
                f.write(result.stdout)
            return send_file(temp_path, mimetype='image/jpeg')

        # Try JpgFromRaw
        result = subprocess.run(
            ['exiftool', '-b', '-JpgFromRaw', file_path],
            stdout=subprocess.PIPE
        )
        if result.stdout:
            with open(temp_path, 'wb') as f:
                f.write(result.stdout)
            return send_file(temp_path, mimetype='image/jpeg')

        # Try PreviewTIFF (e.g. for .3FR)
        with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as tiff_file:
            tiff_path = tiff_file.name

        result = subprocess.run(
            ['exiftool', '-b', '-PreviewTIFF', file_path],
            stdout=subprocess.PIPE
        )
        if result.stdout:
            with open(tiff_path, 'wb') as f:
                f.write(result.stdout)

            # Convert TIFF to JPEG using Pillow
            im = Image.open(tiff_path)
            im.convert('RGB').save(temp_path, 'JPEG')
            return send_file(temp_path, mimetype='image/jpeg')

        return "No preview available", 404

    except Exception as e:
        return f"Error generating preview: {str(e)}", 500

    finally:
        try:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            if 'tiff_path' in locals() and os.path.exists(tiff_path):
                os.unlink(tiff_path)
        except Exception:
            pass


@app.route('/preview_image')
def preview_image():
    file_path = request.args.get('file')

    # Security check - allow only specific base paths
    allowed_dirs = ['/mnt/usb/source/', '/mnt/usb/destination/', '/mnt/usb/check/']
    if not any(file_path.startswith(path) for path in allowed_dirs):
        return "Access denied", 403

    if not os.path.exists(file_path):
        return "File not found", 404

    return send_file(file_path)

@app.route('/browse_folder', methods=['GET'])
def browse_folder():
    """Browse folders and display contents, including files."""
    base_path = request.args.get('base_path', '/mnt/usb/source')  # Default to source
    current_path = request.args.get('current_path', base_path)

    # Prevent accessing outside the base folder
    if not current_path.startswith(base_path):
        current_path = base_path

    # Get folder contents
    folders, files = list_folders_and_files(current_path)

    # Determine parent folder (if not at base)
    parent_folder = None
    if current_path != base_path:
        parent_folder = os.path.dirname(current_path)

    return render_template('browse.html', folders=folders, files=files, current_path=current_path, parent_folder=parent_folder)


def list_folders_and_files(directory):
    """List folders and files inside a directory."""
    folders = []
    files = []
    
    try:
        for item in os.listdir(directory):
            if item.startswith('.'):
                continue  # Skip hidden files

            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                size = get_folder_size(item_path)
                size_gb = size / (1024 ** 3)
                folders.append({'name': item, 'path': item_path, 'size': f"{size_gb:.2f} GB"})
            else:
                file_size = os.path.getsize(item_path) / (1024 ** 2)  # MB
                
                # Get creation time (birth time) if available, fall back to modification time
                try:
                    file_stat = os.stat(item_path)
                    file_ctime = file_stat.st_birthtime if hasattr(file_stat, 'st_birthtime') else file_stat.st_ctime
                except AttributeError:
                    # For systems that don't support st_birthtime (like some Linux filesystems)
                    file_ctime = os.path.getctime(item_path)
                
                date_created = datetime.fromtimestamp(file_ctime).strftime("%Y-%m-%d %H:%M:%S")
                files.append({
                    'name': item,
                    'size': f"{file_size:.2f} MB",
                    'date': date_created  # Now shows creation date
                })
    except Exception as e:
        logging.error(f"Error listing directory {directory}: {e}")

    return folders, files

@app.route('/delete_folder', methods=['POST'])
def delete_folder():
    folder_name = request.form.get('folder_name')
    mount_point = '/mnt/usb/destination'  # Same mount point as in create_folder
    logging.debug(f"Attempting to delete folder: {folder_name}")
    import os
    folder_path = os.path.join(mount_point, folder_name)
    logging.debug(f"Computed folder path: {folder_path}")
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)  # Use shutil.rmtree to delete non-empty directories
            logging.debug(f"Folder '{folder_name}' deleted successfully.")
            status = f"Folder '{folder_name}' deleted successfully."
            source_folders = list_folders_with_sizes('/mnt/usb/source')
            destination_folders = list_folders_with_sizes('/mnt/usb/destination')
            return redirect(url_for('folder_selection', source_folders=json.dumps(source_folders), destination_folders=json.dumps(destination_folders)))
        else:
            logging.error(f"Folder '{folder_name}' not found.")
            status = "Folder not found."
            return redirect(url_for('folder_selection', source_folders=json.dumps(list_folders_with_sizes('/mnt/usb/source')), destination_folders=json.dumps(list_folders_with_sizes('/mnt/usb/destination'))))
    except Exception as e:
        logging.error(f"Error deleting folder '{folder_name}': {str(e)}")
        status = str(e)
        return redirect(url_for('folder_selection', source_folders=json.dumps(list_folders_with_sizes('/mnt/usb/source')), destination_folders=json.dumps(list_folders_with_sizes('/mnt/usb/destination'))))



@app.route('/logs')
def logs():
    try:
        # Set the log directory to your static folder's oled_log subdirectory
        LOG_DIR = os.path.join(app.root_path, 'static', 'oled_log')
        log_entries = {}

        for filename in os.listdir(LOG_DIR):
            if not filename.endswith(".html"):
                continue
            
            parts = filename.split("_")
            if len(parts) < 3:
                continue
            
            # Combine the first two parts (YYYYMMDD and HHMMSS) with an underscore
            timestamp_str = parts[0] + "_" + parts[1]
            try:
                log_datetime = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                human_readable_date = log_datetime.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            
            # Extract log type from the third part (e.g., "src", "dst", "comparison")
            log_type = parts[2].split(".")[0]
            if timestamp_str not in log_entries:
                log_entries[timestamp_str] = {
                    "datetime": human_readable_date,
                    "src": None,
                    "dst": None,
                    "comparison": None,
                    "type": None  # New field for type
                }
            
            if log_type == "src":
                log_entries[timestamp_str]["src"] = filename
            elif log_type == "dst":
                log_entries[timestamp_str]["dst"] = filename
            elif log_type == "comparison":
                log_entries[timestamp_str]["comparison"] = filename
                # Extract type from the comparison file
                comp_file_path = os.path.join(LOG_DIR, filename)
                log_entries[timestamp_str]["type"] = extract_log_type(comp_file_path)

        # Convert dictionary to list and sort by datetime descending (latest on top)
        log_files = sorted(log_entries.values(), key=lambda x: x["datetime"], reverse=True)

        return render_template('logs.html', logs=log_files)

    except Exception as e:
        return f"Error listing logs: {str(e)}"


@app.route('/report')
def report():
    try:
        # Set the log directory to your static folder's oled_log subdirectory
        LOG_DIR = os.path.join(app.root_path, 'static', 'oled_log')
        log_entries = {}

        for filename in os.listdir(LOG_DIR):
            if not filename.endswith(".html"):
                continue
            
            parts = filename.split("_")
            if len(parts) < 3:
                continue
            
            # Combine the first two parts (YYYYMMDD and HHMMSS) with an underscore
            timestamp_str = parts[0] + "_" + parts[1]
            try:
                log_datetime = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                human_readable_date = log_datetime.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            
            # Extract log type from the third part (e.g., "src", "dst", "comparison")
            log_type = parts[2].split(".")[0]
            if timestamp_str not in log_entries:
                log_entries[timestamp_str] = {
                    "datetime": human_readable_date,
                    "src": None,
                    "dst": None,
                    "comparison": None,
                    "type": None  # New field for type
                }
            
            if log_type == "src":
                log_entries[timestamp_str]["src"] = filename
            elif log_type == "dst":
                log_entries[timestamp_str]["dst"] = filename
            elif log_type == "comparison":
                log_entries[timestamp_str]["comparison"] = filename
                # Extract type from the comparison file
                comp_file_path = os.path.join(LOG_DIR, filename)
                log_entries[timestamp_str]["type"] = extract_log_type(comp_file_path)

        # Convert dictionary to list and sort by datetime descending (latest on top)
        log_files = sorted(log_entries.values(), key=lambda x: x["datetime"], reverse=True)

        return render_template('report.html', logs=log_files)

    except Exception as e:
        return f"Error listing logs: {str(e)}"

@app.route('/view_log')
def view_log():
    log_path = request.args.get('path')
    try:
        with open(log_path, 'r') as log_file:
            log_content = log_file.read()
        
        # Render the 'view_log.html' template, passing the log content
        return render_template('view_log.html', log_content=log_content)
    
    except Exception as e:
        return f"Error reading log: {str(e)}"


def get_available_partitions():
    try:
        result = subprocess.run(['lsblk', '--json'], capture_output=True, check=True)
        devices = json.loads(result.stdout)

        partitions = []
        for device in devices['blockdevices']:
            if 'children' in device:
                for child in device['children']:
                    if "mmcblk" in child['name']:
                        continue
                    size_str = child['size']
                    if 'G' in size_str:
                        size = float(size_str.replace('G', ''))
                    elif 'T' in size_str:
                        size = float(size_str.replace('T', '')) * 1024
                    else:
                        size = 0
                    if size >= 1:
                        # Get the label using blkid
                        label = ""
                        try:
                            blkid_result = subprocess.run(['blkid', '-s', 'LABEL', '-o', 'value', f"/dev/{child['name']}"], capture_output=True, check=True)
                            label = blkid_result.stdout.decode().strip()
                        except subprocess.CalledProcessError:
                            label = "No Label"

                        partitions.append({
                            'name': f"/dev/{child['name']}",
                            'size': f"{size:.2f} GB" if size < 1024 else f"{size / 1024:.2f} TB",
                            'label': label
                        })
        return partitions
    except Exception as e:
        return []

def get_folder_size(folder):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except FileNotFoundError:
                logging.warning(f"File not found: {fp}")
            except PermissionError:
                logging.warning(f"Permission denied: {fp}")
    return total_size

def list_folders_with_sizes(directory):
    folders = []
    for item in os.listdir(directory):
        # Exclude hidden files and directories
        if item.startswith('.'):
            continue

        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            size = get_folder_size(item_path)
            size_gb = size / (1024 ** 3)
            folders.append({'name': item, 'size': f"{size_gb:.2f} GB"})
    return folders

@app.route('/')
def index():
    partitions = get_available_partitions()
    return render_template('index.html', status=status, partitions=partitions)

@app.route('/mount', methods=['POST'])
def mount():
    global status
    source = request.form['source']
    destination = request.form['destination']

    try:
        if os.path.ismount('/mnt/usb/source'):
            subprocess.run(['umount', '/mnt/usb/source'], check=True)
        if os.path.ismount('/mnt/usb/destination'):
            subprocess.run(['umount', '/mnt/usb/destination'], check=True)

        subprocess.run(['mount', source, '/mnt/usb/source'], check=True)
        subprocess.run(['mount', destination, '/mnt/usb/destination'], check=True)
        # Get partition labels
        partitions = get_available_partitions()
        source_label = next((p['label'] for p in partitions if p['name'] == source), "No Label")
        destination_label = next((p['label'] for p in partitions if p['name'] == destination), "No Label")

        # Store labels in session
        session['source_label'] = source_label
        session['destination_label'] = destination_label

        status = f"Successfully mounted {source} to /mnt/usb/source and {destination} to /mnt/usb/destination."
        source_folders = list_folders_with_sizes('/mnt/usb/source')
        destination_folders = list_folders_with_sizes('/mnt/usb/destination')

        return redirect(url_for('folder_selection', source_folders=json.dumps(source_folders), destination_folders=json.dumps(destination_folders)))

    except subprocess.CalledProcessError as e:
        status = f"Failed to mount: {str(e)}"
        return render_template('index.html', status=status, partitions=get_available_partitions())

@app.route('/folder_selection')
def folder_selection():
    source_folders = json.loads(request.args.get('source_folders', '[]'))
    destination_folders = json.loads(request.args.get('destination_folders', '[]'))

    # Store the first generated URL in session, if not already set
    if 'home_url' not in session:
        session['home_url'] = request.url  # Store the initial URL

    # Get labels from session with fallback
    source_label = session.get('source_label', 'No Label')
    destination_label = session.get('destination_label', 'No Label')
    return render_template('folder.html',
                           source_folders=source_folders,
                           destination_folders=destination_folders,
                           source_label=source_label,
                           destination_label=destination_label)



import os
import subprocess
import time

def copy_files(source, destination):
    global copy_progress, overall_progress, copy_complete, copied_files

    # Reset copied_files at the start of a new copy process
    copied_files = []

    # Create logs directory if it doesn't exist
    os.makedirs('log', exist_ok=True)

    # Define log file path
    log_filename = time.strftime("log/copy_%Y%m%d_%H%M%S.log")

    # Remove old logs, keep only the last 10
    log_files = sorted([f for f in os.listdir('log') if f.startswith('copy_')], reverse=True)
    for old_log in log_files[10:]:
        os.remove(os.path.join('log', old_log))

    try:
        # Step 1: Use rsync --dry-run to list files that will be copied
        dry_run_process = subprocess.Popen(
            ['rsync', '-a', '--dry-run', '--info=NAME', '--exclude', '.*', '--exclude', '*/.*', source, destination],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        dry_run_output, dry_run_error = dry_run_process.communicate()

        if dry_run_process.returncode != 0:
            raise Exception(f"Dry run failed: {dry_run_error}")

        # Step 2: Calculate the size of files to be copied
        new_data_size = 0
        files_to_copy = []
        for line in dry_run_output.splitlines():
            if line.strip() and not line.endswith('/'):  # Exclude directories
                file_path = os.path.join(source, line.strip())
                try:
                    file_size = os.path.getsize(file_path)
                    new_data_size += file_size
                    files_to_copy.append(line.strip())
                except FileNotFoundError:
                    continue
                except PermissionError:
                    continue

        logging.debug(f"Source size: {new_data_size / (1024 ** 3):.2f} GB")
        logging.debug(f"Files to copy: {len(files_to_copy)}")

        # Step 3: Start the actual copy process
        with open(log_filename, 'w') as log_file:
            log_file.write("Final Copy Summary:\n")
            log_file.write(f"Source: {source}\n")
            log_file.write(f"Destination: {destination}\n")
            log_file.write(f"Total Data to be Copied: {new_data_size / (1024 ** 3):.2f} GB\n")
            log_file.write("Files to be copied:\n")
            for file in files_to_copy[:10]:  # Log first 10 files as an example
                log_file.write(f"{file}\n")
            log_file.write("\nStarting copy process...\n")
            log_file.flush()

            # Start the rsync process to copy files
            process = subprocess.Popen(
                ['rsync', '-a', '--info=progress2', '--progress', '--inplace', '--exclude', '.*', '--exclude', '*/.*', source, destination],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            copied_size = 0  # Track the amount of data copied
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break

                # Log progress and file names
                if "to-check" in output:  # Progress-related output
                    copy_progress = f"Copying files... {output.strip()}"
                    log_file.write(output)
                    log_file.flush()

                elif output.strip() and not output.startswith(" "):  # Likely a file name (excluding directories)
                    filename = output.strip()
                    if not filename.endswith('/'):  # Exclude directories
                        file_path = os.path.join(source, filename)
                        try:
                            file_size = os.path.getsize(file_path)
                            copied_size += file_size
                            # Add file to the list of copied files (keep only the last 10)
                            if len(copied_files) >= 5:
                                copied_files.pop(0)  # Remove the oldest file
                            copied_files.append(filename)  # Add the new file
                            log_file.write(f"Copied: {filename}\n")
                            log_file.flush()
                        except FileNotFoundError:
                            continue
                        except PermissionError:
                            continue

                # Update progress percentage based on new data size
                if new_data_size > 0:
                    overall_progress = (copied_size / new_data_size) * 100
                else:
                    overall_progress = 0

            # Check rsync process completion status
            if process.returncode == 0:
                copy_progress = "Copy completed successfully."
                overall_progress = 100
                copy_complete = True
                report_webui.generate_reports(source, destination)
            else:
                error_output = process.stderr.read()
                log_file.write(f"\nError: {error_output}\n")
                log_file.flush()
                copy_progress = f"Failed to copy: {error_output.strip()} - Error code: {process.returncode}"
                overall_progress = 0
                copy_complete = False

            # Final copy summary at the bottom after the copy is done
            log_file.write("\nFinal Copy Summary:\n")
            log_file.write(f"Total Data Copied: {copied_size / (1024 ** 3):.2f} GB\n")
            log_file.write("Files Copied:\n")
            for file in copied_files:  # Log the last 10 copied files
                log_file.write(f"{file}\n")
            log_file.write("\n")

    except Exception as e:
        copy_progress = f"Failed to copy: {e}"
        overall_progress = 0
        copy_complete = False

@app.route('/start_copy', methods=['POST'])
def start_copy():
    global copy_progress, overall_progress, copy_complete
    copy_progress = "Copying..."
    overall_progress = 0
    copy_complete = False  # Reset the flag before starting a new copy

    source_folder = request.form['source_folder']
    destination_folder = request.form['destination_folder']

    source_path = os.path.join('/mnt/usb/source', source_folder) + '/'
    destination_path = os.path.join('/mnt/usb/destination', destination_folder)

    # Start the copy process in a separate thread
    copy_thread = threading.Thread(target=copy_files, args=(source_path, destination_path))
    copy_thread.start()

    source_folders = list_folders_with_sizes('/mnt/usb/source')
    destination_folders = list_folders_with_sizes('/mnt/usb/destination')

    return redirect(url_for('progress_page', source_folders=json.dumps(source_folders), destination_folders=json.dumps(destination_folders)))

@app.route('/progress')
def progress_page():
    global copy_progress, overall_progress
    return render_template('progress.html', copy_progress=copy_progress, overall_progress=overall_progress)

@app.route('/progress_status')
def progress_status():
    global copy_progress, overall_progress, copy_complete, copied_files
    source_folders = list_folders_with_sizes('/mnt/usb/source')
    destination_folders = list_folders_with_sizes('/mnt/usb/destination')
    return jsonify(
        copy_progress=copy_progress,
        overall_progress=overall_progress,
        copy_complete=copy_complete,
        copied_files=copied_files,  # Send the list of copied files
        source_folders=source_folders,
        destination_folders=destination_folders
    )

@app.route('/create_folder', methods=['POST'])
def create_folder():
    global status
    mount_point = request.form['mount_point']
    new_folder_name = request.form['new_folder_name'].strip()  # Remove trailing spaces

    try:
        subprocess.run(['mkdir', '-p', os.path.join(mount_point, new_folder_name)], check=True)
        status = f"Folder '{new_folder_name}' created successfully in {mount_point}."
    except subprocess.CalledProcessError as e:
        status = f"Failed to create folder in {mount_point}: {str(e)}"

    return redirect(url_for('folder_selection', source_folders=json.dumps(list_folders_with_sizes('/mnt/usb/source')), destination_folders=json.dumps(list_folders_with_sizes('/mnt/usb/destination'))))

import re

def extract_log_type(file_path):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        # Look for a pattern like: <h2>[WebUI Backup]Comparison Report</h2>
        match = re.search(r'\[([^\]]+)\]Comparison Report', content)
        if match:
            return match.group(1)
    except Exception as e:
        logging.error("Error extracting log type from %s: %s", file_path, str(e))
    return "Unknown"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
