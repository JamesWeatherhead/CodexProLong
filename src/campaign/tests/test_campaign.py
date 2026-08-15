import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arena_campaign import (  # noqa: E402
    CampaignError,
    append_event,
    clears_gate,
    load_candidate,
    read_events,
    validate_candidate,
)


class CampaignTests(unittest.TestCase):
    def test_gate_directions_and_zero_gate(self):
        self.assertTrue(clears_gate(10.1, 10.0, "maximize", 0.1))
        self.assertFalse(clears_gate(10.09, 10.0, "maximize", 0.1))
        self.assertTrue(clears_gate(9.9, 10.0, "minimize", 0.1))
        self.assertFalse(clears_gate(9.91, 10.0, "minimize", 0.1))
        self.assertTrue(clears_gate(9.999, 10.0, "minimize", 0))
        self.assertFalse(clears_gate(10.0, 10.0, "minimize", 0))

    def test_candidate_key_and_finite_validation(self):
        validate_candidate({"values": [1.0, -2.0]}, {"values": "array"})
        with self.assertRaises(CampaignError):
            validate_candidate({"wrong": []}, {"values": "array"})
        with self.assertRaises(CampaignError):
            validate_candidate({"values": [float("nan")]}, {"values": "array"})

    def test_submission_envelope_is_normalized(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "candidate.json"
            path.write_text(json.dumps({"problem_id": 9, "solution": {"values": [1, 2]}}))
            candidate, payload, artifact_hash = load_candidate(path)
            self.assertEqual(candidate, {"values": [1, 2]})
            self.assertEqual(json.loads(payload), candidate)
            self.assertEqual(len(artifact_hash), 64)

    def test_journal_records_can_be_reopened(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            first = append_event(state, "submit", {"submission_id": 7})
            second = append_event(state, "submission_check", {"submission_id": 7, "status": "pending"})
            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["previous_hash"], first["hash"])
            self.assertEqual(read_events(state)[-1]["payload"]["status"], "pending")

    def test_journal_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            append_event(state, "one", {"value": 1})
            append_event(state, "two", {"value": 2})
            self.assertEqual(len(read_events(state)), 2)
            path = state / "events.jsonl"
            lines = path.read_text().splitlines()
            event = json.loads(lines[0])
            event["payload"]["value"] = 9
            lines[0] = json.dumps(event, separators=(",", ":"), sort_keys=True)
            path.write_text("\n".join(lines) + "\n")
            with self.assertRaises(CampaignError):
                read_events(state)


if __name__ == "__main__":
    unittest.main()
