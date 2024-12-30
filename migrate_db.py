from main import app, db
from models import Target, PingResult
from sqlalchemy import text
import sqlite3

def migrate_database():
    """Perform database migration."""
    # Connect to the database
    conn = sqlite3.connect('ping_monitor.db')
    cursor = conn.cursor()

    try:
        # Add webhook_url column if it doesn't exist
        cursor.execute('''
        ALTER TABLE target ADD COLUMN webhook_url TEXT;
        ''')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        # Add last_notification_type column if it doesn't exist
        cursor.execute('''
        ALTER TABLE target ADD COLUMN last_notification_type TEXT;
        ''')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        # Add webhook_message column if it doesn't exist
        cursor.execute('''
        ALTER TABLE target ADD COLUMN webhook_message TEXT;
        ''')
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()
