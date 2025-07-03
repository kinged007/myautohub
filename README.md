# Task Scheduler

A robust Python background task management system that automatically handles dependencies, scheduling, overdue handling and execution of tasks with built-in memory management and monitoring.

Super simple example task:

```python
"""
---
title: "Hello World Task"
description: "A simple example task"
dependencies: []
enabled: true
timeout: 60
---
"""

from task_scheduler.decorators import repeat, every
from helpers import log_task_start, log_task_complete, log_info

@repeat(every(10).minutes)
def start():
    """This function will be called every 10 minutes at clock boundaries"""
    log_info("Hello from scheduled task!") # Logs to logs/tasks.log with [Hello World Task] prefix
```

Comes with more built in example tasks to get you started.


## Features

- **Cron-like Scheduling**: Tasks run at clock boundaries (e.g., every 5 minutes at :00, :05, :10) instead of relative intervals
- **Automatic Dependency Management**: Tasks specify their own Python package requirements in frontmatter
- **Dynamic Task Loading**: Automatically discovers and loads new task files without restart
- **Flexible Configuration Management**: Centralized config system with task-specific configs and secrets management
- **Memory Management**: Built-in memory cleanup and monitoring to prevent memory leaks
- **Database Tracking**: SQLite database tracks execution history and handles missed schedules
- **Comprehensive Logging**: Structured logging with rotation and task-specific logs
- **Hybrid Scheduling System**: Combines cron-like precision with overdue task detection
- **Frontmatter Task Configuration**: YAML frontmatter in docstrings for IDE compatibility
- **Hot Configuration Reloading**: Config changes applied automatically without restart

## Project Structure

High level overview of project structure:

```
task-scheduler/
├── task_scheduler/          # Core scheduler package
├── tasks/                   # Directory for task files
├── helpers/                 # Reusable helper modules with dependencies
│   ├── __init__.py          # Helper module imports
│   ├── config_loader.py     # Configuration management
│   ├── system_notifications.py  # Cross-platform notifications
│   ├── external_execution.py    # External script/command execution
│   ├── task_logging.py      # Task logging utilities
│   └── ...                  # More helper modules
├── config/                  # Configuration files
│   └── config.yaml
├── logs/                    # Log files
├── data/                    # Database and data files
├── scripts/                 # Setup and utility scripts
│   ├── install.sh           # Installation script (Linux only)
│   ├── setup_cron.sh        # Cron setup script (Linux/macOS)
│   ├── run_scheduler.sh     # Wrapper script for cron (auto-generated from setup_cron.sh)
│   ├── reset_schedules.py   # Database schedule reset utility
│   ├── restart_scheduler.py # Advanced process management script
│   ├── rotate_logs.sh       # Log rotation script (auto-generated from setup_cron.sh)
│   ├── monitor_scheduler.sh # Automatic scheduler monitoring and restart (auto-generated from setup_cron.sh)
│   └── run_tests.py         # Test runner script
├── tests/                   # Pytest test suite
│   ├── ...                  # Test files
│   └── README.md            # Testing documentation
├── main.py                  # Main entry point
├── requirements.txt         # Python dependencies
├── pytest.ini              # Pytest configuration
└── README.md
```

## Installation

### Option 1: Systemd Service (Recommended for Linux)

1. **Clone or download the project**:
   ```bash
   git clone <repository-url>
   cd task-scheduler
   ```

2. **Run the installation script** (requires root):
   ```bash
   sudo ./scripts/install.sh
   ```

3. **Start the service**:
   ```bash
   sudo systemctl start task-scheduler
   sudo systemctl status task-scheduler
   ```

### Option 2: Cron Job Setup (Recommended for macOS/Windows)

