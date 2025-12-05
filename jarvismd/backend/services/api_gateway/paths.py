"""
Centralized path configuration for the application
Uses pathlib for cross-platform compatibility
"""
from pathlib import Path

# Project root - 4 levels up from this file
# api_gateway -> services -> backend -> project_root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
MEDICAL_CASES_DIR = DATA_DIR / "medical_cases"
PROMPTS_DIR = DATA_DIR / "prompts"

# Configuration files
ENV_FILE = PROJECT_ROOT / ".env"
DATABASE_FILE = PROJECT_ROOT / "jarvismd_automation.db"

# Specific files
APPRAISE_V2_PROMPT = PROMPTS_DIR / "appraise_v2.txt"

def ensure_directories():
    """Ensure all necessary directories exist"""
    # No directories need to be created automatically
    # All required directories are created as needed by the system
    pass

def get_project_root() -> Path:
    """Get the project root directory"""
    return PROJECT_ROOT

def get_data_dir() -> Path:
    """Get the data directory"""
    return DATA_DIR

def get_medical_cases_dir() -> Path:
    """Get the medical cases directory"""
    return MEDICAL_CASES_DIR

def get_prompts_dir() -> Path:
    """Get the prompts directory"""
    return PROMPTS_DIR