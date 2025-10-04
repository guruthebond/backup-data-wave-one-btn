#!/bin/bash

echo "--------------------------------------"
echo "Backup Data Setup Script"
echo "--------------------------------------"

# Update and upgrade system
echo "Updating and upgrading system packages..."
sudo apt update -y && sudo apt upgrade -y 

# Install required packages
echo "Installing required packages..."
echo "Packages being installed: libopenjp2-7 git vim python3-pip hostapd dnsmasq ddcutil exiftool"
sudo apt-get install -y libopenjp2-7 git vim python3-pip hostapd dnsmasq ddcutil libimage-exiftool-perl

echo "ExifTool installed for RAW to JPG preview extraction."

# Enable I2C and disable USB current limit
echo "Configuring system for SPI and USB current limits..."
echo "Disabling i2c and enabling SPI..."
# Disable i2c
sudo sed -i '/^dtparam=i2c_arm=on/d' /boot/firmware/config.txt
# Enable SPI
echo "dtparam=spi=on" | sudo tee -a /boot/firmware/config.txt
# Enable USB Current at MAX
echo "Setting USB current to maximum..."
echo "usb_max_current_enable=1" | sudo tee -a /boot/firmware/config.txt
# Load SPI at Boot
echo "Adding SPI module to load at boot..."
echo "spi-dev" | sudo tee -a /etc/modules
#echo "i2c-dev" |sudo tee -a /etc/modules
#Copy Performance Tuning 
#sudo sed -i 's/$/ pcie_aspm=performance/' /boot/firmware/cmdline.txt
echo 'io_is_busy=1' | sudo tee -a /boot/firmware/config.txt
echo -e '\ndtoverlay=rpi-active-cooler\ndtparam=fan_temp0=60000,fan_temp1=65000,fan_temp2=70000,fan_temp3=75000' | sudo tee -a /boot/firmware/config.txt

# Display control commands
echo "Configuring display settings..."
echo "Disabling HDMI Display..."
ddcutil setvcp d6 5

#Command to Enable HDMI Display
#ddcutil setvcp d6 1

# Create project folders
echo "Creating project directories..."
echo "Creating mount points and backup directory..."
sudo mkdir -p /mnt/usb/source /mnt/usb/destination /mnt/src /mnt/dst /mnt/usb/check
mkdir -p /backup-data
cd /backup-data || exit

# Generate SSH key
echo "Setting up SSH for GitHub access..."
echo "Generating new ED25519 SSH key..."
ssh-keygen -t ed25519 -C "metoocool@gmail.com" -f ~/.ssh/id_ed25519 -N ""
# Display the SSH public key and wait for user confirmation
echo "Copy the following SSH key to your GitHub account (https://github.com/settings/keys):"
cat ~/.ssh/id_ed25519.pub
echo "Once you've added the SSH key to GitHub, press Enter to continue."
read -r

# Test SSH connection to GitHub
echo "Testing SSH connection to GitHub..."
echo "Attempting first connection to GitHub (will add to known_hosts)..."
ssh -T -o StrictHostKeyChecking=no git@github.com
# Clone the repository
echo "Cloning the backup-data-wave repository..."
git clone git@github.com:guruthebond/backup-data-wave-one-btn.git /backup-data

# Set up Python virtual environment
echo "Setting up Python environment..."
echo "Creating virtual environment 'myenv'..."
python3 -m venv myenv
source myenv/bin/activate
echo "Upgrading pip and installing requirements..."
pip install --upgrade pip  --trusted-host pypi.org --trusted-host files.pythonhosted.org
pip install -r requirements.txt  --trusted-host pypi.org --trusted-host files.pythonhosted.org
echo "Installing DejaVu font..."
mv dejavu-sans.condensed.ttf /usr/share/fonts/truetype/dejavu/dejavu-sans.condensed.ttf
mv lineawesome-webfont.ttf /usr/share/fonts/truetype/dejavu/lineawesome-webfont.ttf

# Configure system services
echo "Configuring system services..."
echo "Moving service files to systemd directory..."
sudo mv backup-data.service /etc/systemd/system/
sudo mv web-ui/web-ui-flask-app.service /etc/systemd/system/
sudo mv reset.service /etc/systemd/system/
echo "Reloading systemd and enabling services..."
sudo systemctl daemon-reload
sudo systemctl enable backup-data.service
sudo systemctl enable reset.service

