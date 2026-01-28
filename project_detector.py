"""
Project Detection Module
Automatically detects which project folder corresponds to coding sessions
based on file modification times (mtime) in git repositories.
Works even if files aren't committed to git.
"""
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re


class ProjectDetector:
    def __init__(self, base_path: str = "~/SCM"):
        self.base_path = Path(os.path.expanduser(base_path))
        self._git_repos_cache = None
    
    def to_local_timezone(self, dt: datetime) -> datetime:
        """
        Convert a timezone-aware datetime to local timezone.
        If datetime is naive, assume it's already in local timezone.
        File modification times are in local timezone (naive).
        """
        if dt.tzinfo is None:
            # Already naive, assume local timezone
            return dt
        
        # Convert to local timezone
        return dt.astimezone()
    
    def normalize_datetime(self, dt: datetime) -> datetime:
        """
        Normalize datetime to naive local time for comparison with file mtimes.
        File mtimes are always in local timezone and naive.
        """
        if dt.tzinfo is not None:
            # Convert to local timezone and make naive
            return dt.astimezone().replace(tzinfo=None)
        return dt
    
    def find_git_repos(self) -> List[Dict[str, str]]:
        """
        Recursively find all git repositories in the base path and subdirectories.
        Returns list of dicts with 'path' and 'name' keys.
        """
        if self._git_repos_cache is not None:
            return self._git_repos_cache
        
        repos = []
        visited_git_dirs = set()  # Track .git directories we've seen
        
        if not self.base_path.exists():
            return repos
        
        # Recursively walk through all subdirectories
        for root, dirs, files in os.walk(self.base_path):
            root_path = Path(root)
            
            # Skip if we're inside a .git directory
            if '.git' in root_path.parts:
                dirs[:] = []  # Don't descend further
                continue
            
            # Check if current directory is a git repo
            git_dir = root_path / '.git'
            if git_dir.exists() and git_dir.is_dir():
                git_dir_str = str(git_dir.resolve())
                if git_dir_str not in visited_git_dirs:
                    visited_git_dirs.add(git_dir_str)
                    # Use relative path from base for name
                    rel_path = root_path.relative_to(self.base_path)
                    repos.append({
                        'path': str(root_path),
                        'name': str(rel_path) if str(rel_path) != '.' else root_path.name,
                        'git_path': str(git_dir)
                    })
                    # Don't descend into subdirectories of a git repo (they're part of the repo)
                    dirs[:] = []
        
        self._git_repos_cache = repos
        return repos
    
    def find_all_directories(self) -> List[Dict[str, str]]:
        """
        Find all directories (not just git repos) for comprehensive file scanning.
        Returns list of dicts with 'path' and 'name' keys.
        """
        directories = []
        
        if not self.base_path.exists():
            return directories
        
        # Recursively walk through all subdirectories
        for root, dirs, files in os.walk(self.base_path):
            root_path = Path(root)
            
            # Skip .git directories and common build/cache dirs
            if '.git' in root_path.parts or any(skip in root_path.parts for skip in ['node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', '.cache', '.DS_Store']):
                dirs[:] = []
                continue
            
            # Skip if it's the base path itself
            if root_path == self.base_path:
                continue
            
            rel_path = root_path.relative_to(self.base_path)
            directories.append({
                'path': str(root_path),
                'name': str(rel_path)
            })
        
        return directories
    
    def get_git_commits_in_range(self, repo_path: str, start_time: datetime, end_time: datetime, 
                                  buffer_minutes: int = 30) -> List[Dict]:
        """
        Get git commits within the time range (with buffer).
        Returns list of commit dicts with 'hash', 'date', 'message', 'author'.
        """
        try:
            # Add buffer to catch commits slightly before/after session
            start_with_buffer = start_time - timedelta(minutes=buffer_minutes)
            end_with_buffer = end_time + timedelta(minutes=buffer_minutes)
            
            # Format dates for git log
            start_str = start_with_buffer.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_with_buffer.strftime('%Y-%m-%d %H:%M:%S')
            
            # Run git log command
            cmd = [
                'git', 'log',
                '--all',
                '--since', start_str,
                '--until', end_str,
                '--format=%H|%ai|%an|%s',  # hash|date|author|subject
                '--date=iso'
            ]
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|', 3)
                if len(parts) >= 4:
                    try:
                        commit_date = datetime.fromisoformat(parts[1].replace(' +', '+').replace(' -', '-'))
                        commits.append({
                            'hash': parts[0],
                            'date': commit_date,
                            'author': parts[2],
                            'message': parts[3]
                        })
                    except (ValueError, IndexError):
                        continue
            
            return commits
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
            print(f"Error getting commits from {repo_path}: {e}")
            return []
    
    def get_file_modifications_in_range(self, repo_path: str, start_time: datetime, end_time: datetime,
                                         buffer_minutes: int = 30) -> Dict:
        """
        Check file modification times (mtime) within the time range.
        Returns dict with file count and total modification count.
        This works even if files aren't committed to git.
        
        Note: File mtimes are in local timezone (naive), so we normalize session times to local.
        """
        try:
            # Normalize session times to local timezone (naive) for comparison with file mtimes
            start_time_local = self.normalize_datetime(start_time)
            end_time_local = self.normalize_datetime(end_time)
            
            start_with_buffer = start_time_local - timedelta(minutes=buffer_minutes)
            end_with_buffer = end_time_local + timedelta(minutes=buffer_minutes)
            
            # Convert to timestamps for comparison (naive datetime uses local timezone)
            start_ts = start_with_buffer.timestamp()
            end_ts = end_with_buffer.timestamp()
            
            repo_path_obj = Path(repo_path)
            modified_files = []
            total_modifications = 0
            
            # Walk through the repository (excluding .git directory)
            for root, dirs, files in os.walk(repo_path):
                root_path = Path(root)
                
                # Skip .git directory and its contents
                if '.git' in root_path.parts:
                    dirs[:] = []  # Don't descend into .git
                    continue
                
                # Skip common build/cache directories (don't descend into them)
                dirs[:] = [d for d in dirs if d not in [
                    'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', 
                    '.next', '.cache', '.pytest_cache', '.mypy_cache', '.idea', 
                    '.vscode', 'target', '.gradle', '.sass-cache', 'coverage'
                ]]
                
                for file in files:
                    file_path = Path(root) / file
                    
                    try:
                        # Get file modification time
                        mtime = file_path.stat().st_mtime
                        mtime_dt = datetime.fromtimestamp(mtime)
                        
                        # Check if file was modified within the time range
                        if start_ts <= mtime <= end_ts:
                            modified_files.append({
                                'path': str(file_path.relative_to(repo_path_obj)),
                                'mtime': mtime_dt,
                                'timestamp': mtime
                            })
                            total_modifications += 1
                        
                        # Also check if file was modified very close to session (within buffer)
                        # This helps catch files modified just before/after the session
                        # Use normalized local times for comparison
                        time_diff_start = abs((mtime_dt - start_time_local).total_seconds())
                        time_diff_end = abs((mtime_dt - end_time_local).total_seconds())
                        
                        if time_diff_start < buffer_minutes * 60 or time_diff_end < buffer_minutes * 60:
                            # Check if we already counted this file
                            if not any(f['path'] == str(file_path.relative_to(repo_path_obj)) for f in modified_files):
                                modified_files.append({
                                    'path': str(file_path.relative_to(repo_path_obj)),
                                    'mtime': mtime_dt,
                                    'timestamp': mtime
                                })
                                total_modifications += 1
                    
                    except (OSError, PermissionError):
                        # Skip files we can't access
                        continue
            
            # Count files modified exactly during the session (not just buffer)
            # Use normalized local times for comparison
            files_during_session = [
                f for f in modified_files
                if start_time_local <= f['mtime'] <= end_time_local
            ]
            
            return {
                'total_files': len(modified_files),
                'files_during_session': len(files_during_session),
                'total_modifications': total_modifications,
                'file_details': modified_files
            }
        
        except Exception as e:
            print(f"Error getting file modifications from {repo_path}: {e}")
            return {
                'total_files': 0,
                'files_during_session': 0,
                'total_modifications': 0,
                'file_details': []
            }
    
    def detect_project_for_session(self, start_time: datetime, end_time: datetime,
                                   buffer_minutes: int = 30) -> Optional[Dict]:
        """
        Detect which project folder has activity during the session time window.
        Uses file modification times (mtime) - scans both git repos and all directories.
        Returns dict with project info, confidence score, and modified files/folders.
        
        Note: Handles timezone conversion - CSV times are UTC, file mtimes are local.
        """
        # Normalize session times to local timezone for comparison
        start_time_local = self.normalize_datetime(start_time)
        end_time_local = self.normalize_datetime(end_time)
        
        # Get both git repos and all directories for comprehensive scanning
        repos = self.find_git_repos()
        all_dirs = self.find_all_directories()
        
        # Combine repos and directories, prioritizing repos
        all_paths = []
        repo_paths = {r['path'] for r in repos}
        
        for repo in repos:
            all_paths.append(repo)
        
        # Add non-repo directories
        for dir_info in all_dirs:
            if dir_info['path'] not in repo_paths:
                all_paths.append(dir_info)
        
        if not all_paths:
            return None
        
        best_match = None
        best_score = 0
        
        for path_info in all_paths:
            # Get file modifications in time range (uses normalized times internally)
            file_mods = self.get_file_modifications_in_range(path_info['path'], start_time, end_time, buffer_minutes)
            
            # Skip if no file modifications
            if file_mods['total_files'] == 0:
                continue
            
            # Check for git commits if it's a git repo (also normalize commit times)
            commits = []
            if path_info['path'] in repo_paths:
                commits_raw = self.get_git_commits_in_range(path_info['path'], start_time, end_time, buffer_minutes)
                # Normalize commit times to local for comparison
                commits = [
                    {**c, 'date': self.normalize_datetime(c['date'])}
                    for c in commits_raw
                ]
            
            # Calculate confidence score based primarily on file modifications
            score = 0
            
            # File modifications are the primary indicator
            # Base score from number of files modified
            score += file_mods['total_files'] * 5
            
            # Bonus for files modified exactly during session
            if file_mods['files_during_session'] > 0:
                score += file_mods['files_during_session'] * 10
            
            # Check how close file modifications are to session start (using local times)
            for file_info in file_mods['file_details']:
                time_diff = abs((file_info['mtime'] - start_time_local).total_seconds())
                if time_diff < 1800:  # Within 30 minutes of session start
                    score += 3
                elif time_diff < 3600:  # Within 1 hour
                    score += 1
            
            # Git commits are secondary indicators (bonus points)
            if commits:
                score += len(commits) * 3
                commits_during_session = [
                    c for c in commits 
                    if start_time_local <= c['date'] <= end_time_local
                ]
                if commits_during_session:
                    score += len(commits_during_session) * 5
            
            if score > best_score:
                best_score = score
                
                # Sort files by proximity to session start time (using local times)
                sorted_files = sorted(
                    file_mods['file_details'],
                    key=lambda x: abs((x['mtime'] - start_time_local).total_seconds())
                )
                
                best_match = {
                    'name': path_info['name'],
                    'path': path_info['path'],
                    'score': score,
                    'files_modified': file_mods['total_files'],
                    'files_during_session': file_mods['files_during_session'],
                    'commits': len(commits) if commits else 0,
                    'commits_during_session': len([c for c in commits if start_time_local <= c['date'] <= end_time_local]) if commits else 0,
                    'all_files': [
                        {
                            'path': f['path'],
                            'mtime': f['mtime'].isoformat(),  # Already in local timezone (naive)
                            'time_diff_minutes': round(abs((f['mtime'] - start_time_local).total_seconds()) / 60, 1),
                            'during_session': start_time_local <= f['mtime'] <= end_time_local
                        }
                        for f in sorted_files
                    ],
                    'top_files': [
                        {
                            'path': f['path'],
                            'mtime': f['mtime'].isoformat(),  # Already in local timezone (naive)
                            'time_diff_minutes': round(abs((f['mtime'] - start_time_local).total_seconds()) / 60, 1)
                        }
                        for f in sorted_files[:10]  # Top 10 for display
                    ]
                }
        
        # Only return if confidence is above threshold
        if best_match and best_match['score'] >= 5:
            return best_match
        
        return None
    
    def detect_projects_for_sessions(self, sessions: List[Dict]) -> List[Dict]:
        """
        Detect projects for multiple sessions.
        sessions: List of dicts with 'id', 'start_time', 'end_time'
        Returns list of suggestions with session_id and project info.
        """
        suggestions = []
        
        for session in sessions:
            start_time = session['start_time']
            end_time = session['end_time']
            
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
            
            match = self.detect_project_for_session(start_time, end_time)
            
            if match:
                suggestions.append({
                    'session_id': session['id'],
                    'project_name': match['name'],
                    'project_path': match['path'],
                    'confidence_score': match['score'],
                    'files_modified': match['files_modified'],
                    'files_during_session': match['files_during_session'],
                    'commits': match.get('commits', 0),
                    'commits_during_session': match.get('commits_during_session', 0),
                    'top_files': match.get('top_files', []),
                    'all_files': match.get('all_files', [])
                })
        
        return suggestions
    
    def clear_cache(self):
        """Clear the git repos cache (useful if repos are added/removed)."""
        self._git_repos_cache = None
