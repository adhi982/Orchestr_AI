#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Create Kafka topics for the security agent.
"""

import os
import sys
import logging
from kafka.admin import KafkaAdminClient, NewTopic

# Fix Python path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv('config/.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("create_security_topics")

def create_topics():
    """Create Kafka topics for the security agent."""
    topics_to_create = ['agent.security']
    
    logger.info(f"Creating topics: {topics_to_create}")
    
    try:
        # Create admin client
        admin_client = KafkaAdminClient(
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
            client_id='topics-creator'
        )
        
        # Get existing topics
        try:
            existing_topics = admin_client.list_topics()
            logger.info(f"Existing topics: {existing_topics}")
        except Exception as e:
            logger.error(f"Error listing topics: {e}")
            existing_topics = []
        
        # Create topics that don't exist
        new_topics = []
        for topic in topics_to_create:
            if topic not in existing_topics:
                new_topics.append(NewTopic(
                    name=topic,
                    num_partitions=3,
                    replication_factor=1
                ))
        
        if new_topics:
            logger.info(f"Creating {len(new_topics)} new topics")
            admin_client.create_topics(new_topics=new_topics)
            logger.info("Topics created successfully")
        else:
            logger.info("All topics already exist")
            
    except Exception as e:
        logger.error(f"Error creating topics: {e}")
    finally:
        try:
            admin_client.close()
        except:
            pass
    
    logger.info("Topic creation process completed")

if __name__ == "__main__":
    create_topics()
