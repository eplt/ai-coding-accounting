"""
Migration script to convert existing UTC datetimes to local timezone.
Run this once if you have existing data that was stored in UTC.

Usage: python migrate_timezones.py
"""
from app import app, db, UsageEvent, CodingSession
from datetime import datetime, timezone

def to_local_timezone(dt: datetime) -> datetime:
    """Convert datetime to local timezone (naive)"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    # If naive, assume it's UTC (old data) and convert to local
    # This is a heuristic - we can't be 100% sure
    utc_dt = dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone().replace(tzinfo=None)

def migrate_timezones():
    """Convert all UTC datetimes to local timezone"""
    with app.app_context():
        # Migrate UsageEvent dates
        events = UsageEvent.query.all()
        print(f"Migrating {len(events)} events...")
        for event in events:
            if event.date:
                # Check if it looks like UTC (early morning times suggest UTC)
                # This is a heuristic - adjust based on your timezone
                local_date = to_local_timezone(event.date)
                event.date = local_date
        
        # Migrate CodingSession times
        sessions = CodingSession.query.all()
        print(f"Migrating {len(sessions)} sessions...")
        for session in sessions:
            if session.start_time:
                session.start_time = to_local_timezone(session.start_time)
            if session.end_time:
                session.end_time = to_local_timezone(session.end_time)
        
        db.session.commit()
        print("Migration complete!")

if __name__ == '__main__':
    migrate_timezones()
