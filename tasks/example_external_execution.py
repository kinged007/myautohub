"""
---
title: "External Script Execution Task"
description: "Executes external Python scripts and CLI commands, captures output, and processes results"
dependencies: []
enabled: true
timeout: 120
---
"""

from task_scheduler.decorators import repeat, every
from helpers.external_execution import execute_python_script, execute_cli_command, process_execution_results
import json
from datetime import datetime
from pathlib import Path
import tempfile

@repeat(every(15).minutes)
def start():
    """Execute external scripts and commands every 10 minutes"""
    try:
        print("Starting external execution task...")
        results = []
        
        # Example 1: Execute a Python script from our current codebase
        print("\n1. Executing internal Python script...")
        script_result = execute_python_script(
            script_path="scripts/check_overdue.py",
            cwd=".",
            timeout=30
        )
        results.append(script_result)
        
        if script_result["success"]:
            print("✅ Internal script executed successfully")
            if script_result["stdout"]:
                print(f"Output preview: {script_result['stdout'][:100]}...")
        else:
            print(f"❌ Internal script failed: {script_result['error']}")
        
        # Example 2: Execute system commands
        print("\n2. Executing system commands...")
        
        # Get system information
        sys_info_result = execute_cli_command(
            command="python --version && pip list | head -5",
            timeout=15
        )
        results.append(sys_info_result)
        
        if sys_info_result["success"]:
            print("✅ System info command executed successfully")
            print(f"Python version info: {sys_info_result['stdout'].strip()}")
        
        # Example 3: Execute git commands (if in a git repository)
        print("\n3. Executing git commands...")
        git_result = execute_cli_command(
            command="git status --porcelain",
            timeout=10
        )
        results.append(git_result)
        
        if git_result["success"]:
            print("✅ Git command executed successfully")
            if git_result["stdout"].strip():
                print(f"Git status: {git_result['stdout'].strip()}")
            else:
                print("Git status: Clean working directory")
        else:
            print("ℹ️ Git command failed (may not be a git repository)")
        
        # Example 4: Create and execute a temporary Python script
        print("\n4. Creating and executing temporary script...")
        temp_script_content = '''
import sys
import json
from datetime import datetime

data = {
    "message": "Hello from temporary script!",
    "timestamp": datetime.now().isoformat(),
    "python_version": sys.version,
    "arguments": sys.argv[1:] if len(sys.argv) > 1 else []
}

print(json.dumps(data, indent=2))
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_file.write(temp_script_content)
            temp_script_path = temp_file.name
        
        try:
            temp_result = execute_python_script(
                script_path=temp_script_path,
                args=["arg1", "arg2", "test"],
                timeout=15
            )
            results.append(temp_result)
            
            if temp_result["success"]:
                print("✅ Temporary script executed successfully")
                try:
                    # Parse JSON output
                    output_data = json.loads(temp_result["stdout"])
                    print(f"Temp script message: {output_data['message']}")
                    print(f"Temp script args: {output_data['arguments']}")
                except json.JSONDecodeError:
                    print(f"Temp script output: {temp_result['stdout'][:100]}...")
        finally:
            # Clean up temporary file
            Path(temp_script_path).unlink(missing_ok=True)
        
        # Process and summarize results
        print("\n5. Processing execution results...")
        summary = process_execution_results(results)
        
        print(f"\n📊 Execution Summary:")
        print(f"  Total executions: {summary['total_executions']}")
        print(f"  Successful: {summary['successful']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Total execution time: {summary['total_execution_time']:.2f}s")
        print(f"  Average execution time: {summary['average_execution_time']:.2f}s")
        
        if summary['errors']:
            print(f"\n❌ Errors encountered:")
            for error in summary['errors']:
                print(f"  - {error['command']}: {error['error']}")
        
        # Save results to file
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        results_file = data_dir / f"external_executions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        execution_log = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "detailed_results": results
        }
        
        with open(results_file, 'a') as f:
            f.write(json.dumps(execution_log) + '\n')
        
        print(f"\n💾 Results saved to: {results_file}")
        print("External execution task completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in external execution task: {e}")
        raise
