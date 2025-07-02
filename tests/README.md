# Task Scheduler Tests

This directory contains pytest-compatible tests for the Task Scheduler project.

## Running Tests

### Quick Start
```bash
# Run all tests
python scripts/run_tests.py

# Run specific test file
python scripts/run_tests.py tests/test_installation.py

# Run tests with coverage
python scripts/run_tests.py --coverage

# Skip slow tests
python scripts/run_tests.py --fast
```

### Direct pytest usage
```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_cron_scheduling.py

# Run with verbose output
pytest -v

# Skip slow tests
pytest -m "not slow"
```

## Test Structure

- `test_installation.py` - Tests basic installation and project structure
- `test_cron_scheduling.py` - Tests cron-like scheduling functionality  
- `test_overdue_tasks.py` - Tests overdue task detection and handling
- `test_basic_functionality.py` - Tests basic scheduler functionality
- `conftest.py` - Pytest configuration and shared fixtures

## Test Markers

- `@pytest.mark.slow` - Marks tests that take longer to run
- `@pytest.mark.integration` - Marks integration tests
- `@pytest.mark.unit` - Marks unit tests

## Fixtures

Available fixtures from `conftest.py`:
- `project_root` - Path to project root directory
- `db_path` - Path to scheduler database
- `tasks_dir` - Path to tasks directory
- `config_path` - Path to configuration file

## Writing New Tests

When adding new tests:

1. Follow the naming convention `test_*.py`
2. Use descriptive test class names like `TestFeatureName`
3. Use descriptive test method names like `test_specific_behavior`
4. Add appropriate markers for slow or integration tests
5. Use fixtures for common setup/teardown
6. Include docstrings explaining what the test validates

Example:
```python
class TestNewFeature:
    """Test new feature functionality"""
    
    def test_specific_behavior(self, project_root):
        """Test that specific behavior works correctly"""
        # Test implementation
        assert expected_result == actual_result
```
