"""
Task file parser for extracting frontmatter and task metadata
"""

import re
import yaml
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TaskMetadata:
    """Metadata extracted from task file frontmatter"""
    title: str
    description: str = ""
    dependencies: List[str] = None
    python_version: str = "3.8"
    enabled: bool = True
    timeout: int = 300  # seconds
    retry_count: int = 0
    retry_delay: int = 60  # seconds
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class TaskFile:
    """Represents a parsed task file"""
    path: Path
    metadata: TaskMetadata
    content: str
    file_hash: str
    last_modified: float
    
    
class TaskParser:
    """Parser for task files with frontmatter"""

    # Original YAML frontmatter pattern
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)',
        re.DOTALL | re.MULTILINE
    )

    # Python-syntax-correct pattern (YAML in docstring)
    DOCSTRING_FRONTMATTER_PATTERN = re.compile(
        r'^"""[\s]*\n---\s*\n(.*?)\n---\s*\n"""[\s]*\n(.*)',
        re.DOTALL | re.MULTILINE
    )
    
    def __init__(self):
        self._file_cache: Dict[str, TaskFile] = {}
    
    def parse_file(self, file_path: Path) -> Optional[TaskFile]:
        """Parse a task file and extract metadata and content"""
        try:
            if not file_path.exists() or not file_path.is_file():
                return None
                
            # Check if file has changed
            stat = file_path.stat()
            last_modified = stat.st_mtime
            
            # Calculate file hash for change detection
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            # Check cache
            cache_key = str(file_path)
            if (cache_key in self._file_cache and 
                self._file_cache[cache_key].file_hash == file_hash):
                return self._file_cache[cache_key]
            
            # Read and parse file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract frontmatter - try both patterns
            match = self.FRONTMATTER_PATTERN.match(content)
            docstring_match = self.DOCSTRING_FRONTMATTER_PATTERN.match(content)

            if match:
                # Original YAML frontmatter format
                frontmatter_str, task_content = match.groups()
            elif docstring_match:
                # Python-syntax-correct format (YAML in docstring)
                frontmatter_str, task_content = docstring_match.groups()
            else:
                # No frontmatter, create default metadata
                metadata = TaskMetadata(
                    title=file_path.stem,
                    description=f"Task from {file_path.name}"
                )
                task_content = content
                frontmatter_str = None

            if frontmatter_str:
                try:
                    frontmatter_data = yaml.safe_load(frontmatter_str)
                    metadata = self._parse_metadata(frontmatter_data, file_path.stem)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in frontmatter: {e}")

            # Validate task content has start() function or @repeat decorators (except for helper files)
            is_helper = 'helpers' in str(file_path)
            has_start_function = 'def start(' in task_content
            has_repeat_decorators = '@repeat(' in task_content

            if not is_helper and not has_start_function and not has_repeat_decorators:
                raise ValueError("Task file must contain either a 'start()' function or @repeat decorated functions")

            task_file = TaskFile(
                path=file_path,
                metadata=metadata,
                content=task_content,
                file_hash=file_hash,
                last_modified=last_modified
            )

            # Cache the parsed file
            self._file_cache[cache_key] = task_file

            return task_file
        except Exception as e:
            raise ValueError(f"Error parsing task file {file_path}: {e}")
    
    def _parse_metadata(self, data: Dict[str, Any], default_title: str) -> TaskMetadata:
        """Parse frontmatter data into TaskMetadata"""
        return TaskMetadata(
            title=data.get('title', default_title),
            description=data.get('description', ''),
            dependencies=data.get('dependencies', []),
            python_version=data.get('python_version', '3.8'),
            enabled=data.get('enabled', True),
            timeout=data.get('timeout', 300),
            retry_count=data.get('retry_count', 0),
            retry_delay=data.get('retry_delay', 60)
        )
    
    def scan_tasks_directory(self, tasks_dir: Path, include_example_tasks: bool = True) -> List[TaskFile]:
        """Scan tasks directory and return all valid task files

        Args:
            tasks_dir: Path to the tasks directory
            include_example_tasks: Whether to include tasks prefixed with 'example_'
        """
        task_files = []

        if not tasks_dir.exists():
            return task_files

        for file_path in tasks_dir.glob("*.py"):
            try:
                # Check if this is an example task and if we should include it
                task_name = file_path.stem
                if task_name.startswith("example_") and not include_example_tasks:
                    continue

                task_file = self.parse_file(file_path)
                if task_file and task_file.metadata.enabled:
                    task_files.append(task_file)
            except Exception as e:
                # Log error but continue with other files
                from loguru import logger
                logger.error(f"Failed to parse task file {file_path}: {e}")
                logger.debug(f"Task parsing error details: {e.__class__.__name__}: {str(e)}")
                continue

        return task_files
    
    def clear_cache(self):
        """Clear the file cache"""
        self._file_cache.clear()
    
    def remove_from_cache(self, file_path: Path):
        """Remove a specific file from cache"""
        cache_key = str(file_path)
        if cache_key in self._file_cache:
            del self._file_cache[cache_key]
