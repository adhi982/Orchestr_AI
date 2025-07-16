# Kafka Connectivity Troubleshooting Guide

This document explains common Kafka connectivity issues and their solutions, specifically for the DevOps Orchestrator project.

## Common Issues and Solutions

### 1. Socket Disconnected Errors

**Symptom:**
```
socket disconnected
KafkaConnectionError: socket disconnected
```

**Causes:**
- IPv6/IPv4 connectivity conflicts
- Insufficient timeout settings
- Kafka broker configuration issues

**Solution:**
1. Configure Kafka listeners properly in docker-compose.yaml:
   ```yaml
   KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:29092,PLAINTEXT_HOST://0.0.0.0:9092
   ```

2. Adjust JVM settings for Kafka:
   ```yaml
   KAFKA_HEAP_OPTS: "-Xmx512M -Xms512M"
   KAFKA_JVM_PERFORMANCE_OPTS: "-XX:+UseG1GC -XX:MaxGCPauseMillis=20 -XX:InitiatingHeapOccupancyPercent=35"
   ```

3. Ensure compatible configuration parameters for kafka-python client:
   - Check your kafka-python version for supported parameters
   - Remove unsupported parameters like `socket_timeout_ms` if needed

### 2. Module Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'common'
```

**Solution:**
1. Create proper Python package structure with `__init__.py` files
2. Add project root to Python path:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
   ```

3. Or install package in development mode:
   ```
   pip install -e .
   ```

### 3. Verifying Kafka Setup

To verify that Kafka is working correctly:

1. Check if containers are running:
   ```powershell
   docker ps | Select-String -Pattern "kafka|zookeeper"
   ```

2. Run a test script that produces and consumes messages
   ```powershell
   python scripts\test_kafka.py
   ```

3. Check Kafka logs:
   ```powershell
   docker-compose logs kafka
   ```

4. Use Kafka UI at [http://localhost:8080](http://localhost:8080)

## Kafka Client Best Practices

1. **Robust Error Handling**: 
   - Implement retry logic with backoff
   - Properly close connections to prevent resource leaks

2. **Configuration Management**:
   - Use environment variables for Kafka configuration
   - Ensure parameters are compatible with your kafka-python version

3. **Testing**:
   - Always verify connectivity with a simple producer/consumer test
   - Test with small messages before sending real payload

## Next Steps

With Kafka working properly, you can now proceed to implement:

1. The Central Orchestrator (Phase 3)
2. Agent implementations (Phases 4-7)
3. Results handling and notifications (Phase 8)
