#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Create and check Kafka topics for the test agent.
"""

import os
import sys
import logging

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
from common.kafka_client import KafkaClient

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("check_test_topics")

def check_topics():
    """Check if the topics for the test agent exist, and create them if they don't."""
    topics = ['agent.test']
    
    logger.info(f"Checking topics: {topics}")
    
    # Check if topics exist, create them if not
    for topic in topics:
        try:
            if not KafkaClient.topic_exists(topic):
                logger.info(f"Topic '{topic}' does not exist. Creating...")
                KafkaClient.create_topic(topic)
                logger.info(f"Topic '{topic}' created successfully.")
            else:
                logger.info(f"Topic '{topic}' already exists.")
        except Exception as e:
            logger.error(f"Error checking/creating topic '{topic}': {e}")
            
    logger.info("Topic check/creation completed.")

if __name__ == "__main__":
    check_topics()
