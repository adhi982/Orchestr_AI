"""
Configuration module for the DevOps Orchestrator.
This module handles configuration loading and validation.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class StageConfig(BaseModel):
    """Configuration for a pipeline stage."""
    name: str
    timeout: int = Field(default=1800, description="Timeout in seconds")
    retries: int = Field(default=3, description="Number of retries on failure")
    dependencies: List[str] = Field(default_factory=list, description="Stages that must complete before this one")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables for this stage")
    allow_failure: bool = Field(default=False, description="Whether pipeline continues if this stage fails")


class NotificationConfig(BaseModel):
    """Configuration for notifications."""
    slack_webhook: Optional[str] = None
    email: Optional[str] = None
    notify_on_success: bool = True
    notify_on_failure: bool = True


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""
    name: str = "default"
    stages: List[StageConfig]
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    timeout: int = Field(default=7200, description="Overall pipeline timeout in seconds")
    retry_on_failure: bool = Field(default=True)
    max_retries: int = Field(default=3)


class ConfigLoader:
    """Loads and validates configuration from YAML files."""
    
    @staticmethod
    def load_pipeline_config(config_path: str = None) -> Dict[str, Any]:
        """
        Load pipeline configuration from YAML file.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            Dict: Pipeline configuration
        """
        if config_path is None:
            config_path = os.getenv("PIPELINE_CONFIG_PATH", "config/pipeline.yml")
        
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load pipeline config from {config_path}: {e}")
            # Return default config if loading fails
            return {
                "pipeline": {
                    "name": "default",
                    "stages": [
                        {"name": "lint", "timeout": 300},
                        {"name": "test", "timeout": 600},
                        {"name": "build", "timeout": 900},
                        {"name": "security", "timeout": 600}
                    ],
                    "retry_on_failure": True,
                    "max_retries": 3,
                    "notifications": {
                        "notify_on_success": True,
                        "notify_on_failure": True
                    }
                }
            }


if __name__ == "__main__":
    # Quick test to validate loading
    config = ConfigLoader.load_pipeline_config()
    print("Loaded pipeline config:")
    print(yaml.dump(config))
