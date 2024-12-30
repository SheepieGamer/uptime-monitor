import time
import statistics
import threading
from datetime import datetime, timedelta
# from ping3 import ping
from typing import Dict, List, Optional
from flask import Flask, jsonify, request, render_template
from models import db, Target, PingResult
import requests
from urllib.parse import urlparse
import urllib3
import warnings

# Suppress only the specific InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ping_monitor.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

class PingMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.targets = {}

    def add_target(self, target: str):
        """Add a new target to monitor."""
        with self.lock:
            existing = Target.query.filter_by(hostname=target).first()
            if not existing:
                new_target = Target(hostname=target)
                db.session.add(new_target)
                db.session.commit()
    
    def remove_target(self, target: str):
        """Remove a target from monitoring."""
        with self.lock:
            target_obj = Target.query.filter_by(hostname=target).first()
            if target_obj:
                db.session.delete(target_obj)
                db.session.commit()
    
    def ping_target(self, target: str) -> Optional[PingResult]:
        """Ping a target and store the result."""
        try:
            target_obj = Target.query.filter_by(hostname=target).first()
            if not target_obj:
                return None

            response = None
            latency = None

            # Try HTTPS first
            try:
                start_time = time.time()
                response = requests.get(
                    f"https://{target}",
                    timeout=5,
                    allow_redirects=True,
                    verify=False
                )
                latency = (time.time() - start_time)
            except requests.exceptions.RequestException:
                # If HTTPS fails, try HTTP
                try:
                    start_time = time.time()
                    response = requests.get(
                        f"http://{target}",
                        timeout=5,
                        allow_redirects=True
                    )
                    latency = (time.time() - start_time)
                except requests.exceptions.RequestException as e:
                    # Both HTTPS and HTTP failed
                    response = None
                    latency = None
            
            if response is None:
                success = False
            else:
                # Consider these status codes as "successful"
                success_codes = list(range(200, 299)) + list(range(300, 399)) + [401, 403]
                success = response.status_code in success_codes
            
            result = PingResult(target=target_obj, success=success, latency=latency)
            db.session.add(result)
            db.session.flush()
            
            # Get the last result before this one
            last_result = PingResult.query.filter_by(
                target_id=target_obj.id
            ).order_by(PingResult.timestamp.desc()).offset(1).first()
            
            # Site is considered down if current ping failed and last ping was successful
            is_down = not success and (last_result is None or last_result.success)
            # Site is considered up if current ping succeeded and last ping failed
            is_up = success and last_result and not last_result.success
            
            if is_down:
                stats = self._get_target_stats(target)
                self.send_webhook(target_obj, 'down', stats)
            elif is_up:
                stats = self._get_target_stats(target)
                self.send_webhook(target_obj, 'up', stats)
            
            db.session.commit()
            return result
            
        except Exception as e:
            target_obj = Target.query.filter_by(hostname=target).first()
            if target_obj:
                result = PingResult(target=target_obj, success=False, latency=None)
                db.session.add(result)
                db.session.flush()
                
                last_result = PingResult.query.filter_by(
                    target_id=target_obj.id
                ).order_by(PingResult.timestamp.desc()).offset(1).first()
                
                if last_result is None or last_result.success:
                    stats = self._get_target_stats(target)
                    self.send_webhook(target_obj, 'down', stats)
                
                db.session.commit()
            return None
    
    def get_statistics(self, target: str = None, time_range: str = '1h') -> Dict:
        """Get statistics for a target or all targets."""
        with self.lock:
            if target:
                return self._get_target_stats(target, time_range)
            targets = Target.query.all()
            return {t.hostname: self._get_target_stats(t.hostname, time_range) for t in targets}
    
    def _get_target_stats(self, target: str, time_range: str = '1h') -> Dict:
        """Get statistics for a specific target."""
        target_obj = Target.query.filter_by(hostname=target).first()
        if not target_obj:
            return {}

        # Calculate time range
        end_time = datetime.utcnow()
        
        # Parse time range
        if time_range == 'lifetime':
            start_time = datetime.min
        else:
            amount = int(time_range[:-1])  # Get the number
            unit = time_range[-1]          # Get the unit (h/d/m/y)
            
            if unit == 'h':
                start_time = end_time - timedelta(hours=amount)
            elif unit == 'd':
                start_time = end_time - timedelta(days=amount)
            elif unit == 'm':
                start_time = end_time - timedelta(days=amount * 30)  # Approximate
            elif unit == 'y':
                start_time = end_time - timedelta(days=amount * 365)  # Approximate
            else:
                start_time = end_time - timedelta(hours=1)  # Default to 1 hour

        # Get ping results within time range
        recent_pings = PingResult.query.filter(
            PingResult.target_id == target_obj.id,
            PingResult.timestamp >= start_time,
            PingResult.timestamp <= end_time
        ).order_by(PingResult.timestamp.desc()).all()
        
        if not recent_pings:
            return {
                'uptime_percentage': 0,
                'avg_latency': 0,
                'min_latency': 0,
                'max_latency': 0,
                'std_dev': 0,
                'last_success': None,
                'downtime_start': None,
                'history': []
            }

        successful_pings = [p for p in recent_pings if p.success]
        latencies = [p.latency for p in successful_pings if p.latency is not None]
        
        last_ping = recent_pings[0]
        last_success = next((p.timestamp for p in recent_pings if p.success), None)
        downtime_start = None if last_ping.success else last_success

        # Create history data (reversed to be in chronological order)
        history = []
        for ping in reversed(recent_pings):
            if ping.success and ping.latency is not None:
                history.append({
                    'timestamp': ping.timestamp.isoformat(),
                    'latency': ping.latency
                })

        stats = {
            'uptime_percentage': (len(successful_pings) / len(recent_pings) * 100),
            'avg_latency': statistics.mean(latencies) if latencies else 0,
            'min_latency': min(latencies) if latencies else 0,
            'max_latency': max(latencies) if latencies else 0,
            'current_latency': last_ping.latency if last_ping.success else None,
            'last_success': last_success,
            'downtime_start': downtime_start,
            'history': history,
            'time_range': time_range
        }
        
        if len(latencies) > 1:
            stats['std_dev'] = statistics.stdev(latencies)
        else:
            stats['std_dev'] = 0
            
        return stats

    def send_webhook(self, target: Target, notification_type: str, stats: Dict = None) -> None:
        """Send webhook notification for target status change."""
        if not target.webhook_url:
            return

        # Don't send duplicate notifications of the same type
        if target.last_notification_type == notification_type and notification_type != 'test':
            return

        # Format timestamp for the message
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        message = ""

        if target.webhook_message:
            # Use custom message with replacements
            replacements = {
                '{status}': ':red_circle:' if notification_type == 'down' else ':green_circle:' if notification_type == 'up' else ':blue_circle:',
                '{hostname}': target.hostname,
                '{time}': current_time,
                '{downtime}': self._format_downtime(stats.get('downtime_start', None) if stats else None),
                '{last_success}': stats.get('last_success').strftime('%Y-%m-%d %H:%M:%S UTC') if stats and stats.get('last_success') else 'unknown'
            }
            
            message = target.webhook_message
            for key, value in replacements.items():
                message = message.replace(key, str(value))
        else:
            # Use default message format
            if notification_type == 'down':
                last_success = stats.get('last_success').strftime('%Y-%m-%d %H:%M:%S UTC') if stats and stats.get('last_success') else 'unknown'
                message = f"🔴 {target.hostname} is DOWN!\nLast successful response: {last_success}\nDetected at: {current_time}"
            elif notification_type == 'up':
                downtime = self._format_downtime(stats.get('downtime_start', None) if stats else None)
                message = f"🟢 {target.hostname} is back UP!\nTotal downtime: {downtime}\nDetected at: {current_time}"
            else:  # test
                message = f"🔵 Test notification for {target.hostname}\nWebhooks are working! You will be notified when the site goes down or comes back up."

        try:
            # Support both Discord and generic webhooks
            if 'discord.com' in target.webhook_url:
                payload = {
                    'username': 'Uptime Monitor',
                    'content': message
                }
            else:
                payload = {
                    'text': message,
                    'type': notification_type,
                    'target': target.hostname,
                    'timestamp': current_time
                }

            response = requests.post(target.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            # Update last notification type only if webhook was successful
            target.last_notification_type = notification_type
            db.session.commit()
            
        except Exception as e:
            print(f"Error sending webhook for {target.hostname}: {str(e)}")

    def _format_downtime(self, downtime_start):
        if not downtime_start:
            return "unknown"
        
        duration = datetime.utcnow() - downtime_start
        minutes = duration.total_seconds() / 60
        
        if minutes < 60:
            return f"{int(minutes)} minutes"
        elif minutes < 1440:  # 24 hours
            return f"{int(minutes / 60)} hours, {int(minutes % 60)} minutes"
        else:
            days = int(minutes / 1440)
            remaining_hours = int((minutes % 1440) / 60)
            return f"{days} days, {remaining_hours} hours"

    def cleanup_old_results(self, days_to_keep: int = 7):
        """Clean up ping results older than the specified number of days."""
        with app.app_context():
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            PingResult.query.filter(PingResult.timestamp < cutoff_date).delete()
            db.session.commit()

# Create a global PingMonitor instance
monitor = PingMonitor()

def ping_worker():
    """Background worker to continuously ping targets."""
    with app.app_context():
        while True:
            with monitor.lock:
                targets = Target.query.all()
            
            for target in targets:
                monitor.ping_target(target.hostname)
            
            time.sleep(5)  # Wait 5 seconds between ping cycles

@app.route('/')
def index():
    """Render the main monitoring page."""
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    """Get statistics for all targets."""
    time_range = request.args.get('time_range', default='1h', type=str)
    return jsonify(monitor.get_statistics(time_range=time_range))

@app.route('/api/targets', methods=['POST'])
def add_target():
    """Add a new target to monitor."""
    data = request.get_json()
    target = data.get('target')
    if target:
        monitor.add_target(target)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'No target specified'}), 400

