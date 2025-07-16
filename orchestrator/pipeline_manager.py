"""
Pipeline manager module that handles the pipeline state and orchestrates the flow.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

# Add project root to path to fix imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.kafka_client import KafkaClient
from orchestrator.config import ConfigLoader, PipelineConfig
from orchestrator.results_handler import get_results_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Enum for pipeline status values."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    """Enum for stage status values."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineInstance:
    """
    Represents a running pipeline instance with its current state.
    """
    def __init__(
        self, 
        pipeline_id: str, 
        repo_name: str, 
        branch: str, 
        config: PipelineConfig
    ):
        self.pipeline_id = pipeline_id
        self.repo_name = repo_name
        self.branch = branch
        self.config = config
        self.status = PipelineStatus.PENDING
        self.start_time = datetime.now()
        self.end_time = None
        self.stages = {
            stage.name: {
                "status": StageStatus.PENDING,
                "start_time": None,
                "end_time": None,
                "results": None,
                "retries": 0
            }
            for stage in config.stages
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pipeline instance to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "stages": self.stages
        }
    
    def update_stage_status(self, stage_name: str, status: StageStatus, results: Optional[Dict] = None):
        """Update the status of a stage."""
        if stage_name not in self.stages:
            logger.warning(f"Stage {stage_name} not found in pipeline {self.pipeline_id}")
            return
        
        self.stages[stage_name]["status"] = status
        
        if status == StageStatus.RUNNING:
            self.stages[stage_name]["start_time"] = datetime.now().isoformat()
        
        if status in [StageStatus.SUCCESS, StageStatus.FAILED, StageStatus.SKIPPED]:
            self.stages[stage_name]["end_time"] = datetime.now().isoformat()
        
        if results:
            self.stages[stage_name]["results"] = results
    
    def all_stages_completed(self) -> bool:
        """Check if all stages have completed."""
        return all(
            self.stages[stage]["status"] in [StageStatus.SUCCESS, StageStatus.FAILED, StageStatus.SKIPPED]
            for stage in self.stages
        )
    
    def update_pipeline_status(self):
        """Update overall pipeline status based on stages."""
        if any(self.stages[stage]["status"] == StageStatus.FAILED for stage in self.stages):
            self.status = PipelineStatus.FAILED
        elif all(self.stages[stage]["status"] == StageStatus.SUCCESS for stage in self.stages):
            self.status = PipelineStatus.SUCCESS
        elif any(self.stages[stage]["status"] == StageStatus.RUNNING for stage in self.stages):
            self.status = PipelineStatus.RUNNING
        elif any(self.stages[stage]["status"] == StageStatus.PENDING for stage in self.stages):
            self.status = PipelineStatus.PENDING
        
        if self.all_stages_completed():
            self.end_time = datetime.now()


