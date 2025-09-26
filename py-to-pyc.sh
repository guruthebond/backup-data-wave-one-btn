#!/bin/bash

# Function to compile and rename .pyc files
compile_and_move() {
    local dir=$1
    shift
    local files=("$@")

    cd "$dir" || exit
    python -m compileall "${files[@]}"

    for file in "${files[@]}"; do
        base_name="${file%.py}"
        pyc_file=$(ls "__pycache__/${base_name}".*.pyc 2>/dev/null)
        if [[ -n "$pyc_file" ]]; then
            mv "$pyc_file" "${base_name}.pyc"
        fi
    done

    rm -rf __pycache__
}

# Compile .py files
compile_and_move "/backup-data" main.py copynow_combined.py error_handler.py startup.py reset.py report.py report_dated.py copynow_ssd.py
compile_and_move "/backup-data/web-ui" app.py report_webui.py

# Update systemd service files to reference .pyc instead of .py
sed -i 's|\bapp\.py\b|app.pyc|g' /etc/systemd/system/web-ui-flask-app.service
sed -i 's|\bstartup\.py\b|startup.pyc|g' /etc/systemd/system/backup-data.service
sed -i 's|\breset\.py\b|reset.pyc|g' /etc/systemd/system/reset.service
systemctl daemon-reload

# Ask user whether to delete .py files
read -p "Do you want to delete all original .py files? (yes/no): " choice
case "$choice" in
  yes|YES|y|Y )
    echo "Deleting original .py files..."
    find /backup-data /backup-data/web-ui -maxdepth 1 -name "*.py" -delete
    echo "All .py files deleted."

    # Delete old backup directory if it exists
    if [ -d "/root/backup-data-stable" ]; then
        echo "Removing old /root/backup-data-stable..."
        rm -rf /root/backup-data-stable
    fi

    # Create fresh system backup
    echo "Creating system backup..."
    echo "Backing up application data to /root/backup-data-stable..."
    mkdir -p /root/backup-data-stable
    rsync -a --exclude='myenv/' /backup-data/ /root/backup-data-stable/

    mkdir -p /root/backup-data-services
    cp /etc/systemd/system/backup-data.service \
       /etc/systemd/system/web-ui-flask-app.service \
       /etc/systemd/system/reset.service \
       /root/backup-data-services/

    rm -f /root/backup-data-stable/copy-log.csv
    touch /root/backup-data-stable/copy-log.csv

    rm -rf /root/backup-data-stable/web-ui/log/*
    echo "System backup completed."
    ;;
  no|NO|n|N )
    echo "Keeping original .py files. Skipping backup cleanup."
    ;;
  * )
    echo "Invalid choice. Keeping original .py files. Skipping backup cleanup."
    ;;
esac
