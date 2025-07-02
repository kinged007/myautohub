"""
Test the cron-like scheduling functionality
"""

import pytest
from datetime import datetime
from task_scheduler.decorators import CronLikeInterval, CronLikeJob


class TestCronScheduling:
    """Test cron-like scheduling functionality"""

    def test_minute_alignment(self):
        """Test that minute intervals align to clock boundaries"""
        def dummy_task():
            pass
        
        # Test 5-minute intervals
        job = CronLikeJob(5, 'minutes', dummy_task)
        next_minute = job.next_run.minute
        assert next_minute % 5 == 0, f"5-minute alignment incorrect: {next_minute} is not divisible by 5"
        
        # Test 1-minute intervals  
        job1 = CronLikeJob(1, 'minutes', dummy_task)
        # Should be aligned to next minute boundary
        assert job1.next_run.second == 0, "1-minute job should align to minute boundary"
        
        # Test 10-minute intervals
        job10 = CronLikeJob(10, 'minutes', dummy_task)
        next_minute_10 = job10.next_run.minute
        assert next_minute_10 % 10 == 0, f"10-minute alignment incorrect: {next_minute_10} is not divisible by 10"

    def test_hour_alignment(self):
        """Test that hour intervals align to clock boundaries"""
        def dummy_task():
            pass
        
        job = CronLikeJob(1, 'hours', dummy_task)
        
        # Check that it's at the top of the hour
        assert job.next_run.minute == 0, f"Hour alignment incorrect: minute should be 0, got {job.next_run.minute}"
        assert job.next_run.second == 0, f"Hour alignment incorrect: second should be 0, got {job.next_run.second}"

    def test_multiple_runs(self):
        """Test that subsequent runs maintain alignment"""
        import time

        def dummy_task():
            pass

        job = CronLikeJob(5, 'minutes', dummy_task)
        first_run = job.next_run

        # Wait a small amount to ensure time progresses
        time.sleep(0.1)

        # Manually simulate the job execution without calling run()
        # (which tries to update database)
        job.last_run = datetime.now()
        job.next_run = job._calculate_next_run()
        second_run = job.next_run

        # Check that both runs are aligned to 5-minute boundaries
        assert first_run.minute % 5 == 0, "First run not aligned to 5-minute boundary"
        assert second_run.minute % 5 == 0, "Second run not aligned to 5-minute boundary"

        # For cron-like scheduling, the next run is calculated from current time,
        # so if we're still in the same 5-minute window, the next run should be the same
        # or the next 5-minute boundary
        time_diff = (second_run - first_run).total_seconds()
        assert time_diff >= 0, f"Second run {second_run} should not be before first run {first_run}"
        assert time_diff <= 300, f"Time difference {time_diff}s should not exceed 5 minutes"

    def test_should_run_logic(self):
        """Test the should_run method"""
        def dummy_task():
            pass
        
        job = CronLikeJob(5, 'minutes', dummy_task)
        
        # Should not run immediately (next_run is in the future)
        assert not job.should_run(), "Job should not run immediately after creation"

    def test_cron_like_interval_creation(self):
        """Test CronLikeInterval creation and properties"""
        interval = CronLikeInterval(5)
        
        # Test minutes property
        minutes_interval = interval.minutes
        assert minutes_interval._unit == 'minutes'
        assert minutes_interval._use_cron_like is True
        
        # Test hours property  
        interval2 = CronLikeInterval(2)
        hours_interval = interval2.hours
        assert hours_interval._unit == 'hours'
        assert hours_interval._use_cron_like is True

    def test_job_string_representation(self):
        """Test job string representation"""
        def dummy_task():
            pass
        
        job = CronLikeJob(5, 'minutes', dummy_task)
        job_str = str(job)
        
        assert "Every 5 minutes" in job_str
        assert "next run:" in job_str
