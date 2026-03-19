# Pi Print Server

A lightweight web print server for Raspberry Pi. Upload files from any browser on your local network and print them to a USB-connected printer.

**Supported file types:** PDF, JPG, PNG, TXT (max 50 MB)

---

## Hardware requirements

- Raspberry Pi 1 Model B or B+ (ARMv6, 256–512 MB RAM) or newer (Pi 4 recommended for faster image conversion)
- Raspberry Pi OS Lite (32-bit, Bullseye or later)
- USB printer
- WiFi adapter (or Ethernet) — static IP recommended

---

## Quick install

```bash
git clone <your-repo-url> /opt/pi_printer
cd /opt/pi_printer
sudo bash install.sh
```

The script handles static IP, CUPS, Python venv, and the systemd service automatically.

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

## 2. Install CUPS and drivers

```bash
sudo apt-get update
sudo apt-get install -y cups cups-bsd printer-driver-splix printer-driver-foo2zjs img2pdf

# Allow your user to manage printers (replace 'admin' with your username)
sudo usermod -aG lp admin
sudo usermod -aG lpadmin admin

# Allow CUPS admin access from the local network
sudo cupsctl --remote-any

sudo systemctl enable cups
sudo systemctl start cups
```

Add your printer via the CUPS web interface:
```
http://<pi-ip>:631
```
Go to **Administration → Add Printer** and follow the wizard.

### Xerox Phaser 3020 (and similar Samsung-based printers)

The Phaser 3020 is not in the CUPS driver list. Use the Samsung ML-2160 driver:

```bash
lpadmin -p XeroxPhaser3020 -E \
  -v "usb://Xerox/Phaser%203020?serial=<your-serial>" \
  -m drv:///splix-samsung.drv/ml2160.ppd
lpoptions -d XeroxPhaser3020
```

Find your serial with:
```bash
lpinfo -v | grep -i xerox
```

After adding, verify with:
```bash
lpstat -p
```

---

## 3. Install the app

```bash
git clone <your-repo-url> /opt/pi_printer
cd /opt/pi_printer

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Run manually (for testing)

```bash
cd /opt/pi_printer
sudo python app.py
```

Open `http://<pi-ip>:1200` in a browser.

> Run with `sudo` so CUPS can access the USB printer device.

---

## 5. Run as a systemd service (auto-start on boot)

```bash
sudo mkdir -p /var/log/pi-printer
sudo chown admin:admin /var/log/pi-printer

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

> Make sure `User=` and `Group=` in the service file match your username (default: `admin`), and that `WorkingDirectory=` and `ExecStart=` point to `/opt/pi_printer`.

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
The printer has not been added in CUPS yet. Go to `http://<pi-ip>:631`.

**Printer prints an "Exception Report" page instead of the file**
The driver is receiving a format it can't process. Make sure `img2pdf` is installed (`sudo apt install img2pdf`) — the app uses it to convert JPG/PNG to PDF before printing.

**`Backend usb returned status 1 (failed)`**
USB communication failed. Try:
```bash
sudo rmmod usblp && sudo modprobe usblp
sudo systemctl restart cups
```
If it persists, power cycle the printer.

**Permission denied on `/opt/pi_printer/uploads`**
```bash
sudo chown -R admin:admin /opt/pi_printer/uploads
```

**Permission denied on `/dev/usb/lp0`**
```bash
sudo usermod -aG lp admin
# Then log out and back in, or reboot
```

**Service fails with `status=217/USER`**
The user in the service file doesn't exist. Edit `/etc/systemd/system/pi-printer.service` and set `User=` and `Group=` to your actual username, then:
```bash
sudo systemctl daemon-reload && sudo systemctl restart pi-printer
```

**Service fails to start: `cups.service` not found**
Make sure CUPS is installed and running (`sudo systemctl status cups`).

**Migrating to a new Pi**
```bash
# Copy project from old Pi
scp -r /opt/pi_printer admin@<new-pi-ip>:/opt/pi_printer

# On new Pi — re-run install and re-add the printer
cd /opt/pi_printer
sudo bash install.sh
```
