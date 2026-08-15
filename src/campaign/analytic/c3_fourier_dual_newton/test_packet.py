from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "c3_fourier_dual_newton", HERE / "fourier_dual_newton.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PacketTests(unittest.TestCase):
    def test_fft_objective_matches_direct_small_vector(self) -> None:
        values = np.array([0.8, -0.3, 0.1, 0.6, -0.2], dtype=np.float64)
        objective = MODULE.FFTObjective(len(values))
        normalized = values / np.sum(values)
        direct = 2.0 * len(values) * np.max(np.convolve(normalized, normalized))
        self.assertAlmostEqual(objective.score(values), direct, places=13)

    def test_cap_projection_preserves_mass_and_cap(self) -> None:
        convolution = np.array([0.6, -0.2, 0.7, -0.1], dtype=np.float64)
        projected = MODULE.project_cap_with_mass(convolution, 0.4)
        self.assertAlmostEqual(float(np.sum(projected)), 1.0, places=13)
        self.assertLessEqual(float(np.max(projected)), 0.4 + 1e-14)

    def test_frozen_decision_is_not_gate_clearer(self) -> None:
        summary = json.loads(
            (HERE / "runs/20260815T124000Z/summary.json").read_text(encoding="utf-8")
        )
        self.assertFalse(summary["gate_cleared"])
        self.assertGreater(summary["remaining_gate_gap"], 3.5e-6)
        self.assertLess(summary["maximum_newton_fft_gain"], 1e-9)


if __name__ == "__main__":
    unittest.main()
