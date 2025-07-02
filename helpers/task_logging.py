"""
---
title: "Task Logging Helper"
description: "Easy-to-use logging utilities for tasks with automatic task name detection"
dependencies: []
enabled: true
timeout: 30
---
"""

import inspect
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict
from loguru import logger
import json

def get_calling_task_name() -> str:
    """
    Automatically detect the task name from the calling context.
    
    Returns:
        Task name extracted from the calling module
    """
    # Get the calling frame
    frame = inspect.currentframe()
    try:
        # Go up the call stack to find the task module
        while frame:
            frame = frame.f_back
            if frame and frame.f_globals.get('__name__'):
                module_name = frame.f_globals['__name__']
                
                # Check if this is a task module
                if module_name.startswith('task_') or 'tasks.' in module_name:
                    # Extract task name from module name
                    if 'tasks.' in module_name:
                        # Format: tasks.example_hello_world
                        return module_name.split('.')[-1]
                    elif module_name.startswith('task_'):
                        # Format: task_example_hello_world_123456
                        parts = module_name.split('_')
                        if len(parts) >= 3:
                            # Remove 'task_' prefix and timestamp suffix
                            return '_'.join(parts[1:-1])
                        else:
                            return module_name
        
        # Fallback: return unknown
        return "unknown_task"
    finally:
        del frame

def log(
    message: str,
    level: str = "INFO",
    task_name: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
) -> None:
    """
    Log a message with automatic task name detection and proper routing.
    
    Args:
        message: The log message
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        task_name: Task name (auto-detected if not provided)
        extra_data: Additional data to include in the log
        exception: Exception object to include traceback
    """
    # Auto-detect task name if not provided
    if task_name is None:
        task_name = get_calling_task_name()
    
    # Prepare log data
    log_data = {
        "task_name": task_name,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Add extra data if provided
    if extra_data:
        log_data.update(extra_data)
    
    # Create bound logger with task context
    task_logger = logger.bind(**log_data)
    
    # Format message with task context
    formatted_message = f"[{task_name}] {message}"
    
    # Add exception info if provided
    if exception:
        formatted_message += f" | Exception: {str(exception)}"
        if level.upper() in ["ERROR", "CRITICAL"]:
            formatted_message += f" | Traceback: {traceback.format_exc()}"
    
    # Log at appropriate level
    level_upper = level.upper()
    if level_upper == "DEBUG":
        task_logger.debug(formatted_message)
    elif level_upper == "INFO":
        task_logger.info(formatted_message)
    elif level_upper == "WARNING":
        task_logger.warning(formatted_message)
    elif level_upper == "ERROR":
        task_logger.error(formatted_message)
    elif level_upper == "CRITICAL":
        task_logger.critical(formatted_message)
    else:
        # Default to INFO for unknown levels
        task_logger.info(f"[{level}] {formatted_message}")

def log_debug(message: str, task_name: Optional[str] = None, **kwargs) -> None:
    """Log a debug message"""
    log(message, "DEBUG", task_name, kwargs)

def log_info(message: str, task_name: Optional[str] = None, **kwargs) -> None:
    """Log an info message"""
    log(message, "INFO", task_name, kwargs)

def log_warning(message: str, task_name: Optional[str] = None, **kwargs) -> None:
    """Log a warning message"""
    log(message, "WARNING", task_name, kwargs)

def log_error(
    message: str, 
    task_name: Optional[str] = None, 
    exception: Optional[Exception] = None,
    **kwargs
) -> None:
    """Log an error message with optional exception"""
    log(message, "ERROR", task_name, kwargs, exception)

def log_critical(
    message: str, 
    task_name: Optional[str] = None, 
    exception: Optional[Exception] = None,
    **kwargs
) -> None:
    """Log a critical message with optional exception"""
    log(message, "CRITICAL", task_name, kwargs, exception)

def log_task_start(task_name: Optional[str] = None, **kwargs) -> None:
    """Log task start with optional metadata"""
    if task_name is None:
        task_name = get_calling_task_name()
    log(f"Task started", "INFO", task_name, kwargs)

def log_task_complete(
    task_name: Optional[str] = None, 
    duration: Optional[float] = None,
    **kwargs
) -> None:
    """Log task completion with optional duration"""
    if task_name is None:
        task_name = get_calling_task_name()
    
    extra_data = kwargs.copy()
    if duration is not None:
        extra_data["duration_seconds"] = duration
        message = f"Task completed successfully in {duration:.2f}s"
    else:
        message = "Task completed successfully"
    
    log(message, "INFO", task_name, extra_data)

def log_task_error(
    error_message: str,
    task_name: Optional[str] = None,
    exception: Optional[Exception] = None,
    **kwargs
) -> None:
    """Log task error with exception details"""
    if task_name is None:
        task_name = get_calling_task_name()
    
    message = f"Task failed: {error_message}"
    log(message, "ERROR", task_name, kwargs, exception)

def log_execution_result(
    operation: str,
    success: bool,
    details: Optional[Dict[str, Any]] = None,
    task_name: Optional[str] = None
) -> None:
    """
    Log the result of an operation (e.g., external script execution, API call).
    
    Args:
        operation: Description of the operation
        success: Whether the operation succeeded
        details: Additional details about the operation
        task_name: Task name (auto-detected if not provided)
    """
    if task_name is None:
        task_name = get_calling_task_name()
    
    status = "SUCCESS" if success else "FAILED"
    message = f"{operation}: {status}"
    
    extra_data = {"operation": operation, "success": success}
    if details:
        extra_data.update(details)
    
    level = "INFO" if success else "ERROR"
    log(message, level, task_name, extra_data)

def log_structured_data(
    event_type: str,
    data: Dict[str, Any],
    task_name: Optional[str] = None,
    level: str = "INFO"
) -> None:
    """
    Log structured data for analysis and monitoring.
    
    Args:
        event_type: Type of event (e.g., "metric_collected", "notification_sent")
        data: Structured data to log
        task_name: Task name (auto-detected if not provided)
        level: Log level
    """
    if task_name is None:
        task_name = get_calling_task_name()
    
    # Create structured log entry
    log_entry = {
        "event_type": event_type,
        "task_name": task_name,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    # Log as JSON for easy parsing
    message = f"STRUCTURED_EVENT: {json.dumps(log_entry)}"
    log(message, level, task_name)

def create_task_logger(task_name: str):
    """
    Create a logger instance bound to a specific task name.
    
    Args:
        task_name: Name of the task
        
    Returns:
        Logger instance with task context
    """
    return logger.bind(task_name=task_name)

# Convenience aliases for common logging patterns
task_log = log
task_info = log_info
task_error = log_error
task_warning = log_warning
task_debug = log_debug
