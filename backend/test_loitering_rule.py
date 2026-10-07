import unittest
from dataclasses import dataclass

from rules.loitering_rule import LoiteringRule


@dataclass
class MockPoint:
    timestamp: float
    x: float
    y: float


@dataclass
class MockTrack:
    track_id: int
    trajectory: list
    class_name: str = "person"

    @property
    def centroid(self):
        point = self.trajectory[-1]
        return point.x, point.y


class TestLoiteringRule(unittest.TestCase):
    def setUp(self):
        self.rule = LoiteringRule()
        self.config = {
            "loitering": {
                "enabled": True,
                "threshold_seconds": 10,
                "stationary_radius_px": 30,
                "zone_name": "Camera-wide test",
            },
            "zones": [{
                "id": "test-zone",
                "name": "Test Zone",
                "polygon": [[0, 0], [500, 0], [500, 500], [0, 500]],
                "rules": [{
                    "type": "loitering",
                    "enabled": True,
                    "threshold_seconds": 10,
                    "stationary_radius_px": 30,
                }],
            }]
        }

    def test_no_incident_before_ten_stationary_seconds(self):
        track = MockTrack(1, [
            MockPoint(0, 100, 100),
            MockPoint(5, 105, 101),
            MockPoint(9.9, 103, 102),
        ])

        self.assertEqual(self.rule.evaluate([track], self.config), [])

    def test_incident_after_ten_stationary_seconds(self):
        track = MockTrack(1, [
            MockPoint(0, 100, 100),
            MockPoint(5, 105, 101),
            MockPoint(10, 103, 102),
        ])

        results = self.rule.evaluate([track], self.config)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rule_type, "loitering")
        self.assertEqual(results[0].metadata["dwell_time"], 10)
        self.assertEqual(results[0].metadata["threshold_seconds"], 10)
        self.assertEqual(results[0].metadata["zone_name"], "Camera-wide test")

    def test_movement_resets_stationary_duration(self):
        track = MockTrack(1, [
            MockPoint(0, 100, 100),
            MockPoint(5, 200, 100),
            MockPoint(10, 300, 100),
            MockPoint(15, 300, 100),
            MockPoint(19.9, 300, 100),
        ])

        self.assertEqual(self.rule.evaluate([track], self.config), [])

        track.trajectory.append(MockPoint(20, 300, 100))
        results = self.rule.evaluate([track], self.config)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].metadata["dwell_time"], 10)


if __name__ == "__main__":
    unittest.main()
