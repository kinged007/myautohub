"""
Test Task Scheduler installation and basic setup
"""

import pytest
import importlib.util
import yaml
from pathlib import Path


class TestInstallation:
    """Test installation and basic setup"""

    def test_required_dependencies(self):
        """Test that all required modules can be imported"""
        required_modules = [
            'schedule',
            'loguru', 
            'yaml',
            'psutil'
        ]
        
        for module_name in required_modules:
            try:
                __import__(module_name)
            except ImportError:
                pytest.fail(f"Required module '{module_name}' not available")

    def test_project_structure(self, project_root):
        """Test that project structure is correct"""
        required_dirs = [
            "task_scheduler",
            "tasks", 
            "config",
            "logs",
            "data",
            "scripts"
        ]
        
        required_files = [
            "main.py",
            "requirements.txt",
            "config/config.yaml",
            "task_scheduler/__init__.py",
            "task_scheduler/scheduler.py",
            "task_scheduler/task_parser.py",
            "task_scheduler/database.py"
        ]
        
        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists(), f"Required directory '{dir_name}' is missing"
            
        for file_name in required_files:
            file_path = project_root / file_name
            assert file_path.exists(), f"Required file '{file_name}' is missing"

    def test_task_scheduler_modules(self):
        """Test that task scheduler modules can be imported"""
        modules = [
            "task_scheduler.scheduler",
            "task_scheduler.task_parser", 
            "task_scheduler.database",
            "task_scheduler.venv_manager",
            "task_scheduler.memory_manager",
            "task_scheduler.decorators",
            "task_scheduler.logging_config"
        ]
        
        for module_name in modules:
            spec = importlib.util.find_spec(module_name)
            assert spec is not None, f"Module '{module_name}' not found"

    def test_config_file(self, config_path):
        """Test that config file is valid"""
        assert config_path.exists(), "Config file not found"
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        required_sections = ['scheduler', 'database', 'logging', 'virtual_env', 'tasks']
        
        for section in required_sections:
            assert section in config, f"Config section '{section}' is missing"

    def test_example_tasks(self, tasks_dir):
        """Test that example tasks are valid"""
        task_files = list(tasks_dir.glob("*.py"))
        assert len(task_files) > 0, "No task files found"
        
        for task_file in task_files:
            with open(task_file, 'r') as f:
                content = f.read()
            
            assert 'def start(' in content, f"Task {task_file.name} missing start function"
            assert '---' in content, f"Task {task_file.name} missing YAML frontmatter"
