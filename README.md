```markdown
# Backup Data using Rapberry Pi with 0.96 inch OLED

This project is designed to help content creators like photographers and videographers back up their data in a simple, space-saving manner. Follow the instructions below to set up and use the project on your system.

## Prerequisites

Make sure you have the following installed on your system:

- A Linux-based OS (Ubuntu/Debian-based system recommended)
- Python 3
- `pip` for Python package management
- Git


Install : sudo apt-get install libopenjp2-7

Enable I2C on your Raspberry Pi: To use I2C, you need to ensure it's enabled in the Raspberry Pi settings:

Run sudo raspi-config.
Navigate to Interface Options.
Select I2C and enable it.

Disabl e UB Curerent lmit  in Performance Options 
Reboot your Raspberry Pi for the changes to take effect.wq

## Installation

1. **Create a folder for the project**  
   Before pulling the repository, create a folder on your system:

   ```bash
   mkdir /backup-data
   cd /backup-data
   ```

2. **Update your system**  
   Run the following commands to update your system:

   ```bash
   sudo apt-get update
   sudo apt-get upgrade
   sudo reboot
   ```

3. **Install Python and pip**  
   Install Python and `pip` if they are not already installed:

   ```bash
   sudo apt install python3-pip
   ```

4. **Set up Git repository**  
   Set the remote URL for the repository:

   ```bash
   git remote set-url origin git@github.com:guruthebond/backup-data.git
   git remote -v  # To validate the remote URL
   ```

   Pull the project from the repository:

   ```bash
   git pull origin main --allow-unrelated-histories
   ```

5. **Upgrade pip**  
   Upgrade `pip` to the latest version:

   ```bash
   pip install --upgrade pip
   ```

6. **Create a virtual environment**  
   Create and activate a virtual environment:

   ```bash
   python3 -m venv myenv
   source myenv/bin/activate
   ```

7. **Install dependencies**  
   Install the required Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Now you can use the project for backing up data as per the instructions provided within the repository. Follow the instructions in the documentation for further details on usage.

## Contributing

Contributions are welcome! Feel free to fork the repository, make changes, and submit pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
