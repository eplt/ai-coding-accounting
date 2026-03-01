"""
Flask app for AI Coding Usage Tracker.
Serves the dashboard, CSV upload, project/session APIs, and settings.
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import csv
import glob
import io
import json
import os
import sys
from werkzeug.utils import secure_filename
from project_detector import ProjectDetector
import config

# Frozen (PyInstaller .app): bundle paths for templates and uploads
_frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
if _frozen:
    _template_folder = os.path.join(sys._MEIPASS, 'templates')
    _upload_folder = os.path.expanduser('~/Library/Application Support/AI Coding Accounting/uploads')
    os.makedirs(_upload_folder, exist_ok=True)
    app = Flask(__name__, template_folder=_template_folder)
    app.config['UPLOAD_FOLDER'] = _upload_folder
else:
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = 'uploads'

# DB path is resolved at app init (launch sets AI_CODING_DB_PATH from config file before importing app)
_db_path = config.get_database_path()
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_db_path}'  # absolute path: sqlite:////path
config._config_debug_log(f"App using database: {_db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize project detector with configured path
# This will be updated when user selects a folder via UI
project_detector = ProjectDetector(base_path=config.SCM_PATH)
current_scm_path = config.SCM_PATH

# Database Models
class UsageEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    user = db.Column(db.String(255), nullable=True)  # Optional in CSV (Cursor exports with or without User)
    kind = db.Column(db.String(100))
    model = db.Column(db.String(100))
    max_mode = db.Column(db.String(50))
    input_with_cache = db.Column(db.Integer, default=0)
    input_without_cache = db.Column(db.Integer, default=0)
    cache_read = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)
    
    # Relationships
    session_id = db.Column(db.Integer, db.ForeignKey('coding_session.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    
    # Unique identifier for deduplication
    unique_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CodingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    total_cost = db.Column(db.Float, default=0.0)
    total_tokens = db.Column(db.Integer, default=0)
    event_count = db.Column(db.Integer, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    events = db.relationship('UsageEvent', backref='session', lazy=True)
    project = db.relationship('Project', backref='sessions')

class ProjectGroup(db.Model):
    """Optional grouping of projects (e.g. Work, Product X)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    projects = db.relationship('Project', backref='group', lazy=True, foreign_keys='Project.group_id')


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('project_group.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    events = db.relationship('UsageEvent', backref='project', lazy=True)


class AppSettings(db.Model):
    """Key-value store for app settings (session gap, SCM path, etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImportBatch(db.Model):
    """Record of each CSV file import (upload or from Downloads)."""
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(1024), nullable=True)
    file_name = db.Column(db.String(512), nullable=False)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)
    new_events_count = db.Column(db.Integer, default=0)
    duplicate_count = db.Column(db.Integer, default=0)
    sessions_created = db.Column(db.Integer, default=0)
    # Relationships
    archive_rows = db.relationship('EventArchive', backref='batch', lazy=True, cascade='all, delete-orphan')


class EventArchive(db.Model):
    """Raw CSV row per line for audit/reprocess. One row per imported line."""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('import_batch.id'), nullable=False)
    line_index = db.Column(db.Integer, nullable=False)
    raw_line = db.Column(db.Text, nullable=True)
    raw_json = db.Column(db.Text, nullable=True)

    __table_args__ = (db.Index('ix_event_archive_batch_line', 'batch_id', 'line_index'),)


# App Version and Database Migrations
APP_VERSION = "1.3.0"  # Bump this when adding new migrations


class DatabaseMigration(db.Model):
    """Track which database migrations have been applied."""
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False, unique=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)


def get_setting(key: str, default: str = None) -> str:
    """Get a setting value from AppSettings. Returns default if not set."""
    row = AppSettings.query.filter_by(key=key).first()
    return row.value if row is not None else default


def set_setting(key: str, value: str) -> None:
    """Set a setting value. Creates or updates."""
    row = AppSettings.query.filter_by(key=key).first()
    if row is None:
        row = AppSettings(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    db.session.commit()


def _seed_default_settings():
    """Ensure default settings exist (run once after create_all)."""
    defaults = {
        'session_gap_hours': '2',
        'downloads_lookback_hours': '24',
    }
    for k, v in defaults.items():
        if AppSettings.query.filter_by(key=k).first() is None:
            db.session.add(AppSettings(key=k, value=v))
    db.session.commit()


def _run_database_migrations():
    """Run pending database migrations on startup.
    
    Migrations are versioned and only run once. Add new migrations to the
    MIGRATIONS dict with version as key and function as value.
    """
    try:
        # Create migration table if it doesn't exist
        db.create_all()
        
        # Get list of already applied migrations
        applied = {m.version for m in DatabaseMigration.query.all()}
        
        # Define migrations: version -> (function, description)
        MIGRATIONS = {
            "1.1.0": (_migrate_1_1_0_recalc_hashes, "Recalculate unique_hash for existing UsageEvent records"),
        }
        
        # Run pending migrations in version order
        for version in sorted(MIGRATIONS.keys()):
            if version not in applied:
                migrate_func, description = MIGRATIONS[version]
                print(f"Running database migration: {version} - {description}")
                migrate_func()
                # Record migration
                db.session.add(DatabaseMigration(version=version, description=description))
                db.session.commit()
                print(f"Migration {version} completed successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Database migration failed: {e}")
        raise


def _migrate_1_1_0_recalc_hashes():
    """Migration 1.1.0: Recalculate unique_hash for all existing UsageEvent records.

    The old hash included User and Model fields, causing duplicates when importing
    CSVs without the User column. The new hash uses only timestamp and token counts.

    This migration recalculates hashes for all existing events based on their
    current token data. Events with the same timestamp+tokens will be detected
    as duplicates and removed.
    """
    from sqlalchemy import text

    events = UsageEvent.query.all()
    updated = 0
    duplicates_removed = 0
    seen_hashes = {}

    for event in events:
        # Build new hash from event data (reconstruct what CSV row would look like)
        new_hash = _calculate_hash_from_event(event)

        # Check for duplicates (same hash = same event)
        if new_hash in seen_hashes:
            # This event is a duplicate of an existing one - delete it
            db.session.delete(event)
            duplicates_removed += 1
        else:
            # Update hash
            event.unique_hash = new_hash
            seen_hashes[new_hash] = event.id
            updated += 1

    db.session.commit()
    print(f"  Recalculated hashes: {updated} events updated, {duplicates_removed} duplicates removed")
    
    # Also clean up any orphaned sessions (sessions with no events)
    orphaned_sessions = CodingSession.query.outerjoin(UsageEvent).filter(
        UsageEvent.id.is_(None)
    ).all()
    for session in orphaned_sessions:
        db.session.delete(session)
    db.session.commit()
    print(f"  Cleaned up {len(orphaned_sessions)} orphaned sessions")


def _calculate_hash_from_event(event):
    """Calculate new-format hash from a UsageEvent record.
    
    Reconstructs the same hash that would be generated from a CSV row
    with the same timestamp and token values. Normalizes datetime to
    naive local time to match CSV import behavior.
    """
    import hashlib
    # Normalize datetime to naive local time (matches to_local_timezone behavior)
    dt = event.date
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    # Match the format in create_unique_hash()
    key = f"{dt.isoformat()}_{event.input_with_cache}_{event.cache_read}_{event.output_tokens}_{event.total_tokens}"
    return hashlib.sha256(key.encode()).hexdigest()


def _user_from_row(row):
    """User column is optional in Cursor CSV; use '' or 'n/a' when missing."""
    return (row.get('User') or '').strip() or 'n/a'


def _process_csv_rows(rows, file_name, file_path=None, gap_hours=None):
    """Create batch, archive rows, dedupe, create events and sessions. Returns (batch, new_count, dup_count, sessions_created)."""
    if gap_hours is None:
        gap_hours = int(get_setting('session_gap_hours') or '2')
    batch = ImportBatch(file_name=file_name, file_path=file_path, new_events_count=0, duplicate_count=0, sessions_created=0)
    db.session.add(batch)
    db.session.flush()
    new_events = []
    duplicate_count = 0
    for line_index, row in enumerate(rows):
        db.session.add(EventArchive(batch_id=batch.id, line_index=line_index, raw_json=json.dumps(row)))
        unique_hash = create_unique_hash(row)
        if UsageEvent.query.filter_by(unique_hash=unique_hash).first():
            duplicate_count += 1
            continue
        try:
            parsed_date = parse_date(row['Date'])
            local_date = to_local_timezone(parsed_date)
            event = UsageEvent(
                date=local_date,
                user=_user_from_row(row),
                kind=row.get('Kind', ''),
                model=row.get('Model', ''),
                max_mode=row.get('Max Mode', ''),
                input_with_cache=int(row.get('Input (w/ Cache Write)', 0) or 0),
                input_without_cache=int(row.get('Input (w/o Cache Write)', 0) or 0),
                cache_read=int(row.get('Cache Read', 0) or 0),
                output_tokens=int(row.get('Output Tokens', 0) or 0),
                total_tokens=int(row.get('Total Tokens', 0) or 0),
                cost=float(row.get('Cost', 0) or 0),
                unique_hash=unique_hash
            )
            new_events.append(event)
        except Exception:
            continue
    batch.new_events_count = len(new_events)
    batch.duplicate_count = duplicate_count
    db.session.add_all(new_events)
    db.session.commit()
    all_events = UsageEvent.query.filter_by(session_id=None).order_by(UsageEvent.date).all()
    sessions = detect_sessions(all_events, gap_hours)
    created_sessions = 0
    for session_events in sessions:
        if not session_events:
            continue
        session = CodingSession(
            start_time=min(e.date for e in session_events),
            end_time=max(e.date for e in session_events),
            total_cost=sum(e.cost for e in session_events),
            total_tokens=sum(e.total_tokens for e in session_events),
            event_count=len(session_events)
        )
        db.session.add(session)
        db.session.flush()
        for event in session_events:
            event.session_id = session.id
        created_sessions += 1
    batch.sessions_created = created_sessions
    db.session.commit()
    return batch, len(new_events), duplicate_count, created_sessions


def create_unique_hash(row):
    """Create a unique hash for deduplication based on timestamp and token counts.
    
    The hash is based on:
    - Date/timestamp (the unique identifier for when the event occurred)
    - Input tokens (with cache write)
    - Cache read tokens
    - Output tokens
    - Total tokens
    
    This ensures that events with the same timestamp and token counts are considered
    duplicates, regardless of whether the CSV includes a User column or which model was used.
    """
    import hashlib
    key = f"{row.get('Date','')}_{row.get('Input (w/ Cache Write)', '0')}_{row.get('Cache Read', '0')}_{row.get('Output Tokens', '0')}_{row.get('Total Tokens', '0')}"
    return hashlib.sha256(key.encode()).hexdigest()

def parse_date(date_str):
    """Parse ISO format date string"""
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')

def to_local_timezone(dt: datetime) -> datetime:
    """
    Convert a datetime to local timezone (naive).
    If datetime is timezone-aware, convert to local timezone and make naive.
    If datetime is naive, assume it's already in local timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        # Convert to local timezone and make naive
        return dt.astimezone().replace(tzinfo=None)
    # If already naive, return as-is (assume it's already in local timezone)
    return dt

def format_datetime_local(dt: datetime) -> str:
    """
    Format datetime in local timezone as ISO string (without timezone info).
    Handles both new data (already in local timezone) and old data (might be UTC).
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        # If it's a string, try to parse it
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    
    # If datetime is timezone-aware, convert to local timezone
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    
    # Now dt is naive and should be in local timezone (for new data)
    # For old data that was stored as UTC naive, we can't distinguish it
    # So we assume all naive datetimes are in local timezone
    return dt.isoformat()

def detect_sessions(events, gap_hours=2):
    """Group events into coding sessions based on time gaps"""
    if not events:
        return []
    
    # Sort events by date
    sorted_events = sorted(events, key=lambda e: e.date)
    sessions = []
    current_session_events = [sorted_events[0]]
    
    for i in range(1, len(sorted_events)):
        time_gap = sorted_events[i].date - sorted_events[i-1].date
        
        # If gap is more than gap_hours, start a new session
        if time_gap > timedelta(hours=gap_hours):
            # Save current session
            if current_session_events:
                sessions.append(current_session_events)
            # Start new session
            current_session_events = [sorted_events[i]]
        else:
            current_session_events.append(sorted_events[i])
    
    # Add the last session
    if current_session_events:
        sessions.append(current_session_events)
    
    return sessions

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    """Handle CSV file upload and process it"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        rows = list(csv.DictReader(stream))
        if not rows:
            return jsonify({'error': 'CSV has no data rows'}), 400
        gap_hours = request.form.get('gap_hours', type=int) or int(get_setting('session_gap_hours') or '2')
        batch, new_count, dup_count, sessions_created = _process_csv_rows(rows, file.filename, file_path=None, gap_hours=gap_hours)
        return jsonify({
            'success': True,
            'new_events': new_count,
            'duplicates': dup_count,
            'sessions_created': sessions_created,
            'batch_id': batch.id,
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/import-from-downloads', methods=['POST'])
def import_from_downloads():
    """Scan ~/Downloads for usage-events-*.csv and team-usage-events-*.csv, import files from last N hours."""
    try:
        raw = (request.json or {}).get('lookback_hours') if request.is_json else None
        lookback_hours = int(raw) if raw is not None else int(get_setting('downloads_lookback_hours') or '24')
        downloads = os.path.expanduser('~/Downloads')
        if not os.path.isdir(downloads):
            return jsonify({'error': 'Downloads folder not found', 'batches': []}), 400
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (lookback_hours * 3600)
        patterns = [
            os.path.join(downloads, 'usage-events-*.csv'),
            os.path.join(downloads, 'team-usage-events-*.csv'),
        ]
        paths = []
        for p in patterns:
            paths.extend(glob.glob(p))
        paths = [p for p in paths if os.path.getmtime(p) >= cutoff]
        paths.sort(key=os.path.getmtime, reverse=True)
        gap_hours = int(get_setting('session_gap_hours') or '2')
        results = []
        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    rows = list(csv.DictReader(f))
                if not rows:
                    results.append({'file': os.path.basename(path), 'error': 'No data rows'})
                    continue
                batch, new_count, dup_count, sessions_created = _process_csv_rows(rows, os.path.basename(path), file_path=path, gap_hours=gap_hours)
                results.append({
                    'file': os.path.basename(path),
                    'batch_id': batch.id,
                    'new_events': new_count,
                    'duplicates': dup_count,
                    'sessions_created': sessions_created,
                })
            except Exception as e:
                results.append({'file': os.path.basename(path), 'error': str(e)})
        return jsonify({'success': True, 'lookback_hours': lookback_hours, 'batches': results})
    except Exception as e:
        return jsonify({'error': str(e), 'batches': []}), 500


@app.route('/api/import-batches', methods=['GET'])
def get_import_batches():
    """List recent import batches for audit/history."""
    limit = request.args.get('limit', 50, type=int)
    batches = ImportBatch.query.order_by(ImportBatch.imported_at.desc()).limit(limit).all()
    return jsonify([{
        'id': b.id,
        'file_name': b.file_name,
        'file_path': b.file_path,
        'imported_at': format_datetime_local(b.imported_at),
        'new_events_count': b.new_events_count,
        'duplicate_count': b.duplicate_count,
        'sessions_created': b.sessions_created,
    } for b in batches])


@app.route('/api/import-batches/<int:batch_id>', methods=['DELETE'])
def delete_import_batch(batch_id):
    """Delete an import batch and all events that were created from it.

    This allows re-importing a CSV file if it was imported with incorrect settings
    or if you want to re-run session detection with different parameters.
    
    Events are matched by their data (date + token counts) rather than hash to
    handle cases where the hash format has changed between versions.
    """
    batch = ImportBatch.query.get(batch_id)
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404

    events_deleted = 0
    sessions_to_delete = set()

    # Get all archive rows for this batch
    archive_rows = EventArchive.query.filter_by(batch_id=batch_id).all()

    # For each archive row, find matching events by data (not hash)
    for archive_row in archive_rows:
        try:
            row_data = json.loads(archive_row.raw_json) if archive_row.raw_json else {}
            if not row_data or 'Date' not in row_data:
                continue
            
            # Parse the date from CSV row
            from datetime import datetime
            date_str = row_data.get('Date', '')
            try:
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                # Convert to local timezone (naive) to match how events are stored
                if parsed_date.tzinfo:
                    parsed_date = parsed_date.astimezone().replace(tzinfo=None)
            except Exception:
                continue
            
            # Get token values from row
            input_cache = int(row_data.get('Input (w/ Cache Write)', 0) or 0)
            cache_read = int(row_data.get('Cache Read', 0) or 0)
            output_tokens = int(row_data.get('Output Tokens', 0) or 0)
            total_tokens = int(row_data.get('Total Tokens', 0) or 0)
            
            # Find ALL matching events by date and token counts (this catches duplicates)
            matching_events = UsageEvent.query.filter(
                UsageEvent.date == parsed_date,
                UsageEvent.input_with_cache == input_cache,
                UsageEvent.cache_read == cache_read,
                UsageEvent.output_tokens == output_tokens,
                UsageEvent.total_tokens == total_tokens
            ).all()
            
            for event in matching_events:
                if event.session_id:
                    sessions_to_delete.add(event.session_id)
                db.session.delete(event)
                events_deleted += 1
                
        except Exception as e:
            app.logger.error(f'Error processing archive row: {e}')
            continue

    # Delete sessions that were associated with deleted events
    sessions_deleted = 0
    for session_id in sessions_to_delete:
        session = CodingSession.query.get(session_id)
        if session:
            db.session.delete(session)
            sessions_deleted += 1

    # Delete the batch (archive rows cascade delete via foreign key)
    db.session.delete(batch)
    db.session.commit()

    return jsonify({
        'success': True,
        'events_deleted': events_deleted,
        'sessions_deleted': sessions_deleted,
        'batch_id': batch_id,
    })


@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects with optional group info"""
    projects = Project.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'group_id': p.group_id,
        'group_name': p.group.name if p.group else None,
        'created_at': format_datetime_local(p.created_at)
    } for p in projects])

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    data = request.json or {}
    project = Project(
        name=data.get('name', '').strip(),
        description=data.get('description', '') or '',
        group_id=data.get('group_id') or None
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({'id': project.id, 'name': project.name, 'group_id': project.group_id}), 201

@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get a single project"""
    project = Project.query.get_or_404(project_id)
    return jsonify({
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'group_id': project.group_id,
        'group_name': project.group.name if project.group else None,
        'created_at': format_datetime_local(project.created_at)
    })

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project"""
    project = Project.query.get_or_404(project_id)
    data = request.json or {}
    if 'name' in data:
        project.name = data['name']
    if 'description' in data:
        project.description = data['description']
    if 'group_id' in data:
        project.group_id = data['group_id'] if data['group_id'] else None
    db.session.commit()
    return jsonify({'id': project.id, 'name': project.name, 'group_id': project.group_id})

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and unassign all sessions"""
    project = Project.query.get_or_404(project_id)
    
    # Unassign all sessions from this project
    sessions = CodingSession.query.filter_by(project_id=project_id).all()
    for session in sessions:
        session.project_id = None
        for event in session.events:
            event.project_id = None
    
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/project-groups', methods=['GET'])
def get_project_groups():
    """List all project groups (with project count)."""
    groups = ProjectGroup.query.order_by(ProjectGroup.sort_order, ProjectGroup.name).all()
    return jsonify([{
        'id': g.id,
        'name': g.name,
        'description': g.description or '',
        'sort_order': g.sort_order or 0,
        'project_count': len(g.projects),
    } for g in groups])


@app.route('/api/project-groups', methods=['POST'])
def create_project_group():
    """Create a new project group."""
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Group name is required'}), 400
    group = ProjectGroup(
        name=name,
        description=(data.get('description') or '').strip(),
        sort_order=data.get('sort_order', 0)
    )
    db.session.add(group)
    db.session.commit()
    return jsonify({'id': group.id, 'name': group.name, 'description': group.description or '', 'sort_order': group.sort_order}), 201


@app.route('/api/project-groups/<int:group_id>', methods=['GET'])
def get_project_group(group_id):
    """Get a single group with its project ids."""
    group = ProjectGroup.query.get_or_404(group_id)
    return jsonify({
        'id': group.id,
        'name': group.name,
        'description': group.description or '',
        'sort_order': group.sort_order or 0,
        'project_ids': [p.id for p in group.projects],
    })


@app.route('/api/project-groups/<int:group_id>', methods=['PUT'])
def update_project_group(group_id):
    """Update a project group."""
    group = ProjectGroup.query.get_or_404(group_id)
    data = request.json or {}
    if 'name' in data:
        group.name = (str(data['name']) or '').strip() or group.name
    if 'description' in data:
        group.description = data['description']
    if 'sort_order' in data:
        group.sort_order = data['sort_order']
    db.session.commit()
    return jsonify({'id': group.id, 'name': group.name, 'description': group.description or '', 'sort_order': group.sort_order})


@app.route('/api/project-groups/<int:group_id>', methods=['DELETE'])
def delete_project_group(group_id):
    """Delete a group; projects in it become ungrouped (group_id set to null)."""
    group = ProjectGroup.query.get_or_404(group_id)
    for p in group.projects:
        p.group_id = None
    db.session.delete(group)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all coding sessions with optional filters"""
    project_id = request.args.get('project_id', type=int)
    group_id = request.args.get('group_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = CodingSession.query
    
    if group_id and not project_id:
        group = ProjectGroup.query.get(group_id)
        if group:
            ids = [p.id for p in group.projects]
            if ids:
                query = query.filter(CodingSession.project_id.in_(ids))
    elif project_id:
        query = query.filter_by(project_id=project_id)
    
    if start_date:
        query = query.filter(CodingSession.start_time >= datetime.fromisoformat(start_date))
    
    if end_date:
        query = query.filter(CodingSession.end_time <= datetime.fromisoformat(end_date))
    
    sessions = query.order_by(CodingSession.start_time.desc()).all()
    
    result = []
    for s in sessions:
        # Get unique models used in this session
        models = list(set([e.model for e in s.events if e.model]))
        models_str = ', '.join(models) if models else 'N/A'
        
        result.append({
            'id': s.id,
            'start_time': format_datetime_local(s.start_time),
            'end_time': format_datetime_local(s.end_time),
            'duration_hours': (s.end_time - s.start_time).total_seconds() / 3600,
            'total_cost': s.total_cost,
            'total_tokens': s.total_tokens,
            'event_count': s.event_count,
            'project_id': s.project_id,
            'project_name': s.project.name if s.project else None,
            'models': models_str,
            'model_list': models
        })
    
    return jsonify(result)

@app.route('/api/sessions/<int:session_id>/assign', methods=['POST'])
def assign_session_to_project(session_id):
    """Assign a session to a project"""
    session = CodingSession.query.get_or_404(session_id)
    data = request.json
    project_id = data.get('project_id')
    
    if project_id:
        project = Project.query.get_or_404(project_id)
        session.project_id = project_id
        # Also assign all events in the session
        for event in session.events:
            event.project_id = project_id
    else:
        session.project_id = None
        for event in session.events:
            event.project_id = None
    
    db.session.commit()
    return jsonify({'success': True})


@app.route('/api/sessions/<int:session_id>/events', methods=['GET'])
def get_session_events(session_id):
    """Get all events for a session (for detail drill-down)."""
    session = CodingSession.query.get_or_404(session_id)
    events = session.events
    projects = Project.query.all()
    return jsonify({
        'session_id': session_id,
        'start_time': format_datetime_local(session.start_time),
        'end_time': format_datetime_local(session.end_time),
        'events': [{
            'id': e.id,
            'date': format_datetime_local(e.date),
            'user': e.user or '',
            'model': e.model,
            'cost': e.cost,
            'total_tokens': e.total_tokens,
            'project_id': e.project_id,
        } for e in events],
        'projects': [{'id': p.id, 'name': p.name} for p in projects],
    })


@app.route('/api/events/<int:event_id>', methods=['PATCH'])
def update_event(event_id):
    """Update an event's project_id or session_id (unlink from session)."""
    event = UsageEvent.query.get_or_404(event_id)
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    data = request.json or {}
    if 'project_id' in data:
        event.project_id = data['project_id'] if data['project_id'] else None
    old_session_id = event.session_id
    if 'session_id' in data:
        event.session_id = data['session_id'] if data['session_id'] else None
    db.session.commit()
    # If event was unlinked from a session, recompute that session's aggregates (or delete if empty)
    if old_session_id and event.session_id is None:
        session = CodingSession.query.get(old_session_id)
        if session:
            remaining = list(session.events)  # excludes the event we just unlinked
            if not remaining:
                db.session.delete(session)
            else:
                session.start_time = min(e.date for e in remaining)
                session.end_time = max(e.date for e in remaining)
                session.total_cost = sum(e.cost for e in remaining)
                session.total_tokens = sum(e.total_tokens for e in remaining)
                session.event_count = len(remaining)
            db.session.commit()
    return jsonify({'success': True})


@app.route('/api/sessions/redetect', methods=['POST'])
def redetect_sessions():
    """Unlink all events from sessions, then re-run session detection with current gap setting."""
    gap_hours = int(get_setting('session_gap_hours') or '2')
    # Unlink all events from sessions
    UsageEvent.query.update({UsageEvent.session_id: None})
    # Delete existing sessions
    CodingSession.query.delete()
    db.session.commit()
    # Re-detect
    all_events = UsageEvent.query.order_by(UsageEvent.date).all()
    sessions = detect_sessions(all_events, gap_hours)
    created = 0
    for session_events in sessions:
        if not session_events:
            continue
        session = CodingSession(
            start_time=min(e.date for e in session_events),
            end_time=max(e.date for e in session_events),
            total_cost=sum(e.cost for e in session_events),
            total_tokens=sum(e.total_tokens for e in session_events),
            event_count=len(session_events)
        )
        db.session.add(session)
        db.session.flush()
        for event in session_events:
            event.session_id = session.id
        created += 1
    db.session.commit()
    return jsonify({'success': True, 'sessions_created': created})


@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Overall stats
        total_events = UsageEvent.query.count()
        total_cost = db.session.query(db.func.sum(UsageEvent.cost)).scalar() or 0
        total_tokens = db.session.query(db.func.sum(UsageEvent.total_tokens)).scalar() or 0
        total_sessions = CodingSession.query.count()

        # Project stats (group_id may be missing on older DBs)
        projects = Project.query.all()
        project_stats = []
        for project in projects:
            project_events = UsageEvent.query.filter_by(project_id=project.id).all()
            project_cost = sum(e.cost for e in project_events)
            project_tokens = sum(e.total_tokens for e in project_events)
            project_sessions = CodingSession.query.filter_by(project_id=project.id).count()
            group_id = getattr(project, 'group_id', None)
            group = getattr(project, 'group', None)
            project_stats.append({
                'id': project.id,
                'name': project.name,
                'group_id': group_id,
                'group_name': group.name if group else None,
                'cost': project_cost,
                'tokens': project_tokens,
                'sessions': project_sessions,
                'event_count': len(project_events)
            })

        # Group stats (aggregated)
        groups = ProjectGroup.query.order_by(ProjectGroup.sort_order, ProjectGroup.name).all()
        group_stats = []
        for g in groups:
            g_projects = [p for p in project_stats if p.get('group_id') == g.id]
            group_stats.append({
                'id': g.id,
                'name': g.name,
                'description': g.description or '',
                'sort_order': g.sort_order or 0,
                'cost': sum(p['cost'] for p in g_projects),
                'tokens': sum(p['tokens'] for p in g_projects),
                'sessions': sum(p['sessions'] for p in g_projects),
                'event_count': sum(p['event_count'] for p in g_projects),
                'project_count': len(g_projects),
            })

        # Unassigned stats
        unassigned_events = UsageEvent.query.filter_by(project_id=None).all()
        unassigned_cost = sum(e.cost for e in unassigned_events)
        unassigned_tokens = sum(e.total_tokens for e in unassigned_events)
        unassigned_sessions = CodingSession.query.filter_by(project_id=None).count()

        return jsonify({
            'overall': {
                'total_events': total_events,
                'total_cost': total_cost,
                'total_tokens': total_tokens,
                'total_sessions': total_sessions
            },
            'projects': project_stats,
            'groups': group_stats,
            'unassigned': {
                'cost': unassigned_cost,
                'tokens': unassigned_tokens,
                'sessions': unassigned_sessions,
                'event_count': len(unassigned_events)
            }
        })
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"get_dashboard_stats error: {e}\n{tb}")
        return jsonify({'error': str(e), 'traceback': tb}), 500

@app.route('/api/events', methods=['GET'])
def get_events():
    """Get usage events with optional filters"""
    project_id = request.args.get('project_id', type=int)
    limit = request.args.get('limit', 100, type=int)
    
    query = UsageEvent.query
    
    if project_id:
        query = query.filter_by(project_id=project_id)
    
    events = query.order_by(UsageEvent.date.desc()).limit(limit).all()
    
    return jsonify([{
        'id': e.id,
        'date': format_datetime_local(e.date),
        'user': e.user,
        'model': e.model,
        'cost': e.cost,
        'total_tokens': e.total_tokens,
        'project_id': e.project_id,
        'session_id': e.session_id
    } for e in events])

@app.route('/api/detect/projects', methods=['POST'])
def detect_projects():
    """Detect projects for unassigned sessions based on git activity"""
    try:
        # Get unassigned sessions
        sessions = CodingSession.query.filter_by(project_id=None).order_by(CodingSession.start_time.desc()).all()
        
        if not sessions:
            return jsonify({'suggestions': [], 'message': 'No unassigned sessions found'})
        
        # Convert to dict format for detector
        session_dicts = [{
            'id': s.id,
            'start_time': s.start_time,
            'end_time': s.end_time
        } for s in sessions]
        
        # Detect projects
        suggestions = project_detector.detect_projects_for_sessions(session_dicts)
        
        # Get or create projects based on suggestions
        project_map = {}  # Map project name to Project object
        
        for suggestion in suggestions:
            project_name = suggestion['project_name']
            
            # Check if project already exists
            if project_name not in project_map:
                project = Project.query.filter_by(name=project_name).first()
                
                if not project:
                    # Create new project
                    project = Project(
                        name=project_name,
                        description=f"Auto-detected from {suggestion['project_path']}"
                    )
                    db.session.add(project)
                    db.session.flush()
                
                project_map[project_name] = project
            
            suggestion['project_id'] = project_map[project_name].id
        
        db.session.commit()
        
        return jsonify({
            'suggestions': suggestions,
            'total_sessions': len(sessions),
            'matched_sessions': len(suggestions)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect/apply', methods=['POST'])
def apply_detections():
    """Apply auto-detected project assignments"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        min_confidence = data.get('min_confidence', 5)
        auto_assign = data.get('auto_assign', False)
        
        print(f"Applying detections: min_confidence={min_confidence}, auto_assign={auto_assign}")
        
        # Get unassigned sessions
        sessions = CodingSession.query.filter_by(project_id=None).order_by(CodingSession.start_time.desc()).all()
        print(f"Found {len(sessions)} unassigned sessions")
        
        if not sessions:
            return jsonify({
                'success': True,
                'assigned_sessions': 0,
                'total_suggestions': 0,
                'filtered_suggestions': 0,
                'message': 'No unassigned sessions found'
            })
        
        session_dicts = [{
            'id': s.id,
            'start_time': s.start_time,
            'end_time': s.end_time
        } for s in sessions]
        
        print("Detecting projects for sessions...")
        suggestions = project_detector.detect_projects_for_sessions(session_dicts)
        print(f"Found {len(suggestions)} suggestions")
        
        # Filter by confidence
        filtered_suggestions = [s for s in suggestions if s['confidence_score'] >= min_confidence]
        print(f"Filtered to {len(filtered_suggestions)} suggestions with confidence >= {min_confidence}")
        
        assigned_count = 0
        
        for suggestion in filtered_suggestions:
            session = CodingSession.query.get(suggestion['session_id'])
            if not session:
                print(f"Session {suggestion['session_id']} not found, skipping")
                continue
            
            # Get or create project
            project = Project.query.filter_by(name=suggestion['project_name']).first()
            if not project:
                project = Project(
                    name=suggestion['project_name'],
                    description=f"Auto-detected from {suggestion['project_path']}"
                )
                db.session.add(project)
                db.session.flush()
                print(f"Created new project: {project.name}")
            
            # Assign session to project
            session.project_id = project.id
            for event in session.events:
                event.project_id = project.id
            
            assigned_count += 1
            print(f"Assigned session {session.id} to project {project.name}")
        
        db.session.commit()
        print(f"Successfully assigned {assigned_count} sessions")
        
        return jsonify({
            'success': True,
            'assigned_sessions': assigned_count,
            'total_suggestions': len(suggestions),
            'filtered_suggestions': len(filtered_suggestions)
        })
    
    except Exception as e:
        db.session.rollback()
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in apply_detections: {error_trace}")
        return jsonify({'error': str(e), 'traceback': error_trace}), 500

@app.route('/api/detect/repos', methods=['GET'])
def list_git_repos():
    """List all git repositories found in configured SCM path"""
    global current_scm_path
    try:
        repos = project_detector.find_git_repos()
        return jsonify({
            'repos': repos,
            'count': len(repos),
            'scm_path': current_scm_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _load_scm_path_from_settings():
    """Apply persisted SCM path to current_scm_path and project_detector if set."""
    global current_scm_path, project_detector
    saved = get_setting('scm_path')
    if saved and os.path.exists(saved) and os.path.isdir(saved):
        current_scm_path = saved
        project_detector = ProjectDetector(base_path=current_scm_path)


@app.route('/api/debug-db', methods=['GET'])
def debug_db():
    """Return DB path and row counts. Only available when AI_CODING_DEBUG=true (for troubleshooting)."""
    if not config.DEBUG:
        return jsonify({'error': 'Not available'}), 404
    n_events = UsageEvent.query.count()
    n_sessions = CodingSession.query.count()
    return jsonify({
        'database_path': config.DATABASE_PATH,
        'usage_event_count': n_events,
        'coding_session_count': n_sessions,
        'engine_url': str(db.engine.url) if db.engine else None,
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration (legacy; also see GET /api/settings)."""
    global current_scm_path
    _load_scm_path_from_settings()
    return jsonify({
        'scm_path': current_scm_path,
        'database_path': config.DATABASE_PATH,
        'scm_path_exists': os.path.exists(current_scm_path),
        'default_scm_path': config.SCM_PATH
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all app settings for the Settings UI. Seeds defaults if none exist."""
    global current_scm_path
    if AppSettings.query.count() == 0:
        _seed_default_settings()
    _load_scm_path_from_settings()
    scm_path = get_setting('scm_path') or current_scm_path or config.SCM_PATH
    return jsonify({
        'scm_path': scm_path,
        'scm_path_exists': os.path.exists(scm_path),
        'database_path': config.DATABASE_PATH,
        'session_gap_hours': get_setting('session_gap_hours') or '2',
        'downloads_lookback_hours': get_setting('downloads_lookback_hours') or '24',
    })


@app.route('/api/settings', methods=['PATCH'])
def update_settings():
    """Update one or more settings. Body: { key: value, ... }. database_path is saved to config file and applies on next launch."""
    global current_scm_path, project_detector
    if not request.is_json:
        return jsonify({'error': 'Content-Type must be application/json'}), 400
    data = request.json or {}
    allowed = {'session_gap_hours', 'downloads_lookback_hours', 'scm_path', 'database_path'}
    db_path_saved = False
    for key, value in data.items():
        if key not in allowed:
            continue
        if value is None:
            continue
        str_val = str(value).strip()
        if key == 'scm_path':
            if not str_val:
                continue
            expanded = os.path.expanduser(str_val)
            if not os.path.exists(expanded) or not os.path.isdir(expanded):
                return jsonify({'error': f'Path does not exist or is not a directory: {expanded}'}), 400
            str_val = expanded
            current_scm_path = str_val
            project_detector = ProjectDetector(base_path=current_scm_path)
            project_detector.clear_cache()
            set_setting(key, str_val)
        elif key == 'database_path':
            # Empty = clear saved path so app uses default on next launch.
            # Store absolute path so restart reads the same path (no ~/ vs expanduser mismatch).
            if str_val:
                expanded = os.path.abspath(os.path.expanduser(str_val))
                try:
                    os.makedirs(os.path.dirname(expanded), exist_ok=True)
                except OSError:
                    pass  # e.g. sandbox can't create ~/Documents/db; still persist for next launch
                try:
                    config.write_app_config({'database_path': expanded})
                except OSError as e:
                    return jsonify({'error': f'Could not save config: {e}'}), 500
            else:
                config_path = config.get_app_config_path()
                if os.path.exists(config_path):
                    try:
                        with open(config_path, encoding='utf-8') as f:
                            data = json.load(f)
                        data.pop('database_path', None)
                        with open(config_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2)
                    except Exception:
                        pass
            db_path_saved = True
        else:
            set_setting(key, str_val)
    out = {'success': True}
    if db_path_saved:
        out['message'] = 'Settings saved. Restart the app for the new database path to take effect.'
    return jsonify(out)

@app.route('/api/config/scm_path', methods=['POST'])
def update_scm_path():
    """Update the SCM path for project detection"""
    global current_scm_path, project_detector
    
    try:
        if not request.is_json:
            print(f"DEBUG: Request is not JSON. Content-Type: {request.content_type}")
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.json
        if not data:
            print("DEBUG: Request body is empty")
            return jsonify({'error': 'Request body is required'}), 400
        
        new_path = data.get('scm_path', '').strip()
        print(f"DEBUG: Received SCM path: '{new_path}'")
        
        if not new_path:
            return jsonify({'error': 'SCM path is required'}), 400
        
        # Expand user home directory (~) if present
        original_path = new_path
        if new_path.startswith('~'):
            new_path = os.path.expanduser(new_path)
            print(f"DEBUG: Expanded path from '{original_path}' to '{new_path}'")
        
        # Validate path exists
        if not os.path.exists(new_path):
            print(f"DEBUG: Path does not exist: '{new_path}'")
            return jsonify({
                'error': f'Path does not exist: {new_path}',
                'received_path': original_path,
                'expanded_path': new_path
            }), 400
        
        if not os.path.isdir(new_path):
            return jsonify({'error': f'Path is not a directory: {new_path}'}), 400
        
        # Update path and persist for Settings
        current_scm_path = new_path
        project_detector = ProjectDetector(base_path=current_scm_path)
        project_detector.clear_cache()
        set_setting('scm_path', current_scm_path)

        return jsonify({
            'success': True,
            'scm_path': current_scm_path,
            'scm_path_exists': True
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect/session/<int:session_id>/files', methods=['GET'])
def get_session_files(session_id):
    """Get detailed file modification information for a specific session"""
    try:
        session = CodingSession.query.get_or_404(session_id)
        
        # Detect project and get file details
        match = project_detector.detect_project_for_session(session.start_time, session.end_time)
        
        if match and 'all_files' in match:
            return jsonify({
                'session_id': session_id,
                'project_name': match['name'],
                'project_path': match['path'],
                'files_modified': match['files_modified'],
                'files_during_session': match['files_during_session'],
                'all_files': match.get('all_files', []),
                'top_files': match.get('top_files', []),
                'confidence_score': match['score']
            })
        else:
            return jsonify({
                'session_id': session_id,
                'project_name': None,
                'files_modified': 0,
                'all_files': []
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        _run_database_migrations()
    app.run(debug=True, port=config.PORT)
