#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enhanced Lint Agent Main Module

This agent:
1. Listens to the Kafka topic 'agent.lint'
2. Clones the specified GitHub repository
3. Runs both pylint and Gemini AI analysis in parallel
4. Combines results for comprehensive feedback
5. Falls back to pylint-only if Gemini fails
6. Reports results back to the orchestrator via 'agent.results'
"""

import os
import sys
import json
import logging
import tempfile
import shutil
import subprocess
import time
import asyncio
import threading
from typing import Dict, Any, List, Optional, Tuple
import argparse
import stat
from dataclasses import asdict
import re
from pathlib import Path
import io

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
import git  # GitPython for better Git handling
from common.kafka_client import KafkaClient
from common.timeout_handler import TimeoutHandler
from agents.lint_agent.ml_model.advanced_ml_lint_agent import AdvancedMLLintAgent

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("lint_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("lint_agent")


class LintAgent:
    """
    Enhanced agent that performs static code analysis using both pylint and Gemini AI.
    """
    
    def __init__(self):
        """Initialize the Enhanced Lint Agent."""
        self.kafka_topic = "agent.lint"
        self.results_topic = "agent.results"
        self.consumer_group = "lint-agent"
        
        # Get timeout value from pipeline configuration
        self.timeout_seconds = self._get_timeout_seconds()
        self.timeout_handler = None
        
        # Initialize the advanced ML lint agent
        ml_model_dir = os.path.join(os.path.dirname(__file__), "ml_model")
        self.advanced_lint_agent = AdvancedMLLintAgent(
            model_path=os.path.join(ml_model_dir, "checkpoints", "codet5p-finetuned"),
            config_path=os.path.join(ml_model_dir, "advanced_ml_lint_config.json")
        )
        
    def _get_timeout_seconds(self) -> int:
        """Get the timeout value from the pipeline config."""
        try:
            # Default to 30 seconds if not found in config
            import yaml
            config_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'config/pipeline.yml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            
            # Find the lint stage and get its timeout
            for stage in config.get('pipeline', {}).get('stages', []):
                if stage.get('name') == 'lint':
                    return stage.get('timeout', 30)
            
            return 30  # Default timeout
        except Exception as e:
            logger.warning(f"Error reading timeout config, using default: {e}")
            return 30  # Default timeout if something goes wrong
        
    def start(self):
        """Start listening for lint jobs."""
        logger.info(f"Starting Enhanced Lint Agent, listening to topic: {self.kafka_topic}")
        
        # Initialize timeout handler
        self.timeout_handler = TimeoutHandler(
            timeout_seconds=self.timeout_seconds, 
            agent_name="lint_agent"
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
        logger.warning("Lint agent timed out - gracefully shutting down")
        
        # Send a timeout message to the results topic
        try:
            KafkaClient.send_message(
                topic=self.results_topic,
                message={
                    'pipeline_id': "timeout",
                    'stage': 'lint',
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
        
    def _on_rm_error(self, func, path, exc_info):
        """Error handler for shutil.rmtree to handle read-only files on Windows."""
        import os
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception as e:
            logger.warning(f"Failed to forcibly remove {path}: {e}")
    
    def process_message(self, message: Dict[str, Any]):
        """
        Process a lint job message.
        
        Args:
            message: The Kafka message containing job details
        """
        logger.info(f"Received lint job: {message.get('pipeline_id', 'unknown')}")
        
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
            
            # Clone repository and run enhanced lint
            temp_dir = None
            try:
                # Mark as processing (prevents timeout while actively working)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(True)
                
                # Create a temporary directory for the repository
                temp_dir = tempfile.mkdtemp(prefix="lint_")
                logger.info(f"Using temporary directory: {temp_dir}")
                
                # Clone the repository
                self.clone_repository(repo_url, branch, temp_dir)
                
                # Run enhanced lint analysis (pylint + Gemini)
                lint_results = self.run_enhanced_lint(temp_dir)
                
                # If no issues, call Mistral for explanation
                if isinstance(lint_results, dict) and (not lint_results.get('issues') or len(lint_results.get('issues', [])) == 0):
                    # Gather checked files
                    checked_files = [str(f) for f in list(Path(temp_dir).rglob("*.py")) if not self.advanced_lint_agent._should_skip_file(str(f))]
                    explanation = self.advanced_lint_agent.get_no_issues_explanation(checked_files)
                    lint_results['no_issues_explanation'] = explanation
                
                # Mark as not processing (allows timeout if idle)
                if self.timeout_handler:
                    self.timeout_handler.set_processing(False)
                
                # Send results
                self.send_results(pipeline_id, message, lint_results)
                
            finally:
                # Robust cleanup of temporary directory
                if temp_dir and os.path.exists(temp_dir):
                    logger.info(f"Cleaning up temporary directory: {temp_dir}")
                    for attempt in range(3):
                        try:
                            self._on_rm_error  # Ensure method exists
                            shutil.rmtree(temp_dir, onerror=self._on_rm_error)
                            break
                        except Exception as cleanup_err:
                            logger.warning(f"Attempt {attempt+1}: Failed to clean up temp dir {temp_dir}: {cleanup_err}")
                            time.sleep(1)
                    else:
                        logger.error(f"Could not remove temp dir {temp_dir} after 3 attempts.")
                        # TEMP DIR CLEANUP REMOVED
                pass
        
        except Exception as e:
            # Mark as not processing on error
            if self.timeout_handler:
                self.timeout_handler.set_processing(False)
                
            logger.error(f"Error processing lint job: {e}", exc_info=True)
            # Send failure results
            try:
                self.send_results(
                    pipeline_id=message.get('pipeline_id', 'unknown'),
                    original_message=message,
                    lint_results={
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
    
    def run_enhanced_lint(self, repo_dir: str) -> Dict[str, Any]:
        """
        Run advanced ML lint analysis and return results, capturing ML CLI logs.
        """
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()
        try:
            results = self.advanced_lint_agent.analyze_project_intelligent(repo_dir)
        finally:
            sys.stdout = old_stdout
        ml_logs = mystdout.getvalue().splitlines()
        # Attach ML logs to results
        results['ml_logs'] = ml_logs
        return results
    
    def run_pylint(self, repo_dir: str, python_files: List[str]) -> Dict[str, Any]:
        """
        Run pylint on Python files.
        
        Args:
            repo_dir: Path to the repository
            python_files: List of Python file paths
        
        Returns:
            Dict containing pylint results
        """
        logger.info(f"Running pylint on {len(python_files)} Python files")
        
        try:
            # Create a temporary file for the lint output
            output_file = os.path.join(tempfile.gettempdir(), f"pylint_output_{int(time.time())}.txt")
            
            # Use .pylintrc from repo_dir if it exists
            pylintrc_path = os.path.join(repo_dir, ".pylintrc")
            cmd = [
                sys.executable, "-m", "pylint",
                "--rcfile", pylintrc_path if os.path.exists(pylintrc_path) else "",
                "--output-format=json",
                *python_files
            ]
            # Remove empty rcfile argument if not present
            if cmd[4] == "":
                del cmd[3:5]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Parse the results
            try:
                lint_output = json.loads(result.stdout) if result.stdout.strip() else []
            except json.JSONDecodeError:
                # Fall back to text output if JSON parsing fails
                lint_output = result.stdout
            
            # Write output to file for reference
            with open(output_file, 'w') as f:
                if isinstance(lint_output, list):
                    json.dump(lint_output, f, indent=2)
                else:
                    f.write(lint_output)
            
            logger.info(f"Pylint results written to {output_file}")
            
            # Extract score from stderr if available
            score = 0.0
            for line in result.stderr.split('\n'):
                if "Your code has been rated at" in line:
                    try:
                        score_text = line.split("rated at ")[1].split('/')[0]
                        score = float(score_text)
                    except (IndexError, ValueError):
                        pass
            
            # Generate a summary
            error_count = len([msg for msg in lint_output if isinstance(msg, dict) and msg.get('type') == 'error']) if isinstance(lint_output, list) else 0
            warning_count = len([msg for msg in lint_output if isinstance(msg, dict) and msg.get('type') == 'warning']) if isinstance(lint_output, list) else 0
            
            return {
                'success': result.returncode < 8,  # pylint returns 0 for no errors, higher for errors
                'score': score,
                'output_file': output_file,
                'error_count': error_count,
                'warning_count': warning_count,
                'message': f"Pylint completed with score {score}/10.0, {error_count} errors, {warning_count} warnings",
                'details': lint_output if isinstance(lint_output, list) else {'raw_output': lint_output}
            }
            
        except Exception as e:
            logger.error(f"Error running pylint: {e}", exc_info=True)
            return {
                'success': False,
                'message': f"Failed to run pylint: {str(e)}",
                'error': str(e)
            }
    
    def send_results(self, pipeline_id: str, original_message: Dict[str, Any], lint_results: Dict[str, Any]):
        """
        Send lint results back to the orchestrator.
        
        Args:
            pipeline_id: The ID of the pipeline
            original_message: The original message from Kafka
            lint_results: The results of the lint operation
        """
        logger.info(f"Sending enhanced lint results for pipeline: {pipeline_id}")
        
        # Convert CodeIssue objects to dicts if present
        if 'issues' in lint_results and isinstance(lint_results['issues'], list):
            lint_results['issues'] = [
                asdict(issue) if hasattr(issue, '__dataclass_fields__') else issue
                for issue in lint_results['issues']
            ]
        # Convert ProjectContext to dict if present
        if 'project_context' in lint_results and hasattr(lint_results['project_context'], '__dataclass_fields__'):
            lint_results['project_context'] = asdict(lint_results['project_context'])
        
        # Construct result message
        result_message = {
            'pipeline_id': pipeline_id,
            'stage': 'lint',
            'success': lint_results.get('success', True),
            'repository': original_message.get('repository', {}),
            'branch': original_message.get('branch', 'main'),
            'timestamp': time.time(),
            'results': lint_results
        }
        
        # Send to results topic
        try:
            KafkaClient.send_message(
                topic=self.results_topic,
                message=result_message,
                key=pipeline_id
            )
            logger.info(f"Enhanced results sent successfully for pipeline: {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to send results: {e}", exc_info=True)
            raise

    def _make_paths_relative(self, results: dict, repo_dir: str):
        """
        Convert all file_path fields in issues to be relative to the repo root.
        """
        import os
        issues = results.get("issues", [])
        for issue in issues:
            # If issue is a dataclass, convert to dict for path update
            if hasattr(issue, '__dataclass_fields__'):
                issue = asdict(issue)
            if "file_path" in issue and issue["file_path"].startswith(repo_dir):
                rel_path = os.path.relpath(issue["file_path"], repo_dir)
                issue["file_path"] = rel_path

    def _filter_real_suggestions(self, issues):
        filtered = []
        for issue in issues:
            explanation = issue.get('explanation', '') if isinstance(issue, dict) else getattr(issue, 'explanation', '')
            suggested_fix = issue.get('suggested_fix', '') if isinstance(issue, dict) else getattr(issue, 'suggested_fix', '')
            ml_reasoning = issue.get('ml_reasoning', '') if isinstance(issue, dict) else getattr(issue, 'ml_reasoning', '')

            # Remove prompt-like or repetitive explanations
            if any(phrase in explanation.lower() for phrase in [
                'analyze this code', 'review this code', 'suggest fixes', 'potential problems'
            ]):
                continue
            if any(phrase in ml_reasoning.lower() for phrase in [
                'analyze this code', 'review this code', 'suggest fixes', 'potential problems'
            ]):
                continue
            # Remove generic or empty fixes
            if suggested_fix.strip().lower() in ['apply suggested improvements', '', 'no suggestion']:
                continue
            # Remove if explanation or reasoning is mostly code (e.g., >50% non-alpha)
            if len(explanation) > 20 and (len(re.sub(r'[^a-zA-Z]', '', explanation)) / len(explanation)) < 0.3:
                continue
            if len(ml_reasoning) > 20 and (len(re.sub(r'[^a-zA-Z]', '', ml_reasoning)) / len(ml_reasoning)) < 0.3:
                continue

            filtered.append(issue)
        return filtered


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enhanced Lint Agent for DevOps Pipeline")
    parser.add_argument("--once", action="store_true", help="Process one message and exit")
    parser.add_argument("--test-gemini", action="store_true", help="Test Gemini API connection")
    args = parser.parse_args()
    
    agent = None
    
    try:
        agent = LintAgent()
        
        if args.test_gemini:
            # Test Gemini API
            print("Testing Gemini API connection...")
            test_files = ["test_file.py"]
            test_pylint_results = {'success': True, 'score': 8.0, 'error_count': 0, 'warning_count': 2}
            gemini_results = agent.gemini_analyzer.analyze_code(test_files, test_pylint_results)
            print(f"Gemini test results: {json.dumps(gemini_results, indent=2)}")
            return 0
        
        if args.once:
            # TODO: Implement single message processing for testing
            logger.info("Single message processing not yet implemented")
        else:
            # Start the agent
            agent.start()
            
    except KeyboardInterrupt:
        logger.info("Lint agent interrupted, shutting down")
    except Exception as e:
        logger.error(f"Lint agent failed: {e}", exc_info=True)
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
