"""
Custom decorators for task scheduling with tracking and execution management
"""

import functools
import time
import traceback
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict
import schedule
from loguru import logger

from .database import DatabaseManager, TaskExecution, TaskSchedule


class TaskTracker:
    """Tracks task execution and manages scheduling"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._running_tasks: Dict[str, bool] = {}
    
    def is_task_running(self, task_name: str) -> bool:
        """Check if a task is currently running"""
        return self._running_tasks.get(task_name, False)
    
    def set_task_running(self, task_name: str, running: bool):
        """Set task running status"""
        self._running_tasks[task_name] = running


# Global task tracker instance
_task_tracker: Optional[TaskTracker] = None

# Global registry to map job functions to task names
_job_task_registry: Dict[Any, str] = {}

# Global registry to track recently executed tasks (to prevent double execution)
_recently_executed_tasks: Dict[str, datetime] = {}


def set_task_tracker(tracker: TaskTracker):
    """Set the global task tracker"""
    global _task_tracker
    _task_tracker = tracker


def get_task_tracker() -> TaskTracker:
    """Get the global task tracker"""
    if _task_tracker is None:
        raise RuntimeError("Task tracker not initialized")
    return _task_tracker


def tracked_schedule(schedule_func):
    """
    Decorator that wraps schedule decorators to add execution tracking
    
    Usage:
        @tracked_schedule(schedule.every(10).minutes)
        def my_task():
            pass
    """
    def decorator(func: Callable) -> Callable:
        # Try to get task name from module name, fallback to function name
        if hasattr(func, '__module__') and func.__module__.startswith('task_'):
            # Extract task name from module name (e.g., 'task_example_hello_world_123' -> 'example_hello_world')
            module_parts = func.__module__.split('_')
            if len(module_parts) >= 3:
                task_name = '_'.join(module_parts[1:-1])  # Remove 'task_' prefix and timestamp suffix
            else:
                task_name = func.__name__
        else:
            task_name = func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracker = get_task_tracker()
            
            # Check if task is already running
            if tracker.is_task_running(task_name):
                logger.warning(f"Task {task_name} is already running, skipping execution")
                return
            
            # Mark task as running
            tracker.set_task_running(task_name, True)
            
            start_time = time.time()
            execution_time = datetime.now()
            status = "success"
            error_message = None
            
            try:
                # Create task-specific logger
                task_logger = logger.bind(task_name=task_name)
                task_logger.info(f"Starting task: {task_name}")

                result = func(*args, **kwargs)

                task_logger.info(f"Task {task_name} completed successfully")
                return result

            except Exception as e:
                status = "failed"
                error_message = str(e)

                # Log error with task context
                task_logger = logger.bind(task_name=task_name)
                task_logger.error(f"Task {task_name} failed: {error_message}")
                task_logger.error(f"Task {task_name} traceback: {traceback.format_exc()}")

                # Also log to general error log
                logger.error(f"Task execution failed - {task_name}: {error_message}")
                logger.error(traceback.format_exc())
                raise
                
            finally:
                # Mark task as not running
                tracker.set_task_running(task_name, False)
                
                # Calculate duration and next run time
                duration = time.time() - start_time
                
                # Get next run time from schedule
                next_run = None
                for job in schedule.jobs:
                    if job.job_func == wrapper:
                        next_run = job.next_run
                        break
                
                # Record execution
                execution = TaskExecution(
                    task_name=task_name,
                    execution_time=execution_time,
                    next_run_time=next_run,
                    status=status,
                    duration=duration,
                    error_message=error_message
                )

                tracker.db_manager.record_execution(execution)

                # Track this task as recently executed to prevent double execution
                _recently_executed_tasks[task_name] = execution_time
                
                # Update schedule in database
                if next_run:
                    # Ensure consistent datetime format
                    next_run_normalized = next_run
                    if isinstance(next_run_normalized, datetime):
                        next_run_normalized = next_run_normalized.replace(microsecond=0)

                    schedule_record = TaskSchedule(
                        task_name=task_name,
                        next_run_time=next_run_normalized,
                        schedule_config="",  # Will be updated by scheduler
                        last_updated=datetime.now()
                    )
                    tracker.db_manager.update_task_schedule(schedule_record)
        
        # Apply the original schedule decorator
        scheduled_func = schedule_func.do(wrapper)

        # Store original function reference for identification
        wrapper._original_func = func
        wrapper._task_name = task_name

        # Register the job function with the task name in our global registry
        # Find the job that was just created and register it
        for job in schedule.jobs:
            if hasattr(job.job_func, 'func') and job.job_func.func == wrapper:
                _job_task_registry[job.job_func] = task_name
                logger.debug(f"Registered job function with task name: {task_name}")
                break

        return wrapper
    
    return decorator


def repeat(interval):
    """
    Custom repeat decorator that works with our tracking system

    Usage:
        @repeat(every(10).minutes)
        def my_task():
            pass
    """
    # Check if this is a cron-like interval
    if isinstance(interval, CronLikeInterval):
        # Use cron-like scheduling
        def decorator(func: Callable) -> Callable:
            # Extract task name from module
            if hasattr(func, '__module__') and func.__module__.startswith('task_'):
                # Extract task name from module name (e.g., 'task_example_hello_world_123' -> 'example_hello_world')
                module_parts = func.__module__.split('_')
                if len(module_parts) >= 3:
                    task_name = '_'.join(module_parts[1:-1])  # Remove 'task_' prefix and timestamp suffix
                else:
                    task_name = func.__name__
            else:
                task_name = func.__name__

            # Create wrapper with tracking
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                tracker = get_task_tracker()

                # Check if task is already running
                if tracker.is_task_running(task_name):
                    logger.warning(f"Task {task_name} is already running, skipping execution")
                    return

                # Mark task as running
                tracker.set_task_running(task_name, True)

                start_time = time.time()
                execution_time = datetime.now()
                status = "success"
                error_message = None

                try:
                    logger.info(f"Starting task: {task_name}")
                    result = func(*args, **kwargs)
                    logger.info(f"Task {task_name} completed successfully")
                    return result

                except Exception as e:
                    status = "failed"
                    error_message = str(e)
                    logger.error(f"Task {task_name} failed: {error_message}")
                    logger.error(traceback.format_exc())
                    raise

                finally:
                    # Mark task as not running
                    tracker.set_task_running(task_name, False)

                    # Calculate duration
                    duration = time.time() - start_time

                    # Record execution
                    execution = TaskExecution(
                        task_name=task_name,
                        execution_time=execution_time,
                        next_run_time=None,  # Will be set by cron-like job
                        status=status,
                        duration=duration,
                        error_message=error_message
                    )

                    tracker.db_manager.record_execution(execution)

                    # Track this task as recently executed to prevent double execution
                    _recently_executed_tasks[task_name] = execution_time

            # Store task name on function for later reference
            wrapper._task_name = f"{func.__module__}.{func.__name__}"
            wrapper._original_func = func

            # Register the job function with task name for database sync
            _job_task_registry[wrapper] = task_name

            # Create cron-like job
            job = interval.do(wrapper)

            logger.debug(f"Created cron-like job for task {task_name}: {job}")

            return wrapper

        return decorator
    else:
        # Use regular schedule library
        return tracked_schedule(interval)


class CronLikeInterval:
    """
    Enhanced interval class that supports both cron-like intervals and standard schedule library API
    """
    def __init__(self, interval: int):
        self.interval = interval
        self._unit = None
        self._use_cron_like = True  # Default to cron-like behavior for numeric intervals

    # Cron-like properties (align to clock boundaries)
    @property
    def minutes(self):
        """Schedule every N minutes aligned to clock boundaries (0, 5, 10, 15, etc.)"""
        self._unit = 'minutes'
        self._use_cron_like = True
        return self

    @property
    def hours(self):
        """Schedule every N hours aligned to clock boundaries (top of hour)"""
        self._unit = 'hours'
        self._use_cron_like = True
        return self

    @property
    def days(self):
        """Schedule every N days at midnight"""
        self._unit = 'days'
        self._use_cron_like = True
        return self

    # Standard schedule library properties (delegate to schedule library)
    @property
    def seconds(self):
        """Standard schedule library: every N seconds"""
        return ScheduleWrapper(schedule.every(self.interval).seconds)

    @property
    def minute(self):
        """Standard schedule library: every minute (only for interval=1)"""
        if self.interval != 1:
            raise ValueError("Use 'minutes' for intervals other than 1")
        return ScheduleWrapper(schedule.every().minute)

    @property
    def hour(self):
        """Standard schedule library: every hour (only for interval=1)"""
        if self.interval != 1:
            raise ValueError("Use 'hours' for intervals other than 1")
        return ScheduleWrapper(schedule.every().hour)

    @property
    def day(self):
        """Standard schedule library: every day (only for interval=1)"""
        if self.interval != 1:
            raise ValueError("Use 'days' for intervals other than 1")
        return ScheduleWrapper(schedule.every().day)

    @property
    def week(self):
        """Standard schedule library: every week (only for interval=1)"""
        if self.interval != 1:
            raise ValueError("Use 'weeks' for intervals other than 1")
        return ScheduleWrapper(schedule.every().week)

    @property
    def weeks(self):
        """Standard schedule library: every N weeks"""
        return ScheduleWrapper(schedule.every(self.interval).weeks)

    # Day of week properties
    @property
    def monday(self):
        """Standard schedule library: every Monday"""
        return ScheduleWrapper(schedule.every(self.interval).monday)

    @property
    def tuesday(self):
        """Standard schedule library: every Tuesday"""
        return ScheduleWrapper(schedule.every(self.interval).tuesday)

    @property
    def wednesday(self):
        """Standard schedule library: every Wednesday"""
        return ScheduleWrapper(schedule.every(self.interval).wednesday)

    @property
    def thursday(self):
        """Standard schedule library: every Thursday"""
        return ScheduleWrapper(schedule.every(self.interval).thursday)

    @property
    def friday(self):
        """Standard schedule library: every Friday"""
        return ScheduleWrapper(schedule.every(self.interval).friday)

    @property
    def saturday(self):
        """Standard schedule library: every Saturday"""
        return ScheduleWrapper(schedule.every(self.interval).saturday)

    @property
    def sunday(self):
        """Standard schedule library: every Sunday"""
        return ScheduleWrapper(schedule.every(self.interval).sunday)

    def at(self, time_str: str, tz=None):
        """Schedule at a specific time (delegates to schedule library)"""
        if self._unit is None:
            raise ValueError("Must specify time unit before using at()")

        # Delegate to standard schedule library for all at() usage
        schedule_unit = getattr(schedule.every(self.interval), self._unit)
        if tz:
            return ScheduleWrapper(schedule_unit.at(time_str, tz))
        else:
            return ScheduleWrapper(schedule_unit.at(time_str))

    def do(self, func):
        """Create a job - either cron-like or standard schedule"""
        if self._unit is None:
            raise ValueError("Must specify time unit (minutes, hours, days, etc.)")

        if self._use_cron_like and self._unit in ['minutes', 'hours', 'days']:
            # Use our cron-like job for alignment to clock boundaries
            job = CronLikeJob(self.interval, self._unit, func)
            # Add to our separate cron-like jobs list, NOT to schedule.jobs
            if not hasattr(schedule, '_cron_like_jobs'):
                schedule._cron_like_jobs = []
            schedule._cron_like_jobs.append(job)
            return job
        else:
            # Delegate to standard schedule library
            schedule_unit = getattr(schedule.every(self.interval), self._unit)
            return schedule_unit.do(func)


class CronLikeJob:
    """
    A job that runs at cron-like intervals aligned to clock boundaries
    """
    def __init__(self, interval: int, unit: str, job_func):
        self.interval = interval
        self.unit = unit
        self.job_func = job_func
        self.last_run = None
        self.next_run = self._calculate_next_run()

    def _calculate_next_run(self):
        """Calculate next run time aligned to clock boundaries"""
        from datetime import datetime, timedelta

        now = datetime.now()

        if self.unit == 'minutes':
            # Align to minute boundaries: 0, 5, 10, 15, etc.
            current_minute = now.minute
            next_minute = ((current_minute // self.interval) + 1) * self.interval

            if next_minute >= 60:
                # Move to next hour
                next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            else:
                next_run = now.replace(minute=next_minute, second=0, microsecond=0)

        elif self.unit == 'hours':
            # Align to hour boundaries: top of hour
            next_hour = now.hour + self.interval
            if next_hour >= 24:
                # Move to next day
                next_run = (now + timedelta(days=1)).replace(hour=next_hour % 24, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)

        elif self.unit == 'days':
            # Align to day boundaries: midnight
            next_run = (now + timedelta(days=self.interval)).replace(hour=0, minute=0, second=0, microsecond=0)

        else:
            raise ValueError(f"Unsupported unit: {self.unit}")

        return next_run

    def should_run(self):
        """Check if this job should run now"""
        from datetime import datetime
        return datetime.now() >= self.next_run

    def run(self):
        """Run the job and reschedule"""
        from datetime import datetime

        self.last_run = datetime.now()
        result = self.job_func()
        self.next_run = self._calculate_next_run()

        # Update database with new next run time
        try:
            tracker = get_task_tracker()
            if tracker and hasattr(self.job_func, '_task_name'):
                # Extract task name from the function
                task_name = None
                if self.job_func in _job_task_registry:
                    task_name = _job_task_registry[self.job_func]

                if task_name:
                    from .database import TaskSchedule
                    # Ensure consistent datetime format
                    next_run_normalized = self.next_run.replace(microsecond=0)

                    updated_schedule = TaskSchedule(
                        task_name=task_name,
                        next_run_time=next_run_normalized,
                        schedule_config=str(self),
                        last_updated=datetime.now(),
                        is_active=True
                    )
                    tracker.db_manager.update_task_schedule(updated_schedule)
                    logger.debug(f"Updated database for cron-like job {task_name}: next run at {next_run_normalized}")
        except Exception as e:
            logger.error(f"Error updating database for cron-like job: {e}")

        return result

    def __str__(self):
        return f"Every {self.interval} {self.unit} (next run: {self.next_run})"

    def __lt__(self, other):
        """Support comparison for schedule library sorting"""
        if hasattr(other, 'next_run'):
            return self.next_run < other.next_run
        return False

    def __le__(self, other):
        """Support comparison for schedule library sorting"""
        if hasattr(other, 'next_run'):
            return self.next_run <= other.next_run
        return False

    def __gt__(self, other):
        """Support comparison for schedule library sorting"""
        if hasattr(other, 'next_run'):
            return self.next_run > other.next_run
        return False

    def __ge__(self, other):
        """Support comparison for schedule library sorting"""
        if hasattr(other, 'next_run'):
            return self.next_run >= other.next_run
        return False

    def __eq__(self, other):
        """Support comparison for schedule library sorting"""
        if hasattr(other, 'next_run'):
            return self.next_run == other.next_run
        return False


class ScheduleWrapper:
    """
    Wrapper for schedule library objects to maintain compatibility
    """
    def __init__(self, schedule_unit):
        self.schedule_unit = schedule_unit

    def __call__(self, *args, **kwargs):
        """Handle cases where the wrapper is called as a function"""
        if hasattr(self.schedule_unit, '__call__'):
            result = self.schedule_unit(*args, **kwargs)
            # If result is a schedule unit, wrap it; otherwise return as-is
            if hasattr(result, 'do') and hasattr(result, 'at'):
                return ScheduleWrapper(result)
            return result
        else:
            raise TypeError(f"'{self.schedule_unit.__class__.__name__}' object is not callable. "
                          f"Did you mean to use it as a property instead of calling it as a function? "
                          f"For example, use 'every().day.at(\"10:30\")' instead of 'every().day().at(\"10:30\")'")

    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped schedule unit"""
        attr = getattr(self.schedule_unit, name)

        # If it's a method that returns a schedule unit, wrap the result
        if callable(attr):
            def wrapper(*args, **kwargs):
                result = attr(*args, **kwargs)
                # If result is a schedule unit, wrap it; otherwise return as-is
                if hasattr(result, 'do') and hasattr(result, 'at'):
                    return ScheduleWrapper(result)
                return result
            return wrapper

        # If it's a property that returns a schedule unit, wrap it
        if hasattr(attr, 'do') and hasattr(attr, 'at'):
            return ScheduleWrapper(attr)

        return attr


