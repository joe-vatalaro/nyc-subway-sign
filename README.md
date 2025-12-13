# NYC Subway Sign

A Raspberry Pi-powered LED matrix display showing real-time NYC subway arrivals using the MTA API.

## Features

- Real-time subway arrival information from MTA GTFS-realtime API
- Customizable routes and stops
- HUB75 LED matrix display support
- Configurable display settings
- Automatic updates at configurable intervals

## Hardware Requirements

- Raspberry Pi 4
- MicroSD card (16GB+ recommended)
- HUB75 LED matrix panel (64x32 or compatible)
- HUB75 connector/cable
- Power supply for Raspberry Pi
- Power supply for LED matrix (5V, sufficient amperage)

## Software Setup

### 1. Install Raspberry Pi OS

Install Raspberry Pi OS (64-bit recommended) on your microSD card. Enable SSH and configure WiFi if needed.

### 2. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev python3-pil git build-essential
```

### 3. Install RGB Matrix Library

The `rpi-rgb-led-matrix` library requires compilation. Clone and build it:

```bash
cd ~
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd rpi-rgb-led-matrix
make
cd bindings/python
sudo pip3 install -e .
```

### 4. Clone and Setup Project

```bash
cd ~
git clone <your-repo-url> nyc-subway-sign
cd nyc-subway-sign
pip3 install -r requirements.txt
```

### 5. Configure MTA API Key

**Note:** An API key is only required if you're using bus routes. Subway routes work without an API key.

If you're using bus routes, get your MTA API key from https://api.mta.info/

Create a `.env` file in the project root:

```bash
cp env.template .env
nano .env
```

Add your API key (only needed for bus routes):
```
MTA_API_KEY=your_actual_api_key_here
UPDATE_INTERVAL=30
```

If you're only using subway routes, you can leave `MTA_API_KEY` empty or omit it entirely.

### 6. Configure Routes

Edit `config/routes.json` to specify which routes and stops you want to monitor. You can mix subway and bus routes:

```json
{
  "routes": [
    {
      "route_id": "6",
      "stop_id": "623S",
      "direction": "1",
      "display_name": "6 ↓ Downtown",
      "type": "subway"
    },
    {
      "route_id": "M14A-SBS",
      "stop_id": "401657",
      "direction": "0",
      "display_name": "M14A ↑ North",
      "type": "bus"
    }
  ]
}
```

**Configuration Fields:**
- `route_id`: The route identifier (e.g., "1", "A", "M1", "B44")
- `stop_id`: The stop identifier (different format for subway vs bus)
- `direction`: "0" = Northbound/Upbound, "1" = Southbound/Downbound (optional for buses)
- `display_name`: What to show on the display (defaults to route_id)
- `type`: Either "subway" or "bus" (defaults to "subway" if not specified)

**Subway Routes:**
- Route IDs: Single letter/number like "1", "2", "3", "A", "B", "C", etc.
- "SIR" for Staten Island Railway
- Stop IDs: Typically follow patterns like "101N" (northbound) or "101S" (southbound)
- Use MTA GTFS static data or online tools to find subway stop IDs

**Bus Routes:**
- Route IDs: Include prefix letter (e.g., "M1", "B44", "Q58", "S79")
- Stop IDs: Numeric identifiers (e.g., "200001", "400123")
- Finding bus stop IDs:
  - Use the MTA Bus Time API or GTFS static data
  - Online tools like https://bustime.mta.info/ can help identify stops
  - Bus stop IDs are typically 6-digit numbers
  - Direction is optional for buses but can help filter results

### 7. Configure Display Settings

Edit `config/display_config.json` to match your LED matrix specifications:

- `matrix_width` / `matrix_height`: Your panel dimensions
- `chain_length`: Number of panels chained horizontally
- `parallel`: Number of parallel chains
- `brightness`: 0-100
- `gpio_slowdown`: May need to increase if you see flickering

### 8. Run the Application

You can run the application in two ways:

**Option 1: Using the run script**
```bash
cd ~/nyc-subway-sign
sudo ./run.sh
```

**Option 2: Direct Python execution**
```bash
cd ~/nyc-subway-sign
sudo python3 src/main.py
```

**Note:** `sudo` is required for GPIO access on Raspberry Pi.

### 9. Auto-start on Boot (Optional)

Create a systemd service to run the sign automatically:

```bash
sudo nano /etc/systemd/system/subway-sign.service
```

Add:
```ini
[Unit]
Description=NYC Subway Sign
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/nyc-subway-sign
ExecStart=/usr/bin/sudo /usr/bin/python3 /home/pi/nyc-subway-sign/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable subway-sign.service
sudo systemctl start subway-sign.service
```

## Project Structure

```
nyc-subway-sign/
├── src/
│   ├── __init__.py
│   ├── main.py          # Main application entry point
│   ├── config.py        # Configuration management
│   ├── mta_api.py       # MTA API client
│   └── display.py       # LED matrix display handler
├── config/
│   ├── routes.json      # Route and stop configuration
│   └── display_config.json  # Display hardware settings
├── requirements.txt     # Python dependencies
├── env.template         # Environment variables template
├── run.sh              # Convenience run script
└── README.md           # This file
```

## Troubleshooting

### Display Issues
- If the display doesn't work, check `gpio_slowdown` in `display_config.json` (try 2-4)
- Ensure proper power supply for the LED matrix
- Verify HUB75 connections

### API Issues
- Verify your MTA API key is correct
- Check internet connectivity: `ping api-endpoint.mta.info`
- Ensure stop IDs and route IDs are correct

### Permission Issues
- The application must run with `sudo` for GPIO access
- If using systemd, ensure proper user permissions

## License

Personal project - use as you wish!