1. **Setup the project**:
   ```bash
   git clone <repository-url>
   cd task-scheduler
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the cron setup script**:
   ```bash
   ./scripts/setup_cron.sh
   ```

   This creates:
   - `monitor_scheduler.sh` - Automatic scheduler monitoring and restart
   - `restart_scheduler.py` - Advanced process management script
   - `rotate_logs.sh` - Log rotation script

3. **Follow the instructions** to add cron entries for automatic monitoring.

### Option 3: Manual Setup

1. **Install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the scheduler**:
   ```bash
   python main.py --config config/config.yaml
   ```

## Creating Tasks

Tasks are Python files placed in the `tasks/` directory. Each task file includes YAML frontmatter to specify dependencies and metadata, and a `start()` function to define the task logic.

### Frontmatter Format

The task system supports YAML frontmatter at the top of the task file, either wrapped in a docstring or as a standalone block:

#### Option 1: Python-syntax-correct (Recommended)
```python
"""
---
title: "Hello World Task"
description: "A simple example task"
dependencies:
  - "requests>=2.25.0"
  - "beautifulsoup4==4.9.3"
enabled: true
timeout: 300
---
"""

from task_scheduler.decorators import repeat, every
import requests

@repeat(every(10).minutes)
def start():
    """This function will be called every 10 minutes at clock boundaries"""
    print("Hello from scheduled task!")

    # Your task logic here
    response = requests.get("https://httpbin.org/json")
    print(f"Response status: {response.status_code}")
```

#### Option 2: Traditional YAML frontmatter
```python
---
title: "Hello World Task"
description: "A simple example task"
dependencies:
  - "requests>=2.25.0"
  - "beautifulsoup4==4.9.3"
enabled: true
timeout: 300
---

from task_scheduler.decorators import repeat, every
import requests

@repeat(every(10).minutes)
def start():
    """This function will be called every 10 minutes at clock boundaries"""
    print("Hello from scheduled task!")

    # Your task logic here
    response = requests.get("https://httpbin.org/json")
    print(f"Response status: {response.status_code}")
```

> **Note**: The Python-syntax-correct format (Option 1) is recommended as it allows the task files to be valid Python modules that can be imported and tested independently, as well as pass python linters in IDEs.


### YAML Frontmatter Reference

The frontmatter uses **YAML format** and supports the following fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | filename | Task display name |
| `description` | string | "" | Task description |
| `dependencies` | list | [] | Python packages to install (pip format) |
| `python_version` | string | "3.8" | Minimum Python version |
| `enabled` | boolean | true | Whether task is active |
| `timeout` | integer | 300 | Task timeout in seconds |
| `retry_count` | integer | 0 | Number of retries on failure |
| `retry_delay` | integer | 60 | Delay between retries in seconds |

### Dependency Specification

Dependencies follow standard pip requirement format:

```yaml
dependencies:
  - "requests>=2.25.0"           # Minimum version
  - "beautifulsoup4==4.9.3"      # Exact version
  - "pandas>=1.3.0,<2.0.0"       # Version range
  - "python-dateutil>=2.8.0"     # Package with hyphens
  - "plyer>=2.1.0"               # Cross-platform notifications
```

### Frontmatter Validation

The task parser validates:
- ✅ **YAML syntax**: Must be valid YAML format
- ✅ **Required fields**: `title` and `description` are recommended
- ✅ **Data types**: Fields must match expected types
- ✅ **Python syntax**: When using docstring format, file must be valid Python

## Configuration

Edit `config/config.yaml` to customize the scheduler behavior:

```yaml
scheduler:
  loop_interval: 10          # Main loop interval (seconds)
  task_check_interval: 5     # Task file scan interval (seconds)
  memory_cleanup_interval: 300  # Memory cleanup interval (seconds)
  max_memory_usage: 500      # Max memory usage in MB before restart

database:
  path: "data/scheduler.db"
  backup_interval: 3600      # Database backup interval (seconds)

logging:
  level: "INFO"              # Log level (DEBUG, INFO, WARNING, ERROR)
  file: "scheduler.log"
  max_size: "10 MB"
  retention: "7 days"
  rotation: "daily"

virtual_env:
  path: "venv"
  python_executable: "python3"

tasks:
  directory: "tasks"
  file_pattern: "*.py"
  reload_on_change: true
  include_example_tasks: false   # Include tasks prefixed with 'example_'
