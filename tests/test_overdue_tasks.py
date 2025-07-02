"""
Test overdue task detection and execution functionality
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from task_scheduler.database import DatabaseManager, TaskSchedule


class TestOverdueTasks:
    """Test overdue task functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)

        # Initialize database (happens automatically in __init__)
        db_manager = DatabaseManager(db_path)

        yield db_manager, db_path

        # Cleanup
        db_path.unlink(missing_ok=True)

    def test_overdue_task_detection(self, temp_db):
        """Test that overdue tasks are correctly detected"""
        db_manager, _ = temp_db
        
        current_time = datetime.now()
        past_time = current_time - timedelta(minutes=10)
        future_time = current_time + timedelta(minutes=10)
        
        # Create test schedules
        overdue_schedule = TaskSchedule(
            task_name="overdue_task",
            next_run_time=past_time,
            schedule_config="test_config",
            last_updated=current_time,
            is_active=True
        )
        
        future_schedule = TaskSchedule(
            task_name="future_task", 
            next_run_time=future_time,
            schedule_config="test_config",
            last_updated=current_time,
            is_active=True
        )
        
        # Insert schedules
        db_manager.update_task_schedule(overdue_schedule)
        db_manager.update_task_schedule(future_schedule)
        
        # Get overdue tasks
        overdue_tasks = db_manager.get_overdue_tasks(current_time)
        
        assert len(overdue_tasks) == 1
        assert overdue_tasks[0].task_name == "overdue_task"

    def test_inactive_tasks_not_overdue(self, temp_db):
        """Test that inactive tasks are not considered overdue"""
        db_manager, _ = temp_db
        
        current_time = datetime.now()
        past_time = current_time - timedelta(minutes=10)
        
        # Create inactive overdue schedule
        inactive_schedule = TaskSchedule(
            task_name="inactive_task",
            next_run_time=past_time,
            schedule_config="test_config", 
            last_updated=current_time,
            is_active=False
        )
        
        db_manager.update_task_schedule(inactive_schedule)
        
        # Get overdue tasks
        overdue_tasks = db_manager.get_overdue_tasks(current_time)
        
        assert len(overdue_tasks) == 0

    def test_schedule_update_after_execution(self, temp_db):
        """Test that schedules are updated after task execution"""
        db_manager, _ = temp_db
        
        current_time = datetime.now()
        new_next_run = current_time + timedelta(minutes=5)
        
        # Create initial schedule
        schedule = TaskSchedule(
            task_name="test_task",
            next_run_time=current_time - timedelta(minutes=1),
            schedule_config="test_config",
            last_updated=current_time,
            is_active=True
        )
        
        db_manager.update_task_schedule(schedule)
        
        # Update schedule with new next run time (simulating post-execution update)
        updated_schedule = TaskSchedule(
            task_name="test_task",
            next_run_time=new_next_run,
            schedule_config="test_config",
            last_updated=current_time,
            is_active=True
        )
        
        db_manager.update_task_schedule(updated_schedule)
        
        # Verify update
        retrieved_schedule = db_manager.get_task_schedule("test_task")
        assert retrieved_schedule is not None
        assert retrieved_schedule.next_run_time == new_next_run

    def test_multiple_overdue_tasks_ordering(self, temp_db):
        """Test that multiple overdue tasks are returned in correct order"""
        db_manager, _ = temp_db
        
        current_time = datetime.now()
        
        # Create multiple overdue schedules with different times
        schedules = [
            TaskSchedule(
                task_name="task_1",
                next_run_time=current_time - timedelta(minutes=30),
                schedule_config="test_config",
                last_updated=current_time,
                is_active=True
            ),
            TaskSchedule(
                task_name="task_2", 
                next_run_time=current_time - timedelta(minutes=10),
                schedule_config="test_config",
                last_updated=current_time,
                is_active=True
            ),
            TaskSchedule(
                task_name="task_3",
                next_run_time=current_time - timedelta(minutes=20),
                schedule_config="test_config",
                last_updated=current_time,
                is_active=True
            )
        ]
        
        for schedule in schedules:
            db_manager.update_task_schedule(schedule)
        
        # Get overdue tasks
        overdue_tasks = db_manager.get_overdue_tasks(current_time)
        
        assert len(overdue_tasks) == 3
        # Should be ordered by next_run_time (oldest first)
        assert overdue_tasks[0].task_name == "task_1"  # 30 minutes ago
        assert overdue_tasks[1].task_name == "task_3"  # 20 minutes ago  
        assert overdue_tasks[2].task_name == "task_2"  # 10 minutes ago
