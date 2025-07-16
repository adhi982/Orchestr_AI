#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Results Handler Module for DevOps Orchestrator

This module:
1. Listens to the 'agent.results' Kafka topic
2. Processes results from various agents (lint, test, build, security)
3. Implements retry logic for failed stages
4. Sends notifications (e.g., to Slack) based on results
"""

import os
import json
import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

import requests
from dotenv import load_dotenv

# Import from project
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.kafka_client import KafkaClient

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("orchestrator_results.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("results_handler")

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY_SECONDS = int(os.getenv('RETRY_DELAY_SECONDS', '60'))


class ResultsTracker:
    """
    Tracks the results of pipeline stages and manages retry attempts.
    """
    def __init__(self):
        # Dictionary to track pipeline results by pipeline ID
        # Format: {pipeline_id: {stage: {status, results, retries, timestamp}}}
        self.pipelines = {}
        # New: logs and notifications per pipeline
        self.logs = {}  # {pipeline_id: [ {time, agent, message} ]}
        self.notifications = {}  # {pipeline_id: [ {type, title, message, time} ]}
        # Lock for thread-safe access
        self.lock = threading.RLock()
    
    def record_result(self, pipeline_id: str, stage: str, success: bool, results: Dict[str, Any], 
                      status: str = None) -> Dict[str, Any]:
        """
        Record the result of a pipeline stage.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            stage (str): The pipeline stage (lint, test, build, security, etc.)
            success (bool): Whether the stage was successful
            results (Dict[str, Any]): Detailed results data
            status (str, optional): Explicit status to set (success, failed, in_progress, pending)
            
        Returns:
            Dict: Updated pipeline status
        """
        with self.lock:
            # Create pipeline entry if it doesn't exist
            if pipeline_id not in self.pipelines:
                self.pipelines[pipeline_id] = {}
            # Get previous stage info if exists
            prev_stage = self.pipelines[pipeline_id].get(stage, {})
            # Determine status - use provided status if given, otherwise infer from success
            if status is not None:
                stage_status_value = status
            else:
                stage_status_value = 'success' if success else 'failed'
            logger.info(f"🎯 Setting stage {stage} status to: {stage_status_value} (success={success}, provided_status={status})")
            # Set start_time and end_time
            now_iso = datetime.now().isoformat()
            start_time = prev_stage.get('start_time')
            end_time = prev_stage.get('end_time')
            if stage_status_value == 'in_progress':
                if not start_time:
                    start_time = now_iso
                end_time = None
            elif stage_status_value in ['success', 'failed']:
                if not start_time:
                    start_time = now_iso  # fallback if missing
                end_time = now_iso
            # Record the result
            stage_status = {
                'status': stage_status_value,
                'results': results,
                'retries': prev_stage.get('retries', 0),
                'timestamp': now_iso,
                'start_time': start_time,
                'end_time': end_time
            }
            logger.info(f"📝 Recording stage status: {json.dumps(stage_status, indent=2)}")
            # Update in pipelines dictionary
            self.pipelines[pipeline_id][stage] = stage_status
            logger.info(f"💾 Updated pipeline {pipeline_id} stage {stage}. Current stages: {list(self.pipelines[pipeline_id].keys())}")
            # Add demo log and notification
            self.add_log(pipeline_id, stage, f'Stage {stage} set to {stage_status_value}.')
            # Add ML logs if present and this is the lint stage
            if stage == 'lint' and results and 'ml_logs' in results:
                for ml_log in results['ml_logs']:
                    self.add_log(pipeline_id, stage, ml_log)
            if stage_status_value == 'success':
                self.add_notification(pipeline_id, 'success', f'{stage.title()} Succeeded', f'Stage {stage} completed successfully.')
            elif stage_status_value == 'failed':
                self.add_notification(pipeline_id, 'error', f'{stage.title()} Failed', f'Stage {stage} failed.')
            # Return a copy of the current pipeline status
            return self._get_pipeline_status(pipeline_id)
    
    def should_retry(self, pipeline_id: str, stage: str) -> bool:
        """
        Determine if a failed stage should be retried.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            stage (str): The pipeline stage (lint, test, build, security, etc.)
            
        Returns:
            bool: True if the stage should be retried, False otherwise
        """
        with self.lock:
            # Check if pipeline and stage exist
            if pipeline_id not in self.pipelines or stage not in self.pipelines[pipeline_id]:
                return False
            
            stage_info = self.pipelines[pipeline_id][stage]
            
            # Only retry failures
            if stage_info['status'] == 'success':
                return False
            
            # Check retry count
            return stage_info['retries'] < MAX_RETRIES
    
    def increment_retry_count(self, pipeline_id: str, stage: str) -> int:
        """
        Increment the retry count for a stage.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            stage (str): The pipeline stage to retry
            
        Returns:
            int: New retry count
        """
        with self.lock:
            if pipeline_id not in self.pipelines or stage not in self.pipelines[pipeline_id]:
                return 0
            
            current_retries = self.pipelines[pipeline_id][stage].get('retries', 0)
            new_retries = current_retries + 1
            
            logger.info(f"Incrementing retry count for pipeline {pipeline_id}, stage {stage}: {current_retries} -> {new_retries} (MAX_RETRIES={MAX_RETRIES})")
            
            # Update retry count
            self.pipelines[pipeline_id][stage]['retries'] = new_retries
            return new_retries
    
    def get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Get the current status of a pipeline.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            
        Returns:
            Dict: Current pipeline status
        """
        with self.lock:
            return self._get_pipeline_status(pipeline_id)
    
    def _get_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Internal method to get pipeline status without locking.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            
        Returns:
            Dict: Current pipeline status
        """
        logger.info(f"Getting status for pipeline: {pipeline_id}")
        logger.info(f"Current pipelines tracked: {list(self.pipelines.keys())}")
        
        if pipeline_id not in self.pipelines:
            logger.warning(f"Pipeline {pipeline_id} not found in tracking system")
            return {'pipeline_id': pipeline_id, 'status': 'unknown', 'stages': {}, 'message': 'Pipeline not found in tracking system'}
        
        # Determine overall status
        stages = self.pipelines[pipeline_id]
        logger.info(f"Pipeline {pipeline_id} has stages: {list(stages.keys())}")
        
        # Only consider agent stages with 'status' key
        agent_stages = {k: v for k, v in stages.items() if isinstance(v, dict) and 'status' in v}
        # Count states to determine overall status
        stage_statuses = {}
        for stage, info in agent_stages.items():
            status = info.get('status', 'unknown')
            retries = info.get('retries', 0)
            retry_timestamp = info.get('retry_timestamp', None)
            stage_statuses[stage] = {
                'status': status,
                'retries': retries,
                'retry_timestamp': retry_timestamp,
            }
        
        # Check for terminal failures (exhausted retries)
        terminal_failures = False
        for stage, info in agent_stages.items():
            if info['status'] == 'failed' and info['retries'] >= MAX_RETRIES:
                logger.warning(f"Stage {stage} has terminally failed with {info['retries']} retries (MAX_RETRIES={MAX_RETRIES})")
                terminal_failures = True
        
        # Count different statuses
        num_success = sum(1 for status in stage_statuses.values() if status['status'] == 'success')
        num_failed = sum(1 for status in stage_statuses.values() if status['status'] == 'failed')
        num_pending = sum(1 for status in stage_statuses.values() if status['status'] == 'pending')
        num_in_progress = sum(1 for status in stage_statuses.values() if status['status'] == 'in_progress')
        
        # Also count failed stages that still have retries available (not terminal)
        retriable_failures = 0
        for stage, info in agent_stages.items():
            if info['status'] == 'failed' and info['retries'] < MAX_RETRIES:
                retriable_failures += 1
        
        # Debug the terminal failure detection
        logger.info(f"Pipeline {pipeline_id} terminal failures check: {terminal_failures}")
        for stage, info in agent_stages.items():
            if info['status'] == 'failed':
                logger.info(f"  Stage {stage}: failed with retries {info['retries']}/{MAX_RETRIES} (terminal: {info['retries'] >= MAX_RETRIES})")
        
        # Determine status with clear priority:
        if num_success == len(stage_statuses):
            status = 'success'
        elif terminal_failures:
            status = 'failed'
        elif num_in_progress > 0:
            status = 'in_progress'
        elif retriable_failures > 0:
            status = 'in_progress'  # These will be retried
        elif num_pending > 0:
            status = 'pending'
        else:
            status = 'unknown'  # Shouldn't happen but handle the edge case
        
        logger.info(f"Calculated status for pipeline {pipeline_id}: {status} (success:{num_success}, failed:{num_failed}, pending:{num_pending}, in_progress:{num_in_progress}, retriable_failures:{retriable_failures})")
        
        # Return formatted status (only agent stages)
        return {
            'pipeline_id': pipeline_id,
            'status': status,
            'stages': stage_statuses,
            # New: include logs and notifications
            'logs': self.logs.get(pipeline_id, []),
            'notifications': self.notifications.get(pipeline_id, [])
        }
    
    def cleanup_old_pipelines(self, max_age_hours: int = 24) -> int:
        """
        Remove pipelines older than specified hours.
        
        Args:
            max_age_hours (int): Maximum age in hours
            
        Returns:
            int: Number of pipelines removed
        """
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for pipeline_id, stages in self.pipelines.items():
                # Check if any stage timestamp is recent
                timestamps = [
                    datetime.fromisoformat(info['timestamp']) 
                    for info in stages.values() 
                    if 'timestamp' in info
                ]
                
                if not timestamps:
                    continue
                
                latest_timestamp = max(timestamps)
                age_hours = (now - latest_timestamp).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    to_remove.append(pipeline_id)
            
            # Remove old pipelines
            for pipeline_id in to_remove:
                del self.pipelines[pipeline_id]
                
            return len(to_remove)
    
    def initialize_pipeline(self, pipeline_id: str, stages: List[str]):
        """
        Initialize a pipeline with pending status for all stages.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            stages (List[str]): List of stage names in the pipeline
            
        Returns:
            Dict: Initialized pipeline status
        """
        with self.lock:
            if pipeline_id not in self.pipelines:
                self.pipelines[pipeline_id] = {}
            self.add_notification(pipeline_id, 'info', 'Pipeline Created', f'Pipeline {pipeline_id} initialized.')
            self.add_log(pipeline_id, 'orchestrator', f'Pipeline {pipeline_id} created with stages: {", ".join(stages)}')
            for stage in stages:
                if stage not in self.pipelines[pipeline_id]:
                    now_iso = datetime.now().isoformat()
                    self.pipelines[pipeline_id][stage] = {
                        'status': 'pending',
                        'results': {},
                        'retries': 0,
                        'timestamp': now_iso,
                        'start_time': None,
                        'end_time': None
                    }
            return self._get_pipeline_status(pipeline_id)
    
    def mark_stage_in_progress(self, pipeline_id: str, stage: str) -> Dict[str, Any]:
        """
        Mark a pipeline stage as in_progress when agent begins processing.
        
        Args:
            pipeline_id (str): The unique identifier for the pipeline
            stage (str): The pipeline stage (lint, test, build, security, etc.)
            
        Returns:
            Dict: Updated pipeline status
        """
        return self.record_result(
            pipeline_id=pipeline_id,
            stage=stage,
            success=False,  # Not yet determined
            results={},
            status='in_progress'
        )
    
    def force_update_pipeline_status(self, pipeline_id: str) -> Dict[str, Any]:
        """
        Force update a pipeline's status if it appears to be stuck.
        This is used to kick-start pipelines that aren't transitioning properly.
        
        Args:
            pipeline_id (str): The pipeline ID to update
            
        Returns:
            Dict: Updated pipeline status
        """
        with self.results_tracker.lock:
            if pipeline_id not in self.results_tracker.pipelines:
                logger.warning(f"Cannot force update - pipeline {pipeline_id} not found")
                return {'pipeline_id': pipeline_id, 'status': 'unknown', 'stages': {}}
            
            # Check if all stages are pending and have retry counts > 0
            # This suggests we've attempted to run them but they're stuck in pending
            stages = self.results_tracker.pipelines[pipeline_id]
            all_pending_with_retries = all(
                info['status'] == 'pending' and info['retries'] > 0 
                for info in stages.values()
            )
            
            if all_pending_with_retries:
                logger.info(f"Force updating pipeline {pipeline_id} - stages appear stuck in 'pending' with retries")
                for stage, info in stages.items():
                    if info['status'] == 'pending' and info['retries'] > 0:
                        logger.info(f"Transitioning stage {stage} from pending to in_progress")
                        self.results_tracker.mark_stage_in_progress(pipeline_id, stage)
            
            return self.results_tracker.get_pipeline_status(pipeline_id)
    
    def add_log(self, pipeline_id: str, agent: str, message: str):
        with self.lock:
            if pipeline_id not in self.logs:
                self.logs[pipeline_id] = []
            self.logs[pipeline_id].append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'agent': agent,
                'message': message
            })

    def add_notification(self, pipeline_id: str, type_: str, title: str, message: str):
        with self.lock:
            if pipeline_id not in self.notifications:
                self.notifications[pipeline_id] = []
            self.notifications[pipeline_id].append({
                'type': type_,
                'title': title,
                'message': message,
                'time': datetime.now().strftime('%H:%M')
            })

    def add_demo_logs_and_notifications_to_all(self):
        """
        For all pipelines, if they have no logs/notifications, add demo entries for testing.
        """
        with self.lock:
            for pipeline_id, stages in self.pipelines.items():
                if not self.logs.get(pipeline_id):
                    self.add_log(pipeline_id, 'orchestrator', f'Pipeline {pipeline_id} (retro) - demo log entry.')
                if not self.notifications.get(pipeline_id):
                    self.add_notification(pipeline_id, 'info', 'Demo Notification', f'Pipeline {pipeline_id} (retro) - demo notification.')


class SlackNotifier:
    """
    Sends notifications to Slack about pipeline events.
    """
    def __init__(self, webhook_url: str = None):
        """
        Initialize with optional webhook URL. If not provided, use environment variable.
        
        Args:
            webhook_url (str, optional): Slack webhook URL
        """
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL
        
    def send_notification(self, message: str, blocks: List[Dict[str, Any]] = None) -> bool:
        """
        Send a notification to Slack.
        
        Args:
            message (str): The message text
            blocks (List[Dict], optional): Slack block elements for rich formatting
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured. Skipping notification.")
            return False
            
        payload = {'text': message}
        if blocks:
            payload['blocks'] = blocks
            
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info(f"Slack notification sent successfully: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
    
    def notify_pipeline_status(self, status: Dict[str, Any]) -> bool:
        """
        Send a formatted notification about pipeline status.
        
        Args:
            status (Dict): Pipeline status as returned by ResultsTracker
            
        Returns:
            bool: True if successful, False otherwise
        """
        pipeline_id = status['pipeline_id']
        overall_status = status['status']
        stages = status['stages']
        
        # Create emoji for status
        emoji = "✅" if overall_status == "success" else "❌" if overall_status == "failed" else "🔄"
        
        # Create main message
        message = f"{emoji} Pipeline {pipeline_id} status: {overall_status.upper()}"
        
        # Create rich blocks for Slack
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{emoji} Pipeline Status Update*\n*ID:* {pipeline_id}\n*Status:* {overall_status.upper()}"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add stage details
        stage_details = []
        for stage, info in stages.items():
            stage_emoji = "✅" if info['status'] == "success" else "❌" if info['status'] == "failed" else "🔄"
            retry_info = f" (Retries: {info['retries']})" if info['retries'] > 0 else ""
            stage_details.append(f"{stage_emoji} *{stage}*: {info['status']}{retry_info}")
        
        if stage_details:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(stage_details)
                }
            })
        
        return self.send_notification(message, blocks)