class NoIntervalSchedule:
    """
    Handles schedule patterns without an interval like every().day or every().monday
    """
    def __init__(self):
        pass

    # Time unit properties
    @property
    def minute(self):
        """Every minute"""
        return ScheduleWrapper(schedule.every().minute)

    @property
    def hour(self):
        """Every hour"""
        return ScheduleWrapper(schedule.every().hour)

    @property
    def day(self):
        """Every day"""
        return ScheduleWrapper(schedule.every().day)

    @property
    def week(self):
        """Every week"""
        return ScheduleWrapper(schedule.every().week)

    # Day of week properties
    @property
    def monday(self):
        """Every Monday"""
        return ScheduleWrapper(schedule.every().monday)

    @property
    def tuesday(self):
        """Every Tuesday"""
        return ScheduleWrapper(schedule.every().tuesday)

    @property
    def wednesday(self):
        """Every Wednesday"""
        return ScheduleWrapper(schedule.every().wednesday)

    @property
    def thursday(self):
        """Every Thursday"""
        return ScheduleWrapper(schedule.every().thursday)

    @property
    def friday(self):
        """Every Friday"""
        return ScheduleWrapper(schedule.every().friday)

    @property
    def saturday(self):
        """Every Saturday"""
        return ScheduleWrapper(schedule.every().saturday)

    @property
    def sunday(self):
        """Every Sunday"""
        return ScheduleWrapper(schedule.every().sunday)


