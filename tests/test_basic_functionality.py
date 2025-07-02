"""
Test basic Task Scheduler functionality
"""

import pytest
import subprocess


class TestBasicFunctionality:
    """Test basic scheduler functionality"""

    def test_virtual_environment_exists(self, project_root):
        """Test that virtual environment exists and is properly configured"""
        venv_dir = project_root / "venv"
        assert venv_dir.exists(), "Virtual environment directory not found"
        
        # Check if required packages are available
        result = subprocess.run(
            ["bash", "-c", "source venv/bin/activate && pip list"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, "Failed to activate virtual environment"
        assert "schedule" in result.stdout, "schedule package not installed"
        assert "loguru" in result.stdout, "loguru package not installed"

    def test_database_creation(self, project_root):
        """Test that database is created when scheduler runs"""
        # The actual database path is data/data/scheduler.db due to config path construction
        db_file = project_root / "data" / "data" / "scheduler.db"

        # Remove database if it exists
        if db_file.exists():
            db_file.unlink()

        # Run scheduler briefly using Python's signal handling
        import signal
        import os

        # Start scheduler process
        process = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && python main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
        )

        # Wait a bit for scheduler to start and create database
        import time
        time.sleep(3)

        # Terminate the process group
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            # Force kill if needed
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

        # Database should be created
        assert db_file.exists(), f"Database file was not created at {db_file}"

    def test_log_file_creation(self, project_root):
        """Test that log files are created"""
        log_file = project_root / "logs" / "scheduler.log"

        # Run scheduler briefly using signal handling (macOS compatible)
        import signal
        import os
        import time

        process = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && python main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        time.sleep(2)  # Wait for log creation

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        
        # Log file should be created
        assert log_file.exists(), "Log file was not created"
        
        # Check log content
        with open(log_file, 'r') as f:
            log_content = f.read()
        
        assert "Task Scheduler Starting" in log_content, "Expected log content not found"

    def test_task_loading(self, project_root):
        """Test that tasks are loaded successfully"""
        log_file = project_root / "logs" / "scheduler.log"

        # Run scheduler briefly using signal handling (macOS compatible)
        import signal
        import os
        import time

        process = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && python main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        time.sleep(3)  # Wait for task loading

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        
        # Check if tasks were loaded
        if log_file.exists():
            with open(log_file, 'r') as f:
                log_content = f.read()
            
            # Should see task registration messages
            assert "registered with scheduler" in log_content, "No tasks were registered"
            
            # Should see specific example tasks
            example_tasks = ["example_hello_world", "shutdown_reminder"]
            for task in example_tasks:
                if f"Loading task: {task}" in log_content:
                    assert f"Task {task} registered with scheduler" in log_content, f"Task {task} failed to register"

    @pytest.mark.slow
    def test_scheduler_runs_without_errors(self, project_root):
        """Test that scheduler can run for a short period without errors"""
        # Run scheduler for a few seconds using signal handling
        import signal
        import os
        import time

        process = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && python main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        time.sleep(5)  # Run for 5 seconds

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            _, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                _, stderr = process.communicate(timeout=1)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                stderr = b""

        # Check for critical errors in stderr
        stderr_text = stderr.decode('utf-8', errors='ignore')
        critical_errors = ["Traceback", "Error:", "Exception:", "CRITICAL"]
        for error in critical_errors:
            assert error not in stderr_text, f"Critical error found in stderr: {stderr_text}"

    def test_config_loading(self, project_root):
        """Test that configuration is loaded properly"""
        # This is tested indirectly by checking if scheduler starts without config errors
        import signal
        import os
        import time

        process = subprocess.Popen(
            ["bash", "-c", "source venv/bin/activate && python main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )

        time.sleep(2)  # Brief run to check config loading

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            _, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                _, stderr = process.communicate(timeout=1)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                stderr = b""

        # Should not have config-related errors
        stderr_text = stderr.decode('utf-8', errors='ignore')
        config_errors = ["Config file error", "Configuration error", "YAML error"]
        for error in config_errors:
            assert error not in stderr_text, f"Configuration error found: {stderr_text}"
