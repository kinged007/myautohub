"""
Logging configuration for task scheduler using loguru
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
import yaml


class LoggingManager:
    """Manages logging configuration and setup"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._configured = False
    
    def setup_logging(self, logs_dir: Path):
        """Setup loguru logging with configuration"""
        if self._configured:
            return
        
        # Ensure logs directory exists
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove default logger
        logger.remove()
        
        # Add console handler
        logger.add(
            sys.stderr,
            level=self.config.get("level", "INFO"),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            colorize=True
        )
        
        # Add file handler
        log_file = logs_dir / self.config.get("file", "scheduler.log")
        logger.add(
            str(log_file),
            level=self.config.get("level", "INFO"),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation=self.config.get("rotation", "daily"),
            retention=self.config.get("retention", "7 days"),
            compression="gz",
            serialize=False
        )
        
        # Add error file handler
        error_log_file = logs_dir / "errors.log"
        logger.add(
            str(error_log_file),
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="1 week",
            retention="30 days",
            compression="gz"
        )
        
        # Add task execution log handler
        task_log_file = logs_dir / "tasks.log"
        logger.add(
            str(task_log_file),
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=lambda record: "task_name" in record["extra"],
            rotation="daily",
            retention="30 days",
            compression="gz"
        )
        
        self._configured = True
        logger.info("Logging system initialized")
    
    def get_task_logger(self, task_name: str):
        """Get a logger instance for a specific task"""
        return logger.bind(task_name=task_name)
    
    def log_system_info(self):
        """Log system information at startup"""
        import platform
        import psutil
        
        logger.info("=" * 50)
        logger.info("Task Scheduler Starting")
        logger.info("=" * 50)
        logger.info(f"Python version: {platform.python_version()}")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"CPU count: {psutil.cpu_count()}")
        logger.info(f"Memory: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
        logger.info("=" * 50)


def setup_logging_from_config(config_path: Path, logs_dir: Path) -> LoggingManager:
    """Setup logging from configuration file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        logging_config = config.get('logging', {})
        logging_manager = LoggingManager(logging_config)
        logging_manager.setup_logging(logs_dir)
        
        return logging_manager
        
    except Exception as e:
        # Fallback logging setup
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(logs_dir / "scheduler.log", rotation="daily", retention="7 days")
        logger.error(f"Failed to setup logging from config: {e}")
        
        return LoggingManager({})


class TaskLogger:
    """Context manager for task-specific logging"""
    
    def __init__(self, task_name: str, logging_manager: LoggingManager):
        self.task_name = task_name
        self.logging_manager = logging_manager
        self.logger = logging_manager.get_task_logger(task_name)
    
    def __enter__(self):
        self.logger.info(f"Task {self.task_name} starting")
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.info(f"Task {self.task_name} completed successfully")
        else:
            self.logger.error(f"Task {self.task_name} failed: {exc_val}")
        return False


def log_performance_metrics(func):
    """Decorator to log performance metrics for functions"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} completed in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    
    return wrapper


class StructuredLogger:
    """Structured logging helper for consistent log formatting"""
    
    @staticmethod
    def log_task_execution(task_name: str, status: str, duration: float, 
                          error: Optional[str] = None, **extra_fields):
        """Log task execution with structured data"""
        log_data = {
            "event": "task_execution",
            "task_name": task_name,
            "status": status,
            "duration": duration,
            **extra_fields
        }
        
        if error:
            log_data["error"] = error
        
        if status == "success":
            logger.info("Task execution completed", **log_data)
        else:
            logger.error("Task execution failed", **log_data)
    
    @staticmethod
    def log_scheduler_event(event_type: str, message: str, **extra_fields):
        """Log scheduler events with structured data"""
        log_data = {
            "event": "scheduler_event",
            "event_type": event_type,
            "message": message,
            **extra_fields
        }

        logger.debug("Scheduler event", **log_data)
    
    @staticmethod
    def log_system_metrics(metrics: Dict[str, Any]):
        """Log system metrics"""
        logger.info("System metrics", event="system_metrics", **metrics)
    
    @staticmethod
    def log_dependency_installation(package_name: str, version: str, 
                                   status: str, duration: float):
        """Log dependency installation"""
        log_data = {
            "event": "dependency_installation",
            "package": package_name,
            "version": version,
            "status": status,
            "duration": duration
        }
        
        if status == "success":
            logger.info("Package installed successfully", **log_data)
        else:
            logger.error("Package installation failed", **log_data)


# Global logging manager instance
_logging_manager: Optional[LoggingManager] = None


def get_logging_manager() -> Optional[LoggingManager]:
    """Get the global logging manager instance"""
    return _logging_manager


def set_logging_manager(manager: LoggingManager):
    """Set the global logging manager instance"""
    global _logging_manager
    _logging_manager = manager