class ResultsHandler:
    """
    Main handler for agent results.
    Listens to Kafka, tracks results, manages retries, and sends notifications.
    """
    def __init__(self):
        self.results_tracker = ResultsTracker()
        self.slack_notifier = SlackNotifier()
        self.consumer = None
        self.running = False
    
    def start(self):
        """Start listening for results."""
        if self.running:
            return
            
        self.running = True
        
        # Start background cleanup thread
        self._start_cleanup_thread()
        
        # Start consuming results
        logger.info("Starting to listen for agent results...")
        try:
            self.consumer = KafkaClient.consume_messages_async(
                topic="agent.results",
                group_id="orchestrator-results-handler-v3",
                message_handler=self._handle_result,
                auto_offset_reset="earliest"  # Read all messages, not just new ones
            )
        except Exception as e:
            logger.error(f"Failed to start results handler: {e}")
            self.running = False
            raise
    
    def stop(self):
        """Stop listening for results."""
        if not self.running:
            return
            
        logger.info("Stopping results handler...")
        self.running = False
        
        if self.consumer:
            self.consumer.stop()
            self.consumer = None
        
        logger.info("Results handler stopped.")
    
    def _handle_result(self, message: Dict[str, Any]):
        """
        Process a result message from an agent.
        
        Args:
            message: The result message from Kafka
        """
        try:
            # Log the full message for debugging
            logger.info(f"🔍 RECEIVED MESSAGE from agent.results: {json.dumps(message, indent=2)}")
            
            # Extract key fields
            pipeline_id = message.get('pipeline_id')
            stage = message.get('stage')
            success = message.get('success', False)
            results = message.get('results', {})
            
            logger.info(f"📋 Extracted fields - pipeline_id: {pipeline_id}, stage: {stage}, success: {success}")
            
            if not pipeline_id or not stage:
                logger.warning(f"❌ Received invalid result message: missing pipeline_id or stage: {message}")
                return
            
            # Check if this is a start message or completion message
            event = message.get('event')
            logger.info(f"📋 Event type: {event}")
            
            # If event is explicitly 'start', mark as in_progress
            if event == 'start':
                logger.info(f"🔄 Marking stage {stage} as in_progress for pipeline {pipeline_id}")
                status = self.results_tracker.mark_stage_in_progress(
                    pipeline_id=pipeline_id,
                    stage=stage
                )
                logger.info(f"✅ Stage {stage} marked as in_progress. New status: {status}")
            # If event is explicitly 'complete' or message has success field (most typical case),
            # treat it as a completion result
            elif event == 'complete' or 'success' in message:
                logger.info(f"✅ Recording completion result for pipeline {pipeline_id}, stage {stage}: {'success' if success else 'failed'}")
                status = self.results_tracker.record_result(
                    pipeline_id=pipeline_id,
                    stage=stage,
                    success=success,
                    results=results
                )
                logger.info(f"✅ Completion recorded. New pipeline status: {json.dumps(status, indent=2)}")
                
                # Check if we need to retry
                if not success and self.results_tracker.should_retry(pipeline_id, stage):
                    retry_count = self.results_tracker.pipelines[pipeline_id][stage]['retries']
                    logger.info(f"🔄 Stage {stage} failed but has retry attempts left ({retry_count}/{MAX_RETRIES})")
                    self._schedule_retry(pipeline_id, stage, message)
                elif not success:
                    logger.warning(f"❌ Stage {stage} failed and has exhausted all retry attempts")
                
                # Send notification about stage completion
                self._send_stage_notification(pipeline_id, stage, success, status)
                
                # If pipeline is complete, send overall notification
                if status['status'] in ['success', 'failed']:
                    self._send_pipeline_notification(status)
            else:
                # Unknown event type, log it but still update status
                logger.warning(f"⚠️ Received message with unknown event type: {event}. Treating as completion.")
                status = self.results_tracker.record_result(
                    pipeline_id=pipeline_id,
                    stage=stage,
                    success=success,
                    results=results
                )
                logger.info(f"✅ Unknown event processed. New status: {json.dumps(status, indent=2)}")
                
                # If success is explicitly provided, handle as completion
                if 'success' in message:
                    logger.info(f"✅ Processing as completion based on success field: {success}")
                    # Check for retries if needed
                    if not success and self.results_tracker.should_retry(pipeline_id, stage):
                        retry_count = self.results_tracker.pipelines[pipeline_id][stage]['retries']
                        logger.info(f"🔄 Stage {stage} failed but has retry attempts left ({retry_count}/{MAX_RETRIES})")
                        self._schedule_retry(pipeline_id, stage, message)
                    elif not success:
                        logger.warning(f"❌ Stage {stage} failed and has exhausted all retry attempts")
                    
                    # Send notification
                    self._send_stage_notification(pipeline_id, stage, success, status)
                    
                    if status['status'] in ['success', 'failed']:
                        self._send_pipeline_notification(status)
                
        except Exception as e:
            logger.error(f"❌ Error processing result message: {e}", exc_info=True)
    
    def _schedule_retry(self, pipeline_id: str, stage: str, original_message: Dict[str, Any]):
        """
        Schedule a retry for a failed stage.
        
        Args:
            pipeline_id (str): The pipeline ID
            stage (str): The stage to retry
            original_message (Dict): The original message to be retried
        """
        # Increment retry count
        retry_count = self.results_tracker.increment_retry_count(pipeline_id, stage)
        logger.info(f"Scheduling retry #{retry_count} for pipeline {pipeline_id}, stage {stage}")
        
        # Reset the stage to pending for the retry
        # This ensures it's not counted as failed until the retry completes
        self.results_tracker.record_result(
            pipeline_id=pipeline_id,
            stage=stage,
            success=False,
            results={},
            status='pending'  # Mark as pending until the retry starts
        )
        
        # Modify message to include retry information
        retry_message = original_message.copy()
        if 'retries' not in retry_message:
            retry_message['retries'] = 0
        retry_message['retries'] = retry_count
        retry_message['retry_timestamp'] = datetime.now().isoformat()
        
        # Ensure we're sending a proper command message, not a results message
        retry_message['event'] = 'start'  # This indicates the agent should start processing
        
        # Schedule the retry
        def retry_task():
            try:
                logger.info(f"Executing retry #{retry_count} for pipeline {pipeline_id}, stage {stage}")
                topic = f"agent.{stage}"

                # Create a clean retry message with just the necessary fields
                clean_retry_message = {
                    'pipeline_id': pipeline_id,
                    'stage': stage,
                    'retries': retry_count,
                    'retry_timestamp': datetime.now().isoformat(),
                    'event': 'start',  # Explicitly mark as a start event
                    'command': original_message.get('command', {}),  # Include original command if present
                    'repository': original_message.get('repository', {}),  # Include repository info if present
                    'is_retry': True  # Flag to indicate this is a retry attempt
                }
                # If this is the security stage, include image from build stage results if available
                if stage == 'security':
                    build_stage = self.results_tracker.pipelines.get(pipeline_id, {}).get('build', {})
                    build_results = build_stage.get('results', {}) if build_stage else {}
                    image = build_results.get('image')
                    if image:
                        clean_retry_message['image'] = image

                KafkaClient.send_message(
                    topic=topic,
                    message=clean_retry_message,
                    key=pipeline_id
                )
                logger.info(f"Retry message sent to {topic}: {json.dumps(clean_retry_message)}")
            except Exception as e:
                logger.error(f"Failed to send retry message: {e}", exc_info=True)
        
        # Execute retry after delay
        threading.Timer(RETRY_DELAY_SECONDS, retry_task).start()
        logger.info(f"Retry scheduled in {RETRY_DELAY_SECONDS} seconds")
    
    def _send_stage_notification(self, pipeline_id: str, stage: str, success: bool, status: Dict[str, Any]):
        """
        Send notification about stage completion.
        
        Args:
            pipeline_id (str): The pipeline ID
            stage (str): The completed stage
            success (bool): Whether the stage was successful
            status (Dict): Current pipeline status
        """
        stage_info = status['stages'].get(stage, {})
        retry_info = f" (Retry {stage_info.get('retries', 0)})" if stage_info.get('retries', 0) > 0 else ""
        
        emoji = "✅" if success else "❌"
        message = f"{emoji} Pipeline {pipeline_id}: {stage} stage {('completed successfully' if success else 'failed')}{retry_info}."
        
        self.slack_notifier.send_notification(message)
    
    def _send_pipeline_notification(self, status: Dict[str, Any]):
        """
        Send notification about overall pipeline status.
        
        Args:
            status (Dict): Current pipeline status
        """
        self.slack_notifier.notify_pipeline_status(status)
    
    def _start_cleanup_thread(self):
        """Start background thread to clean up old pipeline data."""
        def cleanup_task():
            while self.running:
                try:
                    removed = self.results_tracker.cleanup_old_pipelines(max_age_hours=24)
                    if removed > 0:
                        logger.info(f"Cleaned up {removed} old pipelines")
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
                
                # Sleep for 1 hour before next cleanup
                for _ in range(60):  # Check running status every minute
                    if not self.running:
                        break
                    time.sleep(60)
        
        thread = threading.Thread(target=cleanup_task)
        thread.daemon = True
        thread.start()


# Singleton instance
_results_handler = None

def get_results_handler():
    """Get the singleton results handler instance."""
    global _results_handler
    if _results_handler is None:
        _results_handler = ResultsHandler()
    return _results_handler


# Export the results tracker instance for direct use
# Make sure we don't re-initialize if already done (could happen with module reloading)
if '_results_handler' not in globals() or _results_handler is None:
    _results_handler = ResultsHandler()

results_tracker = _results_handler.results_tracker

# Expose the force_update method for the API
def force_update_pipeline_status(pipeline_id: str) -> Dict[str, Any]:
    """
    Force update a pipeline's status if it appears to be stuck.
    This is an API-friendly wrapper around the results handler method.
    """
    handler = get_results_handler()
    return handler.force_update_pipeline_status(pipeline_id)


if __name__ == "__main__":
    # For standalone testing
    handler = get_results_handler()
    handler.start()
    
    try:
        logger.info("Results handler running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down results handler.")
        handler.stop()
