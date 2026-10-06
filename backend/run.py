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
    import os

    VIDEO_MAP = {
        "1": "./media/video1_loitering.mp4",
        "2": "./media/video2_traffic.mp4",
        "3": "./media/video3_alley.mp4",
        "0": "0",
        "cam": "0",
        "webcam": "0",
    }

    selected_source = None

    # Check CLI arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower()
        if arg in VIDEO_MAP:
            selected_source = VIDEO_MAP[arg]
        else:
            selected_source = sys.argv[1] # custom path
    else:
        # Interactive prompt
        print("\n" + "=" * 55)
        print("    🎥  SENTRYEYE — LIVE DEMONSTRATION SELECTOR")
        print("=" * 55)
        print("  [1] Video 1 : Loitering CCTV Footage")
        print("  [2] Video 2 : Traffic CCTV (Wrong-Side Driving)")
        print("  [3] Video 3 : Alleyway CCTV (Suspicious Activity)")
        print("  [0] Webcam  : Live Laptop Camera")
        print("=" * 55)
        try:
            choice = input("Enter choice (1-3, 0) [Default: 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "1"
        if not choice:
            choice = "1"
        selected_source = VIDEO_MAP.get(choice, VIDEO_MAP["1"])

    os.environ["VIDEO_SOURCE"] = selected_source
    logger.info(f"Selected Video Source: {selected_source}")

    # Start API server in a background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    # Brief pause to let the server bind
    import time
    time.sleep(2)

    logger.info("Starting detection pipeline ...")
    asyncio.run(start_pipeline())