```

### Example Tasks

The scheduler includes several example tasks (prefixed with `example_`) that demonstrate various features:

- `example_hello_world.py` - Basic task with simple logging
- `example_web_scraper.py` - Web scraping with requests
- `example_daily_cleanup.py` - Daily maintenance operations
- `example_system_monitor.py` - System monitoring and alerts
- `example_external_execution.py` - External script execution
- `example_system_notification.py` - Cross-platform notifications
- `example_config_usage.py` - Configuration management and task-specific configs
- `example_helper_showcase.py` - Comprehensive helper system demonstration

**Configuration**: Set `include_example_tasks: true` in `config/config.yaml` to enable example tasks, or `false` to ignore them. This is useful for:

- **Development**: Enable examples to test scheduler functionality
- **Production**: Disable examples to run only your custom tasks
- **Learning**: Study example implementations for best practices

## Configuration Management

The scheduler includes a centralized configuration system that allows tasks to load their own configuration files for secrets and task-specific settings.

### Config Helper

Use the config helper to manage configurations in your tasks with simple imports:

```python
# Simple import from helpers package
from helpers import load_config, get_config_value, save_config, log

# Load main configuration
config = load_config()  # Loads config/config.yaml

# Load task-specific configuration
task_config = load_config("my_task.yaml")  # Loads config/my_task.yaml

# Get specific values with dot notation and defaults
api_key = get_config_value("api.key", "secrets.yaml", default="not-set")
timeout = get_config_value("timeout", "my_task.yaml", default=30)

# Save configuration
new_config = {"setting": "value"}
save_config(new_config, "my_task.yaml")
```

**Available Functions:**
- `load_config(config_name)` - Load any YAML config from config/ directory
- `get_config_value(key_path, config_name, default)` - Get values using dot notation
- `save_config(config_data, config_name)` - Save configuration data
- `list_config_files()` - List all available config files
- `get_project_root()` - Get the project root directory


### Secrets Management

1. **Copy the example**: `cp config/secrets.yaml.example config/secrets.yaml`
2. **Add your secrets** to `config/secrets.yaml`
3. **Load in tasks**:
   ```python
   secrets = load_config("secrets.yaml")
   api_key = secrets.get("api_keys", {}).get("openai")
   ```

The `secrets.yaml` file is automatically excluded from git commits.

## Helper System

The scheduler includes a comprehensive helper system that provides reusable functions for common task operations. All helpers are available through simple imports:

```python
# Import everything you need from the helpers package
from helpers import (
    # Configuration management
    load_config, get_config_value, save_config,

    # Logging
    log, log_info, log_error, log_warning,

    # System notifications
    send_notification, send_and_log_notification,

    # External execution
    execute_python_script, execute_cli_command
)
```

### Available Built-in Helpers

- **Configuration Management** (`config_loader.py`):
  - Centralized config loading with task-specific configs
  - Secrets management and dot notation access
  - Automatic fallbacks and error handling

- **Task Logging** (`task_logging.py`):
  - Structured logging with automatic task name detection
  - Multiple log levels and task-specific log files
  - Execution result logging and error handling

- **System Notifications** (`system_notifications.py`):
  - Cross-platform desktop notifications
  - Integration with logging system
  - Configurable notification settings

- **External Execution** (`external_execution.py`):
  - Execute Python scripts and CLI commands
  - Retry mechanisms and timeout handling
  - Result processing and error capture

Each helper manages its own dependencies automatically, so you only install what you use.

## Usage

### Command Line Options

```bash
# Run scheduler
python main.py

# Run with custom config
python main.py --config /path/to/config.yaml

# Run as daemon (Linux only)
python main.py --daemon

# Show status
python main.py --status
```

### Process Management

The scheduler includes advanced process management features for production use:

#### Restart Script

```bash
# Restart the scheduler (graceful shutdown + start)
python scripts/restart_scheduler.py

# Restart with custom timeout
python scripts/restart_scheduler.py --timeout 15

# Force restart if graceful shutdown fails
python scripts/restart_scheduler.py --force