def every(interval=None):
    """
    Enhanced wrapper that supports both cron-like intervals and full schedule library API

    Cron-like usage (aligns to clock boundaries):
        @repeat(every(5).minutes)  # Runs at :00, :05, :10, :15, :20, etc.

    Standard schedule library usage:
        @repeat(every().day.at("10:30"))  # Runs daily at 10:30
        @repeat(every().monday.at("13:15"))  # Runs Mondays at 13:15
        @repeat(every(3).seconds)  # Runs every 3 seconds
        @repeat(every(3).days.at("10:30"))  # Every 3 days at 10:30
    """
    if interval is None:
        # Return our no-interval handler for patterns like every().day
        return NoIntervalSchedule()
    else:
        # Return our enhanced interval handler for numeric intervals
        return CronLikeInterval(interval)


def force_run_if_overdue(task_name: str, func: Callable, max_delay_minutes: int = 60):
    """
    Force run a task if it's overdue based on database records
    
    Args:
        task_name: Name of the task
        func: Task function to execute
        max_delay_minutes: Maximum delay before forcing execution
    """
    tracker = get_task_tracker()
    
    # Check if task is already running
    if tracker.is_task_running(task_name):
        return
    
    # Get last execution and schedule
    last_execution = tracker.db_manager.get_last_execution(task_name)
    task_schedule = tracker.db_manager.get_task_schedule(task_name)
    
    if not task_schedule:
        return
    
    current_time = datetime.now()
    
    # Check if task is overdue
    if (task_schedule.next_run_time <= current_time and 
        task_schedule.is_active):
        
        # Check if we're within the acceptable delay window
        delay = current_time - task_schedule.next_run_time
        if delay.total_seconds() / 60 <= max_delay_minutes:
            logger.info(f"Force running overdue task: {task_name}")
            try:
                func()
            except Exception as e:
                logger.error(f"Force run failed for task {task_name}: {e}")


