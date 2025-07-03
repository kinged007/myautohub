#!/usr/bin/env python3
"""
Reset Task Schedule Database Script

This script resets the next run times in the database to ensure only future tasks 
are executed according to their schedule, and overdue tasks are ignored.

Usage:
    python scripts/reset_schedules.py [options]

Options:
    --dry-run       Show what would be changed without making changes
    --task TASK     Reset only specific task (can be used multiple times)
    --all           Reset all tasks (default)
    --future-only   Only reset overdue tasks to future times
    --help          Show this help message
"""

import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from task_scheduler.database import DatabaseManager, TaskSchedule
from helpers.config_loader import load_config


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Reset task schedule database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be changed without making changes'
    )
    
    parser.add_argument(
        '--task',
        action='append',
        dest='tasks',
        help='Reset only specific task (can be used multiple times)'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        default=True,
        help='Reset all tasks (default)'
    )
    
    parser.add_argument(
        '--future-only',
        action='store_true', 
        help='Only reset overdue tasks to future times'
    )
    
    return parser.parse_args()


def calculate_next_run_time(task_name: str, schedule_config: str) -> datetime:
    """
    Calculate the next appropriate run time for a task based on its schedule configuration
    """
    current_time = datetime.now()
    
    # Parse schedule configuration to determine interval
    if "Every 1 minutes" in schedule_config:
        # Next minute boundary
        next_run = current_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    elif "Every 5 minutes" in schedule_config:
        # Next 5-minute boundary
        minutes = current_time.minute
        next_5min = ((minutes // 5) + 1) * 5
        if next_5min >= 60:
            next_run = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_run = current_time.replace(minute=next_5min, second=0, microsecond=0)
    elif "Every 10 minutes" in schedule_config:
        # Next 10-minute boundary
        minutes = current_time.minute
        next_10min = ((minutes // 10) + 1) * 10
        if next_10min >= 60:
            next_run = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            next_run = current_time.replace(minute=next_10min, second=0, microsecond=0)
    elif "Every 1 hours" in schedule_config:
        # Next hour boundary
        next_run = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif "daily" in schedule_config.lower() or "Every 1 days" in schedule_config:
        # Next day at configured time (default 2:00 AM)
        next_run = (current_time + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
    else:
        # Default: next hour
        next_run = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    return next_run


def reset_schedules(args):
    """Reset task schedules based on arguments"""
    config = load_config()
    db_path = project_dir / "data" / config['database']['path']
    
    if not db_path.exists():
        print("❌ Database not found. Please run the scheduler first to create it.")
        return 1
    
    print(f"📊 Resetting task schedules in: {db_path}")
    print(f"🕐 Current time: {datetime.now().isoformat()}")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    
    print()
    
    try:
        db_manager = DatabaseManager(db_path)
        current_time = datetime.now()
        
        # Get tasks to reset
        if args.tasks:
            # Reset specific tasks
            schedules_to_reset = []
            for task_name in args.tasks:
                schedule = db_manager.get_task_schedule(task_name)
                if schedule:
                    schedules_to_reset.append(schedule)
                else:
                    print(f"⚠️  Task '{task_name}' not found in database")
        else:
            # Get all schedules
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT * FROM task_schedules WHERE is_active = 1")
            rows = cursor.fetchall()
            conn.close()
            
            schedules_to_reset = []
            for row in rows:
                schedule = TaskSchedule(
                    task_name=row[0],
                    next_run_time=datetime.fromisoformat(row[1]),
                    schedule_config=row[2],
                    last_updated=datetime.fromisoformat(row[3]),
                    is_active=bool(row[4])
                )
                schedules_to_reset.append(schedule)
        
        if not schedules_to_reset:
            print("ℹ️  No schedules found to reset")
            return 0
        
        # Process each schedule
        reset_count = 0
        skip_count = 0
        
        for schedule in schedules_to_reset:
            is_overdue = schedule.next_run_time <= current_time
            
            # Skip if future-only mode and task is not overdue
            if args.future_only and not is_overdue:
                skip_count += 1
                continue
            
            # Calculate new next run time
            new_next_run = calculate_next_run_time(schedule.task_name, schedule.schedule_config)
            
            # Show what will be changed
            status = "OVERDUE" if is_overdue else "FUTURE"
            delay_minutes = (current_time - schedule.next_run_time).total_seconds() / 60 if is_overdue else 0
            
            print(f"📋 {schedule.task_name}:")
            print(f"   Current: {schedule.next_run_time} ({status})")
            if is_overdue:
                print(f"   Overdue: {delay_minutes:.1f} minutes")
            print(f"   New:     {new_next_run}")
            
            if not args.dry_run:
                # Update the schedule
                updated_schedule = TaskSchedule(
                    task_name=schedule.task_name,
                    next_run_time=new_next_run,
                    schedule_config=schedule.schedule_config,
                    last_updated=current_time,
                    is_active=True
                )
                db_manager.update_task_schedule(updated_schedule)
                print(f"   ✅ Updated")
            else:
                print(f"   🔍 Would update (dry run)")
            
            print()
            reset_count += 1
        
        # Summary
        print("=" * 50)
        if args.dry_run:
            print(f"🔍 DRY RUN SUMMARY:")
            print(f"   Would reset: {reset_count} tasks")
            print(f"   Would skip:  {skip_count} tasks")
            print(f"\nTo apply changes, run without --dry-run")
        else:
            print(f"✅ RESET COMPLETE:")
            print(f"   Reset: {reset_count} tasks")
            print(f"   Skipped: {skip_count} tasks")
            print(f"\nAll selected tasks now have future run times.")
            print(f"Overdue tasks will be ignored until their next scheduled time.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error resetting schedules: {e}")
        return 1


def main():
    """Main function"""
    args = parse_arguments()
    
    if len(sys.argv) == 1:
        # No arguments provided, show help
        parse_arguments().print_help()
        return 0
    
    return reset_schedules(args)


if __name__ == "__main__":
    sys.exit(main())
