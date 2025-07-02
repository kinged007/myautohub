"""
Memory management and module reloading for long-running task scheduler
"""

import gc
import sys
import psutil
import importlib
import importlib.util
import threading
from typing import Dict, Set, Optional, Any
from pathlib import Path
import time
from loguru import logger


class MemoryManager:
    """Manages memory usage and module reloading for long-running processes"""
    
    def __init__(self, max_memory_mb: int = 500):
        self.max_memory_mb = max_memory_mb
        self.process = psutil.Process()
        self._loaded_modules: Dict[str, Any] = {}
        self._module_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
                "percent": memory_percent,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {}
    
    def is_memory_usage_high(self) -> bool:
        """Check if memory usage is above threshold"""
        memory_stats = self.get_memory_usage()
        if memory_stats:
            return memory_stats.get("rss_mb", 0) > self.max_memory_mb
        return False
    
    def cleanup_memory(self) -> Dict[str, Any]:
        """Perform memory cleanup operations"""
        logger.info("Starting memory cleanup")
        
        # Get memory stats before cleanup
        before_stats = self.get_memory_usage()
        
        # Force garbage collection
        collected_objects = []
        for generation in range(3):
            collected = gc.collect(generation)
            collected_objects.append(collected)
        
        # Clear module cache for modules that are no longer needed
        self._cleanup_unused_modules()
        
        # Clear various caches
        sys.intern.__dict__.clear() if hasattr(sys.intern, '__dict__') else None
        
        # Get memory stats after cleanup
        after_stats = self.get_memory_usage()
        
        cleanup_stats = {
            "before_memory_mb": before_stats.get("rss_mb", 0),
            "after_memory_mb": after_stats.get("rss_mb", 0),
            "memory_freed_mb": before_stats.get("rss_mb", 0) - after_stats.get("rss_mb", 0),
            "gc_collected": sum(collected_objects),
            "gc_by_generation": collected_objects
        }
        
        logger.info(f"Memory cleanup completed: {cleanup_stats}")
        return cleanup_stats
    
    def _cleanup_unused_modules(self):
        """Remove unused modules from cache"""
        with self._lock:
            # Get list of modules that are safe to remove
            modules_to_remove = []
            
            for module_name in list(self._loaded_modules.keys()):
                # Don't remove core modules or currently imported modules
                if (module_name not in sys.modules and 
                    not module_name.startswith('task_scheduler') and
                    not module_name.startswith('__')):
                    modules_to_remove.append(module_name)
            
            # Remove modules
            for module_name in modules_to_remove:
                if module_name in self._loaded_modules:
                    del self._loaded_modules[module_name]
                if module_name in self._module_timestamps:
                    del self._module_timestamps[module_name]
            
            if modules_to_remove:
                logger.debug(f"Removed {len(modules_to_remove)} unused modules from cache")


class TaskModuleManager:
    """Manages loading and reloading of task modules"""
    
    def __init__(self):
        self._loaded_tasks: Dict[str, Any] = {}
        self._task_timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
    
    def load_task_module(self, task_file_path: Path, task_content: str = None, force_reload: bool = False) -> Optional[Any]:
        """Load or reload a task module"""
        try:
            module_name = f"task_{task_file_path.stem}_{int(time.time())}"
            file_timestamp = task_file_path.stat().st_mtime

            with self._lock:
                # Check if module needs reloading
                if (not force_reload and
                    str(task_file_path) in self._loaded_tasks and
                    self._task_timestamps.get(str(task_file_path)) == file_timestamp):
                    return self._loaded_tasks[str(task_file_path)]

                # Create module spec
                spec = importlib.util.spec_from_loader(module_name, loader=None)
                if spec is None:
                    logger.error(f"Failed to create module spec for {task_file_path}")
                    return None

                module = importlib.util.module_from_spec(spec)

                # If task_content is provided, use it; otherwise read from file
                if task_content is None:
                    with open(task_file_path, 'r', encoding='utf-8') as f:
                        code_content = f.read()
                else:
                    code_content = task_content

                # Execute the module code
                exec(code_content, module.__dict__)

                # Verify the module has a start function
                if not hasattr(module, 'start'):
                    logger.error(f"Task module {task_file_path} does not have a 'start' function")
                    return None

                # Cache the module
                self._loaded_tasks[str(task_file_path)] = module
                self._task_timestamps[str(task_file_path)] = file_timestamp

                logger.debug(f"Loaded task module: {task_file_path}")
                return module
                
        except Exception as e:
            logger.error(f"Failed to load task module {task_file_path}: {e}")
            return None
    
    def unload_task_module(self, task_file_path: Path):
        """Unload a task module"""
        with self._lock:
            path_str = str(task_file_path)
            if path_str in self._loaded_tasks:
                del self._loaded_tasks[path_str]
            if path_str in self._task_timestamps:
                del self._task_timestamps[path_str]
            
            logger.debug(f"Unloaded task module: {task_file_path}")
    
    def reload_task_module(self, task_file_path: Path) -> Optional[Any]:
        """Force reload a task module"""
        self.unload_task_module(task_file_path)
        return self.load_task_module(task_file_path, force_reload=True)
    
    def check_for_changes(self, task_file_path: Path) -> bool:
        """Check if a task file has been modified"""
        try:
            current_timestamp = task_file_path.stat().st_mtime
            cached_timestamp = self._task_timestamps.get(str(task_file_path))
            
            return cached_timestamp is None or current_timestamp != cached_timestamp
            
        except Exception as e:
            logger.error(f"Failed to check file changes for {task_file_path}: {e}")
            return True  # Assume changed if we can't check
    
    def get_loaded_tasks(self) -> Dict[str, Any]:
        """Get all currently loaded task modules"""
        with self._lock:
            return self._loaded_tasks.copy()
    
    def cleanup_all_modules(self):
        """Unload all task modules"""
        with self._lock:
            self._loaded_tasks.clear()
            self._task_timestamps.clear()
            logger.info("Cleared all loaded task modules")


class ResourceMonitor:
    """Monitors system resources and triggers cleanup when needed"""
    
    def __init__(self, memory_manager: MemoryManager, check_interval: int = 60):
        self.memory_manager = memory_manager
        self.check_interval = check_interval
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start_monitoring(self):
        """Start resource monitoring in background thread"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Started resource monitoring")
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped resource monitoring")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                # Check memory usage
                if self.memory_manager.is_memory_usage_high():
                    logger.warning("High memory usage detected, triggering cleanup")
                    self.memory_manager.cleanup_memory()
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(self.check_interval)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_mb": memory.total / 1024 / 1024,
                    "available_mb": memory.available / 1024 / 1024,
                    "used_mb": memory.used / 1024 / 1024,
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": disk.total / 1024 / 1024 / 1024,
                    "free_gb": disk.free / 1024 / 1024 / 1024,
                    "used_gb": disk.used / 1024 / 1024 / 1024,
                    "percent": (disk.used / disk.total) * 100
                },
                "process_memory": self.memory_manager.get_memory_usage()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {}
