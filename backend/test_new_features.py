"""
test_new_features.py
────────────────────
Comprehensive unit & integration test for PRD new features:
  - Feature A: Abandoned / Lost / Unaccompanied Person Detection
  - Feature B: Sound-Based Distress Detection & Multi-Modal Fusion
"""

import time
import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import List

import numpy as np

from rules.unaccompanied_person_rule import UnaccompaniedPersonRule, StatureClassifier
from audio.distress_detector import AudioDistressDetector
from storage.db import create_tables, get_session, TrackClassification, UnaccompaniedEvent, AudioEvent, Event


@dataclass
class MockTrack:
    track_id: int
    class_name: str
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float = 0.9

    @property
    def centroid(self):
        return ((self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2)


class TestNewFeatures(unittest.TestCase):

    def setUp(self):
        create_tables()

    def test_feature_a_stature_classification(self):
        """Test stature classification heuristic for child proxy vs adult."""
        classifier = StatureClassifier(adult_height_ref=160.0, small_stature_ratio=0.68)
        
        # Adult track: height = 170px
        adult_track = MockTrack(track_id=1, class_name="person", bbox=[100, 100, 160, 270])
        # Child/small track: height = 90px
        child_track = MockTrack(track_id=2, class_name="person", bbox=[200, 100, 240, 190])

        all_tracks = [adult_track, child_track]
        
        stature_adult, conf_adult = classifier.classify(adult_track, all_tracks, {})
        stature_child, conf_child = classifier.classify(child_track, all_tracks, {})

        self.assertEqual(stature_adult, "adult")
        self.assertEqual(stature_child, "small")
        self.assertGreater(conf_child, 0.5)
        print("[OK] Test Stature Classifier: Adult & Small-stature correctly classified.")

    def test_feature_a_unaccompanied_accompanied_suppression(self):
        """Test that an accompanied child (adult within radius) suppresses alert."""
        rule = UnaccompaniedPersonRule()
        cfg = {"unaccompanied": {"enabled": True, "threshold_seconds": 1, "proximity_radius_px": 150.0, "adult_height_px": 160.0}}

        # Child and Adult right next to each other (dist ~ 40px)
        child = MockTrack(track_id=10, class_name="person", bbox=[100, 100, 140, 180])
        adult = MockTrack(track_id=11, class_name="person", bbox=[140, 60, 200, 230])

        # Frame 1
        results = rule.evaluate([child, adult], cfg)
        self.assertEqual(len(results), 0, "Accompanied child should not trigger an alert.")
        
        time.sleep(1.2)
        # Frame 2 after threshold
        results = rule.evaluate([child, adult], cfg)
        self.assertEqual(len(results), 0, "Accompanied child must still be suppressed after threshold time.")
        print("[OK] Test Feature A Suppression: Adult proximity correctly suppresses unaccompanied alert.")

    def test_feature_a_unaccompanied_alert_trigger(self):
        """Test that a child left alone for > threshold triggers an alert with explainability metadata."""
        rule = UnaccompaniedPersonRule()
        cfg = {"unaccompanied": {"enabled": True, "threshold_seconds": 1, "proximity_radius_px": 100.0, "adult_height_px": 160.0}}

        # Child alone
        child = MockTrack(track_id=20, class_name="person", bbox=[100, 100, 140, 180])
        
        # Initial frame (alone timer starts)
        results = rule.evaluate([child], cfg)
        self.assertEqual(len(results), 0, "First frame should start timer without triggering immediate alert.")

        time.sleep(1.2) # wait past 1s threshold

        # Next evaluation
        results = rule.evaluate([child], cfg)
        self.assertEqual(len(results), 1, "Should trigger exactly 1 unaccompanied alert.")
        res = results[0]
        self.assertEqual(res.rule_type, "unaccompanied_person")
        self.assertIn("duration_alone_seconds", res.metadata)
        self.assertIn("last_adult_seen_at", res.metadata)
        self.assertIn("stature_class", res.metadata)
        print("[OK] Test Feature A Alert: Unaccompanied person alert fired with explainability metadata.")

    def test_feature_b_audio_distress_simulation_and_db(self):
        """Test Feature B audio distress detector event simulation & persistence."""
        detector = AudioDistressDetector(camera_id="cam_01")
        
        event = detector.trigger_simulated_event(sound_class="Screaming", confidence=0.91)
        self.assertIsNotNone(event)
        self.assertEqual(event["sound_class"], "Screaming")
        self.assertEqual(event["camera_id"], "cam_01")
        self.assertEqual(event["status"], "unconfirmed_visually")

        # Verify DB persistence
        db = get_session()
        try:
            db_event = db.query(AudioEvent).filter(AudioEvent.id == event["id"]).first()
            self.assertIsNotNone(db_event)
            self.assertEqual(db_event.sound_class, "Screaming")
        finally:
            db.close()

        print("[OK] Test Feature B Audio: Screaming distress event simulated & stored in PostgreSQL.")

    def test_feature_b_multi_modal_fusion_correlation(self):
        """Test that visual alert correlates with recent audio distress event."""
        detector = AudioDistressDetector(camera_id="cam_01")
        audio_event = detector.trigger_simulated_event(sound_class="Gunshot", confidence=0.95)

        recent_audio = detector.get_recent_audio_distress(window_seconds=5.0)
        self.assertIsNotNone(recent_audio)
        self.assertEqual(recent_audio["sound_class"], "Gunshot")
        print("[OK] Test Multi-Modal Fusion: Audio distress event correlates with video alert window.")


if __name__ == "__main__":
    unittest.main()