@app.route('/api/targets/<target>', methods=['DELETE'])
def remove_target(target):
    """Remove a target from monitoring."""
    monitor.remove_target(target)
    return jsonify({'status': 'success'})

@app.route('/api/targets/<hostname>/webhook', methods=['POST'])
def set_webhook(hostname):
    """Set or update webhook URL for a target."""
    data = request.get_json()
    webhook_url = data.get('webhook_url')
    webhook_message = data.get('webhook_message')

    if not webhook_url:
        return jsonify({'error': 'Webhook URL is required'}), 400

    target = Target.query.filter_by(hostname=hostname).first()
    if not target:
        return jsonify({'error': 'Target not found'}), 404

    target.webhook_url = webhook_url
    target.webhook_message = webhook_message
    db.session.commit()

    # Send a test notification
    monitor.send_webhook(target, 'test')
    return jsonify({'message': 'Webhook set successfully'})

@app.route('/api/targets/<hostname>/webhook', methods=['DELETE'])
def remove_webhook(hostname):
    """Remove webhook URL for a target."""
    target = Target.query.filter_by(hostname=hostname).first()
    if not target:
        return jsonify({'error': 'Target not found'}), 404
        
    target.webhook_url = None
    target.webhook_message = None
    target.last_notification_type = None
    db.session.commit()
    
    return jsonify({'message': 'Webhook removed successfully'})

if __name__ == "__main__":
    # Start the background ping worker
    ping_thread = threading.Thread(target=ping_worker, daemon=True)
    ping_thread.start()
    
    # Start the cleanup worker
    cleanup_thread = threading.Thread(target=lambda: monitor.cleanup_old_results(), daemon=True)
    cleanup_thread.start()
    
    # Start the Flask server
    app.run(debug=True, host='0.0.0.0', port=5000)