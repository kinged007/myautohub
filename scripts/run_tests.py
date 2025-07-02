#!/usr/bin/env python3
"""
Test runner script for Task Scheduler

This script runs the pytest suite with appropriate configuration.
"""

import sys
import subprocess
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))


def run_tests(test_args=None):
    """Run the test suite"""
    if test_args is None:
        test_args = []
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"] + test_args
    
    print("Running Task Scheduler Tests")
    print("=" * 40)
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Run tests
    result = subprocess.run(cmd, cwd=project_dir)
    return result.returncode


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Task Scheduler tests")
    parser.add_argument(
        '--fast', 
        action='store_true',
        help='Skip slow tests'
    )
    parser.add_argument(
        '--coverage',
        action='store_true', 
        help='Run with coverage reporting'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        'test_path',
        nargs='?',
        help='Specific test file or directory to run'
    )
    
    args = parser.parse_args()
    
    # Build pytest arguments
    test_args = []
    
    if args.fast:
        test_args.extend(['-m', 'not slow'])
    
    if args.coverage:
        test_args.extend(['--cov=task_scheduler', '--cov-report=html', '--cov-report=term'])
    
    if args.verbose:
        test_args.append('-v')
    
    if args.test_path:
        test_args.append(args.test_path)
    
    return run_tests(test_args)


if __name__ == "__main__":
    sys.exit(main())
