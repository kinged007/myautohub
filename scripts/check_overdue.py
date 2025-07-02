#!/usr/bin/env python3
"""
Check which tasks are considered overdue
"""

import sqlite3
import yaml
from datetime import datetime
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent.parent

def load_config(config_path: Path = None):
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = project_dir / "config" / "config.yaml"

    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config from {config_path}: {e}")
        # Fallback to default path
        return {"database": {"path": "scheduler.db"}}

def main():
    config = load_config()
    db_path = project_dir / "data" / config['database']['path']
    current_time = datetime.now()
    
    print(f"Current time: {current_time.isoformat()}")
    print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT task_name, next_run_time 
        FROM task_schedules 
        ORDER BY next_run_time
    """)
    
    print("All tasks:")
    overdue_count = 0
    for row in cursor.fetchall():
        task_name, next_run_time = row
        try:
            next_run_dt = datetime.fromisoformat(next_run_time)
            is_overdue = next_run_dt <= current_time
            status = "OVERDUE" if is_overdue else "FUTURE"
            if is_overdue:
                overdue_count += 1
            print(f"  {task_name}: {next_run_time} ({status})")
        except Exception as e:
            print(f"  {task_name}: {next_run_time} (ERROR: {e})")
    
    print(f"\nTotal overdue tasks: {overdue_count}")
    
    # Test the actual query used by the system (updated version)
    current_time_normalized = current_time.replace(microsecond=0)
    current_time_str = current_time_normalized.isoformat()

    cursor = conn.execute("""
        SELECT task_name, next_run_time
        FROM task_schedules
        WHERE datetime(next_run_time) <= datetime(?) AND is_active = 1
        ORDER BY next_run_time
    """, (current_time_str,))
    
    print(f"\nTasks found by system query (datetime(next_run_time) <= datetime('{current_time_str}')):")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()

if __name__ == "__main__":
    main()
