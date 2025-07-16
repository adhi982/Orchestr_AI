#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import os
import socket
import threading
import time
from typing import Any, Dict, Optional, Callable, List

from dotenv import load_dotenv
from kafka import KafkaProducer, KafkaConsumer, TopicPartition
from kafka.errors import KafkaError, KafkaTimeoutError, NoBrokersAvailable

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Kafka configuration with fallbacks
KAFKA_HOST = os.getenv('KAFKA_HOST', '127.0.0.1')  # Use IPv4 explicitly
KAFKA_PORT = os.getenv('KAFKA_PORT', '9092')
KAFKA_BOOTSTRAP_SERVERS = [f'{KAFKA_HOST}:{KAFKA_PORT}']

# Force IPv4
socket.setdefaulttimeout(30)
socket.AF_INET  # Force IPv4

# Base Kafka configuration shared between producer and consumer
BASE_KAFKA_CONFIG = {
    # Connection settings
    'bootstrap_servers': KAFKA_BOOTSTRAP_SERVERS,
    'security_protocol': 'PLAINTEXT',
    'request_timeout_ms': 30000,
    'connections_max_idle_ms': 540000,  # 9 minutes

    # Retry settings
    'reconnect_backoff_ms': 1000,
    'reconnect_backoff_max_ms': 10000,

    # Socket options for Windows compatibility and IPv4
    'socket_options': [
        (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
    ]
}

# Producer-specific configuration
PRODUCER_CONFIG = {
    **BASE_KAFKA_CONFIG,
    'acks': 'all',
    'retries': 3,
    'retry_backoff_ms': 1000,
    'max_block_ms': 30000,
    'compression_type': 'gzip',
    'batch_size': 16384,
    'linger_ms': 10,
    'max_in_flight_requests_per_connection': 5,
}

# Consumer-specific configuration
CONSUMER_CONFIG = {
    **BASE_KAFKA_CONFIG,
    'enable_auto_commit': True,
    'auto_commit_interval_ms': 5000,
    'auto_offset_reset': 'earliest',
    'session_timeout_ms': 25000,  # Must be less than request_timeout_ms
    'heartbeat_interval_ms': 8000,
    'max_poll_interval_ms': 300000,
    'max_poll_records': 500,
    'api_version_auto_timeout_ms': 5000,  # Reduce version probing timeout
    'group_id': None  # Will be set per consumer instance
}

class KafkaClient:
    """
    A robust Kafka client implementation with built-in retry logic and error handling.
    Provides simplified interfaces for producing and consuming messages with Windows compatibility.
    """

    @classmethod
    def _get_producer_config(cls) -> Dict[str, Any]:
        """Get producer-specific configuration."""
        return {
            **PRODUCER_CONFIG,
            'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
        }

    @classmethod
    def _get_consumer_config(cls, group_id: str) -> Dict[str, Any]:
        """Get consumer-specific configuration."""
        return {
            **CONSUMER_CONFIG,
            'group_id': group_id,
            'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
            'client_id': f'orchestrator-consumer-{group_id}'
        }

    @classmethod
    def get_producer(cls) -> KafkaProducer:
        """Create a Kafka producer with automatic retries and error handling."""
        config = cls._get_producer_config()
        retries = 3
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                producer = KafkaProducer(**config)
                logger.info(f"Created Kafka producer (attempt {attempt}) connected to {KAFKA_BOOTSTRAP_SERVERS}")
                return producer
            except (KafkaError, Exception) as e:
                last_error = e
                if attempt < retries:
                    logger.warning(f"Failed to create producer (attempt {attempt}/{retries}): {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All attempts to create producer failed: {str(e)}")
                    raise

    @classmethod
    def get_consumer(cls, topic: str, group_id: str, auto_offset_reset: str = 'earliest') -> KafkaConsumer:
        """Create a Kafka consumer with automatic retries and error handling."""
        config = cls._get_consumer_config(group_id)
        config['auto_offset_reset'] = auto_offset_reset
        retries = 3
        last_error = None

        for attempt in range(1, retries + 1):
            try:
                consumer = KafkaConsumer(topic, **config)
                # Test the connection by polling once
                consumer.poll(timeout_ms=5000)
                logger.info(f"Created Kafka consumer for topic '{topic}' with group '{group_id}' (offset: {auto_offset_reset})")
                return consumer
            except (KafkaError, Exception) as e:
                last_error = e
                if attempt < retries:
                    logger.warning(f"Failed to create consumer (attempt {attempt}/{retries}): {str(e)}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All attempts to create consumer failed: {str(e)}")
                    raise

    @classmethod
    def send_message(cls, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> None:
        """Send a message to a Kafka topic with retries."""
        producer = None
        try:
            producer = cls.get_producer()
            future = producer.send(topic, value=message, key=key)
            record_metadata = future.get(timeout=10)
            logger.info(f"Message sent to topic={record_metadata.topic}, "
                       f"partition={record_metadata.partition}, offset={record_metadata.offset}")
        except Exception as e:
            logger.error(f"Failed to send message to topic {topic}: {str(e)}")
            raise
        finally:
            if producer:
                try:
                    producer.flush(timeout=5)
                    producer.close(timeout=5)
                except Exception as e:
                    logger.warning(f"Error while closing producer: {str(e)}")

    @classmethod
    def consume_messages(cls, topic: str, group_id: str, 
                        message_handler: Callable[[Dict[str, Any]], None]) -> None:
        """Consume messages from a topic with automatic retries on failure."""
        consumer = None
        try:
            consumer = cls.get_consumer(topic, group_id)
            logger.info(f"Starting to consume messages from topic '{topic}'")
            
            while True:  # Main consumption loop
                try:
                    messages = consumer.poll(timeout_ms=1000)
                    for topic_partition, records in messages.items():
                        for record in records:
                            try:
                                message_handler(record.value)
                            except Exception as e:
                                logger.error(f"Error processing message: {str(e)}")
                                # Continue processing other messages
                except Exception as e:
                    logger.error(f"Error polling messages: {str(e)}")
                    # Brief pause before retry
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Fatal error in message consumption: {str(e)}")
            raise
        finally:
            if consumer:
                try:
                    consumer.close(autocommit=False)
                except Exception as e:
                    logger.warning(f"Error while closing consumer: {str(e)}")

    @classmethod
    def consume_messages_async(cls, topic: str, group_id: str,
                             message_handler: Callable[[Dict[str, Any]], None],
                             auto_offset_reset: str = 'earliest') -> 'AsyncConsumer':
        """Start asynchronous message consumption.
        
        Args:
            topic: The Kafka topic to consume from
            group_id: Consumer group ID
            message_handler: Function to handle received messages
            auto_offset_reset: Where to start consuming from ('earliest' or 'latest')
        """
        return AsyncConsumer(topic, group_id, message_handler, auto_offset_reset)
    



class AsyncConsumer:
    """
    Helper class for asynchronous Kafka message consumption with improved error handling
    and reconnection logic.
    """
    
    def __init__(self, topic: str, group_id: str, message_handler: Callable[[Dict[str, Any]], None], auto_offset_reset: str = 'earliest'):
        """Initialize the async consumer."""
        self.topic = topic
        self.group_id = group_id
        self.message_handler = message_handler
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.running = False
        self.thread = None
        self.start()

    def start(self):
        """Start the consumer in a separate thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._consume_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started async consumer for topic {self.topic} with group {self.group_id}")

    def _consume_loop(self):
        """Background thread for message consumption with automatic reconnection."""
        while self.running:
            try:
                if not self.consumer:
                    self.consumer = KafkaClient.get_consumer(self.topic, self.group_id, self.auto_offset_reset)

                messages = self.consumer.poll(timeout_ms=1000)
                for topic_partition, records in messages.items():
                    for record in records:
                        if not self.running:
                            break
                        try:
                            self.message_handler(record.value)
                        except Exception as e:
                            logger.error(f"Error processing message: {str(e)}")

            except (KafkaError, Exception) as e:
                if self.running:
                    logger.error(f"Error in async consumer: {str(e)}")
                    if self.consumer:
                        try:
                            self.consumer.close(autocommit=False)
                        except Exception:
                            pass
                        self.consumer = None
                    time.sleep(5)  # Wait before reconnecting

    def stop(self):
        """Stop the consumer and clean up resources."""
        if not self.running:
            return

        logger.info(f"Stopping async consumer for topic {self.topic}")
        self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)

        if self.consumer:
            try:
                self.consumer.close(autocommit=False)
            except Exception as e:
                logger.warning(f"Error closing consumer: {str(e)}")

        logger.info(f"Async consumer for topic {self.topic} stopped")


