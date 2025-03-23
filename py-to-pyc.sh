#!/bin/bash

# Function to compile and rename .pyc files
compile_and_move() {
    local dir=$1
    shift
    local files=("$@")

    # Navigate to the target directory
    cd "$dir" || exit

    # Compile Python files
    python -m compileall "${files[@]}"

    # Move compiled files to the current directory and rename them properly
    for file in "${files[@]}"; do
        # Extract filename without extension
        base_name="${file%.py}"

        # Find the corresponding .pyc file (ignoring the Python version suffix)
        pyc_file=$(ls "__pycache__/${base_name}".*.pyc 2>/dev/null)

        # If found, rename and move it
        if [[ -n "$pyc_file" ]]; then
            mv "$pyc_file" "${base_name}.pyc"
        fi
    done

    # Clean up __pycache__ directory
    rm -rf __pycache__
}

# Compile and process files in /backup-data
compile_and_move "/backup-data" main.py copynow.py copynow_dated.py startup.py reset.py report.py report_dated.py

# Compile and process files in /backup-data/web-ui
compile_and_move "/backup-data/web-ui" app.py report_webui.py


# Update systemd services to use .pyc files
#WebUI Service
sed -i 's|\bapp\.py\b|app.pyc|g' /etc/systemd/system/web-ui-flask-app.service
#Startup Service
sed -i 's|\bstartup\.py\b|startup.pyc|g' /etc/systemd/system/backup-data.service
#Reset Service
sed -i 's|\breset\.py\b|reset.pyc|g' /etc/systemd/system/reset.service
# Reload systemd to apply changes
systemctl daemon-reload

# Ask user if they want to delete all .py files
read -p "Do you want to delete all original .py files? (yes/no): " choice
case "$choice" in
  yes|YES|y|Y )
    echo "Deleting original .py files..."
    find /backup-data /backup-data/web-ui -maxdepth 1 -name "*.py" -delete
    echo "All .py files deleted."
    ;;
  no|NO|n|N )
    echo "Keeping original .py files."
    ;;
  * )
    echo "Invalid choice. Keeping original .py files."
    ;;
esac
