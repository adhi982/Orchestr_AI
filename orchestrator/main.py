"""
Main FastAPI application for the DevOps Orchestrator.
This module sets up the web server and webhook endpoints.
"""

import os
import json
import uuid
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import re

import yaml
from fastapi import FastAPI, Request, Response, Depends, Header, HTTPException, status
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import requests

# Add project root to path to fix imports
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.kafka_client import KafkaClient
from orchestrator.results_handler import get_results_handler, ResultsHandler, results_tracker, force_update_pipeline_status

# Absolute path to your .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'config', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("orchestrator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DevOps Pipeline Orchestrator",
    description="A webhook listener that orchestrates CI/CD pipelines using autonomous agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify ["http://localhost:3000"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load configuration
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', 'development_secret_only')
logger.info(f"[DEBUG] GITHUB_WEBHOOK_SECRET loaded: {GITHUB_WEBHOOK_SECRET}")
PIPELINE_CONFIG_PATH = os.getenv('PIPELINE_CONFIG_PATH', 'config/pipeline.yml')
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small")
MISTRAL_API_URL = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")

print("MISTRAL_API_KEY:", os.environ.get("MISTRAL_API_KEY"))
print("MISTRAL_MODEL:", os.environ.get("MISTRAL_MODEL"))
print("MISTRAL_API_URL:", os.environ.get("MISTRAL_API_URL"))

class PipelineEvent(BaseModel):
    """
    Model representing a pipeline event that will be sent to Kafka.
    """
    repository: Dict[str, Any]
    event_type: str
    payload: Dict[str, Any]


async def verify_signature(request: Request) -> bool:
    """
    Verify GitHub webhook signature to ensure requests are legitimate.
    
    Args:
        request: The incoming request
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not GITHUB_WEBHOOK_SECRET:
        logger.error("No GitHub webhook secret configured!")
        return False
    
    # Extract signature from headers - GitHub sends both formats
    x_hub_signature_256 = request.headers.get("X-Hub-Signature-256")
    x_hub_signature = request.headers.get("X-Hub-Signature")
    
    logger.info(f"Signature headers - 256: {x_hub_signature_256}, sha1: {x_hub_signature}")
    
    if not x_hub_signature_256 and not x_hub_signature:
        logger.warning("No signature provided")
        return False
        
    # Get raw body
    body = await request.body()
    
    # Try SHA256 first (preferred by GitHub)
    if x_hub_signature_256:
        try:
            # Extract signature part after 'sha256='
            received_signature = x_hub_signature_256.split('=')[1]
            
            # Generate expected SHA256 signature
            expected_signature = hmac.new(
                GITHUB_WEBHOOK_SECRET.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            logger.info(f"SHA256 verification - Expected: {expected_signature}, Received: {received_signature}")
            
            if hmac.compare_digest(expected_signature, received_signature):
                logger.info("SHA256 signature verification successful")
                return True
        except (IndexError, AttributeError) as e:
            logger.error(f"Invalid SHA256 signature format: {e}")
    
    # Try SHA1 as fallback
    if x_hub_signature:
        try:
            # Extract signature part after 'sha1='
            received_signature = x_hub_signature.split('=')[1]
            
            # Generate expected SHA1 signature
            expected_signature = hmac.new(
                GITHUB_WEBHOOK_SECRET.encode('utf-8'),
                body,
                hashlib.sha1
            ).hexdigest()
            
            logger.info(f"SHA1 verification - Expected: {expected_signature}, Received: {received_signature}")
            
            if hmac.compare_digest(expected_signature, received_signature):
                logger.info("SHA1 signature verification successful")
                return True
        except (IndexError, AttributeError) as e:
            logger.error(f"Invalid SHA1 signature format: {e}")
    
    logger.warning("Signature verification failed for both SHA256 and SHA1")
    return False


def load_pipeline_config() -> Dict[str, Any]:
    """
    Load pipeline configuration from YAML file.
    
    Returns:
        Dict: Pipeline configuration
    """
    try:
        with open(PIPELINE_CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load pipeline config: {e}")
        # Return default config if loading fails
        return {
            "pipeline": {
                "stages": ["lint", "test", "build", "security"],
                "retry_on_failure": True,
                "notify_on_success": True
            }
        }


@app.on_event("startup")
async def startup_event():
    """Runs when the FastAPI server starts up."""
    logger.info("🚀 STARTUP EVENT: Starting DevOps Pipeline Orchestrator")
    logger.info(f"🚀 STARTUP EVENT: Loading pipeline config from: {PIPELINE_CONFIG_PATH}")
    config = load_pipeline_config()
    logger.info(f"🚀 STARTUP EVENT: Pipeline stages: {config.get('pipeline', {}).get('stages', [])}")
    
    # Initialize and start the results handler
    try:
        logger.info("🚀 STARTUP EVENT: Getting results handler...")
        results_handler = get_results_handler()
        logger.info(f"🚀 STARTUP EVENT: Results handler running before start: {getattr(results_handler, 'running', 'Unknown')}")
        
        logger.info("🚀 STARTUP EVENT: Starting results handler...")
        results_handler.start()
        logger.info("🚀 STARTUP EVENT: Results handler started successfully")
        
        # Verify it's still running after a moment
        import asyncio
        await asyncio.sleep(1)
        logger.info(f"🚀 STARTUP EVENT: Results handler running after 1 second: {getattr(results_handler, 'running', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"🚀 STARTUP EVENT: Failed to start results handler: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Runs when the FastAPI server shuts down."""
    logger.info("Shutting down DevOps Pipeline Orchestrator")
    
    # Stop the results handler
    try:
        results_handler = get_results_handler()
        results_handler.stop()
        logger.info("Results handler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping results handler: {e}")


