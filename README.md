# Backup Data Setup System

![Project Banner](https://purrfectbackup.com/wp-content/uploads/2025/04/Logo_BW_PNG-1.png) <!-- Add your banner image if available -->

## Overview

This project provides a complete setup for a Raspberry Pi-based backup data system with:
- Automated backup services
- Web UI interface
- Wi-Fi hotspot configuration
- System optimization for headless operation

## Hardware Requirements

- Raspberry Pi (5 recommended)
- MicroSD card (32GB+ recommended)
- External storage (USB HDD/SSD)
- Power supply (5V/3A recommended)

## Installation

### Prerequisites
- Raspberry Pi Lite OS (64-bit recommended)
- Internet connection for initial setup

### Network Setup
The script configures:
- Static IP: `192.168.0.1` for wlan0
- Wi-Fi hotspot: 
  - SSID: `BackMeUp`
  - Password: `11223344`
  - Channel: 7

### System Services
The following services are installed and enabled:
- `backup-data.service` - Main backup service
- `web-ui-flask-app.service` - Web interface
- `reset.service` - System reset handler

### Optimizations
The script applies several system optimizations:
- Disables unnecessary services
- Configures boot parameters for faster startup
- Sets maximum USB current
- Disables unused hardware (audio, camera, etc.)

## Directory Structure
/backup-data/
├── myenv/ # Python virtual environment
├── web-ui/ # Web interface files
├── backup-data.service # Main service file
├── reset.service # Reset service
├── requirements.txt # Python dependencies
├── setup.sh # This setup script
└── version # Version information


## Backup System

The system automatically creates backups of:
- Application data in `/root/backup-data-stable`
- Service files in `/root/backup-data-services`

## Web Interface

After setup, access the web UI at:

Main URL for Backup Webui
http://<your-pi-ip>:5000
Reporting URL

http://<your-pi-ip>:5000/report
Media Validation UR

http://<your-pi-ip>:5000/chkdisk


## Version History

- **Version 3.0** (June 2025)
  - Added comprehensive backup system
  - Improved service management
  - Enhanced system optimizations
  - Dumplicate file name handleing 
  - removed progress bar and live display files copied out of total
  - Three Buttons use on PrrfectBackup to Control Brightness, Reporting and Media Validation 

## Acknowledgments

- Raspberry Pi Foundation
- Hostapd/Dnsmasq developers
- Python community

## Setup Script

The setup script performs the following actions:

1. Updates and upgrades system packages
2. Installs required dependencies:
   - libopenjp2-7
   - git
   - vim
   - python3-pip
   - hostapd
   - dnsmasq
   - ddcutil
   - exiftool

3. Configures system hardware:
   - Enables SPI
   - Sets maximum USB current
   - Configures display settings
   - Disables unnecessary hardware interfaces

4. Creates project directories and mount points

5. Sets up SSH for GitHub access and clones the repository

6. Configures Python virtual environment and installs dependencies

7. Sets up system services:
   - backup-data.service
   - web-ui-flask-app.service
   - reset.service

8. Configures Wi-Fi hotspot with:
   - Static IP: 192.168.0.1
   - SSID: BackMeUp
   - Password: 11223344
   - Channel: 7

9. Disables unnecessary system services

10. Applies system optimizations:
    - Disables audio
    - Disables camera auto-detection
    - Reduces framebuffers
    - Disables firmware KMS setup

11. Creates system backups of application data and service files

12. Provides final instructions for reboot

To run the setup script:
```bash
chmod +x setup.sh
sudo ./setup.sh
