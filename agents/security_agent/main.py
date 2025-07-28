#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Security Agent Main Module

This agent:
1. Listens to the Kafka topic 'agent.security'
2. Pulls the specified Docker image
3. Scans the image for vulnerabilities using Trivy
4. Reports results back to the orchestrator via 'agent.results'
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
import platform
import requests

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
import docker
from docker.errors import APIError, DockerException
from common.kafka_client import KafkaClient
from common.timeout_handler import TimeoutHandler

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("security_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("security_agent")


class SecurityAgent:
    """
    Agent that scans Docker images for vulnerabilities using Trivy.
    """
    
    def __init__(self):
        """Initialize the Security Agent."""
        self.kafka_topic = "agent.security"
        self.results_topic = "agent.results"
        self.consumer_group = "security-agent"
        self.docker_client = self._create_docker_client()
        self.trivy_path = self._get_trivy_path()
        
        # Get timeout value from pipeline configuration
        self.timeout_seconds = self._get_timeout_seconds()
        self.timeout_handler = None
        
    def _get_timeout_seconds(self) -> int:
        """Get the timeout value from the pipeline config."""
        try:
            # Default to 90 seconds if not found in config
            import yaml
            config_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'config/pipeline.yml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            
            # Find the security stage and get its timeout
            for stage in config.get('pipeline', {}).get('stages', []):
                if stage.get('name') == 'security':
                    return stage.get('timeout', 90)
            
            return 90  # Default timeout
        except Exception as e:
            logger.warning(f"Error reading timeout config, using default: {e}")
            return 90  # Default timeout if something goes wrong

    def _create_docker_client(self):
        """Create a Docker client instance."""
        try:
            # Try to create a client using Docker's default configuration
            client = docker.from_env()
            logger.info("Docker client created successfully")
            return client
        except DockerException as e:
            logger.error(f"Failed to create Docker client: {e}", exc_info=True)
            return None
    
    def _get_trivy_path(self):
        """
        Get the path to the Trivy executable.
        If not found, attempt to download and install it.
        """
        # Check if Trivy is in PATH
        if platform.system() == "Windows":
            trivy_cmd = "trivy.exe"
            # On Windows, also check in the agent directory
            agent_trivy_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), trivy_cmd
            )
            if os.path.exists(agent_trivy_path):
                return agent_trivy_path
        else:
            trivy_cmd = "trivy"
        
        # Try to find Trivy in PATH
        trivy_path = shutil.which(trivy_cmd)
        if trivy_path:
            logger.info(f"Trivy found at: {trivy_path}")
            return trivy_path
            
        # If not found, try to download and install
        try:
            return self._download_trivy()
        except Exception as e:
            logger.error(f"Failed to download Trivy: {e}", exc_info=True)
            return None
    
    def _download_trivy(self):
        """
        Download and install Trivy based on the platform.
        Returns the path to the Trivy executable.
        """
        system = platform.system()
        temp_dir = tempfile.mkdtemp(prefix="trivy_")
        
        try:
            if system == "Windows":
                # Windows download logic - Get the latest release URL first
                github_api_url = "https://api.github.com/repos/aquasecurity/trivy/releases/latest"
                logger.info(f"Fetching latest Trivy release info from GitHub API")
                
                api_response = requests.get(github_api_url)
                api_response.raise_for_status()
                release_data = api_response.json()
                
                # Find the correct Windows asset
                trivy_url = None
                for asset in release_data.get('assets', []):
                    if 'windows' in asset.get('name', '').lower() and '64bit' in asset.get('name', '').lower() and asset.get('name', '').endswith('.zip'):
                        trivy_url = asset.get('browser_download_url')
                        break
                
                if not trivy_url:
                    raise Exception("Could not find Windows Trivy download in the latest release")
                    
                zip_path = os.path.join(temp_dir, "trivy.zip")
                
                logger.info(f"Downloading Trivy for Windows from {trivy_url}")
                response = requests.get(trivy_url, stream=True)
                response.raise_for_status()
                
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract zip
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                    
                trivy_exe = os.path.join(temp_dir, "trivy.exe")
                # Copy to agent directory for future use
                agent_trivy_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "trivy.exe"
                )
                shutil.copy(trivy_exe, agent_trivy_path)
                logger.info(f"Trivy installed at: {agent_trivy_path}")
                
                # Clean up temp dir
                shutil.rmtree(temp_dir)
                return agent_trivy_path
                
            else:
                # For Linux/macOS
                if system == "Linux":
                    install_cmd = "curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
                elif system == "Darwin":  # macOS
                    install_cmd = "brew install aquasecurity/trivy/trivy"
                else:
                    raise Exception(f"Unsupported platform: {system}")
                    
                logger.info(f"Installing Trivy using: {install_cmd}")
                result = subprocess.run(
                    install_cmd, shell=True, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                
                # Check if installation was successful
                trivy_path = shutil.which("trivy")
                if trivy_path:
                    logger.info(f"Trivy installed at: {trivy_path}")
                    return trivy_path
                else:
                    logger.error("Trivy installation failed")
                    raise Exception("Trivy installation failed")
                    
        except Exception as e:
            logger.error(f"Error downloading/installing Trivy: {e}", exc_info=True)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise
    
    def start(self):
        """Start listening for security scan jobs."""
        if self.docker_client is None:
            logger.error("Cannot start Security Agent: Docker client initialization failed")
            return
            
        if self.trivy_path is None:
            logger.error("Cannot start Security Agent: Trivy not found and couldn't be installed")
            return
        
        logger.info(f"Starting Security Agent, listening to topic: {self.kafka_topic}")
        
        # Initialize timeout handler
        self.timeout_handler = TimeoutHandler(
            timeout_seconds=self.timeout_seconds, 
            agent_name="security_agent"
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
        logger.warning("Security agent timed out - gracefully shutting down")
        
        # Send a timeout message to the results topic if we have a current pipeline
        try:
            # This is a simplistic example - in production, track the current job
            KafkaClient.send_message(
                topic=self.results_topic,
                message={
                    'pipeline_id': "timeout",  # In production: store and use actual pipeline_id
                    'stage': 'security',
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
        logger.info("[DEBUG] process_message called with message: %s", json.dumps(message))
        logger.info(f"Received security scan job: {message.get('pipeline_id', 'unknown')}")
        
        # Reset timeout for new job
        if self.timeout_handler:
            self.timeout_handler.reset()
        
        try:
            # Extract required information
            pipeline_id = message.get('pipeline_id')
            if not pipeline_id:
                raise ValueError("Missing required field 'pipeline_id'")
            
            # Mark as processing (prevents timeout while actively working)
            if self.timeout_handler:
                self.timeout_handler.set_processing(True)
            
            # Get image information
            image_info = message.get('image', {})
            image_name = image_info.get('name')
            image_tag = image_info.get('tag', 'latest')
            image_ref = f"{image_name}:{image_tag}"
            
            if not image_name:
                raise ValueError("Missing required field 'image.name'")
                
            # Get scan options
            scan_options = message.get('scan_options', {})
            severity = scan_options.get('severity', 'CRITICAL,HIGH')
            timeout = scan_options.get('timeout', 300)  # 5 minutes default
            output_format = scan_options.get('format', 'json')
            
            # Pull image if needed
            logger.info(f"Preparing to scan image: {image_ref}")
            pull_result = self._ensure_image_available(image_name, image_tag)
            if not pull_result['success']:
                self.send_results(pipeline_id, message, pull_result)
                return
                
            # Perform security scan
            scan_results = self.scan_image(
                image_name=image_name, 
                image_tag=image_tag, 
                severity=severity, 
                output_format=output_format,
                timeout=timeout
            )

            # --- Gemini Integration (Secondary, Non-blocking) ---
            logger.info("[DEBUG] Entering Gemini integration block. GEMINI_ENABLED=%s, GEMINI_API_KEY set=%s", os.getenv('GEMINI_ENABLED'), bool(os.getenv('GEMINI_API_KEY')))
            gemini_suggestions = None
            try:
                gemini_enabled = os.getenv('GEMINI_ENABLED', 'false').lower() == 'true'
                gemini_api_key = os.getenv('GEMINI_API_KEY')
                gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
                if gemini_enabled and gemini_api_key:
                    gemini_api_url = os.getenv(
                        'GEMINI_API_URL',
                        f'https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent'
                    )
                    logger.info(f"Gemini integration enabled. Using model: {gemini_model}")
                    # Prepare prompt and data
                    dockerfile_content = self._extract_dockerfile(image_name)
                    prompt = (
                        "Summarize the security analysis of this Docker image in exactly 5 concise bullet points. "
                        "Each point should be 1–2 lines, focusing on the most important risks or improvements for this repository. "
                        "Be brief and clear. "
                        "Do not use ** or similar symbols for bolding words unless it is truly necessary to highlight something important. Keep the summary clean and avoid unnecessary markdown formatting."
                    )
                    gemini_payload = {
                        "contents": [
                            {"role": "user", "parts": [
                                {"text": prompt},
                                {"text": f"Image name: {image_name}"},
                                {"text": f"Dockerfile: {dockerfile_content or 'N/A'}"},
                                {"text": f"Scan results: {json.dumps(scan_results)}"}
                            ]}
                        ]
                    }
                    headers = {"Content-Type": "application/json"}
                    params = {"key": gemini_api_key}
                    response = requests.post(gemini_api_url, headers=headers, params=params, json=gemini_payload, timeout=60)
                    response.raise_for_status()
                    gemini_data = response.json()
                    gemini_suggestions = gemini_data
                    logger.info(f"Gemini suggestions: {json.dumps(gemini_suggestions, indent=2)}")
                else:
                    logger.info("Gemini integration is disabled or GEMINI_API_KEY not set; skipping Gemini analysis.")
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")
                gemini_suggestions = {"error": str(e)}
            # --- End Gemini Integration ---

            # Mark as not processing (allows timeout if idle)
            if self.timeout_handler:
                self.timeout_handler.set_processing(False)

            # Attach Gemini suggestions to results
            if gemini_suggestions:
                scan_results["gemini_suggestions"] = gemini_suggestions

            # Send results back
            self.send_results(pipeline_id, message, scan_results)
            
        except ValueError as e:
            # Mark as not processing on error
            if self.timeout_handler:
                self.timeout_handler.set_processing(False)
                
            logger.error(f"Invalid message format: {e}")
            # Send error results
            error_results = {
                'success': False,
                'error': f"Invalid message format: {str(e)}",
                'timestamp': time.time()
            }
            self.send_results(message.get('pipeline_id', 'unknown'), message, error_results)
            
        except Exception as e:
            # Mark as not processing on error
            if self.timeout_handler:
                self.timeout_handler.set_processing(False)
                
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Send error results
            error_results = {
                'success': False,
                'error': f"Processing error: {str(e)}",
                'timestamp': time.time()
            }
            self.send_results(message.get('pipeline_id', 'unknown'), message, error_results)
    
    def _ensure_image_available(self, image_name: str, image_tag: str = 'latest') -> Dict[str, Any]:
        """
        Ensure the specified Docker image is available locally.
        If not, pull it from the registry.
        
        Args:
            image_name: Name of the Docker image
            image_tag: Tag of the Docker image
            
        Returns:
            Dict containing pull results
        """
        image_ref = f"{image_name}:{image_tag}"
        logger.info(f"Ensuring image is available: {image_ref}")
        
        try:
            # Check if image exists locally
            self.docker_client.images.get(image_ref)
            logger.info(f"Image {image_ref} found locally")
            return {
                'success': True,
                'image_ref': image_ref,
                'pulled': False,
                'message': "Image found locally"
            }
        except docker.errors.ImageNotFound:
            # Image not found locally, try to pull it
            logger.info(f"Image {image_ref} not found locally, pulling...")
            try:
                self.docker_client.images.pull(image_name, image_tag)
                logger.info(f"Successfully pulled {image_ref}")
                return {
                    'success': True,
                    'image_ref': image_ref,
                    'pulled': True,
                    'message': "Image pulled successfully"
                }
            except Exception as e:
                error_msg = f"Failed to pull image {image_ref}: {str(e)}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'image_ref': image_ref,
                    'error': error_msg
                }
        except Exception as e:
            error_msg = f"Error checking image {image_ref}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'image_ref': image_ref,
                'error': error_msg
            }
    
    def scan_image(self, 
                  image_name: str, 
                  image_tag: str = 'latest',
                  severity: str = 'CRITICAL,HIGH',
                  output_format: str = 'json',
                  timeout: int = 300) -> Dict[str, Any]:
        """
        Scan a Docker image for vulnerabilities using Trivy.
        
        Args:
            image_name: Name of the Docker image
            image_tag: Tag of the Docker image
            severity: Comma-separated list of severity levels to report
            output_format: Output format (json, table)
            timeout: Scan timeout in seconds
            
        Returns:
            Dict containing scan results
        """
        image_ref = f"{image_name}:{image_tag}"
        start_time = time.time()
        
        logger.info(f"Scanning image {image_ref} for vulnerabilities")
        
        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            output_file = tmp.name
        
        try:
            # Prepare the Trivy command
            cmd = [
                self.trivy_path, 
                "image", 
                "--format", output_format,
                "--output", output_file,
                "--severity", severity,
                "--timeout", str(timeout) + "s",
                image_ref
            ]
            
            logger.info(f"Running Trivy: {' '.join(cmd)}")
            
            # Run Trivy scan
            process = subprocess.run(
                cmd, 
                check=False,  # Don't raise exception on non-zero exit
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=timeout + 30  # Add 30s buffer to the timeout
            )
            
            scan_time = time.time() - start_time
            
            # Read the output file
            with open(output_file, 'r') as f:
                try:
                    scan_output = json.load(f)
                except json.JSONDecodeError:
                    # If not valid JSON, read as text
                    f.seek(0)
                    scan_output = f.read()
            
            # Process the results
            vulnerability_count = 0
            vulnerability_summary = {}
            
            # Process the JSON output structure
            if isinstance(scan_output, dict):
                vulnerabilities = []
                results = scan_output.get('Results', [])
                
                for result in results:
                    vulns = result.get('Vulnerabilities', [])
                    if vulns:
                        vulnerabilities.extend(vulns)
                
                # Count vulnerabilities by severity
                for vuln in vulnerabilities:
                    severity = vuln.get('Severity', 'UNKNOWN')
                    vulnerability_count += 1
                    vulnerability_summary[severity] = vulnerability_summary.get(severity, 0) + 1
            
            # Determine if the scan was successful based on exit code
            # Trivy returns 0 for success with no vulnerabilities
            # 1 for vulnerabilities found
            # >1 for errors
            scan_success = process.returncode <= 1
            has_vulnerabilities = process.returncode == 1
            
            logger.info(f"Scan completed in {scan_time:.2f} seconds")
            logger.info(f"Found {vulnerability_count} vulnerabilities: {vulnerability_summary}")
            
            return {
                'success': scan_success,
                'image_ref': image_ref,
                'vulnerabilities_found': has_vulnerabilities,
                'vulnerability_count': vulnerability_count,
                'vulnerability_summary': vulnerability_summary,
                'scan_time': scan_time,
                'scan_results': scan_output,
                'exit_code': process.returncode,
                'stdout': process.stdout.decode('utf-8') if process.stdout else "",
                'stderr': process.stderr.decode('utf-8') if process.stderr else ""
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Trivy scan timed out after {timeout} seconds")
            return {
                'success': False,
                'image_ref': image_ref,
                'error': f"Scan timed out after {timeout} seconds",
                'scan_time': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Error scanning image: {e}", exc_info=True)
            return {
                'success': False,
                'image_ref': image_ref,
                'error': f"Scan error: {str(e)}",
                'scan_time': time.time() - start_time
            }
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(output_file):
                    os.unlink(output_file)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file: {e}")
    
    def send_results(self, pipeline_id: str, original_message: Dict[str, Any], scan_results: Dict[str, Any]):
        """
        Send scan results back to the orchestrator.
        
        Args:
            pipeline_id: The ID of the pipeline
            original_message: The original message from Kafka
            scan_results: The results of the security scan
        """
        logger.info(f"Sending security scan results for pipeline: {pipeline_id}")
        
        # Construct result message
        result_message = {
            'pipeline_id': pipeline_id,
            'stage': 'security',
            'success': scan_results.get('success', False),
            'timestamp': time.time(),
            'results': scan_results
        }
        
        # Add image info from original message if available
        image_info = original_message.get('image', {})
        if image_info:
            result_message['image'] = image_info
        
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

    def _extract_dockerfile(self, image_name: str) -> str:
        """
        Attempt to extract the Dockerfile content for the given image if available.
        Returns the Dockerfile as a string, or None if not found.
        """
        # This is a placeholder. In a real system, you might fetch from source repo or image labels.
        # For now, just return None.
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Security Agent for DevOps Pipeline")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    args = parser.parse_args()
    
    agent = None
    
    try:
        agent = SecurityAgent()
        
        if args.once:
            # TODO: Implement single message processing for testing
            logger.info("Single message processing not yet implemented")
        else:
            # Start the agent
            agent.start()
            
    except KeyboardInterrupt:
        logger.info("Security agent interrupted, shutting down")
    except Exception as e:
        logger.error(f"Security agent failed: {e}", exc_info=True)
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
