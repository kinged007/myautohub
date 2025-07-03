"""
---
title: "Helper System Showcase"
description: "Demonstrates the power of the simplified helper import system"
dependencies: []
enabled: true
timeout: 300
---
"""

from task_scheduler.decorators import repeat, every
# Import everything you need from helpers with one simple import
from helpers import (
    load_config, get_config_value, save_config,
    log, log_info, log_error, log_warning,
    send_notification, execute_cli_command
)


@repeat(every(1).hour)
def start():
    """Showcase task demonstrating the power of the helper system"""
    log("🚀 Starting Helper System Showcase")
    
    # 1. Configuration Management
    log_info("📋 Configuration Management:")
    
    # Load main config
    config = load_config()
    python_exe = get_config_value('virtual_env.python_executable', default='python3')
    log(f"   Python executable: {python_exe}")
    
    # Get database path with fallback
    db_path = get_config_value('database.path', default='scheduler.db')
    log(f"   Database path: {db_path}")
    
    # 2. External Command Execution
    log_info("⚡ External Command Execution:")
    
    try:
        # Execute a simple command
        result = execute_cli_command("echo 'Hello from helper system!'")
        if result['success']:
            log(f"   Command output: {result['stdout'].strip()}")
        else:
            log_error(f"   Command failed: {result['error']}")
    except Exception as e:
        log_error(f"   Execution error: {e}")
    
    # 3. System Information
    log_info("💻 System Information:")
    
    try:
        # Get system info using helper
        uptime_result = execute_cli_command("uptime")
        if uptime_result['success']:
            log(f"   System uptime: {uptime_result['stdout'].strip()}")
    except Exception:
        log_warning("   Could not get system uptime")
    
    # 4. Configuration Saving Example
    log_info("💾 Configuration Management:")
    
    # Create a simple task config
    task_config = {
        'last_run': str(datetime.now()),
        'run_count': get_config_value('run_count', 'helper_showcase.yaml', default=0) + 1,
        'status': 'active'
    }
    
    # Save the config
    if save_config(task_config, 'helper_showcase.yaml'):
        log(f"   Saved config: Run #{task_config['run_count']}")
    else:
        log_error("   Failed to save task config")
    
    # 5. Notification (optional - only if enabled)
    try:
        notification_enabled = get_config_value('notifications.enabled', default=False)
        if notification_enabled:
            log_info("🔔 Sending notification:")
            send_notification(
                title="Helper Showcase Complete",
                message=f"Task completed successfully on run #{task_config['run_count']}",
                timeout=5
            )
            log("   Notification sent!")
        else:
            log("   Notifications disabled in config")
    except Exception as e:
        log_warning(f"   Notification failed: {e}")
    
    # 6. List available configs
    log_info("📁 Available Configuration Files:")
    try:
        from helpers import list_config_files
        config_files = list_config_files()
        for config_file in config_files:
            log(f"   - {config_file}")
    except Exception as e:
        log_error(f"   Could not list config files: {e}")
    
    log("✅ Helper System Showcase completed successfully!")


# Import datetime for the config example
from datetime import datetime


if __name__ == "__main__":
    # For testing the task directly
    start()