# Check what would happen without making changes
python scripts/restart_scheduler.py --dry-run

# Start as daemon process
python scripts/restart_scheduler.py --daemon
```

#### Hot Configuration Reloading

The scheduler automatically detects and applies configuration changes without restart:

- **Config file monitoring**: Checks `config/config.yaml` every 5 seconds
- **Memory limit updates**: Changes to `max_memory_usage` are applied immediately
- **Directory changes**: Task directory changes are detected and applied

#### Process Identification

The scheduler runs with a recognizable process name for easy management:

```bash
# Check if scheduler is running
ps aux | grep myautohub-scheduler

# Find scheduler process ID
pgrep -f myautohub-scheduler

# Using built-in script
python scripts/restart_scheduler.py --dry-run
```

### Systemd Commands (if installed as service)

```bash
# Start service
sudo systemctl start task-scheduler

# Stop service
sudo systemctl stop task-scheduler

# Restart service
sudo systemctl restart task-scheduler

# Check status
sudo systemctl status task-scheduler

# View logs
sudo journalctl -u task-scheduler -f

# Enable auto-start on boot
sudo systemctl enable task-scheduler
```

### Monitoring

#### Automated Monitoring

Use the monitoring script for automatic scheduler management:

```bash
# Check and start scheduler if not running
bash scripts/monitor_scheduler.sh

# Set up cron job for automatic monitoring (every 5 minutes)
*/5 * * * * /path/to/scripts/monitor_scheduler.sh
```

The monitoring script:
- Detects if scheduler is running using process name
- Automatically starts scheduler if stopped
- Uses the restart script for reliable startup
- Logs all activities to `logs/monitor.log`

#### Log Files

- `logs/scheduler.log` - Main scheduler logs
- `logs/tasks.log` - Task execution logs
- `logs/errors.log` - Error logs only
- `logs/monitor.log` - Monitoring script logs

#### Database

The SQLite database (`data/scheduler.db`) contains:
- Task execution history
- Next run times
- Scheduler state

#### Memory Usage

The scheduler automatically monitors memory usage and will restart if it exceeds the configured limit.

## Scheduling System

The scheduler uses a **hybrid cron-like scheduling system** that combines precision timing with overdue task detection.

### Cron-like Scheduling

Tasks run at **clock boundaries** instead of relative intervals:

```python
from task_scheduler.decorators import repeat, every

# Every N minutes - runs at clock boundaries
@repeat(every(5).minutes)   # Runs at :00, :05, :10, :15, :20, etc.
@repeat(every(10).minutes)  # Runs at :00, :10, :20, :30, :40, :50
@repeat(every(30).minutes)  # Runs at :00, :30

# Every N hours - runs at hour boundaries
@repeat(every(2).hours)     # Runs at 00:00, 02:00, 04:00, etc.
@repeat(every(6).hours)     # Runs at 00:00, 06:00, 12:00, 18:00

# Daily tasks - runs at specific times
@repeat(every(1).day)       # Runs at 00:00 daily
```

### Traditional Schedule Library Support

The scheduler uses the [schedule](https://schedule.readthedocs.io/en/stable/) library for traditional scheduling patterns.

For more complex scheduling patterns:

```python
# At specific times (uses traditional schedule library)
@repeat(every().day.at("10:30"))        # Daily at 10:30 AM
@repeat(every().monday.at("09:00"))     # Every Monday at 9:00 AM
@repeat(every().hour.at(":15"))         # 15 minutes past every hour
```

### Key Benefits of Cron-like Scheduling

- ✅ **Predictable timing**: Tasks run at exact clock boundaries
- ✅ **System alignment**: Multiple instances stay synchronized
- ✅ **Resource efficiency**: Avoids drift and timing conflicts
- ✅ **Monitoring friendly**: Easy to predict when tasks will run


## Testing

The project includes a comprehensive pytest test suite to ensure reliability and functionality.

### Running Tests

```bash
# Run all tests
python scripts/run_tests.py

# Run specific test file
python scripts/run_tests.py tests/test_installation.py

