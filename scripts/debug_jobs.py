#!/usr/bin/env python3
"""
Debug what jobs are actually in the schedule
"""

import sys
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

import schedule
from task_scheduler.decorators import CronLikeJob

def main():
    print(f"Total jobs in schedule: {len(schedule.jobs)}")
    print()
    
    for i, job in enumerate(schedule.jobs):
        print(f"Job {i+1}:")
        print(f"  Type: {type(job)}")
        print(f"  Is CronLikeJob: {isinstance(job, CronLikeJob)}")
        
        if isinstance(job, CronLikeJob):
            print(f"  Interval: {job.interval}")
            print(f"  Unit: {job.unit}")
            print(f"  Next run: {job.next_run}")
            print(f"  Should run now: {job.should_run()}")
            if hasattr(job.job_func, '_task_name'):
                print(f"  Task name: {job.job_func._task_name}")
        else:
            print(f"  Next run: {getattr(job, 'next_run', 'N/A')}")
            if hasattr(job, 'job_func') and hasattr(job.job_func, '_task_name'):
                print(f"  Task name: {job.job_func._task_name}")
        
        print()

if __name__ == "__main__":
    main()