# Configure Wi-Fi hotspot
echo "Setting up Wi-Fi hotspot configuration..."
echo "Cleaning up existing WiFi connections..."
sudo nmcli connection show | grep wifi | awk '{print $1}' | xargs -I {} sudo nmcli connection delete "{}"

echo "Configuring dnsmasq..."
echo -e "interface=wlan0\n\
dhcp-range=192.168.0.2,192.168.0.20,255.255.255.0,24h\n\
dhcp-option=3,192.168.0.1\n\
dhcp-option=6,192.168.0.1" | sudo tee /etc/dnsmasq.conf

echo "Configuring hostapd..."
echo -e "interface=wlan0\n\
driver=nl80211\n\
ssid=BackMeUp\n\
hw_mode=g\n\
channel=7\n\
wmm_enabled=0\n\
auth_algs=1\n\
ignore_broadcast_ssid=0\n\
wpa=2\n\
wpa_passphrase=11223344\n\
wpa_key_mgmt=WPA-PSK\n\
rsn_pairwise=CCMP" | sudo tee /etc/hostapd/hostapd.conf

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee /etc/default/hostapd

echo "Configuring IP forwarding..."
sudo sed -i '/^net.ipv4.ip_forward/d' /etc/sysctl.conf
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

echo "Setting static IP for wlan0..."
echo -e "auto wlan0\n\
iface wlan0 inet static\n\
address 192.168.0.1\n\
netmask 255.255.255.0" | sudo tee /etc/network/interfaces

echo "Creating systemd network configuration..."
echo -e "[Match]\nName=wlan0\n\n[Network]\nAddress=192.168.0.1/24" | sudo tee /etc/systemd/network/20-wlan0.network > /dev/null

echo "Enabling network services..."
sudo systemctl enable systemd-networkd
sudo systemctl unmask hostapd
echo "Restarting network services..."
sudo systemctl restart dnsmasq 
sudo systemctl restart hostapd 
sudo systemctl enable dnsmasq

# Disable unnecessary services
echo "Disabling unnecessary system services..."
echo "The following services will be disabled:"
echo "- avahi-daemon.service (Zeroconf/Bonjour)"
echo "- bluetooth.service"
echo "- dphys-swapfile.service"
echo "- e2scrub_reap.service"
echo "- hciuart.service"
echo "- hostapd.service"
echo "- ModemManager.service"
echo "- NetworkManager-wait-online.service"
echo "- nftables.service"
echo "- pigpiod.service"
echo "- regenerate_ssh_host_keys.service"
echo "- rpcbind.service"
echo "- systemd-pstore.service"
echo "- triggerhappy.service"

sudo systemctl disable --now avahi-daemon.service
sudo systemctl disable --now bluetooth.service
sudo systemctl disable --now dphys-swapfile.service
sudo systemctl disable --now e2scrub_reap.service
sudo systemctl disable --now hciuart.service
sudo systemctl disable --now hostapd.service
sudo systemctl disable --now ModemManager.service
sudo systemctl disable --now NetworkManager-wait-online.service
sudo systemctl disable --now nftables.service
sudo systemctl disable --now pigpiod.service
sudo systemctl disable --now regenerate_ssh_host_keys.service
sudo systemctl disable --now rpcbind.service
sudo systemctl disable --now systemd-pstore.service
sudo systemctl disable --now triggerhappy.service

echo "Masking services to prevent activation..."
sudo systemctl mask alsa-utils.service avahi-daemon.service bluetooth.service ModemManager.service NetworkManager-wait-online.service rpcbind.service systemd-timesyncd.service triggerhappy.service

# System optimizations
echo "Applying system optimizations..."

# Disable audio
echo "Disabling audio..."
if grep -q "^dtparam=audio=" /boot/firmware/config.txt; then
    sudo sed -i 's/^dtparam=audio=.*/dtparam=audio=off/' /boot/firmware/config.txt
    echo "Updated: dtparam=audio=off"
else
    echo "dtparam=audio=off" | sudo tee -a /boot/firmware/config.txt
    echo "Added: dtparam=audio=off"
