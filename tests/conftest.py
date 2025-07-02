"""
Pytest configuration and fixtures for Task Scheduler tests
"""

import sys
import pytest
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))


@pytest.fixture
def project_root():
    """Fixture providing the project root directory"""
    return project_dir


@pytest.fixture
def db_path(project_root):
    """Fixture providing the database path"""
    return project_root / "data" / "data" / "scheduler.db"


@pytest.fixture
def tasks_dir(project_root):
    """Fixture providing the tasks directory"""
    return project_root / "tasks"


@pytest.fixture
def config_path(project_root):
    """Fixture providing the config file path"""
    return project_root / "config" / "config.yaml"