class ScheduleManager:
    """Manages schedule objects and their database synchronization"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def sync_schedules_with_database(self, loaded_tasks=None):
        """Synchronize schedule jobs with database records

        Args:
            loaded_tasks: Set of currently loaded task names (optional)
        """
        current_time = datetime.now()

        # Get overdue tasks from database
        overdue_tasks = self.db_manager.get_overdue_tasks(current_time)

        if overdue_tasks:
            logger.info(f"Found {len(overdue_tasks)} overdue tasks to check:")
            for task in overdue_tasks:
                delay_minutes = (current_time - task.next_run_time).total_seconds() / 60
                logger.info(f"  - {task.task_name}: due at {task.next_run_time}, overdue by {delay_minutes:.1f} minutes")

        for task_schedule in overdue_tasks:
            # Check if this task was recently executed (within last 30 seconds)
            # to prevent double execution
            if task_schedule.task_name in _recently_executed_tasks:
                last_execution = _recently_executed_tasks[task_schedule.task_name]
                time_since_execution = (current_time - last_execution).total_seconds()
                if time_since_execution < 30:  # 30 second cooldown
                    logger.info(f"Skipping {task_schedule.task_name} - executed {time_since_execution:.1f}s ago (cooldown)")
                    continue
                else:
                    # Remove old entry
                    logger.info(f"Cooldown expired for {task_schedule.task_name} - last executed {time_since_execution:.1f}s ago")
                    del _recently_executed_tasks[task_schedule.task_name]

            # Find corresponding schedule job
            matching_job = None

            # First check CronLikeJob objects (stored separately)
            cron_jobs = getattr(schedule, '_cron_like_jobs', [])
            for job in cron_jobs:
                if isinstance(job, CronLikeJob):
                    if job.job_func in _job_task_registry:
                        job_task_name = _job_task_registry[job.job_func]
                        if job_task_name == task_schedule.task_name:
                            matching_job = job
                            break
                    elif hasattr(job.job_func, '_task_name'):
                        job_task_name = job.job_func._task_name
                        if '.' in job_task_name:
                            job_task_name = job_task_name.split('.')[-1]

                        if job_task_name == task_schedule.task_name:
                            matching_job = job
                            break

            # If not found in cron jobs, check regular schedule jobs
            if not matching_job:
                for job in schedule.jobs:
                    # Handle regular schedule jobs
                    if hasattr(job, 'job_func'):
                        if job.job_func in _job_task_registry:
                            job_task_name = _job_task_registry[job.job_func]

                            if job_task_name == task_schedule.task_name:
                                matching_job = job
                                break
                        elif hasattr(job.job_func, '_task_name'):
                            # Fallback to checking _task_name attribute
                            job_task_name = job.job_func._task_name

                            if '.' in job_task_name:
                                job_task_name = job_task_name.split('.')[-1]

                            if job_task_name == task_schedule.task_name:
                                matching_job = job
                                break

            if matching_job:
                # Calculate how overdue the task is
                delay = current_time - task_schedule.next_run_time
                delay_minutes = delay.total_seconds() / 60

                # Run overdue tasks (with a reasonable maximum delay)
                if delay_minutes > 0 and delay_minutes <= 1440:  # Up to 24 hours overdue
                    logger.info(f"EXECUTING OVERDUE TASK: {task_schedule.task_name} (overdue by {delay_minutes:.1f} minutes)")
                    try:
                        matching_job.run()

                        # Update the next run time in database after forced execution
                        if matching_job.next_run:
                            # Ensure consistent datetime format
                            next_run_time = matching_job.next_run
                            if isinstance(next_run_time, datetime):
                                next_run_time = next_run_time.replace(microsecond=0)

                            updated_schedule = TaskSchedule(
                                task_name=task_schedule.task_name,
                                next_run_time=next_run_time,
                                schedule_config=task_schedule.schedule_config,
                                last_updated=current_time,
                                is_active=True
                            )
                            self.db_manager.update_task_schedule(updated_schedule)
                            logger.debug(f"Updated next run time for {task_schedule.task_name} to {matching_job.next_run}")
                        else:
                            logger.warning(f"No next_run time available for {task_schedule.task_name}, cannot update database")

                    except Exception as e:
                        logger.error(f"Failed to run overdue task {task_schedule.task_name}: {e}")
                elif delay_minutes > 1440:
                    # Task is too old, just update its next run time without executing
                    logger.warning(f"Task {task_schedule.task_name} is too overdue ({delay_minutes:.1f} minutes), updating next run time without execution")
                    if matching_job.next_run:
                        # Ensure consistent datetime format
                        next_run_time = matching_job.next_run
                        if isinstance(next_run_time, datetime):
                            next_run_time = next_run_time.replace(microsecond=0)

                        updated_schedule = TaskSchedule(
                            task_name=task_schedule.task_name,
                            next_run_time=next_run_time,
                            schedule_config=task_schedule.schedule_config,
                            last_updated=current_time,
                            is_active=True
                        )
                        self.db_manager.update_task_schedule(updated_schedule)
            else:
                # If no matching job found, remove the task from database to prevent future warnings
                logger.debug(f"No matching job found for overdue task: {task_schedule.task_name}, removing from database")
                self.db_manager.deactivate_task(task_schedule.task_name)
    
    def update_schedule_config(self, task_name: str, config: str):
        """Update schedule configuration in database"""
        task_schedule = self.db_manager.get_task_schedule(task_name)
        if task_schedule:
            task_schedule.schedule_config = config
            task_schedule.last_updated = datetime.now()
            self.db_manager.update_task_schedule(task_schedule)
    
    def cleanup_inactive_schedules(self):
        """Remove schedule jobs for tasks that are no longer active"""
        active_task_names = set()
        
        # Get all active tasks from database
        # This would need to be implemented based on your task discovery logic
        
        # Remove jobs for inactive tasks
        jobs_to_remove = []
        for job in schedule.jobs:
            if hasattr(job.job_func, '_task_name'):
                if job.job_func._task_name not in active_task_names:
                    jobs_to_remove.append(job)
        
        for job in jobs_to_remove:
            schedule.cancel_job(job)
            if hasattr(job.job_func, '_task_name'):
                self.db_manager.deactivate_task(job.job_func._task_name)
