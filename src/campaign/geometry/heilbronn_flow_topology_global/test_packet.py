#!/usr/bin/env python3
"""Small deterministic self-check for the publishable Heilbronn packet."""

from __future__ import annotations

import itertools
import json

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

from global_search import (
    COUNT,
    EXPECTED_VERIFIER_SHA256,
    EDGE_TO_SLACK,
    SNAPSHOT,
    VERIFIER,
    barycentric,
    cartesian,
    d3_rms_distance,
    domain_slacks,
    enumerate_templates,
    infer_public_template,
    load_evaluate,
    points_to_raw,
    random_raw,
    raw_to_points,
    sha256_path,
    verifier_score,
)


def main() -> int:
    assert sha256_path(VERIFIER) == EXPECTED_VERIFIER_SHA256
    templates = enumerate_templates()
    assert len(templates) == 23
    assert len({(template.vertex_bits, template.edge_counts) for template in templates}) == 23
    assert all(len(template.modes) == COUNT for template in templates)
    rng = np.random.default_rng(12345)
    for template in templates:
        raw = torch.as_tensor(random_raw(3, rng), dtype=torch.float64)
        points = raw_to_points(raw, torch.as_tensor(template.modes)).numpy()
        assert np.min([np.min(domain_slacks(candidate)) for candidate in points]) >= -1e-14
        for candidate in points:
            slacks = np.abs(domain_slacks(candidate))
            for point, mode in enumerate(template.modes):
                if 1 <= mode <= 3:
                    assert slacks[point, EDGE_TO_SLACK[mode - 1]] <= 1e-14
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    leader = np.asarray(snapshot["solutions"][0]["data"]["points"], dtype=np.float64)
    leader_template = infer_public_template(leader, int(snapshot["solutions"][0]["id"]))
    assert leader_template.vertex_bits == (0, 0, 0)
    assert leader_template.edge_counts == (2, 2, 2)
    leader_raw = points_to_raw(leader, leader_template.modes)
    reconstructed = raw_to_points(
        torch.as_tensor(leader_raw[None, :, :], dtype=torch.float64),
        torch.as_tensor(leader_template.modes),
    )[0].numpy()
    assert np.max(np.abs(reconstructed - leader)) <= 1e-12
    assert verifier_score(load_evaluate(), leader) == float(snapshot["solutions"][0]["score"])

    # A deterministic pair where sum-distance and true RMS assignments differ.
    metric_rng = np.random.default_rng(0)
    first = cartesian(metric_rng.dirichlet(np.ones(3), COUNT))
    second = cartesian(metric_rng.dirichlet(np.ones(3), COUNT))
    squared_cost_rms = np.inf
    unsquared_cost_rms = np.inf
    for permutation in itertools.permutations(range(3)):
        transformed = cartesian(barycentric(first)[:, permutation])
        distances = np.linalg.norm(transformed[:, None, :] - second[None, :, :], axis=2)
        rows, columns = linear_sum_assignment(distances * distances)
        squared_cost_rms = min(squared_cost_rms, float(np.sqrt(np.mean(distances[rows, columns] ** 2))))
        rows, columns = linear_sum_assignment(distances)
        unsquared_cost_rms = min(unsquared_cost_rms, float(np.sqrt(np.mean(distances[rows, columns] ** 2))))
    assert squared_cost_rms < unsquared_cost_rms
    assert d3_rms_distance(first, second) == squared_cost_rms

    public_basins: list[np.ndarray] = []
    for item in snapshot["solutions"]:
        points = np.asarray(item["data"]["points"], dtype=np.float64)
        if any(d3_rms_distance(points, previous) <= 1e-8 for previous in public_basins):
            continue
        public_basins.append(points)
    assert len(public_basins) == 13
    print("heilbronn_flow_topology_global: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
