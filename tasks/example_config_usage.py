"""
---
title: "Config Usage Example"
description: "Demonstrates how to use the config helper for task-specific settings"
dependencies: []
enabled: true
timeout: 300
---
"""

from task_scheduler.decorators import repeat, every
from helpers import load_config, get_config_value, save_config, log


@repeat(every(30).minutes)
def start():
    """Example task showing how to use config helper for task-specific settings"""
    log("Starting config usage example task")
    
    # Example 1: Load main config
    main_config = load_config()  # Loads config/config.yaml
    python_exe = main_config.get('virtual_env', {}).get('python_executable', 'python3')
    log(f"Python executable from main config: {python_exe}")
    
    # Example 2: Load task-specific config
    try:
        task_config = load_config("example_task.yaml")  # Loads config/example_task.yaml
        api_key = task_config.get('api_key', 'not-set')
        timeout = task_config.get('timeout', 30)
        log(f"Task config - API key: {api_key[:8]}..., timeout: {timeout}s")
    except Exception:
        log("Task-specific config not found, creating example...")
        
        # Create example task config
        example_config = {
            'api_key': 'your-secret-api-key-here',
            'timeout': 60,
            'endpoints': {
                'primary': 'https://api.example.com/v1',
                'backup': 'https://backup.example.com/v1'
            },
            'retry_attempts': 3,
            'debug_mode': False
        }
        
        if save_config(example_config, "example_task.yaml"):
            log("Created example task config at config/example_task.yaml")
        else:
            log("Failed to create example task config")
    
    # Example 3: Use get_config_value for specific values with defaults
    db_path = get_config_value("database.path", default="scheduler.db")
    log(f"Database path: {db_path}")
    
    # Example 4: Get task-specific values with dot notation
    primary_endpoint = get_config_value("endpoints.primary", "example_task.yaml", default="https://default.com")
    retry_attempts = get_config_value("retry_attempts", "example_task.yaml", default=1)
    log(f"Primary endpoint: {primary_endpoint}")
    log(f"Retry attempts: {retry_attempts}")
    
    # Example 5: Load secrets config (if it exists)
    try:
        secrets = load_config("secrets.yaml")  # Loads config/secrets.yaml
        if secrets:
            log("Secrets config loaded successfully")
            # Use secrets here (don't log actual secret values!)
        else:
            log("No secrets config found")
    except Exception:
        log("Secrets config not available")
    
    log("Config usage example completed")


if __name__ == "__main__":
    # For testing the task directly
    start()
