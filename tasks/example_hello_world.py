"""
---
title: "Hello World Task"
description: "A simple example task that runs every 5 minutes"
dependencies: []
enabled: true
timeout: 60
---
"""

import time
from datetime import datetime

from task_scheduler.decorators import repeat, every
from helpers import log_task_start, log_task_complete, log_info

@repeat(every(1).minutes)
def start():
    """Simple hello world task that runs every 5 minutes"""
    log_task_start()

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_info(f"Current time: {current_time}")

    print(f"Hello World! Current time: {current_time}")

    # Simulate some work
    time.sleep(2)

    print("Hello World task completed successfully!")
    log_task_complete(duration=2.0)
