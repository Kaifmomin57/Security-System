"""
run.py
───────
Starts FastAPI + one or more pipeline instances in the SAME process/event loop
so that frame_registry and pipeline_status are shared in memory.

Usage:
    python run.py              # interactive selector (single cam)
    python run.py 3            # cam_01 = video3_alley.mp4
    python run.py 3 0          # cam_01 = video3_alley.mp4  +  cam_02 = webcam
    python run.py 1 3          # cam_01 = video1  +  cam_02 = video3
    python run.py 0            # cam_01 = webcam only
"""

import asyncio
import logging
import os
import sys

import uvicorn

logger = logging.getLogger("sentryeye.run")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

VIDEO_MAP = {
    "1": "./media/video1_loitering.mp4",
    "2": "./media/video2_traffic.mp4",
    "3": "./media/video3_alley.mp4",
    "0": "0",       # Still keep 0 as alias to index 0
    "cam": "0",
    "webcam": "0",
    "c0": "0",      # Laptop webcam usually
    "c1": "1",      # External USB webcam usually
    "c2": "2",
}

CAMERA_NAMES = {
    "cam_01": "Main Entrance",
    "cam_02": "Secondary Camera",
    "cam_03": "Camera 03",
    "cam_04": "Camera 04",
}

def resolve_source(arg: str) -> str:
    """Map a short arg (1/2/3/c0/c1) or a raw path/URL to a video source."""
    return VIDEO_MAP.get(arg.strip().lower(), arg)


async def main(sources: list[str]):
    from pipeline import run_pipeline

    # Set primary VIDEO_SOURCE env for backward compat
    os.environ["VIDEO_SOURCE"] = sources[0]

    # Build in-process uvicorn server (no --reload so frame_registry is shared)
    config = uvicorn.Config(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    logger.info("Starting FastAPI server on http://localhost:8000 ...")

    # Keep pipeline coroutines uncreated until the API has completed startup.
    pipelines = []
    for idx, src in enumerate(sources):
        cam_id   = f"cam_{str(idx + 1).zfill(2)}"
        cam_name = CAMERA_NAMES.get(cam_id, f"Camera {idx + 1:02d}")
        logger.info(f"  [{cam_id}] → {src}")
        pipelines.append((cam_id, src, cam_name))

    # Wait for database/API startup rather than a fixed delay. On startup
    # failure, no unawaited pipeline coroutines are left behind.
    async def delayed_pipelines():
        while not server.started:
            if server.should_exit:
                logger.error("API server stopped before startup; camera pipelines will not start.")
                return
            await asyncio.sleep(0.1)
        await asyncio.gather(*(
            run_pipeline(camera_id=cam_id, video_source=src, camera_name=cam_name)
            for cam_id, src, cam_name in pipelines
        ))

    # Run API server + all pipelines concurrently
    await asyncio.gather(server.serve(), delayed_pipelines())


if __name__ == "__main__":
    sources = []

    if len(sys.argv) > 1:
        # Accept 1 or more source args: python run.py 3 0
        for arg in sys.argv[1:]:
            sources.append(resolve_source(arg))
    else:
        # Interactive selector
        print("\n" + "=" * 55)
        print("    🎥  SENTRYEYE — LIVE DEMONSTRATION SELECTOR")
        print("=" * 55)
        print("  [1] Video 1 : Loitering CCTV Footage")
        print("  [2] Video 2 : Traffic CCTV (Wrong-Side Driving)")
        print("  [3] Video 3 : Alleyway CCTV (Suspicious Activity)")
        print("  [0] Webcam  : Live Laptop Camera")
        print("=" * 55)
        print("  TIP: You can enter multiple sources, e.g.  3 0")
        print("=" * 55)
        try:
            raw = input("Enter choice(s) [Default: 1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            raw = "1"
        if not raw:
            raw = "1"
        for token in raw.split():
            sources.append(resolve_source(token))

    if not sources:
        sources = ["./media/video1_loitering.mp4"]

    print(f"\n▶  Starting {len(sources)} camera(s):")
    for i, s in enumerate(sources):
        print(f"   cam_{i+1:02d} → {s}")
    print()

    asyncio.run(main(sources))
