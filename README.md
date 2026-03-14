# Pi Print Server

A lightweight web print server for Raspberry Pi 1. Upload files from any browser on your local network and print them to a USB-connected printer.

**Supported file types:** PDF, JPG, PNG, TXT (max 50 MB)

---

## Hardware requirements

- Raspberry Pi 1 Model B or B+ (ARMv6, 256–512 MB RAM)
- Raspbian / Raspberry Pi OS Lite (32-bit, Bullseye or later)
- USB printer
- WiFi adapter (or Ethernet) — static IP recommended

---

## 1. Set a static IP

Edit `/etc/dhcpcd.conf` on the Pi and append:

```
interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=1.1.1.1
```

Replace `192.168.1.100` and `192.168.1.1` with your network's values.

```bash
sudo systemctl restart dhcpcd
```

> For Ethernet, change `wlan0` to `eth0`.

---

## 2. Install CUPS

```bash
sudo apt-get update
sudo apt-get install -y cups cups-bsd

# Allow the 'pi' user to manage printers
sudo usermod -aG lp pi
sudo usermod -aG lpadmin pi

# Allow CUPS admin access from the local network
sudo cupsctl --remote-any

sudo systemctl enable cups
sudo systemctl start cups
```

Add your printer via the CUPS web interface:
```
http://192.168.1.100:631
```
Go to **Administration → Add Printer** and follow the wizard.

After adding, verify with:
```bash
lpstat -p
```

---

## 3. Install the app

```bash
# Copy the project to the Pi (e.g. via scp or git)
git clone <your-repo-url> /home/pi/pi_printer
cd /home/pi/pi_printer

# Create a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Run manually (for testing)

```bash
cd /home/pi/pi_printer
source venv/bin/activate
python app.py
```

Open `http://192.168.1.100:5000` in a browser.

---

## 5. Run as a systemd service (auto-start on boot)

```bash
# Create log directory
sudo mkdir -p /var/log/pi-printer
sudo chown pi:pi /var/log/pi-printer

# Install and enable the service
sudo cp systemd/pi-printer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-printer
sudo systemctl start pi-printer
```

Check status:
```bash
sudo systemctl status pi-printer
journalctl -u pi-printer -f   # follow logs
```

---

## 6. Configuration

Edit `config.py` to change defaults:

| Variable | Default | Description |
|---|---|---|
| `ALLOWED_EXTENSIONS` | pdf, jpg, jpeg, png, txt | Accepted file types |
| `MAX_CONTENT_LENGTH` | 50 MB | Upload size cap |
| `AUTO_DELETE_AFTER_PRINT` | `False` | Delete file after successful print |
| `DEFAULT_PRINTER` | `None` | Force a specific CUPS printer name |
| `LPR_TIMEOUT` | 30 s | Kill lpr after this many seconds |

---

## 7. Troubleshooting

**`lpstat -p` returns nothing**
The printer has not been added in CUPS yet. Go to `http://<ip>:631`.

**Permission denied on `/dev/usb/lp0`**
```bash
sudo usermod -aG lp pi
# Then log out and back in, or reboot
```
Or add a udev rule:
```bash
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="XXXX", MODE="0666"' \
  | sudo tee /etc/udev/rules.d/99-printer.rules
sudo udevadm control --reload
```

**Out of memory / service crashes**
```bash
free -m      # check available RAM
# gunicorn with --workers 1 uses ~40–60 MB; make sure no other heavy processes are running
```

**Service fails to start: `cups.service` not found**
Make sure CUPS is installed and running (`sudo systemctl status cups`). The service unit lists `Requires=cups.service` — remove that line from `systemd/pi-printer.service` if you want to start without CUPS (raw USB mode only).

**PDF prints as garbage (raw mode)**
Raw `/dev/usb/lp0` mode only works for plain text. PDFs require CUPS to rasterize them. Install CUPS and add the printer.
