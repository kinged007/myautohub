"""
---
title: "System Notifications Helper"
description: "Cross-platform system notification utilities"
dependencies:
  - "plyer>=2.1.0"
enabled: true
timeout: 60
---
"""

import platform
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

def send_notification(
    title: str,
    message: str,
    timeout: int = 5,
    icon: Optional[str] = None,
    urgency: str = "normal",
    app_name: str = "Task Scheduler"
) -> Dict[str, Any]:
    """
    Send a system notification across different operating systems.
    
    Args:
        title: Notification title
        message: Notification message content
        timeout: How long to show notification (seconds)
        icon: Path to icon file (optional)
        urgency: Notification urgency level ("low", "normal", "critical")
        app_name: Application name to display
        
    Returns:
        Dict with success status and details
    """
    result = {
        "success": False,
        "method": None,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    system = platform.system().lower()
    
    try:
        if system == "darwin":  # macOS
            result["method"] = "osascript"
            # Use AppleScript for macOS notifications
            script = f'''
            display notification "{message}" with title "{title}" subtitle "{app_name}"
            '''
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            result["success"] = True
            
        elif system == "linux":  # Linux
            result["method"] = "notify-send"
            # Use notify-send for Linux notifications
            cmd = ["notify-send"]
            
            # Add urgency level
            if urgency in ["low", "normal", "critical"]:
                cmd.extend(["-u", urgency])
            
            # Add timeout
            cmd.extend(["-t", str(timeout * 1000)])  # notify-send uses milliseconds
            
            # Add icon if provided
            if icon and Path(icon).exists():
                cmd.extend(["-i", icon])
            
            # Add title and message
            cmd.extend([title, message])
            
            subprocess.run(cmd, check=True, capture_output=True)
            result["success"] = True
            
        elif system == "windows":  # Windows
            try:
                # Try using plyer first (cross-platform)
                from plyer import notification
                result["method"] = "plyer"
                
                notification.notify(
                    title=title,
                    message=message,
                    app_name=app_name,
                    timeout=timeout,
                    toast=True
                )
                result["success"] = True
                
            except ImportError:
                # Fallback to PowerShell for Windows
                result["method"] = "powershell"
                ps_script = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipTitle = "{title}"
                $notification.BalloonTipText = "{message}"
                $notification.Visible = $true
                $notification.ShowBalloonTip({timeout * 1000})
                Start-Sleep -Seconds {timeout}
                $notification.Dispose()
                '''
                subprocess.run(["powershell", "-Command", ps_script], check=True, capture_output=True)
                result["success"] = True
                
        else:
            # Try plyer as fallback for unknown systems
            try:
                from plyer import notification
                result["method"] = "plyer_fallback"
                
                notification.notify(
                    title=title,
                    message=message,
                    app_name=app_name,
                    timeout=timeout
                )
                result["success"] = True
                
            except ImportError:
                result["error"] = f"Unsupported platform: {system}. Install 'plyer' package for cross-platform support."
                
    except subprocess.CalledProcessError as e:
        result["error"] = f"Command failed: {e.stderr.decode() if e.stderr else str(e)}"
    except Exception as e:
        result["error"] = f"Notification failed: {str(e)}"
    
    return result

def log_notification(
    title: str,
    message: str,
    result: Dict[str, Any],
    log_dir: str = "data"
) -> Path:
    """
    Log notification attempt to a daily JSONL file.
    
    Args:
        title: Notification title
        message: Notification message
        result: Result from send_notification
        log_dir: Directory to save logs
        
    Returns:
        Path to the log file
    """
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(exist_ok=True)
    
    # Append to daily notification log
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir_path / f"notifications_{date_str}.jsonl"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "message": message,
        "result": result,
        "platform": platform.system()
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    return log_file

def send_and_log_notification(
    title: str,
    message: str,
    timeout: int = 5,
    urgency: str = "normal",
    app_name: str = "Task Scheduler",
    log_dir: str = "data"
) -> Dict[str, Any]:
    """
    Send a notification and automatically log the result.
    
    Args:
        title: Notification title
        message: Notification message content
        timeout: How long to show notification (seconds)
        urgency: Notification urgency level ("low", "normal", "critical")
        app_name: Application name to display
        log_dir: Directory to save logs
        
    Returns:
        Dict with success status, details, and log file path
    """
    # Send the notification
    result = send_notification(
        title=title,
        message=message,
        timeout=timeout,
        urgency=urgency,
        app_name=app_name
    )
    
    # Log the result
    log_file = log_notification(title, message, result, log_dir)
    
    # Add log file path to result
    result["log_file"] = str(log_file)
    
    return result
