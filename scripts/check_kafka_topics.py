#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Helper script to check the Kafka topic messages
"""

import os
import sys
import json
import logging
import time
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from common.kafka_client import KafkaClient

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("check_kafka_topics")

def check_topics(topics):
    """Check messages in multiple Kafka topics"""
    for topic in topics:
        logger.info(f"Checking messages in topic: {topic}")
        
        def message_handler(message):
            logger.info(f"Message from topic {topic}:")
            logger.info(json.dumps(message, indent=2))
        
        # Start a consumer for each topic
        consumer_thread = KafkaClient.consume_messages(
            topic=topic, 
            group_id=f"checker-{int(time.time())}", 
            message_handler=message_handler
        )

if __name__ == "__main__":
    topics_to_check = ["agent.lint", "agent.results"]
    
    if len(sys.argv) > 1:
        topics_to_check = sys.argv[1:]
    
    logger.info(f"Checking topics: {topics_to_check}")
    
    try:
        check_topics(topics_to_check)
        
        # Keep script running
        logger.info("Press Ctrl+C to exit...")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Exiting...")
