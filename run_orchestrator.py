#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to run the DevOps Orchestrator FastAPI server with proper startup events.
"""

import sys
import os
import uvicorn
import threading
import time

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from orchestrator.main import app, get_results_handler

def start_results_handler_thread():
    """Start the results handler in a separate thread."""
    print("Starting results handler in background thread...")
    try:
        results_handler = get_results_handler()
        results_handler.start()
        print("✅ Results handler started successfully in background thread")
        
        # Keep the thread alive
        while True:
            time.sleep(1)
            if not getattr(results_handler, 'running', False):
                print("❌ Results handler stopped unexpectedly")
                break
    except Exception as e:
        print(f"❌ Error in results handler thread: {e}")

if __name__ == "__main__":
    print("Starting DevOps Orchestrator...")
    print("Starting results handler in background thread...")
    print("Access the API at: http://localhost:8000")
    print("Health check: http://localhost:8000/health")
    print("Press Ctrl+C to stop")
    
    # Start the results handler in a background thread
    results_thread = threading.Thread(target=start_results_handler_thread, daemon=True)
    results_thread.start()
    
    # Wait a moment for the results handler to start
    time.sleep(3)
    
    # Run the FastAPI app with uvicorn
    try:
        uvicorn.run(
            "orchestrator.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload to ensure startup events work properly
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
        # Stop the results handler
        try:
            results_handler = get_results_handler()
            if getattr(results_handler, 'running', False):
                results_handler.stop()
                print("✅ Results handler stopped")
        except:
            pass
        print("✅ Shutdown complete") 