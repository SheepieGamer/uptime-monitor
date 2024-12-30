# Website Uptime Monitor

A Flask-based web application that monitors website uptime and sends notifications through webhooks when sites go down or come back up.

## Features

- **Real-time Monitoring**: Checks website status every 5 seconds
- **HTTP/HTTPS Support**: Automatically tries HTTPS first, falls back to HTTP
- **Detailed Statistics**:
  - Uptime percentage
  - Response latency
  - Historical data
  - Downtime tracking
- **Webhook Notifications**:
  - Discord webhook support
  - Custom webhook endpoints
  - Customizable notification messages
  - Status change alerts (down/up)
  - Test notifications

## Installation

1. Clone the repository:
```bash
git clone https://github.com/SheepieGamer/uptime-monitor/
cd ping
```

2. Create a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python migrate_db.py
```

5. Run the application:
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## Usage

### Adding Sites to Monitor
1. Enter the hostname in the input field (e.g., "example.com")
2. Click "Add Target"

### Setting Up Notifications
1. Click "Show Detailed Statistics" for a target
2. Enter your webhook URL (Discord or custom endpoint)
3. (Optional) Add a custom notification message using placeholders:
   - `{status}` - Status emoji (:red_circle:, :green_circle:, :blue_circle:)
   - `{hostname}` - Website hostname
   - `{time}` - Current time
   - `{downtime}` - Duration of downtime (for up notifications)
   - `{last_success}` - Last successful response time (for down notifications)
4. Click "Save" to enable notifications

### Example Custom Message
```
{status} Status Change for {hostname}
Current Status: {status == :red_circle: ? "DOWN" : "UP"}
Detected at: {time}
{status == :red_circle: ? "Last successful response: " + last_success : "Total downtime: " + downtime}
```

## Dependencies

- Flask 2.0.1
- SQLAlchemy 1.4.23
- Flask-SQLAlchemy 2.5.1
- Requests 2.31.0
- Python-dotenv 0.19.0

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
