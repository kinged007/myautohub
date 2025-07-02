"""
Core task scheduler implementation
"""

import time
import signal
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import schedule
import yaml
from loguru import logger

try:
    import setproctitle
    HAS_SETPROCTITLE = True
except ImportError:
    HAS_SETPROCTITLE = False

from .task_parser import TaskParser, TaskFile
from .database import DatabaseManager, TaskSchedule
from .venv_manager import VirtualEnvironmentManager
from .memory_manager import MemoryManager, TaskModuleManager, ResourceMonitor
from .decorators import TaskTracker, ScheduleManager, set_task_tracker
from .logging_config import LoggingManager, StructuredLogger


class TaskScheduler:
    """Main task scheduler class"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = self._load_config()
        self.running = False
        self.restart_requested = False
        
        # Initialize components
        self.base_dir = config_path.parent.parent
        self.tasks_dir = self.base_dir / self.config['tasks']['directory']
        self.logs_dir = self.base_dir / "logs"
        self.data_dir = self.base_dir / "data"
        
        # Create directories
        for directory in [self.tasks_dir, self.logs_dir, self.data_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize managers
        self.db_manager = DatabaseManager(self.data_dir / self.config['database']['path'])
        self.task_parser = TaskParser()
        self.venv_manager = VirtualEnvironmentManager(
            self.base_dir / self.config['virtual_env']['path'],
            self.config['virtual_env']['python_executable']
        )
        self.memory_manager = MemoryManager(self.config['scheduler']['max_memory_usage'])
        self.task_module_manager = TaskModuleManager()
        self.resource_monitor = ResourceMonitor(self.memory_manager)
        
        # Initialize tracking
        self.task_tracker = TaskTracker(self.db_manager)
        set_task_tracker(self.task_tracker)
        self.schedule_manager = ScheduleManager(self.db_manager)
        
        # Track loaded tasks
        self._loaded_tasks: Dict[str, TaskFile] = {}
        self._last_scan_time = 0

        # Track config file changes
        self._config_last_modified = self.config_path.stat().st_mtime if self.config_path.exists() else 0
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    def _check_and_reload_config(self) -> bool:
        """Check if config file has changed and reload if necessary"""
        try:
            if not self.config_path.exists():
                return False

            current_mtime = self.config_path.stat().st_mtime
            if current_mtime > self._config_last_modified:
                logger.info("Config file changed, reloading...")
                old_config = self.config.copy()
                self.config = self._load_config()
                self._config_last_modified = current_mtime

                # Check if critical settings changed that require component updates
                config_changed = False

                # Check if memory settings changed
                if old_config.get('scheduler', {}).get('max_memory_usage') != self.config.get('scheduler', {}).get('max_memory_usage'):
                    logger.info("Memory usage limit changed, updating memory manager")
                    self.memory_manager.max_memory_mb = self.config['scheduler']['max_memory_usage']
                    config_changed = True

                # Check if task directory changed
                new_tasks_dir = self.base_dir / self.config['tasks']['directory']
                if new_tasks_dir != self.tasks_dir:
                    logger.info(f"Tasks directory changed from {self.tasks_dir} to {new_tasks_dir}")
                    self.tasks_dir = new_tasks_dir
                    self.tasks_dir.mkdir(parents=True, exist_ok=True)
                    config_changed = True

                # Check if virtual environment settings changed
                new_venv_path = self.base_dir / self.config['virtual_env']['path']
                if (new_venv_path != self.venv_manager.venv_path or
                    self.config['virtual_env']['python_executable'] != self.venv_manager.python_executable):
                    logger.info("Virtual environment settings changed, updating venv manager")
                    self.venv_manager = VirtualEnvironmentManager(
                        new_venv_path,
                        self.config['virtual_env']['python_executable']
                    )
                    config_changed = True

                if config_changed:
                    logger.info("Configuration reloaded successfully with component updates")
                else:
                    logger.debug("Configuration reloaded successfully")

                return True

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False

        return False

    def _set_process_name(self):
        """Set a recognizable process name for the scheduler"""
        process_name = "myautohub-scheduler"

        if HAS_SETPROCTITLE:
            try:
                setproctitle.setproctitle(process_name)
                logger.debug(f"Process name set to: {process_name}")
            except Exception as e:
                logger.debug(f"Failed to set process name: {e}")
        else:
            logger.debug("setproctitle not available, process name not changed")

        # Also set argv[0] as a fallback
        try:
            sys.argv[0] = process_name
        except Exception as e:
            logger.debug(f"Failed to set argv[0]: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def start(self):
        """Start the task scheduler"""
        logger.info("Starting Task Scheduler")

        # Set process name for easy identification
        self._set_process_name()

        # Ensure virtual environment is ready
        if not self.venv_manager.ensure_virtual_environment():
            logger.error("Failed to setup virtual environment")
            return False
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring()
        
        # Initial task scan
        self._scan_and_load_tasks()
        
        # Start main loop
        self.running = True
        self._main_loop()
        
        return True
    
    def stop(self):
        """Stop the task scheduler"""
        logger.info("Stopping Task Scheduler")
        self.running = False
        self.resource_monitor.stop_monitoring()
    
    def restart(self):
        """Request scheduler restart"""
        logger.info("Restart requested")
        self.restart_requested = True
        self.stop()

    def _run_cron_like_jobs(self):
        """Run any pending cron-like jobs"""
        import schedule

        # Get cron-like jobs from our separate list
        cron_jobs = getattr(schedule, '_cron_like_jobs', [])
        pending_jobs = [job for job in cron_jobs if job.should_run()]

        if cron_jobs:
            logger.debug(f"Found {len(cron_jobs)} cron-like jobs, {len(pending_jobs)} pending")

        for job in pending_jobs:
            try:
                logger.info(f"EXECUTING CRON-LIKE JOB: {job}")
                job.run()
            except Exception as e:
                logger.error(f"Error running cron-like job {job}: {e}")

    def _main_loop(self):
        """Main scheduler loop"""
        last_memory_cleanup = time.time()
        last_task_scan = time.time()
        last_config_check = time.time()

        while self.running:
            try:
                current_time = time.time()

                # Check for config file changes (every 5 seconds)
                if current_time - last_config_check >= 5:
                    self._check_and_reload_config()
                    last_config_check = current_time

                # Scan for new/changed tasks
                if current_time - last_task_scan >= self.config['scheduler']['task_check_interval']:
                    self._scan_and_load_tasks()
                    last_task_scan = current_time
                
                # Run our custom cron-like jobs
                logger.debug("Running cron-like jobs")
                self._run_cron_like_jobs()

                # Run standard schedule library jobs
                logger.debug("Running standard schedule jobs")
                schedule.run_pending()

                # Sync schedules with database
                logger.debug("Syncing schedules with database")
                loaded_task_names = set(self._loaded_tasks.keys())
                self.schedule_manager.sync_schedules_with_database(loaded_task_names)
                
                # Memory cleanup
                if current_time - last_memory_cleanup >= self.config['scheduler']['memory_cleanup_interval']:
                    self.memory_manager.cleanup_memory()
                    last_memory_cleanup = current_time
                
                # Check if restart is needed due to high memory usage
                if self.memory_manager.is_memory_usage_high():
                    logger.warning("High memory usage detected, requesting restart")
                    self.restart()
                    break
                
                # Sleep until next iteration (but check for shutdown every second)
                loop_interval = self.config['scheduler']['loop_interval']
                for _ in range(loop_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(self.config['scheduler']['loop_interval'])
        
        logger.info("Main loop stopped")
    
    def _scan_and_load_tasks(self):
        """Scan tasks directory and load/reload tasks as needed"""
        try:
            logger.debug("Scanning tasks directory")

            # First, scan and install helper dependencies
            self._scan_and_install_helper_dependencies()

            # Get all task files
            include_example_tasks = self.config.get('tasks', {}).get('include_example_tasks', True)
            task_files = self.task_parser.scan_tasks_directory(self.tasks_dir, include_example_tasks)

            # Track current task names
            current_tasks = set()
            
            for task_file in task_files:
                task_name = task_file.path.stem
                current_tasks.add(task_name)
                
                # Check if task needs loading/reloading
                needs_reload = (
                    task_name not in self._loaded_tasks or
                    self._loaded_tasks[task_name].file_hash != task_file.file_hash or
                    self.task_module_manager.check_for_changes(task_file.path)
                )
                
                if needs_reload:
                    self._load_task(task_file)
            
            # Remove tasks that no longer exist
            removed_tasks = set(self._loaded_tasks.keys()) - current_tasks
            for task_name in removed_tasks:
                self._unload_task(task_name)
            
            StructuredLogger.log_scheduler_event(
                "task_scan_completed",
                f"Scanned {len(task_files)} tasks, {len(current_tasks)} active",
                active_tasks=len(current_tasks),
                total_files=len(task_files)
            )
            
        except Exception as e:
            logger.error(f"Error scanning tasks: {e}")
    
    def _load_task(self, task_file: TaskFile):
        """Load or reload a single task"""
        try:
            task_name = task_file.path.stem
            logger.info(f"Loading task: {task_name}")
            
            # Install dependencies if needed
            if task_file.metadata.dependencies:
                if not self._install_task_dependencies(task_file):
                    logger.error(f"Failed to install dependencies for task {task_name}")
                    return False
            
            # Load the task module
            module = self.task_module_manager.load_task_module(task_file.path, task_file.content)
            if not module:
                logger.error(f"Failed to load module for task {task_name}")
                return False
            
            # Remove existing schedule if reloading
            if task_name in self._loaded_tasks:
                self._remove_task_from_schedule(task_name)
            
            # Execute the module to register schedules
            try:
                # The module's start function should be decorated with @repeat()
                # which will automatically register it with the schedule
                if hasattr(module, 'start') and hasattr(module.start, '_task_name'):
                    logger.info(f"Task {task_name} registered with scheduler")

                    # Ensure initial schedule is recorded in database
                    self._ensure_initial_schedule_recorded(task_name)

                else:
                    logger.warning(f"Task {task_name} start function not properly decorated")
            except Exception as e:
                logger.error(f"Error registering task {task_name}: {e}")
                return False
            
            # Update loaded tasks
            self._loaded_tasks[task_name] = task_file
            
            StructuredLogger.log_scheduler_event(
                "task_loaded",
                f"Task {task_name} loaded successfully",
                task_name=task_name,
                dependencies=len(task_file.metadata.dependencies)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading task {task_file.path}: {e}")
            return False
    
    def _unload_task(self, task_name: str):
        """Unload a task"""
        try:
            logger.info(f"Unloading task: {task_name}")
            
            # Remove from schedule
            self._remove_task_from_schedule(task_name)
            
            # Unload module
            if task_name in self._loaded_tasks:
                task_file = self._loaded_tasks[task_name]
                self.task_module_manager.unload_task_module(task_file.path)
                del self._loaded_tasks[task_name]
            
            # Deactivate in database
            self.db_manager.deactivate_task(task_name)
            
            StructuredLogger.log_scheduler_event(
                "task_unloaded",
                f"Task {task_name} unloaded",
                task_name=task_name
            )
            
        except Exception as e:
            logger.error(f"Error unloading task {task_name}: {e}")
    
    def _remove_task_from_schedule(self, task_name: str):
        """Remove a task from the schedule"""
        # Remove from standard schedule library jobs
        jobs_to_remove = []
        for job in schedule.jobs:
            if hasattr(job.job_func, '_task_name') and job.job_func._task_name.endswith(task_name):
                jobs_to_remove.append(job)

        for job in jobs_to_remove:
            schedule.cancel_job(job)

        # Remove from cron-like jobs
        if hasattr(schedule, '_cron_like_jobs'):
            cron_jobs_to_remove = []
            for job in schedule._cron_like_jobs:
                if hasattr(job.job_func, '_task_name') and job.job_func._task_name.endswith(task_name):
                    cron_jobs_to_remove.append(job)

            for job in cron_jobs_to_remove:
                schedule._cron_like_jobs.remove(job)
    
    def _install_task_dependencies(self, task_file: TaskFile) -> bool:
        """Install dependencies for a task"""
        if not task_file.metadata.dependencies:
            return True
        
        try:
            logger.info(f"Installing dependencies for task {task_file.path.stem}: {task_file.metadata.dependencies}")
            
            # Check if dependencies have changed
            if not self.venv_manager.check_requirements_changed(task_file.metadata.dependencies):
                logger.debug(f"Dependencies unchanged for task {task_file.path.stem}")
                return True
            
            # Install dependencies
            success = self.venv_manager.install_requirements(task_file.metadata.dependencies)
            
            if success:
                StructuredLogger.log_scheduler_event(
                    "dependencies_installed",
                    f"Dependencies installed for task {task_file.path.stem}",
                    task_name=task_file.path.stem,
                    dependencies=task_file.metadata.dependencies
                )
            else:
                logger.error(f"Failed to install dependencies for task {task_file.path.stem}")
            
            return success

        except Exception as e:
            logger.error(f"Error installing dependencies for task {task_file.path.stem}: {e}")
            return False

    def _scan_and_install_helper_dependencies(self):
        """Scan helpers directory and install dependencies from helper modules"""
        try:
            helpers_dir = Path("helpers")
            if not helpers_dir.exists():
                logger.debug("Helpers directory does not exist, skipping helper dependency scan")
                return

            logger.debug("Scanning helpers directory for dependencies")

            # Get all helper files (always include example helpers for dependency scanning)
            helper_files = self.task_parser.scan_tasks_directory(helpers_dir, include_example_tasks=True)

            # Collect all dependencies from helpers
            all_helper_dependencies = []
            for helper_file in helper_files:
                if helper_file.metadata.dependencies:
                    helper_name = helper_file.path.stem
                    deps = helper_file.metadata.dependencies
                    logger.debug(f"Found dependencies in helper {helper_name}: {deps}")
                    all_helper_dependencies.extend(helper_file.metadata.dependencies)

            # Remove duplicates while preserving order
            unique_dependencies = []
            seen = set()
            for dep in all_helper_dependencies:
                if dep not in seen:
                    unique_dependencies.append(dep)
                    seen.add(dep)

            if unique_dependencies:
                # Check if dependencies have changed
                if not self.venv_manager.check_requirements_changed(unique_dependencies):
                    logger.debug("Helper dependencies unchanged")
                    return

                logger.info(f"Installing helper dependencies: {unique_dependencies}")

                # Install dependencies
                success = self.venv_manager.install_requirements(unique_dependencies)

                if success:
                    StructuredLogger.log_scheduler_event(
                        "helper_dependencies_installed",
                        f"Helper dependencies installed: {unique_dependencies}",
                        dependencies=unique_dependencies
                    )
                else:
                    logger.error("Failed to install helper dependencies")
            else:
                logger.debug("No helper dependencies found")

        except Exception as e:
            logger.error(f"Error scanning helper dependencies: {e}")
    
    def _ensure_initial_schedule_recorded(self, task_name: str):
        """Ensure the initial schedule for a task is recorded in the database"""
        try:
            # Find the corresponding schedule job using our registry
            from .decorators import _job_task_registry, CronLikeJob
            matching_job = None

            # First check CronLikeJob objects (stored separately)
            cron_jobs = getattr(schedule, '_cron_like_jobs', [])
            for job in cron_jobs:
                if isinstance(job, CronLikeJob):
                    if job.job_func in _job_task_registry:
                        job_task_name = _job_task_registry[job.job_func]
                        if job_task_name == task_name:
                            matching_job = job
                            break
                    elif hasattr(job.job_func, '_task_name'):
                        job_task_name = job.job_func._task_name
                        if '.' in job_task_name:
                            job_task_name = job_task_name.split('.')[-1]

                        if job_task_name == task_name:
                            matching_job = job
                            break

            # If not found in cron jobs, check regular schedule jobs
            if not matching_job:
                for job in schedule.jobs:
                    # Handle regular schedule jobs
                    if hasattr(job, 'job_func'):
                        if job.job_func in _job_task_registry:
                            job_task_name = _job_task_registry[job.job_func]
                            if job_task_name == task_name:
                                matching_job = job
                                break
                        elif hasattr(job.job_func, '_task_name'):
                            job_task_name = job.job_func._task_name
                            if '.' in job_task_name:
                                job_task_name = job_task_name.split('.')[-1]

                            if job_task_name == task_name:
                                matching_job = job
                                break

            if matching_job and matching_job.next_run:
                # Check if we already have a schedule record
                existing_schedule = self.db_manager.get_task_schedule(task_name)

                if not existing_schedule:
                    # Create initial schedule record
                    from .database import TaskSchedule
                    # Ensure consistent datetime format (replace space with T for ISO format)
                    next_run_time = matching_job.next_run
                    if isinstance(next_run_time, datetime):
                        # Convert to consistent ISO format
                        next_run_time = next_run_time.replace(microsecond=0)  # Remove microseconds for consistency

                    initial_schedule = TaskSchedule(
                        task_name=task_name,
                        next_run_time=next_run_time,
                        schedule_config=str(matching_job),  # Store job description
                        last_updated=datetime.now(),
                        is_active=True
                    )
                    self.db_manager.update_task_schedule(initial_schedule)
                    logger.info(f"Initial schedule recorded for task {task_name}: next run at {matching_job.next_run}")
                else:
                    logger.debug(f"Schedule already exists for task {task_name}")
            else:
                logger.warning(f"Could not find matching job or next_run time for task {task_name}")

        except Exception as e:
            logger.error(f"Error recording initial schedule for task {task_name}: {e}")

    def get_status(self) -> Dict:
        """Get scheduler status information"""
        return {
            "running": self.running,
            "loaded_tasks": len(self._loaded_tasks),
            "scheduled_jobs": len(schedule.jobs),
            "memory_usage": self.memory_manager.get_memory_usage(),
            "system_stats": self.resource_monitor.get_system_stats(),
            "venv_info": self.venv_manager.get_environment_info()
        }
