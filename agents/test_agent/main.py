#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test Agent Main Module

This agent:
1. Listens to the Kafka topic 'agent.test'
2. Clones the specified GitHub repository
3. Runs pytest on the code
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
from typing import Dict, Any, List, Optional

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
import git  # GitPython for better Git handling
from common.kafka_client import KafkaClient
from common.timeout_handler import TimeoutHandler

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_agent")


class TestAgent:
    """
    Agent that runs automated tests using pytest.
    """
    
    def __init__(self):
        """Initialize the Test Agent."""
        self.kafka_topic = "agent.test"
        self.results_topic = "agent.results"
        self.consumer_group = "test-agent"
        
        # Get timeout value from pipeline configuration
        self.timeout_seconds = self._get_timeout_seconds()
        self.timeout_handler = None
        
    def _get_timeout_seconds(self) -> int:
        """Get the timeout value from the pipeline config."""
        try:
            # Default to 50 seconds if not found in config
            import yaml
            config_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'config/pipeline.yml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            
            # Find the test stage and get its timeout
            for stage in config.get('pipeline', {}).get('stages', []):
                if stage.get('name') == 'test':
                    return stage.get('timeout', 50)
            
            return 50  # Default timeout
        except Exception as e:
            logger.warning(f"Error reading timeout config, using default: {e}")
            return 50  # Default timeout if something goes wrong
        
    def start(self):
        """Start listening for test jobs."""
        logger.info(f"Starting Test Agent, listening to topic: {self.kafka_topic}")
        
        # Initialize timeout handler
        self.timeout_handler = TimeoutHandler(
            timeout_seconds=self.timeout_seconds, 
            agent_name="test_agent"
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
        logger.warning("Test agent timed out - gracefully shutting down")
        # In a real implementation, you might want to:
        # 1. Clean up any temporary resources
        # 2. Send a timeout notification to the orchestrator
        # 3. Reset the agent state
        
        # Send a timeout message to the results topic if we have a current pipeline
        try:
            # This is a simplistic example - in production, track the current job
            KafkaClient.send_message(
                topic=self.results_topic,
                message={
                    'pipeline_id': "timeout",  # In production: store and use actual pipeline_id
                    'stage': 'test',
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
        Process a test job message.
        
        Args:
            message: The Kafka message containing job details
        """
        logger.info(f"Received test job: {message.get('pipeline_id', 'unknown')}")
        
        # Reset timeout for new job
        if self.timeout_handler:
            self.timeout_handler.reset()
        
        try:
            # Extract required information
            pipeline_id = message.get('pipeline_id')
            repo_url = message.get('repository', {}).get('clone_url')
            branch = message.get('branch', 'main')
            
            if not pipeline_id or not repo_url:
                raise ValueError("Missing required fields in message")
            
            # Clone repository and run tests
            temp_dir = None
            try:
                # Mark as processing (prevents timeout while actively working)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(True)
                
                # Create a temporary directory for the repository
                temp_dir = tempfile.mkdtemp(prefix="test_")
                logger.info(f"Using temporary directory: {temp_dir}")
                
                # Clone the repository
                self.clone_repository(repo_url, branch, temp_dir)
                
                # Run tests
                test_results = self.run_tests(temp_dir)
                
                # Mark as not processing (allows timeout if idle)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(False)
                
                # Send results
                self.send_results(pipeline_id, message, test_results)
                
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
                
            logger.error(f"Error processing test job: {e}", exc_info=True)
            # Send failure results
            try:
                self.send_results(
                    pipeline_id=message.get('pipeline_id', 'unknown'),
                    original_message=message,
                    test_results={
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
    
    def run_tests(self, repo_dir: str) -> Dict[str, Any]:
        """
        Run pytest on a Python repository.
        
        Args:
            repo_dir: Path to the repository
        
        Returns:
            Dict containing test results
        """
        logger.info(f"Running tests on {repo_dir}")
        
        # Check if there are any tests to run
        test_files = []
        for root, _, files in os.walk(repo_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    test_files.append(os.path.join(root, file))
                elif file == 'pytest.ini' or file == 'conftest.py':
                    # These files indicate tests are present
                    test_files.append(os.path.join(root, file))
        
        if not test_files:
            logger.warning(f"No test files found in {repo_dir}")
            return {
                'success': True,
                'message': "No test files found",
                'tests_run': 0,
                'passing': 0,
                'failing': 0,
                'skipped': 0,
                'details': []
            }
        
        try:
            # Create a temporary file for the test output
            output_file = os.path.join(tempfile.gettempdir(), f"pytest_output_{int(time.time())}.json")
            
            # Run pytest with coverage using the current Python interpreter
            cmd = [
                sys.executable, "-m", "pytest",
                "-v",
                "--json-report",
                f"--json-report-file={output_file}",
                "--cov=.",
                repo_dir
            ]
            timeout = self.timeout_seconds
            result = None
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=repo_dir,
                    timeout=timeout
                )
            except Exception as e:
                logger.error(f"Error running tests: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "output": None
                }
            
            # Try to parse JSON output file
            try:
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        test_output = json.load(f)
                else:
                    test_output = {'summary': {'failed': 0, 'passed': 0, 'total': 0, 'skipped': 0}}
            except json.JSONDecodeError:
                # Fall back to parsing output
                test_output = self._parse_pytest_output(result.stdout, result.stderr)
            
            # Extract summary metrics
            summary = test_output.get('summary', {})
            tests_run = summary.get('total', 0)
            passing = summary.get('passed', 0)
            failing = summary.get('failed', 0)
            skipped = summary.get('skipped', 0)
            
            # Generate a summary message
            if failing == 0:
                message = f"All tests passed ({passing}/{tests_run})"
                if skipped > 0:
                    message += f", {skipped} skipped"
            else:
                message = f"Tests failed: {failing}/{tests_run} failing"
            
            # Get coverage info if available
            coverage_info = self._extract_coverage_info(result.stdout)
            
            return {
                'success': failing == 0,  # Success if no failures
                'message': message,
                'tests_run': tests_run,
                'passing': passing,
                'failing': failing,
                'skipped': skipped,
                'coverage': coverage_info,
                'output_file': output_file if os.path.exists(output_file) else None,
                'stdout': result.stdout if result else '',
                'stderr': result.stderr if result else '',
                'details': test_output
            }
        except Exception as e:
            logger.error(f"Error running tests: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Failed to run tests: {str(e)}",
                'error': str(e),
                'stdout': getattr(result, 'stdout', '') if 'result' in locals() and result else '',
                'stderr': getattr(result, 'stderr', '') if 'result' in locals() and result else ''
            }
    
    def _parse_pytest_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse pytest output to extract summary information.
        
        Args:
            stdout: Standard output from pytest
            stderr: Standard error from pytest
        
        Returns:
            Dict containing parsed summary information
        """
        total = 0
        passed = 0
        failed = 0
        skipped = 0
        
        # Look for summary line
        summary_lines = [line for line in stdout.split('\n') if '= FAILURES =' in line or '= passed' in line]
        if summary_lines:
            summary = summary_lines[-1]
            # Extract numbers from: "5 passed, 2 failed, 1 skipped"
            parts = summary.split(',')
            for part in parts:
                if 'passed' in part:
                    passed = int(part.strip().split()[0])
                    total += passed
                if 'failed' in part:
                    failed = int(part.strip().split()[0])
                    total += failed
                if 'skipped' in part:
                    skipped = int(part.strip().split()[0])
                    total += skipped
        
        return {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'skipped': skipped
            },
            'stdout': stdout,
            'stderr': stderr
        }
    
    def _extract_coverage_info(self, stdout: str) -> Dict[str, Any]:
        """
        Extract coverage information from pytest-cov output.
        
        Args:
            stdout: Standard output from pytest with coverage
        
        Returns:
            Dict containing coverage information
        """
        coverage_info = {
            'percent': 0.0,
            'covered_lines': 0,
            'total_lines': 0,
            'missing_lines': 0
        }
        
        # Look for coverage summary line
        coverage_lines = [line for line in stdout.split('\n') if 'TOTAL' in line and '%' in line]
        if coverage_lines:
            # Format: "TOTAL       100     20    80%"
            parts = coverage_lines[0].split()
            if len(parts) >= 4:
                try:
                    coverage_info['total_lines'] = int(parts[-3])
                    coverage_info['missing_lines'] = int(parts[-2])
                    coverage_info['percent'] = float(parts[-1].replace('%', ''))
                    coverage_info['covered_lines'] = coverage_info['total_lines'] - coverage_info['missing_lines']
                except (ValueError, IndexError):
                    pass
        
        return coverage_info
    
    def send_results(self, pipeline_id: str, original_message: Dict[str, Any], test_results: Dict[str, Any]):
        """
        Send test results back to the orchestrator.
        
        Args:
            pipeline_id: The ID of the pipeline
            original_message: The original message from Kafka
            test_results: The results of the test operation
        """
        logger.info(f"Sending test results for pipeline: {pipeline_id}")
        
        # Construct result message
        result_message = {
            'pipeline_id': pipeline_id,
            'stage': 'test',
            'success': test_results.get('success', False),
            'repository': original_message.get('repository', {}),
            'branch': original_message.get('branch', 'main'),
            'timestamp': time.time(),
            'results': test_results
        }
        
        # Send to results topic
        try:
            KafkaClient.send_message(
                topic=self.results_topic,
                message=result_message,
                key=pipeline_id
            )
            logger.info(f"Test results sent successfully for pipeline: {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to send test results: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Agent for DevOps Pipeline")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    args = parser.parse_args()
    
    agent = None
    
    try:
        agent = TestAgent()
        
        if args.once:
            # TODO: Implement single message processing for testing
            logger.info("Single message processing not yet implemented")
        else:
            # Start the agent
            agent.start()
            
    except KeyboardInterrupt:
        logger.info("Test agent interrupted, shutting down")
    except Exception as e:
        logger.error(f"Test agent failed: {e}", exc_info=True)
        return 1
    finally:
        # Clean shutdown of timeout handler
        if agent and agent.timeout_handler:
            try:
                agent.timeout_handler.stop()
                logger.info("Timeout handler stopped")
            except Exception as e:
                logger.error(f"Error stopping timeout handler: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
