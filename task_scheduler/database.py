"""
Database management for task scheduling and execution tracking
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
import threading


@dataclass
class TaskExecution:
    """Represents a task execution record"""
    task_name: str
    execution_time: datetime
    next_run_time: Optional[datetime]
    status: str  # 'success', 'failed', 'timeout', 'cancelled'
    duration: float  # seconds
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class TaskSchedule:
    """Represents a task schedule record"""
    task_name: str
    next_run_time: datetime
    schedule_config: str  # JSON string of schedule configuration
    last_updated: datetime
    is_active: bool = True


class DatabaseManager:
    """Manages SQLite database for task scheduling"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with self._lock:
            conn = self._get_connection()
            try:
                # Create tables
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS task_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_name TEXT NOT NULL,
                        execution_time TIMESTAMP NOT NULL,
                        next_run_time TIMESTAMP,
                        status TEXT NOT NULL,
                        duration REAL NOT NULL,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS task_schedules (
                        task_name TEXT PRIMARY KEY,
                        next_run_time TIMESTAMP NOT NULL,
                        schedule_config TEXT NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    );
                    
                    CREATE TABLE IF NOT EXISTS scheduler_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_task_executions_name 
                        ON task_executions(task_name);
                    CREATE INDEX IF NOT EXISTS idx_task_executions_time 
                        ON task_executions(execution_time);
                    CREATE INDEX IF NOT EXISTS idx_task_schedules_next_run 
                        ON task_schedules(next_run_time);
                """)
                conn.commit()
            finally:
                conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        return conn
    
    def record_execution(self, execution: TaskExecution):
        """Record a task execution"""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    INSERT INTO task_executions 
                    (task_name, execution_time, next_run_time, status, 
                     duration, error_message, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    execution.task_name,
                    execution.execution_time,
                    execution.next_run_time,
                    execution.status,
                    execution.duration,
                    execution.error_message,
                    execution.retry_count
                ))
                conn.commit()
            finally:
                conn.close()
    
    def update_task_schedule(self, schedule: TaskSchedule):
        """Update or insert task schedule"""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO task_schedules 
                    (task_name, next_run_time, schedule_config, last_updated, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    schedule.task_name,
                    schedule.next_run_time,
                    schedule.schedule_config,
                    schedule.last_updated,
                    schedule.is_active
                ))
                conn.commit()
            finally:
                conn.close()
    
    def get_task_schedule(self, task_name: str) -> Optional[TaskSchedule]:
        """Get task schedule by name"""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM task_schedules WHERE task_name = ?
                """, (task_name,))
                row = cursor.fetchone()
                if row:
                    return TaskSchedule(
                        task_name=row['task_name'],
                        next_run_time=datetime.fromisoformat(row['next_run_time']),
                        schedule_config=row['schedule_config'],
                        last_updated=datetime.fromisoformat(row['last_updated']),
                        is_active=bool(row['is_active'])
                    )
                return None
            finally:
                conn.close()
    
    def get_overdue_tasks(self, current_time: datetime) -> List[TaskSchedule]:
        """Get tasks that are overdue for execution"""
        with self._lock:
            conn = self._get_connection()
            try:
                # Convert current_time to ISO format string for consistent comparison
                # Remove microseconds for consistent comparison
                current_time_normalized = current_time.replace(microsecond=0)
                current_time_str = current_time_normalized.isoformat()

                cursor = conn.execute("""
                    SELECT * FROM task_schedules
                    WHERE datetime(next_run_time) <= datetime(?) AND is_active = 1
                    ORDER BY next_run_time
                """, (current_time_str,))

                overdue_tasks = []
                rows = cursor.fetchall()

                for row in rows:
                    task_schedule = TaskSchedule(
                        task_name=row['task_name'],
                        next_run_time=datetime.fromisoformat(row['next_run_time']),
                        schedule_config=row['schedule_config'],
                        last_updated=datetime.fromisoformat(row['last_updated']),
                        is_active=bool(row['is_active'])
                    )
                    overdue_tasks.append(task_schedule)

                return overdue_tasks
            finally:
                conn.close()
    
    def get_last_execution(self, task_name: str) -> Optional[TaskExecution]:
        """Get the last execution record for a task"""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT * FROM task_executions 
                    WHERE task_name = ? 
                    ORDER BY execution_time DESC 
                    LIMIT 1
                """, (task_name,))
                row = cursor.fetchone()
                if row:
                    return TaskExecution(
                        task_name=row['task_name'],
                        execution_time=datetime.fromisoformat(row['execution_time']),
                        next_run_time=datetime.fromisoformat(row['next_run_time']) if row['next_run_time'] else None,
                        status=row['status'],
                        duration=row['duration'],
                        error_message=row['error_message'],
                        retry_count=row['retry_count']
                    )
                return None
            finally:
                conn.close()
    
    def cleanup_old_executions(self, days_to_keep: int = 30):
        """Clean up old execution records"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    DELETE FROM task_executions 
                    WHERE execution_time < ?
                """, (cutoff_date,))
                conn.commit()
            finally:
                conn.close()
    
    def deactivate_task(self, task_name: str):
        """Deactivate a task schedule"""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    UPDATE task_schedules 
                    SET is_active = 0, last_updated = CURRENT_TIMESTAMP
                    WHERE task_name = ?
                """, (task_name,))
                conn.commit()
            finally:
                conn.close()
    
    def get_scheduler_state(self, key: str) -> Optional[str]:
        """Get scheduler state value"""
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("""
                    SELECT value FROM scheduler_state WHERE key = ?
                """, (key,))
                row = cursor.fetchone()
                return row['value'] if row else None
            finally:
                conn.close()
    
    def set_scheduler_state(self, key: str, value: str):
        """Set scheduler state value"""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO scheduler_state (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
                conn.commit()
            finally:
                conn.close()