# Run with coverage reporting
python scripts/run_tests.py --coverage

# Skip slow tests (for quick validation)
python scripts/run_tests.py --fast

# Direct pytest usage
pytest -v
pytest -m "not slow"
```

For detailed testing documentation, see [tests/README.md](tests/README.md).

## Database Management

### Reset Schedule Database

The `reset_schedules.py` utility allows you to reset task schedules to clear overdue backlogs or prepare for testing:

```bash
# Preview what would be reset (dry run)
python scripts/reset_schedules.py --dry-run

# Reset only overdue tasks to future times
python scripts/reset_schedules.py --future-only

# Reset specific task
python scripts/reset_schedules.py --task example_hello_world

# Reset multiple specific tasks
python scripts/reset_schedules.py --task task1 --task task2

# Reset all tasks
python scripts/reset_schedules.py --all
```

**Use Cases:**
- Clear overdue task backlog after system downtime
- Reset schedules for development/testing
- Reschedule tasks after maintenance windows
- Fix problematic task schedules

The script intelligently calculates next run times based on each task's schedule configuration and maintains proper clock boundary alignment.

## Recent Updates

### v0.2.0 (2025-07-02)

- Overdue tasks now properly execute when detected
- Fixed job matching logic for CronLikeJob objects
- Comprehensive testing infrastructure
- Smart schedule reset tool with dry-run support
- Moved tests to dedicated directory with proper organization
- Updated README with testing and database management sections

### v0.1.0 (2025-07-01)

- Initial release with core functionality
- Cron-like scheduling system
- YAML frontmatter for task metadata
- Automatic dependency management
- Dynamic task loading and unloading
- Memory management and cleanup
- SQLite database for execution tracking
- Virtual environment isolation
- Comprehensive logging system
- CLI and systemd service support

## Troubleshooting

### Common Issues

1. **Task not running**: Check logs for errors, verify task file syntax
2. **Dependencies not installing**: Check virtual environment permissions
3. **High memory usage**: Reduce `memory_cleanup_interval` or `max_memory_usage`
4. **Tasks not detected**: Verify file is in `tasks/` directory with `.py` extension and YAML frontmatter
5. **Overdue tasks not executing**: Use `python scripts/reset_schedules.py --dry-run` to check schedules
6. **Test failures**: Run `python scripts/run_tests.py --verbose` for detailed test output

### Debug Mode

Enable debug logging in `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"
```

### Manual Task Testing

Test a task manually:

```bash
cd /path/to/task-scheduler
source venv/bin/activate

# Method 1: Direct import (works with Python-syntax frontmatter)
python -c "
import sys
sys.path.append('.')
import tasks.your_task_file as task
task.start()
"

# Method 2: Test individual functions
python -c "
import sys
sys.path.append('.')
from tasks.example_system_notification import send_notification
result = send_notification('Test', 'Hello from manual test!')
print(f'Notification result: {result}')
"

# Method 3: Syntax validation
python -m py_compile tasks/your_task_file.py

# Method 4: Run automated tests
python scripts/run_tests.py tests/test_installation.py
```

## Security Considerations

- Run as dedicated user (not root)
- Restrict file permissions on task files
- Validate task file contents before deployment
- Monitor log files for suspicious activity
- Use virtual environment isolation

## Helper Modules

The task scheduler includes a modular helper system for common operations. Helper modules are located in the `helpers/` directory and have their own dependencies specified in YAML frontmatter.

### Available Helpers

#### System Notifications (`helpers/system_notifications.py`)
Cross-platform system notification utilities:

```python
from helpers import send_notification, send_and_log_notification

# Send a simple notification
result = send_notification(
    title="Task Complete",
    message="Your task finished successfully!",
    timeout=5,
    urgency="normal"
)

# Send and automatically log notification
result = send_and_log_notification(
    title="Status Update",
    message="System is running normally",
    log_dir="data"
)
```

**Dependencies**: `plyer>=2.1.0` (automatically installed)

#### External Execution (`helpers/external_execution.py`)
Execute external Python scripts and CLI commands:

```python
from helpers import execute_python_script, execute_cli_command, process_execution_results

