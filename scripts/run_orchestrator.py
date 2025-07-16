#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Run script for the orchestrator agent.
"""

import os
import sys
import logging
import asyncio
import signal
import uvicorn
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import after setting path
from orchestrator.pipeline_manager import pipeline_manager

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("orchestrator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("orchestrator")

# Set up signal handling for graceful shutdown
shutdown_event = asyncio.Event()


def handle_signal(sig, frame):
    """Handle termination signals."""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    shutdown_event.set()


async def start_result_consumer():
    """Start the Kafka result consumer."""
    try:
        logger.info("Starting pipeline result consumer...")
        await pipeline_manager.start_result_consumer()
    except Exception as e:
        logger.error(f"Error in result consumer: {e}")


async def run_orchestrator():
    """Run the orchestrator and handle graceful shutdown."""
    # Start Kafka consumer
    consumer_task = asyncio.create_task(start_result_consumer())
    
    # Start web server
    config = uvicorn.Config(
        "orchestrator.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=os.getenv('LOG_LEVEL', 'info').lower()
    )
    server = uvicorn.Server(config)
    
    # Run server in a task
    server_task = asyncio.create_task(server.serve())
    
    # Wait for shutdown signal or server completion
    await shutdown_event.wait()
    
    logger.info("Shutting down orchestrator...")
    
    # Stop server
    if not server_task.done():
        server.should_exit = True
        await server_task
    
    # Cancel consumer task
    if not consumer_task.done():
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Orchestrator shutdown complete")


def main():
    """Main entry point."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info("Starting DevOps Pipeline Orchestrator")
    
    # Run the orchestrator
    try:
        asyncio.run(run_orchestrator())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, exiting...")
    except Exception as e:
        logger.error(f"Error running orchestrator: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
