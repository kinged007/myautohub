"""
Virtual environment and dependency management for task scheduler
"""

import os
import sys
import subprocess
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Set, Optional
import venv
from loguru import logger


class VirtualEnvironmentManager:
    """Manages virtual environments and package installations"""
    
    def __init__(self, venv_path: Path, python_executable: str = "python3"):
        self.venv_path = Path(venv_path)
        self.python_executable = python_executable
        self.pip_executable = self.venv_path / "bin" / "pip"
        self.python_venv_executable = self.venv_path / "bin" / "python"
        
        # On Windows, executables are in Scripts directory
        if os.name == 'nt':
            self.pip_executable = self.venv_path / "Scripts" / "pip.exe"
            self.python_venv_executable = self.venv_path / "Scripts" / "python.exe"
        
        self._installed_packages: Optional[Dict[str, str]] = None
        self._requirements_hash: Optional[str] = None
    
    def ensure_virtual_environment(self) -> bool:
        """Ensure virtual environment exists and is properly configured"""
        try:
            if not self.venv_path.exists():
                logger.info(f"Creating virtual environment at {self.venv_path}")
                self._create_virtual_environment()
            
            if not self._is_virtual_environment_valid():
                logger.warning("Virtual environment is invalid, recreating...")
                self._recreate_virtual_environment()
            
            # Ensure pip is up to date
            self._upgrade_pip()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure virtual environment: {e}")
            return False
    
    def _create_virtual_environment(self):
        """Create a new virtual environment"""
        self.venv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create virtual environment
        venv.create(
            self.venv_path,
            system_site_packages=False,
            clear=True,
            symlinks=True if os.name != 'nt' else False,
            with_pip=True
        )
        
        logger.info(f"Virtual environment created at {self.venv_path}")
    
    def _recreate_virtual_environment(self):
        """Recreate virtual environment"""
        import shutil
        if self.venv_path.exists():
            shutil.rmtree(self.venv_path)
        self._create_virtual_environment()
        self._installed_packages = None  # Reset cache
    
    def _is_virtual_environment_valid(self) -> bool:
        """Check if virtual environment is valid"""
        return (
            self.venv_path.exists() and
            self.python_venv_executable.exists() and
            self.pip_executable.exists()
        )
    
    def _upgrade_pip(self):
        """Upgrade pip in virtual environment"""
        try:
            subprocess.run([
                str(self.python_venv_executable), "-m", "pip", "install", "--upgrade", "pip"
            ], check=True, capture_output=True, text=True)
            logger.debug("Pip upgraded successfully")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to upgrade pip: {e}")
    
    def get_installed_packages(self, force_refresh: bool = False) -> Dict[str, str]:
        """Get list of installed packages and their versions"""
        if self._installed_packages is None or force_refresh:
            try:
                result = subprocess.run([
                    str(self.pip_executable), "list", "--format=json"
                ], check=True, capture_output=True, text=True)
                
                packages_list = json.loads(result.stdout)
                self._installed_packages = {
                    pkg["name"].lower(): pkg["version"] 
                    for pkg in packages_list
                }
                
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                logger.error(f"Failed to get installed packages: {e}")
                self._installed_packages = {}
        
        return self._installed_packages.copy()
    
    def parse_requirements(self, requirements: List[str]) -> Dict[str, str]:
        """Parse requirements list into package name and version mapping"""
        parsed = {}
        
        for req in requirements:
            req = req.strip()
            if not req or req.startswith('#'):
                continue
            
            # Handle different requirement formats
            if '>=' in req:
                name, version = req.split('>=', 1)
                parsed[name.strip().lower()] = version.strip()
            elif '==' in req:
                name, version = req.split('==', 1)
                parsed[name.strip().lower()] = version.strip()
            elif '>' in req:
                name, version = req.split('>', 1)
                parsed[name.strip().lower()] = version.strip()
            else:
                # No version specified, use latest
                parsed[req.lower()] = "latest"
        
        return parsed
    
    def check_requirements_changed(self, requirements: List[str]) -> bool:
        """Check if requirements have changed since last check"""
        current_hash = hashlib.md5(
            json.dumps(sorted(requirements)).encode()
        ).hexdigest()
        
        if self._requirements_hash != current_hash:
            self._requirements_hash = current_hash
            return True
        
        return False
    
    def install_requirements(self, requirements: List[str]) -> bool:
        """Install required packages"""
        if not requirements:
            return True
        
        try:
            # Parse requirements
            required_packages = self.parse_requirements(requirements)
            if not required_packages:
                return True
            
            # Get currently installed packages
            installed_packages = self.get_installed_packages()
            
            # Determine packages to install
            packages_to_install = []
            
            for package_name, required_version in required_packages.items():
                installed_version = installed_packages.get(package_name)
                
                if installed_version is None:
                    # Package not installed
                    if required_version == "latest":
                        packages_to_install.append(package_name)
                    else:
                        packages_to_install.append(f"{package_name}=={required_version}")
                
                elif required_version != "latest" and installed_version != required_version:
                    # Version mismatch
                    packages_to_install.append(f"{package_name}=={required_version}")
            
            if packages_to_install:
                logger.info(f"Installing packages: {packages_to_install}")
                
                # Install packages
                cmd = [str(self.pip_executable), "install"] + packages_to_install
                result = subprocess.run(
                    cmd, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                logger.info(f"Successfully installed packages: {packages_to_install}")
                
                # Refresh installed packages cache
                self._installed_packages = None
                
                return True
            else:
                logger.debug("All required packages are already installed")
                return True
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install requirements: {e}")
            logger.error(f"Command output: {e.stdout}")
            logger.error(f"Command error: {e.stderr}")
            return False
        
        except subprocess.TimeoutExpired:
            logger.error("Package installation timed out")
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error during package installation: {e}")
            return False
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a package"""
        try:
            subprocess.run([
                str(self.pip_executable), "uninstall", package_name, "-y"
            ], check=True, capture_output=True, text=True)
            
            logger.info(f"Successfully uninstalled package: {package_name}")
            self._installed_packages = None  # Reset cache
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to uninstall package {package_name}: {e}")
            return False
    
    def get_environment_info(self) -> Dict[str, str]:
        """Get virtual environment information"""
        try:
            # Get Python version
            python_version_result = subprocess.run([
                str(self.python_venv_executable), "--version"
            ], capture_output=True, text=True)
            
            # Get pip version
            pip_version_result = subprocess.run([
                str(self.pip_executable), "--version"
            ], capture_output=True, text=True)
            
            return {
                "venv_path": str(self.venv_path),
                "python_version": python_version_result.stdout.strip(),
                "pip_version": pip_version_result.stdout.strip(),
                "python_executable": str(self.python_venv_executable),
                "pip_executable": str(self.pip_executable)
            }
            
        except Exception as e:
            logger.error(f"Failed to get environment info: {e}")
            return {}
    
    def execute_in_venv(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Execute a command in the virtual environment"""
        # Prepare environment variables
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(self.venv_path)
        env["PATH"] = f"{self.venv_path / 'bin'}:{env.get('PATH', '')}"
        
        if os.name == 'nt':
            env["PATH"] = f"{self.venv_path / 'Scripts'};{env.get('PATH', '')}"
        
        # Execute command
        return subprocess.run(command, env=env, **kwargs)
