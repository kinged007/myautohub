#!/usr/bin/env python3
"""
Task Scheduler - Main entry point
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from task_scheduler.scheduler import TaskScheduler
from task_scheduler.logging_config import setup_logging_from_config, set_logging_manager
from loguru import logger


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Task Scheduler - Background task management system")
    parser.add_argument(
        "--config", 
        type=Path, 
        default=project_dir / "config" / "config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--daemon", 
        action="store_true",
        help="Run as daemon (background process)"
    )
    parser.add_argument(
        "--status", 
        action="store_true",
        help="Show scheduler status and exit"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logs_dir = project_dir / "logs"
    logging_manager = setup_logging_from_config(args.config, logs_dir)
    set_logging_manager(logging_manager)
    
    # Log system info
    logging_manager.log_system_info()
    
    try:
        # Create scheduler
        scheduler = TaskScheduler(args.config)
        
        if args.status:
            # Show status and exit
            status = scheduler.get_status()
            print("Task Scheduler Status:")
            print(f"  Running: {status['running']}")
            print(f"  Loaded Tasks: {status['loaded_tasks']}")
            print(f"  Scheduled Jobs: {status['scheduled_jobs']}")
            print(f"  Memory Usage: {status['memory_usage'].get('rss_mb', 0):.1f} MB")
            return 0
        
        if args.daemon:
            # Run as daemon
            logger.info("Starting scheduler as daemon")
            daemonize()
        
        # Start scheduler
        restart_needed = True
        while restart_needed:
            try:
                scheduler.start()
                restart_needed = scheduler.restart_requested
                
                if restart_needed:
                    logger.info("Restarting scheduler...")
                    # Recreate scheduler instance for clean restart
                    scheduler = TaskScheduler(args.config)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                restart_needed = False
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                restart_needed = False
        
        logger.info("Task Scheduler stopped")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        return 1


def daemonize():
    """Daemonize the process (Unix only)"""
    if os.name == 'nt':
        logger.warning("Daemon mode not supported on Windows")
        return
    
    try:
        # First fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)  # Exit parent
        
        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        
        # Second fork
        pid = os.fork()
        if pid > 0:
            sys.exit(0)  # Exit second parent
        
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Close stdin, stdout, stderr
        with open(os.devnull, 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), sys.stdout.fileno())
            os.dup2(devnull.fileno(), sys.stderr.fileno())
        
        logger.info("Process daemonized successfully")
        
    except OSError as e:
        logger.error(f"Failed to daemonize: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
