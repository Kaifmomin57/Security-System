"""
audio/distress_detector.py
──────────────────────────
Feature B (PRD): Sound-Based Distress Detection (Multi-Modal Audio AI).

Runs an audio analysis worker in a separate daemon thread to detect distress sounds
(Screaming, Shout, Glass Breaking, Gunshot, Call for Help) without slowing down
the video pipeline.
"""

import asyncio
import logging
import math
import os
import queue
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except Exception:
    HAS_SOUNDDEVICE = False

from storage.db import get_session, AudioEvent, Event
from api.websocket_manager import ws_manager

logger = logging.getLogger("sentryeye.audio")


class AudioDistressDetector:
    """
    Real-time audio distress classifier running independently on a background thread.
    
    Supported Distress Categories:
        - "Screaming"
        - "Shout"
        - "Glass Breaking"
        - "Gunshot"
        - "Distress Call"
    """

    def __init__(
        self,
        camera_id: str = "cam_01",
        sample_rate: int = 16000,
        window_duration: float = 1.0,     # 1-second analysis window
        confidence_threshold: float = 0.55,
        on_distress_callback: Optional[Callable[[dict], None]] = None,
    ):
        self.camera_id = camera_id
        self.sample_rate = sample_rate
        self.window_duration = window_duration
        self.chunk_size = int(sample_rate * window_duration)
        self.confidence_threshold = confidence_threshold
        self.on_distress_callback = on_distress_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue(maxsize=50)
        self._recent_detections: deque = deque(maxlen=5) # for temporal smoothing
        self._last_alert_time = 0.0
        self._alert_cooldown = 15.0 # seconds

        # Memory for recent distress audio events to correlate with video fusion
        self.recent_audio_alerts: deque = deque(maxlen=10)

    # ─── Public API ───────────────────────────────────────────────────────────

    def start(self):
        """Start the audio ingestion and analysis loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name=f"AudioWorker-{self.camera_id}")
        self._thread.start()
        logger.info(f"[{self.camera_id}] AudioDistressDetector started on background worker thread.")

    def stop(self):
        """Stop the background audio worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info(f"[{self.camera_id}] AudioDistressDetector stopped.")

    def trigger_simulated_event(self, sound_class: str = "Screaming", confidence: float = 0.88) -> dict:
        """
        Manually inject a simulated audio distress event (ideal for demos / test cases).
        """
        event_data = self._process_distress_event(sound_class, confidence, simulated=True)
        return event_data

    def get_recent_audio_distress(self, window_seconds: float = 6.0) -> Optional[dict]:
        """
        Returns the most recent audio distress event if it occurred within window_seconds.
        Used by the FusionEngine to correlate visual alerts with audio alerts.
        """
        now = time.time()
        for item in reversed(self.recent_audio_alerts):
            if now - item["timestamp_epoch"] <= window_seconds:
                return item
        return None

    # ─── Internal Worker Loop ─────────────────────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.debug(f"Audio stream status: {status}")
        if self._running:
            try:
                # indata shape is (frames, channels), take mono channel
                mono = indata[:, 0].copy()
                self._audio_queue.put_nowait(mono)
            except queue.Full:
                pass

    def _run_loop(self):
        """Main listening & classification loop."""
        stream = None
        if HAS_SOUNDDEVICE:
            try:
                stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    blocksize=self.chunk_size,
                    callback=self._audio_callback,
                )
                stream.start()
                logger.info(f"[{self.camera_id}] Microphone input stream active ({self.sample_rate}Hz).")
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Could not open hardware microphone: {e}. (Simulation/API mode active).")
                stream = None

        buffer = np.zeros(0, dtype=np.float32)

        while self._running:
            try:
                # Wait for next audio chunk from mic queue
                try:
                    chunk = self._audio_queue.get(timeout=0.5)
                    buffer = np.concatenate([buffer, chunk])
                except queue.Empty:
                    chunk = None

                if len(buffer) >= self.chunk_size:
                    window = buffer[:self.chunk_size]
                    buffer = buffer[self.chunk_size // 2:] # 50% overlap

                    # Classify acoustic signature
                    sound_class, conf = self._classify_audio_window(window)
                    if sound_class and conf >= self.confidence_threshold:
                        self._recent_detections.append((sound_class, conf, time.time()))
                        # Check temporal smoothing: 2 out of last 3 windows agree
                        if self._check_temporal_smoothing(sound_class):
                            self._process_distress_event(sound_class, conf, simulated=False)

            except Exception as e:
                logger.error(f"Error in audio analysis loop: {e}", exc_info=False)
                time.sleep(0.2)

        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def _classify_audio_window(self, audio: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Computes acoustic energy, spectral centroid, zero-crossing rate,
        and high-frequency distribution to detect distress sounds.
        """
        if len(audio) == 0:
            return None, 0.0

        # 1. Root Mean Square (RMS) Amplitude
        rms = np.sqrt(np.mean(audio ** 2) + 1e-12)
        if rms < 0.04:  # silence / background ambient noise
            return None, 0.0

        # 2. Fast Fourier Transform & Spectral Centroid
        fft = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), d=1.0 / self.sample_rate)
        
        sum_fft = np.sum(fft) + 1e-12
        spectral_centroid = np.sum(freqs * fft) / sum_fft
        
        # 3. Frequency Band Ratios
        low_band = np.sum(fft[(freqs >= 100) & (freqs < 800)]) / sum_fft
        mid_high_band = np.sum(fft[(freqs >= 1200) & (freqs < 3800)]) / sum_fft
        ultra_high_band = np.sum(fft[freqs >= 4000]) / sum_fft

        # 4. Zero-crossing rate (ZCR)
        zcr = np.mean(np.abs(np.diff(np.sign(audio)))) / 2.0

        # ── Screaming Profile: Loud + High Centroid (1.4kHz - 3.8kHz) + High Vocal Formant
        if rms > 0.12 and spectral_centroid > 1400 and mid_high_band > 0.35:
            conf = min(0.95, 0.55 + (rms * 1.5) + (mid_high_band * 0.4))
            return "Screaming", conf

        # ── Glass Breaking Profile: High Sharp Frequency (> 4kHz) + Fast Transients
        if ultra_high_band > 0.40 and zcr > 0.25 and rms > 0.08:
            conf = min(0.92, 0.60 + (ultra_high_band * 0.5))
            return "Glass Breaking", conf

        # ── Gunshot / Bang Profile: High Transient Peak-to-Average Ratio
        peak = np.max(np.abs(audio))
        crest_factor = peak / (rms + 1e-6)
        if crest_factor > 8.0 and rms > 0.18:
            conf = min(0.96, 0.65 + (crest_factor / 20.0))
            return "Gunshot", conf

        # ── Shout / Distress Call
        if rms > 0.15 and 800 < spectral_centroid < 2000:
            conf = min(0.85, 0.50 + rms * 1.2)
            return "Shout", conf

        return None, 0.0

    def _check_temporal_smoothing(self, target_class: str) -> bool:
        """Requires 2 out of the last 3 detections to match the target sound class."""
        recent = list(self._recent_detections)[-3:]
        match_count = sum(1 for (cls, _, _) in recent if cls == target_class)
        return match_count >= 2

    def _process_distress_event(self, sound_class: str, confidence: float, simulated: bool = False) -> dict:
        """
        Handles raising the audio distress alert, persisting to DB,
        broadcasting via WebSocket, and calling handlers.
        """
        now = time.time()
        if now - self._last_alert_time < self._alert_cooldown and not simulated:
            return {}

        self._last_alert_time = now
        event_id = f"aev_{uuid.uuid4().hex[:8]}"
        now_dt = datetime.utcnow()

        event_data = {
            "id": event_id,
            "camera_id": self.camera_id,
            "sound_class": sound_class,
            "confidence": round(confidence, 2),
            "timestamp": now_dt.isoformat(),
            "timestamp_epoch": now,
            "status": "unconfirmed_visually",
            "simulated": simulated,
            "explanation": f"Audio sensor detected {sound_class} with {int(confidence*100)}% confidence.",
        }

        # Store in memory for video fusion
        self.recent_audio_alerts.append(event_data)

        # Save to database
        db = get_session()
        try:
            db_record = AudioEvent(
                id=event_id,
                camera_id=self.camera_id,
                sound_class=sound_class,
                confidence=confidence,
                timestamp=now_dt,
                status="unconfirmed_visually",
            )
            db.add(db_record)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not persist AudioEvent: {e}")
            db.rollback()
        finally:
            db.close()

        # Broadcast over WebSocket to Web Dashboard
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(ws_manager.broadcast({
                    "type": "audio_distress_alert",
                    "data": event_data,
                }))
        except Exception:
            pass

        logger.warning(
            f"🚨 AUDIO DISTRESS ALERT [{self.camera_id}] {sound_class} "
            f"(Conf: {confidence:.2f}) — Status: Unconfirmed Visually"
        )

        if self.on_distress_callback:
            self.on_distress_callback(event_data)

        return event_data
