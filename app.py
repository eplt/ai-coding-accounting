from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import csv
import io
import os
from werkzeug.utils import secure_filename
from project_detector import ProjectDetector
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{config.DATABASE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
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
    user = db.Column(db.String(255), nullable=False)
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

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    events = db.relationship('UsageEvent', backref='project', lazy=True)

def create_unique_hash(row):
    """Create a unique hash for deduplication based on key fields"""
    import hashlib
    key = f"{row['Date']}_{row['User']}_{row['Model']}_{row['Total Tokens']}_{row['Cost']}"
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
        # Read CSV content
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        new_events = []
        duplicate_count = 0
        
        for row in csv_reader:
            # Create unique hash
            unique_hash = create_unique_hash(row)
            
            # Check if event already exists
            existing = UsageEvent.query.filter_by(unique_hash=unique_hash).first()
            if existing:
                duplicate_count += 1
                continue
            
            # Parse and create new event
            try:
                # Parse date (UTC) and convert to local timezone before storing
                parsed_date = parse_date(row['Date'])
                local_date = to_local_timezone(parsed_date)
                
                event = UsageEvent(
                    date=local_date,
                    user=row['User'],
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
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue
        
        # Add new events to database
        db.session.add_all(new_events)
        db.session.commit()
        
        # Detect and create sessions
        gap_hours = request.form.get('gap_hours', 2, type=int)
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
            
            # Link events to session
            for event in session_events:
                event.session_id = session.id
            
            created_sessions += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'new_events': len(new_events),
            'duplicates': duplicate_count,
            'sessions_created': created_sessions
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    projects = Project.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'created_at': format_datetime_local(p.created_at)
    } for p in projects])

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    data = request.json
    project = Project(
        name=data['name'],
        description=data.get('description', '')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({'id': project.id, 'name': project.name}), 201

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a project"""
    project = Project.query.get_or_404(project_id)
    data = request.json
    project.name = data.get('name', project.name)
    project.description = data.get('description', project.description)
    db.session.commit()
    return jsonify({'id': project.id, 'name': project.name})

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

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all coding sessions with optional filters"""
    project_id = request.args.get('project_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = CodingSession.query
    
    if project_id:
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

@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics"""
    # Overall stats
    total_events = UsageEvent.query.count()
    total_cost = db.session.query(db.func.sum(UsageEvent.cost)).scalar() or 0
    total_tokens = db.session.query(db.func.sum(UsageEvent.total_tokens)).scalar() or 0
    total_sessions = CodingSession.query.count()
    
    # Project stats
    projects = Project.query.all()
    project_stats = []
    for project in projects:
        project_events = UsageEvent.query.filter_by(project_id=project.id).all()
        project_cost = sum(e.cost for e in project_events)
        project_tokens = sum(e.total_tokens for e in project_events)
        project_sessions = CodingSession.query.filter_by(project_id=project.id).count()
        
        project_stats.append({
            'id': project.id,
            'name': project.name,
            'cost': project_cost,
            'tokens': project_tokens,
            'sessions': project_sessions,
            'event_count': len(project_events)
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
        'unassigned': {
            'cost': unassigned_cost,
            'tokens': unassigned_tokens,
            'sessions': unassigned_sessions,
            'event_count': len(unassigned_events)
        }
    })

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

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    global current_scm_path
    return jsonify({
        'scm_path': current_scm_path,
        'database_path': config.DATABASE_PATH,
        'scm_path_exists': os.path.exists(current_scm_path),
        'default_scm_path': config.SCM_PATH
    })

@app.route('/api/config/scm_path', methods=['POST'])
def update_scm_path():
    """Update the SCM path for project detection"""
    global current_scm_path, project_detector
    
    try:
        data = request.json
        new_path = data.get('scm_path', '').strip()
        
        if not new_path:
            return jsonify({'error': 'SCM path is required'}), 400
        
        # Validate path exists
        if not os.path.exists(new_path):
            return jsonify({'error': f'Path does not exist: {new_path}'}), 400
        
        if not os.path.isdir(new_path):
            return jsonify({'error': f'Path is not a directory: {new_path}'}), 400
        
        # Update path
        current_scm_path = new_path
        project_detector = ProjectDetector(base_path=current_scm_path)
        project_detector.clear_cache()  # Clear cached repos
        
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
    app.run(debug=True, port=5000)