class PipelineManager:
    """
    Manages the state and execution of pipelines.
    """
    def __init__(self):
        self.pipelines: Dict[str, PipelineInstance] = {}
        self.config_loader = ConfigLoader()
        
        # Load default pipeline configuration
        self.default_config = self.config_loader.load_pipeline_config()
    
    def generate_pipeline_id(self, repo: str, branch: str) -> str:
        """Generate a unique pipeline ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{repo.replace('/', '-')}-{branch}-{timestamp}"
    
    def create_pipeline(self, repo_name: str, branch: str, event_data: Dict[str, Any]) -> PipelineInstance:
        """Create a new pipeline instance."""
        pipeline_id = self.generate_pipeline_id(repo_name, branch)
        
        # Use repository-specific config if available, otherwise use default
        repo_config_path = f"config/pipelines/{repo_name}.yml"
        if os.path.exists(repo_config_path):
            config = self.config_loader.load_pipeline_config(repo_config_path)
        else:
            config = self.default_config
        
        # Always use the 'pipeline' section and parse as PipelineConfig
        config = PipelineConfig.parse_obj(config["pipeline"])
        
        # Create pipeline instance
        pipeline = PipelineInstance(
            pipeline_id=pipeline_id,
            repo_name=repo_name,
            branch=branch,
            config=config
        )
        
        # Store pipeline
        self.pipelines[pipeline_id] = pipeline
        logger.info(f"Created pipeline {pipeline_id} for {repo_name}:{branch}")
        
        # Start the pipeline
        self.start_pipeline(pipeline_id, event_data)
        
        return pipeline
    
    def start_pipeline(self, pipeline_id: str, event_data: Dict[str, Any]):
        """Start pipeline execution with configurable execution mode."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline {pipeline_id} not found")
            return
        
        pipeline = self.pipelines[pipeline_id]
        pipeline.status = PipelineStatus.RUNNING
        
        # Check execution mode
        execution_mode = getattr(pipeline.config, 'execution_mode', 'sequential')
        
        if execution_mode == "sequential":
            # Sequential execution - only start first stage
            config_stages = pipeline.config.stages
            ordered_stages = self._get_stages_in_order(config_stages)
            
            if ordered_stages:
                first_stage = ordered_stages[0]
                logger.info(f"Starting sequential pipeline {pipeline_id} with first stage: {first_stage}")
                self.trigger_stage(pipeline_id, first_stage, event_data)
        else:
            # Parallel execution - start all stages without dependencies
            config_stages = pipeline.config.stages
        initial_stages = [
                stage.name for stage in config_stages 
                if not getattr(stage, 'dependencies', [])
        ]
        
        for stage_name in initial_stages:
            self.trigger_stage(pipeline_id, stage_name, event_data)
    
    def _get_stages_in_order(self, config_stages: List) -> List[str]:
        """Get stages in proper execution order using topological sort."""
        # Create dependency graph
        graph = {}
        in_degree = {}
        
        for stage in config_stages:
            stage_name = stage.name
            graph[stage_name] = []
            in_degree[stage_name] = 0
        
        for stage in config_stages:
            stage_name = stage.name
            dependencies = getattr(stage, 'dependencies', [])
            for dep in dependencies:
                if dep in graph:
                    graph[dep].append(stage_name)
                    in_degree[stage_name] += 1
        
        # Topological sort
        queue = [stage for stage, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def trigger_stage(self, pipeline_id: str, stage_name: str, event_data: Dict[str, Any]):
        """Trigger a specific pipeline stage."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline {pipeline_id} not found")
            return
        
        pipeline = self.pipelines[pipeline_id]
        if stage_name not in pipeline.stages:
            logger.error(f"Stage {stage_name} not found in pipeline {pipeline_id}")
            return
        
        # Defensive: Only trigger if all dependencies are SUCCESS
        stage_config = next((s for s in pipeline.config.stages if s.name == stage_name), None)
        if stage_config:
            for dep in getattr(stage_config, 'dependencies', []):
                if pipeline.stages.get(dep, {}).get("status") != StageStatus.SUCCESS:
                    logger.warning(f"Not triggering {stage_name} because dependency {dep} is not SUCCESS")
            return
        
        # Update stage status
        pipeline.update_stage_status(stage_name, StageStatus.RUNNING)
        
        # Create event payload for the agent
        repository = event_data.get("repository", {})
        if "clone_url" not in repository:
            repository["clone_url"] = f"https://github.com/{pipeline.repo_name}.git"
        event_payload = {
            "pipeline_id": pipeline_id,
            "repo_name": pipeline.repo_name,
            "branch": pipeline.branch,
            "stage": stage_name,
            "repository": repository,
            "event_type": event_data.get("event_type", ""),
            "timestamp": datetime.now().isoformat()
        }
        # If this is the security stage, include image info at the top level if available
        if stage_name == "security":
            image = event_data.get("image")
            if not image:
                # Try to get image from previous build stage results
                build_stage = pipeline.stages.get("build", {})
                if build_stage and build_stage.get("results"):
                    image = build_stage["results"].get("image")
            if image:
                event_payload["image"] = image
        
        # Send message to appropriate Kafka topic
        topic = f"agent.{stage_name}"
        logger.info(f"Sending payload to {topic}: {event_payload}")
        print(f"Sending payload to {topic}: {event_payload}")
        try:
            KafkaClient.send_message(
                topic=topic,
                message=event_payload,
                key=f"{pipeline.repo_name}-{pipeline.branch}"
            )
            logger.info(f"Triggered stage {stage_name} for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to trigger stage {stage_name}: {e}")
            pipeline.update_stage_status(stage_name, StageStatus.FAILED, {"error": str(e)})
            self.check_pipeline_progress(pipeline_id)
    
    def process_stage_result(self, pipeline_id: str, stage_name: str, result: Dict[str, Any]):
        """Process results from a completed stage."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline {pipeline_id} not found")
            return
        
        pipeline = self.pipelines[pipeline_id]
        if stage_name not in pipeline.stages:
            logger.error(f"Stage {stage_name} not found in pipeline {pipeline_id}")
            return
        
        # Update stage with results
        status = StageStatus.SUCCESS if result.get("success", False) else StageStatus.FAILED
        pipeline.update_stage_status(stage_name, status, result)
        
        # --- Add real log and notification ---
        results_handler = get_results_handler()
        tracker = results_handler.results_tracker
        msg = f"Stage {stage_name} completed with status: {status}."
        tracker.add_log(pipeline_id, stage_name, msg)
        notif_type = "success" if status == StageStatus.SUCCESS else "error"
        tracker.add_notification(pipeline_id, notif_type, f"Stage {stage_name} {status}", msg)
        # --- End real log/notification ---
        
        # Handle retries for failed stages
        if status == StageStatus.FAILED:
            stage_data = pipeline.stages[stage_name]
            stage_config = next(
                (s for s in pipeline.config.stages if s.name == stage_name),
                None
            )
            max_retries = getattr(stage_config, 'retries', 0)
            
            if stage_data["retries"] < max_retries:
                # Retry the stage
                stage_data["retries"] += 1
                logger.info(f"Retrying stage {stage_name} for pipeline {pipeline_id} (attempt {stage_data['retries']})")
                # Re-trigger the stage
                self.trigger_stage(pipeline_id, stage_name, {"repository": {"name": pipeline.repo_name}})
                return
        
        # Check overall pipeline progress
        self.check_pipeline_progress(pipeline_id)
    
    def check_pipeline_progress(self, pipeline_id: str):
        """Check pipeline progress based on execution mode."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline {pipeline_id} not found")
            return
        
        pipeline = self.pipelines[pipeline_id]
        execution_mode = getattr(pipeline.config, 'execution_mode', 'sequential')
        
        # Update overall pipeline status
        pipeline.update_pipeline_status()
        
        # If pipeline is finished, send notifications
        if pipeline.status in [PipelineStatus.SUCCESS, PipelineStatus.FAILED]:
            logger.info(f"Pipeline {pipeline_id} finished with status {pipeline.status}")
            self.send_pipeline_notification(pipeline_id)
            return
        
        if execution_mode == "sequential":
            self._check_sequential_progress(pipeline_id)
        else:
            self._check_parallel_progress(pipeline_id)
    
    def _check_sequential_progress(self, pipeline_id: str):
        """Check progress for sequential execution mode."""
        pipeline = self.pipelines[pipeline_id]
        config_stages = pipeline.config.stages
        ordered_stages = self._get_stages_in_order(config_stages)
        
        # Find the next stage to trigger
        for stage_name in ordered_stages:
            stage_status = pipeline.stages.get(stage_name, {}).get("status")
            
            if stage_status == StageStatus.PENDING:
                # Check if all dependencies are completed successfully
                stage_config = next(
                    (s for s in config_stages if s.name == stage_name),
                    None
                )
                dependencies = getattr(stage_config, 'dependencies', []) if stage_config else []
                all_deps_success = True
                
                for dep in dependencies:
                    dep_status = pipeline.stages.get(dep, {}).get("status")
                    if dep_status != StageStatus.SUCCESS:
                        all_deps_success = False
                        break
                
                if all_deps_success:
                    # Trigger this stage and only this stage
                    logger.info(f"Triggering next stage in sequence: {stage_name} for pipeline {pipeline_id}")
                    self.trigger_stage(
                        pipeline_id, 
                        stage_name, 
                        {"repository": {"name": pipeline.repo_name}}
                    )
                    break
            elif stage_status == StageStatus.RUNNING:
                # A stage is currently running, don't trigger any more
                logger.info(f"Stage {stage_name} is currently running, waiting for completion")
                break
            elif stage_status == StageStatus.FAILED:
                # If a stage failed and doesn't allow failure, stop the pipeline
                stage_config = next(
                    (s for s in config_stages if s.name == stage_name),
                    None
                )
                allow_failure = getattr(stage_config, 'allow_failure', False) if stage_config else False
                if not allow_failure:
                    logger.error(f"Stage {stage_name} failed and doesn't allow failure, stopping pipeline")
                    return
    
    def _check_parallel_progress(self, pipeline_id: str):
        """Check progress for parallel execution mode (original logic)."""
        pipeline = self.pipelines[pipeline_id]
        config_stages = pipeline.config.stages
        
        for stage_config in config_stages:
            stage_name = stage_config.name
            if not stage_name or pipeline.stages.get(stage_name, {}).get("status") != StageStatus.PENDING:
                continue
            
            # Check if dependencies are completed successfully
            dependencies = getattr(stage_config, 'dependencies', [])
            all_deps_success = True
            
            for dep in dependencies:
                dep_status = pipeline.stages.get(dep, {}).get("status")
                if dep_status != StageStatus.SUCCESS:
                    all_deps_success = False
                    break
            
            if all_deps_success:
                # All dependencies are successful, trigger this stage
                logger.info(f"Triggering stage {stage_name} for pipeline {pipeline_id}")
                self.trigger_stage(
                    pipeline_id, 
                    stage_name, 
                    {"repository": {"name": pipeline.repo_name}}
                )
    
    def send_pipeline_notification(self, pipeline_id: str):
        """Send notification about pipeline completion."""
        if pipeline_id not in self.pipelines:
            logger.error(f"Pipeline {pipeline_id} not found")
            return
        
        pipeline = self.pipelines[pipeline_id]
        
        # Check if notifications should be sent
        notification_config = getattr(pipeline.config, 'notifications', {})
        should_notify = (
            (pipeline.status == PipelineStatus.SUCCESS and notification_config.get("notify_on_success", True)) or
            (pipeline.status == PipelineStatus.FAILED and notification_config.get("notify_on_failure", True))
        )
        
        if not should_notify:
            return
        
        # Prepare notification message
        message = {
            "pipeline_id": pipeline_id,
            "repo_name": pipeline.repo_name,
            "branch": pipeline.branch,
            "status": pipeline.status,
            "duration": (pipeline.end_time - pipeline.start_time).total_seconds() if pipeline.end_time else None,
            "stages": {
                name: {
                    "status": data["status"],
                    "duration": (
                        (datetime.fromisoformat(data["end_time"]) - datetime.fromisoformat(data["start_time"])).total_seconds()
                        if data["end_time"] and data["start_time"] else None
                    )
                }
                for name, data in pipeline.stages.items()
            }
        }
        
        # Send to notification topic
        try:
            KafkaClient.send_message("notifications", message, key=pipeline_id)
            logger.info(f"Sent notification for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to send notification for pipeline {pipeline_id}: {e}")
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a pipeline."""
        if pipeline_id not in self.pipelines:
            return None
        
        return self.pipelines[pipeline_id].to_dict()
    
    def list_pipelines(self) -> List[Dict[str, Any]]:
        """List all pipelines."""
        return [self.pipelines[pipeline_id].to_dict() for pipeline_id in self.pipelines]
    
    async def start_result_consumer(self):
        """Start consumer for agent result messages."""
        def handle_result(message):
            try:
                pipeline_id = message.get("pipeline_id")
                stage = message.get("stage")
                
                if not pipeline_id or not stage:
                    logger.error("Received invalid result message")
                    return
                
                logger.info(f"Received result for pipeline {pipeline_id}, stage {stage}")
                self.process_stage_result(pipeline_id, stage, message)
            except Exception as e:
                logger.error(f"Error processing result message: {e}")
        
        # Start Kafka consumer in a separate thread
        KafkaClient.consume_messages("agent.results", "orchestrator", handle_result)


# Singleton instance
pipeline_manager = PipelineManager()

def start_pipeline(pipeline_id: str, event_data: dict = None):
    """Top-level function to start a pipeline by ID."""
    manager = PipelineManager()
    if event_data is None:
        event_data = {}
    manager.start_pipeline(pipeline_id, event_data)

if __name__ == "__main__":
    # For testing only
    asyncio.run(pipeline_manager.start_result_consumer())
