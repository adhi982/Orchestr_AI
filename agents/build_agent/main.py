#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Build Agent Main Module

This agent:
1. Listens to the Kafka topic 'agent.build'
2. Clones the specified GitHub repository
3. Builds a Docker image using the Dockerfile in the repo
4. Optionally pushes the Docker image to a registry
5. Reports results back to the orchestrator via 'agent.results'
"""

import os
import sys
import json
import logging
import tempfile
import shutil
import subprocess
import time
import argparse
from typing import Dict, Any, List, Optional, Tuple
import base64
import re

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
import git  # GitPython for better Git handling
import docker
from docker.errors import BuildError, APIError, DockerException
from common.kafka_client import KafkaClient
from common.timeout_handler import TimeoutHandler

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("build_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("build_agent")


class BuildAgent:
    """
    Agent that builds Docker images from repositories.
    """
    
    def __init__(self):
        """Initialize the Build Agent."""
        self.kafka_topic = "agent.build"
        self.results_topic = "agent.results"
        self.consumer_group = "build-agent"
        self.docker_client = self._create_docker_client()
        
        # Get timeout value from pipeline configuration
        self.timeout_seconds = self._get_timeout_seconds()
        self.timeout_handler = None
        
    def _get_timeout_seconds(self) -> int:
        """Get the timeout value from the pipeline config."""
        try:
            # Default to 70 seconds if not found in config
            import yaml
            config_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'config/pipeline.yml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            
            # Find the build stage and get its timeout
            for stage in config.get('pipeline', {}).get('stages', []):
                if stage.get('name') == 'build':
                    return stage.get('timeout', 70)
            
            return 70  # Default timeout
        except Exception as e:
            logger.warning(f"Error reading timeout config, using default: {e}")
            return 70  # Default timeout if something goes wrong
        
    def _create_docker_client(self):
        """Create a Docker client instance."""
        try:
            print("DOCKER_HOST:", os.environ.get("DOCKER_HOST"))
            print("DOCKER_CONTEXT:", os.environ.get("DOCKER_CONTEXT"))
            print("DOCKER_CONFIG:", os.environ.get("DOCKER_CONFIG"))

            client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')
            print("Client API base_url:", client.api.base_url)
            client.ping()
            logger.info("Docker client created successfully using docker.DockerClient(base_url='npipe:////./pipe/docker_engine')")
            return client
        except DockerException as e:
            logger.error(f"Failed to create Docker client: {e}", exc_info=True)
            return None
        
    def start(self):
        """Start listening for build jobs."""
        if self.docker_client is None:
            logger.error("Cannot start Build Agent: Docker client initialization failed")
            return
        
        logger.info(f"Starting Build Agent, listening to topic: {self.kafka_topic}")
        
        # Initialize timeout handler
        self.timeout_handler = TimeoutHandler(
            timeout_seconds=self.timeout_seconds, 
            agent_name="build_agent"
        )
        
        # Start the timeout handler with a callback
        self.timeout_handler.start(on_timeout_callback=self.handle_timeout)
        
        # Start Kafka consumer
        KafkaClient.consume_messages(
            topic=self.kafka_topic,
            group_id=self.consumer_group,
            message_handler=self.process_message
        )
        
    def handle_timeout(self):
        """Handle timeout events."""
        logger.warning("Build agent timed out - gracefully shutting down")
        
        # Send a timeout message to the results topic if we have a current pipeline
        try:
            # This is a simplistic example - in production, track the current job
            KafkaClient.send_message(
                topic=self.results_topic,
                message={
                    'pipeline_id': "timeout",  # In production: store and use actual pipeline_id
                    'stage': 'build',
                    'success': False,
                    'timestamp': time.time(),
                    'results': {
                        'success': False,
                        'error': "Agent timed out"
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")
    
    def process_message(self, message: Dict[str, Any]):
        """
        Process a build job message.
        
        Args:
            message: The Kafka message containing job details
        """
        logger.info(f"Received build job: {message.get('pipeline_id', 'unknown')}")
        
        # Reset timeout for new job
        if self.timeout_handler:
            self.timeout_handler.reset()
            
        try:
            # Extract required information
            pipeline_id = message.get('pipeline_id')
            repo_url = message.get('repository', {}).get('clone_url')
            branch = message.get('branch', 'main')
            
            # Extract Docker-specific configuration
            docker_config = message.get('docker', {})
            image_name = docker_config.get('image_name') or message.get('repository', {}).get('name', 'default-image')
            image_tag = docker_config.get('tag') or branch or 'latest'
            dockerfile_path = docker_config.get('dockerfile', 'Dockerfile')
            registry = docker_config.get('registry')
            push_image = docker_config.get('push', False)
            build_args = docker_config.get('build_args', {})
            
            if not pipeline_id or not repo_url:
                raise ValueError("Missing required fields in message")
            
            # Sanitize Docker name and tag
            image_name = self.sanitize_docker_name(image_name)
            image_tag = self.sanitize_docker_name(image_tag)
            
            # Clone repository and build image
            temp_dir = None
            try:
                # Mark as processing (prevents timeout while actively working)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(True)
                    
                # Create a temporary directory for the repository
                temp_dir = tempfile.mkdtemp(prefix="build_")
                logger.info(f"Using temporary directory: {temp_dir}")
                
                # Clone the repository
                self.clone_repository(repo_url, branch, temp_dir)
                
                # Build Docker image
                build_results = self.build_docker_image(
                    temp_dir, 
                    image_name, 
                    image_tag, 
                    dockerfile_path,
                    build_args
                )
                
                # Push image if requested
                if push_image and build_results.get('success'):
                    push_results = self.push_docker_image(
                        image_name,
                        image_tag,
                        registry
                    )
                    # Update build results with push results
                    build_results['push'] = push_results
                
                # Mark as not processing (allows timeout if idle)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(False)
                    
                # Ensure image info is present for security agent
                build_results['image'] = {
                    'name': image_name,
                    'tag': image_tag
                }
                
                # Send results
                self.send_results(pipeline_id, message, build_results)
                
            finally:
                # Clean up temporary directory
                if temp_dir and os.path.exists(temp_dir):
                    logger.info(f"Cleaning up temporary directory: {temp_dir}")
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception as cleanup_error:
                        logger.error(f"Failed to clean up temp dir {temp_dir}: {cleanup_error}")
        
        except Exception as e:
            # Mark as not processing on error
            if self.timeout_handler:
                self.timeout_handler.set_processing(False)
                
            logger.error(f"Error processing build job: {e}", exc_info=True)
            # Send failure results
            try:
                self.send_results(
                    pipeline_id=message.get('pipeline_id', 'unknown'),
                    original_message=message,
                    build_results={
                        'success': False,
                        'error': str(e)
                    }
                )
            except Exception as send_error:
                logger.error(f"Failed to send error results: {send_error}")
    
    def clone_repository(self, repo_url: str, branch: str, target_dir: str):
        """
        Clone a Git repository.
        
        Args:
            repo_url: The URL of the repository to clone
            branch: The branch to checkout
            target_dir: The directory to clone into
        
        Raises:
            Exception: If cloning fails
        """
        logger.info(f"Cloning repository: {repo_url}, branch: {branch}")
        
        try:
            # Use GitPython to clone the repository
            git.Repo.clone_from(
                url=repo_url,
                to_path=target_dir,
                branch=branch,
                depth=1,  # Shallow clone for speed
                single_branch=True
            )
            
            logger.info(f"Repository cloned successfully to {target_dir}")
            return True
            
        except git.GitCommandError as e:
            logger.error(f"Git clone failed: {e}")
            raise Exception(f"Failed to clone repository: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during clone: {e}")
            raise
    
    def build_docker_image(self, 
                           repo_dir: str, 
                           image_name: str, 
                           image_tag: str, 
                           dockerfile_path: str = 'Dockerfile',
                           build_args: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Build a Docker image from a repository.
        
        Args:
            repo_dir: Path to the repository containing the Dockerfile
            image_name: Name for the Docker image
            image_tag: Tag for the Docker image
            dockerfile_path: Path to the Dockerfile, relative to repo_dir
            build_args: Docker build arguments
            
        Returns:
            Dict containing build results
        """
        start_time = time.time()
        image_ref = f"{image_name}:{image_tag}"
        build_args = build_args or {}
        
        logger.info(f"Building Docker image {image_ref} from {repo_dir}")
        
        # Full path to Dockerfile
        dockerfile_full_path = os.path.join(repo_dir, dockerfile_path)
        
        # Check if Dockerfile exists
        if not os.path.exists(dockerfile_full_path):
            error_message = f"Dockerfile not found at {dockerfile_full_path}"
            logger.error(error_message)
            return {
                'success': False,
                'image_name': image_name,
                'image_tag': image_tag,
                'dockerfile': dockerfile_path,
                'error': error_message,
                'build_time': 0
            }
        
        # Prepare build context
        context_path = os.path.dirname(dockerfile_full_path)
        dockerfile_name = os.path.basename(dockerfile_full_path)
        
        # Build the image
        build_output = []
        try:
            logger.info(f"Starting Docker build for {image_ref}")
            
            # Build the image
            image, build_logs = self.docker_client.images.build(
                path=context_path,
                dockerfile=dockerfile_name,
                tag=image_ref,
                buildargs=build_args,
                rm=True,  # Remove intermediate containers
                forcerm=True  # Always remove intermediate containers
            )
            
            # Collect build logs
            for log in build_logs:
                if 'stream' in log:
                    log_line = log['stream'].strip()
                    if log_line:
                        logger.debug(log_line)
                        build_output.append(log_line)
                elif 'error' in log:
                    error = log['error'].strip()
                    logger.error(f"Build error: {error}")
                    build_output.append(f"ERROR: {error}")
            
            # Calculate build duration
            build_time = time.time() - start_time
            
            # Get image details
            image_id = image.id
            image_size = image.attrs.get('Size', 0)
            
            logger.info(f"Successfully built image {image_ref} (ID: {image_id})")
            
            return {
                'success': True,
                'image_id': image_id,
                'image_name': image_name,
                'image_tag': image_tag,
                'image_ref': image_ref,
                'image_size': image_size,
                'build_time': build_time,
                'build_output': build_output
            }
            
        except BuildError as e:
            logger.error(f"Docker build failed: {e}")
            return {
                'success': False,
                'image_name': image_name,
                'image_tag': image_tag,
                'dockerfile': dockerfile_path,
                'error': str(e),
                'build_time': time.time() - start_time,
                'build_output': build_output
            }
        except APIError as e:
            logger.error(f"Docker API error: {e}")
            return {
                'success': False,
                'image_name': image_name,
                'image_tag': image_tag,
                'dockerfile': dockerfile_path,
                'error': f"Docker API error: {str(e)}",
                'build_time': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Unexpected error during build: {e}", exc_info=True)
            return {
                'success': False,
                'image_name': image_name,
                'image_tag': image_tag,
                'dockerfile': dockerfile_path,
                'error': f"Unexpected error: {str(e)}",
                'build_time': time.time() - start_time
            }
    
    def push_docker_image(self, 
                         image_name: str, 
                         image_tag: str, 
                         registry: str = None) -> Dict[str, Any]:
        """
        Push a Docker image to a registry.
        
        Args:
            image_name: Name of the Docker image
            image_tag: Tag of the Docker image
            registry: Registry URL (if None, uses Docker Hub)
            
        Returns:
            Dict containing push results
        """
        start_time = time.time()
        
        # Format image reference
        if registry:
            if not registry.endswith('/'):
                registry += '/'
            image_ref = f"{registry}{image_name}:{image_tag}"
            # Tag the image for the registry
            local_image_ref = f"{image_name}:{image_tag}"
            try:
                self.docker_client.images.get(local_image_ref).tag(
                    repository=f"{registry}{image_name}", 
                    tag=image_tag
                )
            except Exception as e:
                logger.error(f"Failed to tag image for registry: {e}")
                return {
                    'success': False,
                    'registry': registry,
                    'image_ref': image_ref,
                    'error': f"Failed to tag image: {str(e)}"
                }
        else:
            image_ref = f"{image_name}:{image_tag}"
        
        logger.info(f"Pushing Docker image {image_ref}")
        
        try:
            # Get registry authentication
            auth_config = self._get_registry_auth(registry)
            
            # Push the image
            push_output = []
            for line in self.docker_client.images.push(
                repository=image_ref.split(':')[0],
                tag=image_tag,
                stream=True,
                decode=True,
                auth_config=auth_config
            ):
                if 'status' in line:
                    status = line['status']
                    push_output.append(status)
                    logger.debug(status)
                if 'error' in line:
                    error = line['error']
                    push_output.append(f"ERROR: {error}")
                    logger.error(f"Push error: {error}")
                    return {
                        'success': False,
                        'registry': registry,
                        'image_ref': image_ref,
                        'error': error,
                        'push_time': time.time() - start_time,
                        'push_output': push_output
                    }
            
            push_time = time.time() - start_time
            logger.info(f"Successfully pushed image {image_ref}")
            
            return {
                'success': True,
                'registry': registry,
                'image_ref': image_ref,
                'push_time': push_time,
                'push_output': push_output
            }
            
        except APIError as e:
            logger.error(f"Docker API error during push: {e}")
            return {
                'success': False,
                'registry': registry,
                'image_ref': image_ref,
                'error': f"Docker API error: {str(e)}",
                'push_time': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Unexpected error during push: {e}", exc_info=True)
            return {
                'success': False,
                'registry': registry,
                'image_ref': image_ref,
                'error': f"Unexpected error: {str(e)}",
                'push_time': time.time() - start_time
            }
    
    def _get_registry_auth(self, registry: str = None) -> Dict[str, str]:
        """
        Get authentication configuration for a Docker registry.
        
        Args:
            registry: Registry URL
            
        Returns:
            Authentication configuration dictionary
        """
        # If no registry specified, return empty auth config
        if not registry:
            return {}
        
        # Try to get auth from environment variables
        registry_host = registry.split('/')[0]
        username_var = f"DOCKER_USERNAME_{registry_host.upper().replace('.', '_').replace(':', '_')}"
        password_var = f"DOCKER_PASSWORD_{registry_host.upper().replace('.', '_').replace(':', '_')}"
        
        username = os.getenv(username_var, os.getenv('DOCKER_USERNAME', ''))
        password = os.getenv(password_var, os.getenv('DOCKER_PASSWORD', ''))
        
        if username and password:
            logger.info(f"Using authentication for registry {registry}")
            auth_string = f"{username}:{password}"
            auth_b64 = base64.b64encode(auth_string.encode()).decode('utf-8')
            return {
                'username': username,
                'password': password,
                'auth': auth_b64
            }
        
        logger.warning(f"No authentication provided for registry {registry}")
        return {}
    
    def send_results(self, pipeline_id: str, original_message: Dict[str, Any], build_results: Dict[str, Any]):
        """
        Send build results back to the orchestrator.
        
        Args:
            pipeline_id: The ID of the pipeline
            original_message: The original message from Kafka
            build_results: The results of the build operation
        """
        logger.info(f"Sending build results for pipeline: {pipeline_id}")
        
        # Construct result message
        result_message = {
            'pipeline_id': pipeline_id,
            'stage': 'build',
            'success': build_results.get('success', False),
            'repository': original_message.get('repository', {}),
            'branch': original_message.get('branch', 'main'),
            'timestamp': time.time(),
            'results': build_results
        }
        
        # Send to results topic
        try:
            KafkaClient.send_message(
                topic=self.results_topic,
                message=result_message,
                key=pipeline_id
            )
            logger.info(f"Results sent successfully for pipeline: {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to send results: {e}", exc_info=True)
            raise

    def sanitize_docker_name(self, name):
        name = name.lower()
        name = re.sub(r'[^a-z0-9_.-]', '-', name)
        return name


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Build Agent for DevOps Pipeline")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    args = parser.parse_args()
    
    agent = None
    
    try:
        agent = BuildAgent()
        
        if args.once:
            # TODO: Implement single message processing for testing
            logger.info("Single message processing not yet implemented")
        else:
            # Start the agent
            agent.start()
            
    except KeyboardInterrupt:
        logger.info("Build agent interrupted, shutting down")
    except Exception as e:
        logger.error(f"Build agent failed: {e}", exc_info=True)
        return 1
    finally:
        # Clean shutdown of timeout handler
        if agent and hasattr(agent, 'timeout_handler') and agent.timeout_handler:
            try:
                agent.timeout_handler.stop()
                logger.info("Timeout handler stopped")
            except Exception as e:
                logger.error(f"Error stopping timeout handler: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
