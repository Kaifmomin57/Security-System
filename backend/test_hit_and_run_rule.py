import unittest
from dataclasses import dataclass

from rules.hit_and_run_rule import HitAndRunRule


@dataclass
class MockTrack:
    track_id: int
    class_name: str
    trajectory: list


class TestHitAndRunRule(unittest.TestCase):
    def run_trajectory(self, vehicle_path, person_path):
        rule = HitAndRunRule()
        results = []
        for index in range(len(vehicle_path)):
            vehicle = MockTrack(1, "car", vehicle_path[:index + 1])
            person = MockTrack(2, "person", person_path[:index + 1])
            results.extend(rule.evaluate([vehicle, person], {}))
        return results

    def test_vehicle_decelerates_at_contact_then_flees(self):
        vehicle_path = [
            (0.0, 0.0, 300.0),
            (1.0, 40.0, 300.0),
            (2.0, 80.0, 300.0),
            (3.0, 90.0, 300.0),
            (4.0, 130.0, 300.0),
        ]
        person_path = [(float(t), 90.0, 300.0) for t in range(5)]

        results = self.run_trajectory(vehicle_path, person_path)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].rule_type, "possible_hit_and_run")
        self.assertEqual(results[0].metadata["track_id_fleeing"], 1)
        self.assertEqual(results[0].metadata["track_id_stationary"], 2)

    def test_vehicle_passing_pedestrian_does_not_trigger(self):
        vehicle_path = [
            (0.0, 0.0, 300.0),
            (1.0, 40.0, 300.0),
            (2.0, 80.0, 300.0),
            (3.0, 120.0, 300.0),
            (4.0, 160.0, 300.0),
        ]
        person_path = [(float(t), 45.0, 300.0) for t in range(5)]

        self.assertEqual(self.run_trajectory(vehicle_path, person_path), [])

    def test_nearby_vehicle_stopping_and_leaving_without_fast_approach_does_not_trigger(self):
        vehicle_path = [
            (0.0, 0.0, 300.0),
            (1.0, 20.0, 300.0),
            (2.0, 30.0, 300.0),
            (3.0, 30.0, 300.0),
            (4.0, 70.0, 300.0),
        ]
        person_path = [(float(t), 35.0, 300.0) for t in range(5)]

        self.assertEqual(self.run_trajectory(vehicle_path, person_path), [])


if __name__ == "__main__":
    unittest.main()
