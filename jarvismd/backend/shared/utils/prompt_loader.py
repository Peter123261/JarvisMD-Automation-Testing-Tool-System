"""
Prompt Loader Utility
Loads evaluation prompts from the data/prompts directory
"""
import os
from pathlib import Path
from typing import Optional

def load_evaluation_prompt(prompt_name: str = "appraise_v2.txt") -> str:
    """
    Load evaluation prompt from data/prompts directory
    
    Args:
        prompt_name: Name of the prompt file (default: appraise_v2.txt)
        
    Returns:
        str: Content of the prompt file
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    # Get the project root directory (3 levels up from this file)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent.parent
    prompt_path = project_root / "data" / "prompts" / prompt_name
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as file:
        return file.read().strip()

def get_available_prompts() -> list[str]:
    """
    Get list of available prompt files
    
    Returns:
        list: List of available prompt file names
    """
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent.parent
    prompts_dir = project_root / "data" / "prompts"
    
    if not prompts_dir.exists():
        return []
    
    return [f.name for f in prompts_dir.glob("*.txt")]