# Execute a Python script
result = execute_python_script(
    script_path="/path/to/script.py",
    args=["arg1", "arg2"],
    cwd="/working/directory",
    timeout=60
)

# Execute CLI commands
result = execute_cli_command(
    command="git status --porcelain",
    cwd="/repo/path"
)

# Process multiple execution results
summary = process_execution_results([result1, result2, result3])
```

**Dependencies**: None (uses standard library)


#### Task Logging (`helpers/task_logging.py`)
Easy-to-use logging utilities with automatic task name detection:

```python
from helpers import log_info, log_error, log_task_start, log_task_complete

@repeat(every(5).minutes)
def start():
    log_task_start()  # Automatically detects task name

    log_info("Processing data...")

    try:
        # Your task logic here
        result = process_data()
        log_info(f"Processed {result['count']} items")

    except Exception as e:
        log_error("Failed to process data", exception=e)
        raise

    log_task_complete(duration=5.2)
```

**Key Features**:
- ✅ **Automatic task detection**: No need to specify task names
- ✅ **Structured logging**: JSON-formatted logs for easy parsing
- ✅ **Error tracking**: Automatic exception capture with tracebacks
- ✅ **Execution results**: Log operation outcomes with details
- ✅ **Multiple log files**: Separate logs for tasks and errors

**Available Functions**:
- `log_info()`, `log_error()`, `log_warning()`, `log_debug()`
- `log_task_start()`, `log_task_complete()`, `log_task_error()`
- `log_execution_result()`, `log_structured_data()`

**Log Files**:
- `logs/tasks.log`: All task-specific logs with `[task_name]` prefix
- `logs/errors.log`: Error logs from tasks and system issues
- `logs/scheduler.log`: General scheduler operation logs


## Quick Reference

### Task File Template

```python
"""
---
title: "My Task"
description: "Description of what this task does"
dependencies:
  - "requests>=2.25.0"
enabled: true
timeout: 300
---
"""

from task_scheduler.decorators import repeat, every
from datetime import datetime

@repeat(every(5).minutes)  # Runs at :00, :05, :10, :15, etc.
def start():
    """Main task function - called by scheduler"""
    print(f"Task executed at {datetime.now()}")
    # Your task logic here
```

### Common Scheduling Patterns

```python
# Every minute (high frequency monitoring)
@repeat(every(1).minutes)

# Every 5 minutes (regular checks)
@repeat(every(5).minutes)

# Every 30 minutes (periodic updates)
@repeat(every(30).minutes)

# Every hour (hourly processing)
@repeat(every(1).hours)

# Every day (daily maintenance)
@repeat(every(1).day)
```

### Utility Commands

```bash
# Testing
python scripts/run_tests.py                    # Run all tests
python scripts/run_tests.py --fast             # Skip slow tests
python scripts/run_tests.py --coverage         # With coverage

# Database Management
python scripts/reset_schedules.py --dry-run    # Preview schedule reset
python scripts/reset_schedules.py --future-only # Reset overdue tasks only
python scripts/check_overdue.py                # Check current overdue tasks

# Process Management
python scripts/restart_scheduler.py --dry-run  # Check scheduler status
python scripts/restart_scheduler.py            # Restart scheduler

# Run Scheduler Directly
python main.py --config config/config.yaml     # Run scheduler in foreground
sh scripts/run_scheduler.sh                    # Run scheduler in foreground via script

# Debugging
python scripts/debug_jobs.py                   # Debug job registration
tail -f logs/scheduler.log                     # Monitor scheduler logs
tail -f logs/tasks.log                         # Monitor task execution
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `python scripts/run_tests.py`
5. Run tests with coverage: `python scripts/run_tests.py --coverage`
6. Submit a pull request

### Development Setup

```bash
# Clone and setup
git clone <repository-url>
cd task-scheduler
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests to verify setup
python scripts/run_tests.py

# Run scheduler in development mode
python main.py --config config/config.yaml
```

## License

MIT License - see LICENSE file for details.
