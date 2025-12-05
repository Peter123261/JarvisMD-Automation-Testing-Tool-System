"""
Settings Configuration for JarvisMD Medical Automation Tool
Centralized configuration management using Pydantic Settings
"""

import os
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Configuration
    api_title: str = Field("JarvisMD Medical Automation API", alias="API_TITLE")
    api_version: str = Field("1.0.0", alias="API_VERSION")
    api_description: str = Field("Medical case evaluation system using LLM technology", alias="API_DESCRIPTION")
    api_port: int = Field(8000, alias="API_PORT")  # Aligned with backend_port for consistency
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    flower_port: int = Field(5555, alias="FLOWER_PORT")
    reload: bool = True
    
    # CORS Configuration - Fixed to properly parse comma-separated values
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS"
    )
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list"""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(',') if origin.strip()]
            return origins
        elif isinstance(v, list):
            return v
        return [str(v)]
    
    # AI Model Configuration
    openai_api_key: str = Field(..., description="OpenAI API key for evaluations")
    default_model: str = Field("gpt-4o", alias="DEFAULT_MODEL")
    model_temperature: float = 0.0
    max_concurrent_evaluations: int = Field(5, alias="MAX_CONCURRENT_EVALUATIONS")
    max_evaluation_cases: int = -1
    
    # Database Configuration
    database_url: Optional[str] = None
    
    # Redis Configuration
    redis_host: str = Field("localhost", alias="REDIS_HOST")
    redis_db: int = Field(0, alias="REDIS_DB")

    # Backend Configuration
    backend_host: str = Field("0.0.0.0", alias="BACKEND_HOST")
    backend_port: int = Field(8000, alias="BACKEND_PORT")
    
    # Align API_PORT with BACKEND_PORT for consistency (use 8000 as standard)
    # Note: api_port is kept for backward compatibility but should match backend_port
    # In docker-compose, API_PORT maps to the host port, BACKEND_PORT is the container port

    # Metrics Configuration
    api_metrics_port: int = Field(8007, alias="API_METRICS_PORT")
    api_metrics_host: str = Field("0.0.0.0", alias="API_METRICS_HOST")
    worker_metrics_port: int = Field(8002, alias="WORKER_METRICS_PORT")
    worker_metrics_host: str = Field("0.0.0.0", alias="WORKER_METRICS_HOST")
    
    # Metrics URLs (constructed from host/port, can be overridden)
    api_metrics_url: Optional[str] = Field(None, alias="API_METRICS_URL")
    worker_metrics_url: Optional[str] = Field(None, alias="WORKER_METRICS_URL")
    
    def get_api_metrics_url(self) -> str:
        """Get API metrics URL, constructing from host/port if not explicitly set"""
        if self.api_metrics_url:
            return self.api_metrics_url
        # Default to localhost for container-to-container communication
        return f"http://localhost:{self.api_metrics_port}/metrics"
    
    def get_worker_metrics_url(self) -> str:
        """Get worker metrics URL, constructing from host/port if not explicitly set"""
        if self.worker_metrics_url:
            return self.worker_metrics_url
        # Use service name for Docker network communication
        return f"http://celery-worker:{self.worker_metrics_port}/metrics"

    # Debug Configuration
    debug: bool = Field(False, alias="DEBUG")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False
    }

# Create settings instance
settings = Settings()
