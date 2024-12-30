from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Target(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(256), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    webhook_url = db.Column(db.String(512))
    webhook_message = db.Column(db.String(512))  # Custom message template
    last_notification_type = db.Column(db.String(50))
    pings = db.relationship('PingResult', backref='target', lazy=True, cascade='all, delete-orphan')

class PingResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_id = db.Column(db.Integer, db.ForeignKey('target.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    latency = db.Column(db.Float, nullable=True)  # Null means ping failed
    success = db.Column(db.Boolean, nullable=False)
