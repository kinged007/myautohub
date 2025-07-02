"""
---
title: "Daily Cleanup Task"
description: "Performs daily maintenance and cleanup operations"
dependencies: []
enabled: true
timeout: 600
---
"""

from task_scheduler.decorators import repeat, every
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

@repeat(every(1).day.at("02:00"))
def start():
    """Daily cleanup task that runs at 2 AM"""
    try:
        print("Starting daily cleanup task...")
        
        # Define directories to clean
        data_dir = Path("data")
        logs_dir = Path("logs")
        temp_dir = Path("temp")
        
        cleanup_stats = {
            'files_removed': 0,
            'bytes_freed': 0,
            'directories_cleaned': 0
        }
        
        # Clean old data files (older than 30 days)
        if data_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=30)
            
            for file_path in data_dir.glob("*.json"):
                try:
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleanup_stats['files_removed'] += 1
                        cleanup_stats['bytes_freed'] += file_size
                        print(f"Removed old data file: {file_path.name}")
                except Exception as e:
                    print(f"Error removing {file_path}: {e}")
        
        # Clean old log files (older than 7 days, keep .log files)
        if logs_dir.exists():
            cutoff_date = datetime.now() - timedelta(days=7)
            
            for file_path in logs_dir.glob("*.log.*"):  # Rotated log files
                try:
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleanup_stats['files_removed'] += 1
                        cleanup_stats['bytes_freed'] += file_size
                        print(f"Removed old log file: {file_path.name}")
                except Exception as e:
                    print(f"Error removing {file_path}: {e}")
        
        # Clean temporary directory
        if temp_dir.exists():
            try:
                for item in temp_dir.iterdir():
                    if item.is_file():
                        file_size = item.stat().st_size
                        item.unlink()
                        cleanup_stats['files_removed'] += 1
                        cleanup_stats['bytes_freed'] += file_size
                    elif item.is_dir():
                        shutil.rmtree(item)
                        cleanup_stats['directories_cleaned'] += 1
                print(f"Cleaned temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Error cleaning temp directory: {e}")
        
        # Create cleanup report
        report = {
            'timestamp': datetime.now().isoformat(),
            'cleanup_stats': cleanup_stats,
            'bytes_freed_mb': round(cleanup_stats['bytes_freed'] / (1024 * 1024), 2)
        }
        
        # Save cleanup report
        data_dir.mkdir(exist_ok=True)
        report_file = data_dir / f"cleanup_report_{datetime.now().strftime('%Y%m%d')}.json"
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("Daily cleanup completed:")
        print(f"  Files removed: {cleanup_stats['files_removed']}")
        print(f"  Directories cleaned: {cleanup_stats['directories_cleaned']}")
        print(f"  Space freed: {report['bytes_freed_mb']} MB")
        print(f"  Report saved: {report_file}")
        
    except Exception as e:
        print(f"Error during daily cleanup: {e}")
        raise
