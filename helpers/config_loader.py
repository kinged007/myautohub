"""
---
title: "Configuration Loader Helper"
description: "Centralized configuration loading for tasks and scripts"
dependencies: []
enabled: true
---
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def get_project_root() -> Path:
    """Get the project root directory"""
    # This helper is in helpers/, so project root is parent directory
    return Path(__file__).parent.parent


def load_config(config_name: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file in the config directory.
    
    Args:
        config_name: Name of the config file (e.g., "config.yaml", "secrets.yaml", "task_config.yaml")
                    The file will be looked for in the config/ directory
    
    Returns:
        Dictionary containing the configuration data
        
    Examples:
        # Load main config
        config = load_config()  # Loads config/config.yaml
        
        # Load task-specific config
        task_config = load_config("my_task.yaml")  # Loads config/my_task.yaml
        
        # Load secrets config
        secrets = load_config("secrets.yaml")  # Loads config/secrets.yaml
    """
    project_root = get_project_root()
    config_path = project_root / "config" / config_name
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                config_data = {}
            return config_data
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        # Return minimal fallback config
        return {
            "database": {"path": "scheduler.db"},
            "virtual_env": {"python_executable": "python3"}
        }
    except Exception as e:
        print(f"Failed to load config from {config_path}: {e}")
        # Return minimal fallback config
        return {
            "database": {"path": "scheduler.db"},
            "virtual_env": {"python_executable": "python3"}
        }


def get_config_value(key_path: str, config_name: str = "config.yaml", default: Any = None) -> Any:
    """
    Get a specific configuration value using dot notation.
    
    Args:
        key_path: Dot-separated path to the config value (e.g., "database.path", "virtual_env.python_executable")
        config_name: Name of the config file to load
        default: Default value to return if key is not found
        
    Returns:
        The configuration value or default if not found
        
    Examples:
        # Get database path
        db_path = get_config_value("database.path")
        
        # Get Python executable with default
        python_exe = get_config_value("virtual_env.python_executable", default="python3")
        
        # Get task-specific setting
        api_key = get_config_value("api.key", "secrets.yaml")
    """
    config = load_config(config_name)
    
    # Navigate through nested dictionary using dot notation
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


def save_config(config_data: Dict[str, Any], config_name: str = "config.yaml") -> bool:
    """
    Save configuration data to a YAML file in the config directory.
    
    Args:
        config_data: Dictionary containing configuration data to save
        config_name: Name of the config file to save to
        
    Returns:
        True if successful, False otherwise
        
    Examples:
        # Save updated config
        config = load_config()
        config['new_setting'] = 'value'
        save_config(config)
        
        # Save task-specific config
        task_config = {'api_key': 'secret', 'timeout': 30}
        save_config(task_config, "my_task.yaml")
    """
    project_root = get_project_root()
    config_path = project_root / "config" / config_name
    
    try:
        # Ensure config directory exists
        config_path.parent.mkdir(exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.safe_dump(config_data, f, default_flow_style=False, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save config to {config_path}: {e}")
        return False


def list_config_files() -> list:
    """
    List all YAML configuration files in the config directory.
    
    Returns:
        List of config file names
    """
    project_root = get_project_root()
    config_dir = project_root / "config"
    
    if not config_dir.exists():
        return []
    
    return [f.name for f in config_dir.glob("*.yaml") if f.is_file()]
