#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Timeout handler implementation for DevOps Pipeline agents.
Provides a common way for agents to handle timeouts gracefully.
"""

import threading
import time
import logging
from typing import Optional, Callable, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("timeout_handler")

class TimeoutHandler:
    """
    Handles timeout logic for agent processing.
    
    This class:
    1. Starts a timer when the agent begins processing
    2. Checks periodically if timeout has been exceeded
    3. Allows callback mechanisms for timeout actions
    4. Tracks the processing state to terminate only when idle/stuck
    """
    
    def __init__(self, timeout_seconds: int, agent_name: str):
        """
        Initialize the timeout handler.
        
        Args:
            timeout_seconds: Number of seconds before timeout
            agent_name: Name of the agent (for logging)
        """
        self.timeout_seconds = timeout_seconds
        self.agent_name = agent_name
        self.timer_thread = None
        self.start_time = None
        self.is_running = False
        self.is_processing = False
        self.on_timeout_callback = None
        self._lock = threading.RLock()
        
    def start(self, on_timeout_callback: Optional[Callable[[], Any]] = None):
        """
        Start the timeout monitor.
        
        Args:
            on_timeout_callback: Function to call when timeout occurs
        """
        with self._lock:
            if self.is_running:
                return
                
            self.on_timeout_callback = on_timeout_callback
            self.is_running = True
            self.start_time = time.time()
            
            # Start monitor thread
            self.timer_thread = threading.Thread(
                target=self._monitor_timeout,
                daemon=True
            )
            self.timer_thread.start()
            
            logger.info(f"{self.agent_name} timeout handler started with {self.timeout_seconds}s timeout")
    
    def stop(self):
        """Stop the timeout monitor."""
        with self._lock:
            if not self.is_running:
                return
                
            self.is_running = False
            # Thread will terminate on next check
            logger.info(f"{self.agent_name} timeout handler stopped")
    
    def reset(self):
        """Reset the timeout counter."""
        with self._lock:
            self.start_time = time.time()
            logger.info(f"{self.agent_name} timeout handler reset")
    
    def set_processing(self, is_processing: bool):
        """
        Set whether the agent is actively processing.
        
        Args:
            is_processing: True if the agent is actively working
        """
        with self._lock:
            self.is_processing = is_processing
    
    def _monitor_timeout(self):
        """Monitor thread checking for timeout conditions."""
        while self.is_running:
            time.sleep(1)  # Check every second
            
            with self._lock:
                if not self.is_running:
                    break
                
                # Calculate elapsed time
                elapsed = time.time() - self.start_time
                
                # Check for timeout condition
                if elapsed > self.timeout_seconds:
                    # Only terminate if not actively processing
                    if not self.is_processing:
                        logger.warning(
                            f"{self.agent_name} timeout ({self.timeout_seconds}s) "
                            f"exceeded while idle. Elapsed: {elapsed:.2f}s"
                        )
                        
                        # Call the timeout callback if provided
                        if self.on_timeout_callback:
                            try:
                                self.on_timeout_callback()
                            except Exception as e:
                                logger.error(f"Error in timeout callback: {e}")
                        
                        # Stop the monitor
                        self.is_running = False
                        break
                    else:
                        # Log that timeout occurred but agent is still working
                        logger.info(
                            f"{self.agent_name} timeout ({self.timeout_seconds}s) "
                            f"exceeded but agent is actively processing. "
                            f"Allowing completion. Elapsed: {elapsed:.2f}s"
                        )
                        # Continue monitoring for stuck state
