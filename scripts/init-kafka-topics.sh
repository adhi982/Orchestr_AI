#!/bin/bash

echo "Waiting for Kafka to be ready..."
sleep 10

echo "Creating Kafka topics..."

# Create topics with proper configurations
kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --topic agent.lint --partitions 3 --replication-factor 1
kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --topic agent.test --partitions 3 --replication-factor 1
kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --topic agent.build --partitions 3 --replication-factor 1
kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --topic agent.security --partitions 3 --replication-factor 1
kafka-topics --create --if-not-exists --bootstrap-server kafka:29092 --topic agent.results --partitions 3 --replication-factor 1

echo "Listing all topics:"
kafka-topics --list --bootstrap-server kafka:29092

echo "Kafka topic initialization complete!"