@app.get("/")
async def root():
    """Root endpoint for health checks and basic information."""
    return {
        "name": "DevOps Pipeline Orchestrator",
        "status": "running",
        "endpoints": {
            "/webhook": "GitHub webhook receiver",
            "/health": "Health check endpoint"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.get("/pipeline/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """
    Get the current status of a pipeline.
    
    Args:
        pipeline_id: The unique identifier of the pipeline
        
    Returns:
        Dict: Current pipeline status
    """
    try:
        # Log pipeline ID for debugging
        logger.info(f"Looking up status for pipeline ID: {pipeline_id}")
        
        # Get the pipeline status
        results_handler = get_results_handler()
        status = results_handler.results_tracker.get_pipeline_status(pipeline_id)
        
        # Log the retrieved status
        logger.info(f"Pipeline status response: {status}")
        
        return status
    except Exception as e:
        logger.error(f"Error retrieving pipeline status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pipeline status: {str(e)}"
        )


@app.post("/webhook")
async def github_webhook(request: Request, response: Response):
    """
    GitHub webhook endpoint that receives events and triggers pipeline stages.
    
    Args:
        request: The incoming request containing GitHub event
        response: The response object
    
    Returns:
        Dict: Result of the webhook processing
    """
    # Verify GitHub webhook signature in production
    if not await verify_signature(request):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    # Get event type from headers
    event_type = request.headers.get("X-GitHub-Event", "push")
    logger.info(f"Received GitHub webhook event: {event_type}")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload format"
        )
    
    # Only process certain events
    if event_type not in ["push", "pull_request"]:
        logger.info(f"Ignoring event type: {event_type}")
        return {"status": "ignored", "event_type": event_type}
    
    # Extract repository info
    try:
        repository = payload.get("repository", {})
        if not repository:
            raise ValueError("No repository information in payload")
        
        repo_name = repository.get("full_name", "unknown")
        repo_url = repository.get("clone_url", "")
        branch = "main"  # Default
        
        # Extract branch information
        if event_type == "push":
            branch = payload.get("ref", "").replace("refs/heads/", "")
        elif event_type == "pull_request":
            branch = payload.get("pull_request", {}).get("head", {}).get("ref", "")
        
        logger.info(f"Processing event for {repo_name}, branch: {branch}")
    except Exception as e:
        logger.error(f"Failed to extract repository info: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not process repository information"
        )
    
    # Load pipeline configuration
    config = load_pipeline_config()
    stages = config.get("pipeline", {}).get("stages", [])
    
    # Generate a unique pipeline ID - just use the hex without prefix
    pipeline_id = uuid.uuid4().hex[:8]
    
    # Create an event object to send to Kafka
    event = PipelineEvent(
        repository=repository,
        event_type=event_type,
        payload={
            "repository": repository,
            "branch": branch,
            "sender": payload.get("sender", {}),
            "event_type": event_type,
            # Include more context as needed
        }
    )
    
    # Add pipeline_id to the dictionary representation
    event_dict = event.dict()
    event_dict["pipeline_id"] = pipeline_id
    
    # Initialize pipeline status in the results tracker
    stage_names = [stage['name'] if isinstance(stage, dict) else stage for stage in stages]
    results_tracker.initialize_pipeline(pipeline_id, stage_names)
    
    # Send event to each agent via Kafka
    try:
        for stage in stages:
            # Create topic name using the agent prefix and stage name
            stage_name = stage['name'] if isinstance(stage, dict) else stage
            topic = f"agent.{stage_name}"
            logger.info(f"Sending event to {topic}")
            
            # Send message to Kafka
            KafkaClient.send_message(
                topic=topic,
                message=event_dict,  # Use the dict with pipeline_id
                key=f"{repo_name}-{branch}"  # Use repo+branch as key for message ordering
            )
        
        # Log success
        logger.info(f"Successfully triggered pipeline {pipeline_id} for {repo_name}, branch: {branch}")
        return {
            "status": "success",
            "message": f"Pipeline triggered for {repo_name}",
            "pipeline_id": pipeline_id,
            "stages": stages
        }
    except Exception as e:
        logger.error(f"Failed to send events to Kafka: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger pipeline: {str(e)}"
        )


@app.post("/test/pipeline/{pipeline_id}")
async def test_initialize_pipeline(pipeline_id: str):
    """
    Test endpoint to initialize a pipeline directly.
    
    Args:
        pipeline_id: The unique identifier for the test pipeline
        
    Returns:
        Dict: Initialized pipeline status
    """
    try:
        # Get the pipeline configuration
        config = load_pipeline_config()
        stages = config.get("pipeline", {}).get("stages", [])
        stage_names = [stage['name'] if isinstance(stage, dict) else stage for stage in stages]
        
        # Initialize the pipeline
        logger.info(f"Test initializing pipeline ID: {pipeline_id} with stages: {stage_names}")
        status = results_tracker.initialize_pipeline(pipeline_id, stage_names)
        logger.info(f"Test initialization result: {status}")
        
        return status
    except Exception as e:
        logger.error(f"Error in test pipeline initialization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize test pipeline: {str(e)}"
        )


@app.get("/pipelines")
async def list_pipelines():
    """
    Get a list of all pipelines being tracked.
    
    Returns:
        Dict: List of pipeline IDs and their statuses
    """
    try:
        results_handler = get_results_handler()
        pipelines = {}
        
        # Get the IDs and statuses of all tracked pipelines
        for pipeline_id in results_handler.results_tracker.pipelines.keys():
            status = results_handler.results_tracker.get_pipeline_status(pipeline_id)
            pipelines[pipeline_id] = status['status']
        
        return {
            "count": len(pipelines),
            "pipelines": pipelines
        }
    except Exception as e:
        logger.error(f"Error listing pipelines: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pipelines: {str(e)}"
        )


@app.get("/pipeline/{pipeline_id}/force-update")
async def force_update_pipeline(pipeline_id: str):
    """
    Force update a pipeline's status if it appears stuck.
    This is helpful for pipelines with stages that are stuck in "pending" state
    even after agents have reported completion.
    
    Args:
        pipeline_id: The unique identifier of the pipeline
        
    Returns:
        Dict: Updated pipeline status
    """
    try:
        logger.info(f"Force updating pipeline status for ID: {pipeline_id}")
        
        # Get the results handler
        handler = get_results_handler()
        
        # Implement force update logic directly as a fallback
        with handler.results_tracker.lock:
            if pipeline_id not in handler.results_tracker.pipelines:
                logger.warning(f"Pipeline {pipeline_id} not found in tracking system")
                return {'pipeline_id': pipeline_id, 'status': 'unknown', 'stages': {}}
            
            # Get pipeline stages
            stages = handler.results_tracker.pipelines[pipeline_id]
            updates_made = False
            
            # Process stages that are pending but have retry counts > 0
            for stage_name, stage_info in stages.items():
                if stage_info['status'] == 'pending' and stage_info['retries'] > 0:
                    logger.info(f"Transitioning stuck stage {stage_name} from pending to in_progress (retries: {stage_info['retries']})")
                    stage_info['status'] = 'in_progress'
                    stage_info['timestamp'] = datetime.now().isoformat()
                    updates_made = True
            
            if updates_made:
                logger.info(f"Made updates to stuck stages in pipeline {pipeline_id}")
        
        # Get the updated status
        status = handler.results_tracker.get_pipeline_status(pipeline_id)
        logger.info(f"Pipeline status after force update: {status}")
        
        return status
    except Exception as e:
        logger.error(f"Error force updating pipeline status: {e}", exc_info=True)
        return {"error": str(e), "pipeline_id": pipeline_id}


@app.get("/pipeline/{pipeline_id}/diagnostic")
async def get_pipeline_diagnostic(pipeline_id: str):
    """
    Get detailed diagnostic information about a pipeline.
    Shows complete stage details including results data, to help troubleshoot
    pipeline issues.
    
    Args:
        pipeline_id: The unique identifier of the pipeline
        
    Returns:
        Dict: Detailed pipeline diagnostic information
    """
    try:
        logger.info(f"Getting diagnostic data for pipeline ID: {pipeline_id}")
        
        # Get the results handler
        results_handler = get_results_handler()
        
        # Check if pipeline exists
        if pipeline_id not in results_handler.results_tracker.pipelines:
            logger.warning(f"Pipeline {pipeline_id} not found for diagnostic")
            return {
                "pipeline_id": pipeline_id,
                "status": "unknown",
                "error": "Pipeline not found in tracking system",
                "stages": {}
            }
        
        # Get the full pipeline data including results
        with results_handler.results_tracker.lock:
            pipeline_data = results_handler.results_tracker.pipelines[pipeline_id]
            
            # Get the standard status too
            status = results_handler.results_tracker.get_pipeline_status(pipeline_id)
            
            # Create diagnostic response
            diagnostic = {
                "pipeline_id": pipeline_id,
                "status": status["status"],
                "stages": {},
                "timestamp": status["timestamp"]
            }
            
            # Add full stage details including results data
            for stage, info in pipeline_data.items():
                diagnostic["stages"][stage] = {
                    "status": info.get("status", "unknown"),
                    "retries": info.get("retries", 0),
                    "timestamp": info.get("timestamp", ""),
                    "results": info.get("results", {}),  # Include the full results data
                }
        
        logger.info(f"Diagnostic data ready for pipeline {pipeline_id}")
        return diagnostic
    except Exception as e:
        logger.error(f"Error getting pipeline diagnostic: {e}", exc_info=True)
        return {"error": str(e), "pipeline_id": pipeline_id}


@app.post("/pipeline/{pipeline_id}/reset")
async def reset_pipeline(pipeline_id: str):
    """
    Completely reset a pipeline to pending state or remove it.
    This is useful for pipelines that are completely stuck or in a bad state.
    
    Args:
        pipeline_id: The unique identifier of the pipeline
        
    Returns:
        Dict: Status message
    """
    try:
        logger.info(f"Resetting pipeline: {pipeline_id}")
        
        # Get the handler
        handler = get_results_handler()
        
        # Option 1: Reset all stages to pending
        with handler.results_tracker.lock:
            if pipeline_id in handler.results_tracker.pipelines:
                stages = handler.results_tracker.pipelines[pipeline_id]
                stage_names = list(stages.keys())
                
                # Initialize with the same stages but reset status
                status = handler.results_tracker.initialize_pipeline(pipeline_id, stage_names)
                
                logger.info(f"Reset pipeline {pipeline_id} stages to pending: {stage_names}")
                return {
                    "message": f"Pipeline {pipeline_id} reset successfully",
                    "status": status
                }
            else:
                logger.warning(f"Pipeline {pipeline_id} not found, cannot reset")
                return {
                    "message": f"Pipeline {pipeline_id} not found",
                    "pipeline_id": pipeline_id
                }
    except Exception as e:
        logger.error(f"Error resetting pipeline: {e}", exc_info=True)
        return {"error": str(e), "pipeline_id": pipeline_id}


@app.post("/test/send-result")
async def test_send_result(result: Dict[str, Any]):
    """
    Test endpoint to simulate sending results from agents.
    
    Args:
        result: The result message to send
        
    Returns:
        Dict: Result of the operation
    """
    try:
        pipeline_id = result.get('pipeline_id')
        stage = result.get('stage')
        
        if not pipeline_id or not stage:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing pipeline_id or stage"
            )
        
        logger.info(f"Test: Sending result for pipeline {pipeline_id}, stage {stage}")
        
        # Send the result message to Kafka
        KafkaClient.send_message(
            topic='agent.results',
            message=result,
            key=pipeline_id
        )
        
        logger.info(f"Test: Result sent successfully for pipeline {pipeline_id}")
        
        return {
            "status": "success",
            "message": f"Result sent for pipeline {pipeline_id}, stage {stage}",
            "pipeline_id": pipeline_id,
            "stage": stage
        }
        
    except Exception as e:
        logger.error(f"Test: Error sending result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send result: {str(e)}"
        )


@app.get("/pipeline/{pipeline_id}/full")
async def get_pipeline_full(pipeline_id: str):
    """
    Get the full details of a pipeline, including logs, notifications, and all metadata.
    Args:
        pipeline_id: The unique identifier of the pipeline
    Returns:
        Dict: Complete pipeline information for frontend real-time display
    """
    results_handler = get_results_handler()
    tracker = results_handler.results_tracker
    with tracker.lock:
        # Compose a full response with all available data
        if pipeline_id not in tracker.pipelines:
            return {"pipeline_id": pipeline_id, "status": "unknown", "error": "Pipeline not found", "stages": {}, "logs": [], "notifications": []}
        stages = tracker.pipelines[pipeline_id]
        # Gather all stage info, including results
        stages_full = {
            stage: {
                "status": info.get("status", "unknown"),
                "retries": info.get("retries", 0),
                "timestamp": info.get("timestamp", ""),
                "results": info.get("results", {})
            }
            for stage, info in stages.items()
        }
        # Compose the full response
        return {
            "pipeline_id": pipeline_id,
            "status": tracker._get_pipeline_status(pipeline_id).get("status", "unknown"),
            "stages": stages_full,
            "logs": tracker.logs.get(pipeline_id, []),
            "notifications": tracker.notifications.get(pipeline_id, []),
            # Optionally add more metadata here
        }


@app.post("/dev/add-demo-logs")
async def add_demo_logs():
    """
    TEMP: Add demo logs and notifications to all pipelines for testing.
    """
    results_handler = get_results_handler()
    tracker = results_handler.results_tracker
    tracker.add_demo_logs_and_notifications_to_all()
    return {"message": "Demo logs and notifications added to all pipelines."}


@app.get("/pipeline/{pipeline_id}/ai-summary")
async def get_pipeline_ai_summary(pipeline_id: str):
    """
    On-demand AI summary for a pipeline using Mistral API. Returns a concise summary (4-5 points, 2-3 lines each).
    """
    results_handler = get_results_handler()
    tracker = results_handler.results_tracker

    with tracker.lock:
        if pipeline_id not in tracker.pipelines:
            return {
                "pipeline_id": pipeline_id,
                "status": "unknown",
                "error": "Pipeline not found"
            }

        stages = tracker.pipelines[pipeline_id]
        status_str = tracker._get_pipeline_status(pipeline_id).get("status", "unknown")

        # Build prompt for Mistral
        prompt = f"Pipeline ID: {pipeline_id} is the id of the workflow for which the AI result is being generated. "
        for stage, info in stages.items():
            prompt += f"Stage: {stage}\n  Status: {info.get('status', 'unknown')}\n  Retries: {info.get('retries', 0)}\n  Results: {info.get('results', {})}\n"
        prompt += (
            "\nYou are an expert DevOps assistant. "
            "Analyze the pipeline execution above. "
            "Summarize the workflow, explain the reasons for success or failure, "
            "highlight any bottlenecks or inefficiencies, and provide actionable, practical suggestions for improvement. "
            "Format your answer as 4-5 concise bullet points, each no more than 2-3 lines. "
            "Do not use ** or similar symbols for bolding words unless it is truly necessary to highlight something important. Keep the summary clean and avoid unnecessary markdown formatting."
        )

    # Mistral API setup
    if not MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY not found in environment variables.")
        raise HTTPException(status_code=500, detail="Mistral API key not configured")

    print("MISTRAL_API_KEY:", MISTRAL_API_KEY)

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    # Call Mistral API
    try:
        logger.info(f"Sending prompt to Mistral: {MISTRAL_API_URL}")
        response = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        suggestion = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not suggestion:
            suggestion = "No summary returned by Mistral."

    except requests.exceptions.HTTPError as e:
        logger.error(f"[MISTRAL ERROR] HTTP error: {e}")
        raise HTTPException(status_code=401, detail=f"[MISTRAL ERROR] Unauthorized. Check your API key.")

    except Exception as e:
        logger.error(f"[MISTRAL ERROR] {e}")
        raise HTTPException(status_code=500, detail=f"[MISTRAL ERROR] {e}")

    # Parse and clean bullet points
    import re
    points = re.split(r'\n\s*[-•*]\s*', suggestion)
    if len(points) == 1:
        points = re.split(r'\n\s*\d+\.\s*', suggestion)

    points = [p.strip() for p in points if p.strip()]
    points = points[:5]

    def truncate(p): return "\n".join(p.split('\n')[:3])
    points = [truncate(p) for p in points]

    return {"ai_summary": points}


if __name__ == "__main__":
    # For development only - in production use uvicorn command
    import uvicorn
    import asyncio
    from orchestrator.pipeline_manager import start_result_consumer
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    asyncio.run(start_result_consumer())
