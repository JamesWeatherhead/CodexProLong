#!/usr/bin/env python3
"""Tests that run unchanged in a copied publication allowlist."""

from __future__ import annotations

import copy
import json
import math
import unittest

import public_verifier_formula as verifier
import replay_public


class PublicReplayTests(unittest.TestCase):
    def test_reference_is_hash_only_and_pinned(self) -> None:
        self.assertEqual(verifier.assert_reference_hash(), verifier.VERIFIER_SHA256)

    def test_compact_artifacts_replay(self) -> None:
        report = replay_public.replay()
        self.assertEqual(report["replayed_artifact_count"], 2)
        self.assertEqual(report["best_changed_score"], 2.629728811166304)
        self.assertFalse(report["gate_clearing"])

    def test_overlap_is_rejected(self) -> None:
        payload_path = replay_public.HERE / "artifacts" / (
            "20260815T074700Z_NEUTRAL_STRAT1000_V2_best_changed.json"
        )
        payload = json.loads(payload_path.read_text())
        invalid = copy.deepcopy(payload)
        invalid["circles"][1] = list(invalid["circles"][0])
        self.assertTrue(math.isinf(verifier.evaluate(invalid)))
        self.assertLess(verifier.evaluate(invalid), 0)


if __name__ == "__main__":
    unittest.main()
