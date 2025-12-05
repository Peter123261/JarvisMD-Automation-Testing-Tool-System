"""
MedBench Automation Testing Tool

A comprehensive medical case evaluation system using LLM technology.
"""

__version__ = "1.0.0"
__author__ = "JarvisMD Team"

# Import main components for easy access
from .backend import *
from .data import *

__all__ = [
    "backend",
    "data"
]
