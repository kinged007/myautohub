#!/usr/bin/env python3
"""
Restart Scheduler Script

This script finds and restarts the MyAutoHub task scheduler process.
It can handle both regular processes and daemon processes.

Usage:
    python scripts/restart_scheduler.py [options]

Options:
    --force         Force kill the process if graceful shutdown fails
    --timeout N     Wait N seconds for graceful shutdown (default: 10)
    --config PATH   Path to config file (default: config/config.yaml)
    --dry-run       Show what would be done without actually doing it
    --help          Show this help message
"""

import sys
import os
import time
import signal
import argparse
import subprocess
import psutil
import yaml
from pathlib import Path
from typing import List, Optional

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))


def load_config(config_path=None):
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = project_dir / "config" / "config.yaml"
    else:
        config_path = Path(config_path)
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to load config from {config_path}: {e}")
        return {}


def find_scheduler_processes() -> List[psutil.Process]:
    """Find all running scheduler processes"""
    processes = []

    # First try using pgrep for more reliable process finding
    try:
        result = subprocess.run(['pgrep', '-f', 'myautohub-scheduler'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            for pid in pids:
                try:
                    proc = psutil.Process(pid)
                    processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if processes:
                return processes
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback to psutil iteration
    for proc in psutil.process_iter():
        try:
            # Get process info safely
            try:
                name = proc.name()
                cmdline = proc.cmdline()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

            # Check for our specific process name (truncated)
            if 'myautohub' in name:
                processes.append(proc)
                continue

            # Check command line for scheduler indicators
            if cmdline:
                cmdline_str = ' '.join(cmdline)

                # Look for main.py in myautohub directory
                if 'main.py' in cmdline_str and 'myautohub' in cmdline_str:
                    processes.append(proc)
                    continue

                # Check for python processes running our main.py
                if (len(cmdline) >= 2 and
                    'python' in cmdline[0] and
                    'main.py' in cmdline[1]):
                    # Verify it's our main.py by checking working directory or path
                    try:
                        cwd = proc.cwd()
                        if 'myautohub' in cwd:
                            processes.append(proc)
                            continue
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    # Fallback: check if any argument contains myautohub
                    for arg in cmdline:
                        if 'myautohub' in arg:
                            processes.append(proc)
                            break

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return processes


def graceful_shutdown(process, timeout=10):
    """Attempt graceful shutdown of the process"""
    try:
        print(f"Sending SIGTERM to process {process.pid}...")
        process.send_signal(signal.SIGTERM)

        # Wait for process to terminate
        try:
            process.wait(timeout=timeout)
            print(f"Process {process.pid} terminated gracefully")
            return True
        except psutil.TimeoutExpired:
            print(f"Process {process.pid} did not terminate within {timeout} seconds")
            # Check if process is actually still running
            try:
                if not process.is_running():
                    print(f"Process {process.pid} has actually terminated")
                    return True
            except psutil.NoSuchProcess:
                print(f"Process {process.pid} has terminated")
                return True
            return False

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Failed to send signal to process {process.pid}: {e}")
        return False


def force_kill(process):
    """Force kill the process"""
    try:
        print(f"Force killing process {process.pid}...")
        process.kill()
        
        # Wait a bit to ensure it's dead
        try:
            process.wait(timeout=5)
            print(f"Process {process.pid} force killed")
            return True
        except psutil.TimeoutExpired:
            print(f"Process {process.pid} still running after force kill")
            return False
            
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        print(f"Failed to force kill process {process.pid}: {e}")
        return False


def start_scheduler(config_path, daemon=False):
    """Start the scheduler process as a detached background process"""
    try:
        # Load config to get the correct Python executable
        config = load_config(config_path)
        python_executable = config.get('virtual_env', {}).get('python_executable', 'python3')

        # Use the venv python if it exists, otherwise use the configured executable
        venv_python = project_dir / "venv" / "bin" / "python"
        if venv_python.exists():
            python_cmd = str(venv_python)
        else:
            python_cmd = python_executable

        cmd = [python_cmd, str(project_dir / "main.py"), "--config", str(config_path)]

        if daemon:
            cmd.append("--daemon")

        print(f"Starting scheduler: {' '.join(cmd)}")

        # Always start as a detached background process
        # This ensures the scheduler runs independently of the restart script
        if sys.platform == 'win32':
            # Windows: use CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                cmd,
                cwd=project_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Unix/Linux/macOS: use start_new_session
            process = subprocess.Popen(
                cmd,
                cwd=project_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )

        print(f"Scheduler process started with PID: {process.pid}")

        # Give it a moment to initialize
        time.sleep(3)

        # Verify it started and is still running
        new_processes = find_scheduler_processes()
        if new_processes:
            running_pid = new_processes[0].pid
            print(f"✅ Scheduler confirmed running (PID: {running_pid})")
            return True
        else:
            print("❌ Failed to start scheduler - process not found after startup")
            return False

    except Exception as e:
        print(f"❌ Failed to start scheduler: {e}")
        return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Restart MyAutoHub Task Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill the process if graceful shutdown fails"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Wait N seconds for graceful shutdown (default: 10)"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=project_dir / "config" / "config.yaml",
        help="Path to config file"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start as daemon process"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    print("🔄 MyAutoHub Scheduler Restart Tool")
    print("=" * 40)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    # Find existing processes
    processes = find_scheduler_processes()
    
    if not processes:
        print("ℹ️  No scheduler processes found")
        print("🚀 Starting new scheduler...")
        
        if not args.dry_run:
            success = start_scheduler(args.config, args.daemon)
            if success:
                print("✅ Scheduler started successfully")
                return 0
            else:
                print("❌ Failed to start scheduler")
                return 1
        else:
            print("🔍 Would start scheduler (dry run)")
            return 0
    
    print(f"📋 Found {len(processes)} scheduler process(es):")
    for proc in processes:
        try:
            print(f"   PID {proc.pid}: {' '.join(proc.cmdline())}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"   PID {proc.pid}: <access denied>")
    
    print()
    
    # Stop existing processes
    stopped_all = True
    for proc in processes:
        if args.dry_run:
            print(f"🔍 Would stop process {proc.pid} (dry run)")
            continue
            
        print(f"🛑 Stopping process {proc.pid}...")
        
        # Try graceful shutdown first
        if graceful_shutdown(proc, args.timeout):
            continue
            
        # Force kill if requested and graceful failed
        if args.force:
            if not force_kill(proc):
                stopped_all = False
        else:
            print(f"❌ Process {proc.pid} did not stop gracefully. Use --force to kill it.")
            stopped_all = False
    
    if not stopped_all and not args.dry_run:
        print("❌ Failed to stop all processes")
        return 1
    
    if args.dry_run:
        print("🔍 Would start new scheduler (dry run)")
        return 0
    
    # Start new process
    print("🚀 Starting new scheduler...")
    success = start_scheduler(args.config, args.daemon)
    
    if success:
        print("✅ Scheduler restarted successfully")
        return 0
    else:
        print("❌ Failed to restart scheduler")
        return 1


if __name__ == "__main__":
    sys.exit(main())
