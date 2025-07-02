"""
Task Scheduler Helper Modules

This package contains reusable helper functions for common task operations.
Each helper module has its own dependencies specified in YAML frontmatter.
"""

# Import commonly used functions for easy access
from .system_notifications import send_notification, send_and_log_notification, log_notification
from .external_execution import (
    execute_python_script, execute_cli_command,
    process_execution_results, execute_script_with_retry
)
from .task_logging import (
    log, log_info, log_error, log_warning, log_debug, log_critical,
    log_task_start, log_task_complete, log_task_error, log_execution_result,
    log_structured_data, create_task_logger, task_log, task_info, task_error
)

__all__ = [
    # System notifications
    'send_notification',
    'send_and_log_notification',
    'log_notification',

    # External execution
    'execute_python_script',
    'execute_cli_command',
    'process_execution_results',
    'execute_script_with_retry',

    # Task logging
    'log', 'log_info', 'log_error', 'log_warning', 'log_debug', 'log_critical',
    'log_task_start', 'log_task_complete', 'log_task_error', 'log_execution_result',
    'log_structured_data', 'create_task_logger', 'task_log', 'task_info', 'task_error'
]
