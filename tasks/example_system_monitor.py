"""
---
title: "System Monitor Task"
description: "Monitors system resources and logs statistics"
dependencies:
  - "psutil>=5.8.0"
enabled: true
timeout: 120
---
"""

from task_scheduler.decorators import repeat, every
import psutil
import json
from datetime import datetime
from pathlib import Path

@repeat(every(10).minutes)
def start():
    """Monitor system resources every 10 minutes"""
    try:
        print("Collecting system metrics...")
        
        # Collect system information
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get network stats
        network = psutil.net_io_counters()
        
        # Compile metrics
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'percent': cpu_percent,
                'count': psutil.cpu_count(),
                'count_logical': psutil.cpu_count(logical=True)
            },
            'memory': {
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'used_gb': round(memory.used / (1024**3), 2),
                'percent': memory.percent
            },
            'disk': {
                'total_gb': round(disk.total / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'percent': round((disk.used / disk.total) * 100, 2)
            },
            'network': {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
        }
        
        # Save metrics to file
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        # Append to daily metrics file
        date_str = datetime.now().strftime("%Y%m%d")
        metrics_file = data_dir / f"system_metrics_{date_str}.jsonl"
        
        with open(metrics_file, 'a') as f:
            f.write(json.dumps(metrics) + '\n')
        
        # Log summary
        print(f"System metrics collected:")
        print(f"  CPU: {cpu_percent}%")
        print(f"  Memory: {memory.percent}% ({metrics['memory']['used_gb']}GB used)")
        print(f"  Disk: {metrics['disk']['percent']}% ({metrics['disk']['used_gb']}GB used)")
        print(f"  Saved to: {metrics_file}")
        
        # Alert if resources are high
        if cpu_percent > 80:
            print(f"WARNING: High CPU usage: {cpu_percent}%")
        
        if memory.percent > 80:
            print(f"WARNING: High memory usage: {memory.percent}%")
        
        if metrics['disk']['percent'] > 90:
            print(f"WARNING: High disk usage: {metrics['disk']['percent']}%")
        
    except Exception as e:
        print(f"Error collecting system metrics: {e}")
        raise