fi

# Disable camera auto-detection
echo "Disabling camera auto-detection..."
if grep -q "^camera_auto_detect=" /boot/firmware/config.txt; then
    sudo sed -i 's/^camera_auto_detect=.*/camera_auto_detect=0/' /boot/firmware/config.txt
    echo "Updated: camera_auto_detect=0"
else
    echo "camera_auto_detect=0" | sudo tee -a /boot/firmware/config.txt
    echo "Added: camera_auto_detect=0"
fi

# Disable DSI display auto-detection
echo "Disabling DSI display auto-detection..."
if grep -q "^display_auto_detect=" /boot/firmware/config.txt; then
    sudo sed -i 's/^display_auto_detect=.*/display_auto_detect=0/' /boot/firmware/config.txt
    echo "Updated: display_auto_detect=0"
else
    echo "display_auto_detect=0" | sudo tee -a /boot/firmware/config.txt
    echo "Added: display_auto_detect=0"
fi

# Reduce framebuffers
echo "Reducing framebuffers to 1..."
if grep -q "^max_framebuffers=" /boot/firmware/config.txt; then
    sudo sed -i 's/^max_framebuffers=.*/max_framebuffers=1/' /boot/firmware/config.txt
    echo "Updated: max_framebuffers=1"
else
    echo "max_framebuffers=1" | sudo tee -a /boot/firmware/config.txt
    echo "Added: max_framebuffers=1"
fi

# Disable firmware-created video settings
echo "Disabling firmware KMS setup..."
if grep -q "^disable_fw_kms_setup=" /boot/firmware/config.txt; then
    sudo sed -i 's/^disable_fw_kms_setup=.*/disable_fw_kms_setup=1/' /boot/firmware/config.txt
    echo "Updated: disable_fw_kms_setup=1"
else
    echo "disable_fw_kms_setup=1" | sudo tee -a /boot/firmware/config.txt
    echo "Added: disable_fw_kms_setup=1"
fi

# Ensure maximum CPU speed
#echo "Enabling ARM boost for maximum CPU speed..."
#if grep -q "^arm_boost=" /boot/firmware/config.txt; then
#    sudo sed -i 's/^arm_boost=.*/arm_boost=1/' /boot/firmware/config.txt
#    echo "Updated: arm_boost=1"
#else
#    echo "arm_boost=1" | sudo tee -a /boot/firmware/config.txt
#    echo "Added: arm_boost=1"
#fi

# Update boot parameters
echo "Updating /boot/firmware/cmdline.txt with optimized parameters..."
#echo "console=tty1 root=PARTUUID=5072fd7b-02 rootfstype=ext4 fsck.repair=no rootwait quiet splash loglevel=0 fastboot noswap" | sudo tee /boot/firmware/cmdline.txt

# Assign static IP to Wi-Fi interface
echo "Assigning Static IP Address to Raspberry Pi..."
sudo ip addr add 192.168.0.1/24 dev wlan0

# Update version information
echo "Updating version information..."
echo "Version 3.0" > version
echo "Mar 2025" >> version

# Create system backup
echo "Creating system backup..."
echo "Backing up application data to /root/backup-data-stable..."
mkdir -p /root/backup-data-stable && \
rsync -a --exclude='myenv/' /backup-data/ /root/backup-data-stable/ && \
mkdir -p /root/backup-data-services && \
cp /etc/systemd/system/backup-data.service /etc/systemd/system/web-ui-flask-app.service /etc/systemd/system/reset.service /root/backup-data-services/
rm /root/backup-data-stable/copy-log.csv
touch /root/backup-data-stable/copy-log.csv 
rm -rf /root/backup-data-stable/web-ui/log/* 
echo "Set power button delay to 3 seconds"
echo -e "\nHoldoffTimeoutSec=3\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=poweroff" | sudo tee -a /etc/systemd/logind.conf && sudo systemctl restart systemd-logind
echo "Remove Fake Clock"
sudo systemctl disable fake-hwclock
sudo systemctl stop fake-hwclock
sudo apt remove fake-hwclock -y
# Final instructions
echo "--------------------------------------"
echo "Setup complete!"
echo "REBOOT NOW to apply all changes!"
echo "--------------------------------------"
