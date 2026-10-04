"""
run.py
───────
Starts both the FastAPI server AND the pipeline in parallel.
Run this single script to launch the full SentryEye system.

Usage:
    python run.py
"""

import asyncio
import logging
import subprocess
import sys
import threading

logger = logging.getLogger("sentryeye.run")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def start_api_server():
    """Launch FastAPI server in a subprocess."""
    logger.info("Starting FastAPI server on http://localhost:8000 ...")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ])


async def start_pipeline():
    """Run the detection pipeline."""
    from pipeline import run_pipeline
    await run_pipeline()


if __name__ == "__main__":
    # Start API server in a background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    # Brief pause to let the server bind
    import time
    time.sleep(2)

    logger.info("Starting detection pipeline ...")
    asyncio.run(start_pipeline())
