"""
---
title: "External Execution Helper"
description: "Utilities for executing external Python scripts and CLI commands"
dependencies: []
enabled: true
timeout: 120
---
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import shlex

def execute_python_script(
    script_path: Union[str, Path],
    args: List[str] = None,
    cwd: Optional[str] = None,
    timeout: int = 60,
    capture_output: bool = True,
    python_executable: str = None
) -> Dict[str, Any]:
    """
    Execute a Python script and capture its output.
    
    Args:
        script_path: Path to the Python script to execute
        args: Command line arguments to pass to the script
        cwd: Working directory for execution
        timeout: Timeout in seconds
        capture_output: Whether to capture stdout/stderr
        python_executable: Python executable to use (defaults to current)
        
    Returns:
        Dict with execution results
    """
    script_path = Path(script_path)
    args = args or []
    python_exe = python_executable or sys.executable
    
    result = {
        "success": False,
        "return_code": None,
        "stdout": "",
        "stderr": "",
        "execution_time": 0,
        "script_path": str(script_path),
        "command": None,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Build command
        cmd = [python_exe, str(script_path)] + args
        result["command"] = " ".join(cmd)
        
        print(f"Executing Python script: {result['command']}")
        if cwd:
            print(f"Working directory: {cwd}")
        
        start_time = datetime.now()
        
        # Execute the script
        process = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=False  # Don't raise exception on non-zero exit
        )
        
        end_time = datetime.now()
        result["execution_time"] = (end_time - start_time).total_seconds()
        result["return_code"] = process.returncode
        result["success"] = process.returncode == 0
        
        if capture_output:
            result["stdout"] = process.stdout
            result["stderr"] = process.stderr
        
        print(f"Script completed in {result['execution_time']:.2f}s with return code {result['return_code']}")
        
    except subprocess.TimeoutExpired:
        result["error"] = f"Script execution timed out after {timeout} seconds"
        print(f"❌ {result['error']}")
    except FileNotFoundError:
        result["error"] = f"Script not found: {script_path}"
        print(f"❌ {result['error']}")
    except Exception as e:
        result["error"] = f"Execution failed: {str(e)}"
        print(f"❌ {result['error']}")
    
    return result

def execute_cli_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    shell: bool = True,
    env: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Execute a CLI command and capture its output.
    
    Args:
        command: Command to execute
        cwd: Working directory for execution
        timeout: Timeout in seconds
        shell: Whether to use shell execution
        env: Environment variables
        
    Returns:
        Dict with execution results
    """
    result = {
        "success": False,
        "return_code": None,
        "stdout": "",
        "stderr": "",
        "execution_time": 0,
        "command": command,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        print(f"Executing CLI command: {command}")
        if cwd:
            print(f"Working directory: {cwd}")
        
        start_time = datetime.now()
        
        # Parse command if not using shell
        if not shell:
            cmd = shlex.split(command)
        else:
            cmd = command
        
        # Execute the command
        process = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            env=env,
            check=False
        )
        
        end_time = datetime.now()
        result["execution_time"] = (end_time - start_time).total_seconds()
        result["return_code"] = process.returncode
        result["success"] = process.returncode == 0
        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        
        print(f"Command completed in {result['execution_time']:.2f}s with return code {result['return_code']}")
        
    except subprocess.TimeoutExpired:
        result["error"] = f"Command execution timed out after {timeout} seconds"
        print(f"❌ {result['error']}")
    except Exception as e:
        result["error"] = f"Command execution failed: {str(e)}"
        print(f"❌ {result['error']}")
    
    return result

def process_execution_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process and analyze execution results.
    
    Args:
        results: List of execution results
        
    Returns:
        Summary of results
    """
    summary = {
        "total_executions": len(results),
        "successful": 0,
        "failed": 0,
        "total_execution_time": 0,
        "average_execution_time": 0,
        "errors": [],
        "outputs": []
    }
    
    for result in results:
        if result["success"]:
            summary["successful"] += 1
        else:
            summary["failed"] += 1
            if result["error"]:
                summary["errors"].append({
                    "command": result.get("command", "unknown"),
                    "error": result["error"]
                })
        
        summary["total_execution_time"] += result["execution_time"]
        
        if result["stdout"]:
            summary["outputs"].append({
                "command": result.get("command", "unknown"),
                "stdout": result["stdout"][:200] + "..." if len(result["stdout"]) > 200 else result["stdout"]
            })
    
    if summary["total_executions"] > 0:
        summary["average_execution_time"] = summary["total_execution_time"] / summary["total_executions"]
    
    return summary

def execute_script_with_retry(
    script_path: Union[str, Path],
    args: List[str] = None,
    max_retries: int = 3,
    retry_delay: int = 5,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute a Python script with retry logic.
    
    Args:
        script_path: Path to the Python script to execute
        args: Command line arguments to pass to the script
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        **kwargs: Additional arguments passed to execute_python_script
        
    Returns:
        Dict with execution results including retry information
    """
    import time
    
    result = None
    attempts = []
    
    for attempt in range(max_retries + 1):
        print(f"Attempt {attempt + 1}/{max_retries + 1}")
        
        result = execute_python_script(script_path, args, **kwargs)
        attempts.append(result.copy())
        
        if result["success"]:
            break
        
        if attempt < max_retries:
            print(f"Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    # Add retry information to final result
    result["retry_attempts"] = len(attempts)
    result["all_attempts"] = attempts
    result["final_success"] = result["success"]
    
    return result
