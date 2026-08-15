#!/usr/bin/env python3
"""Bordered k=25 continuation for ``uncertainty-principle``.

The public k=24 incumbent has a nearly active stationary contact at
49.96662400425927.  Prescribing that contact as the 25th double root opens a
new branch with the same active root.  This solver differentiates the active
root and the dangerous tail contacts, takes a contact-tangent predictor, and
Newton-corrects the tail levels.  Every accepted checkpoint is rescored by the
exact frozen live verifier; this program never posts or submits.

Run with mpmath available, for example:

  uv run --with numpy --with scipy --with mpmath python uncertainty_k25.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mpmath as mp
import numpy as np
from scipy.optimize import brentq, minimize_scalar


ROOT = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = ROOT / "checkpoints" / "latest.json"
INSERTION = 49.96662400425927
INCUMBENT_ID = 2482


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass
class Feature:
    score: float
    metrics: np.ndarray


class FrozenVerifier:
    def __init__(self, record: dict[str, Any]):
        self.problem = record["problem"]
        self.verifier_hash = hashlib.sha256(
            self.problem["verifier"].encode()
        ).hexdigest()
        self.namespace: dict[str, Any] = {}
        exec(self.problem["verifier"], self.namespace)
        mp.mp.dps = 80

    def coefficients(self, roots: np.ndarray):
        values = roots.tolist()
        degrees, alpha, matrix, rhs = self.namespace["build_system_f64"](values)
        coefficients = self.namespace["solve_coeffs_mp"](values, degrees)
        return degrees, alpha, coefficients

    def q_function(self, roots: np.ndarray):
        degrees, alpha, coefficients = self.coefficients(roots)
        values = roots.tolist()

        def q(x: float) -> float:
            return self.namespace["q_val"](
                float(x), coefficients, degrees, alpha, values
            )

        return q

    def contact_positions(self, roots: np.ndarray) -> tuple[float, float]:
        q = self.q_function(roots)
        far = minimize_scalar(
            lambda x: -q(x),
            bounds=(350.0, 390.0),
            method="bounded",
            options={"xatol": 1e-10},
        ).x
        endpoint = float(np.max(roots) * 1.5 + 100.0)
        return float(far), endpoint

    def feature(self, roots: np.ndarray, contacts: tuple[float, ...]) -> Feature:
        q = self.q_function(roots)
        active = brentq(q, 1.5, 2.4, xtol=2e-14, maxiter=100)
        metrics = []
        for contact in contacts:
            # Once the far contact is close to binding, evaluating it at a
            # frozen x misses the O(step) drift of its location and can admit
            # a split pair of roots.  Track the actual local maximum instead.
            if 340.0 < contact < 400.0:
                location = minimize_scalar(
                    lambda x: -q(x),
                    bounds=(350.0, 390.0),
                    method="bounded",
                    options={"xatol": 1e-10},
                ).x
                metrics.append(q(float(location)))
            else:
                metrics.append(q(contact))
        return Feature(
            score=float(active / (2 * math.pi)),
            metrics=np.array(metrics, dtype=float),
        )

    def exact_score(self, roots: np.ndarray) -> float:
        return float(
            self.namespace["evaluate"](
                {"laguerre_double_roots": roots.tolist()}
            )
        )


def derivatives(
    verifier: FrozenVerifier,
    roots: np.ndarray,
    contacts: tuple[float, ...],
    base: Feature,
    step: float,
) -> tuple[np.ndarray, np.ndarray]:
    gradient = np.empty(len(roots))
    jacobian = np.empty((len(contacts), len(roots)))
    scales = np.abs(base.metrics)
    for index in range(len(roots)):
        plus = roots.copy()
        minus = roots.copy()
        plus[index] += step
        minus[index] -= step
        fp = verifier.feature(plus, contacts)
        fm = verifier.feature(minus, contacts)
        gradient[index] = (fp.score - fm.score) / (2 * step)
        jacobian[:, index] = (fp.metrics - fm.metrics) / (2 * step) / scales
    return gradient, jacobian


def tangent(gradient: np.ndarray, jacobian: np.ndarray) -> np.ndarray:
    gram = jacobian @ jacobian.T
    direction = -gradient + jacobian.T @ np.linalg.solve(
        gram, jacobian @ gradient
    )
    direction /= np.max(np.abs(direction))
    return direction


def corrected_trial(
    verifier: FrozenVerifier,
    roots: np.ndarray,
    contacts: tuple[float, ...],
    base: Feature,
    jacobian: np.ndarray,
    direction: np.ndarray,
    distance: float,
    iterations: int = 12,
) -> tuple[np.ndarray, Feature, np.ndarray]:
    predictor = roots + distance * direction
    multiplier = np.zeros(len(contacts))
    gram = jacobian @ jacobian.T
    scales = np.abs(base.metrics)
    feature = verifier.feature(predictor, contacts)
    for _ in range(iterations):
        trial = predictor + jacobian.T @ multiplier
        feature = verifier.feature(trial, contacts)
        error = (feature.metrics - base.metrics) / scales
        if np.max(np.abs(error)) < 1e-7:
            return trial, feature, error
        multiplier -= np.linalg.solve(gram, error)
    trial = predictor + jacobian.T @ multiplier
    feature = verifier.feature(trial, contacts)
    return trial, feature, (feature.metrics - base.metrics) / scales


def save_best(
    verifier: FrozenVerifier,
    incumbent_score: float,
    roots: np.ndarray,
    score: float,
    events: list[dict[str, Any]],
) -> None:
    payload = {"laguerre_double_roots": roots.tolist()}
    atomic_json(ROOT / "payloads" / "uncertainty-k25.json", payload)
    atomic_json(
        ROOT / "checkpoints" / "uncertainty-k25-best.json",
        {
            "slug": "uncertainty-principle",
            "verifier_sha256": verifier.verifier_hash,
            "incumbent_id": INCUMBENT_ID,
            "incumbent_score": incumbent_score,
            "score": score,
            "improvement": incumbent_score - score,
            "gap_to_gate": max(0.0, score - (incumbent_score - 1e-6)),
            "payload": payload,
            "events": events,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--stages", type=int, default=6)
    parser.add_argument("--difference-step", type=float, default=1e-4)
    parser.add_argument("--max-distance", type=float, default=2e-3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--constraint-mode", choices=("both", "far"), default="both"
    )
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text())
    record = snapshot["problems"]["uncertainty-principle"]
    solution = next(item for item in record["solutions"] if item["id"] == INCUMBENT_ID)
    incumbent = np.array(solution["data"]["laguerre_double_roots"], dtype=float)
    incumbent_score = float(solution["score"])
    roots = np.sort(np.append(incumbent, INSERTION))
    verifier = FrozenVerifier(record)
    expected_hash = "8986d94fac865d4aea224c995b408574b9ac0f1c5d0a15dbd810ebc958457289"
    if verifier.verifier_hash != expected_hash:
        raise RuntimeError(f"verifier drift: {verifier.verifier_hash}")

    score = verifier.exact_score(roots)
    best_roots = roots.copy()
    best_score = score
    events: list[dict[str, Any]] = [
        {"event": "contact_birth", "score": score, "insertion": INSERTION}
    ]
    prior_path = ROOT / "checkpoints" / "uncertainty-k25-best.json"
    prior_loaded = False
    if prior_path.exists():
        prior = json.loads(prior_path.read_text())
        if (
            prior.get("verifier_sha256") == verifier.verifier_hash
            and float(prior.get("score", math.inf)) < best_score
        ):
            best_score = float(prior["score"])
            best_roots = np.array(
                prior["payload"]["laguerre_double_roots"], dtype=float
            )
            events.append(
                {"event": "prior_checkpoint", "score": best_score}
            )
            prior_loaded = True
    save_best(verifier, incumbent_score, best_roots, best_score, events)

    if args.resume and prior_loaded:
        roots = best_roots.copy()
    else:
        # Bootstrap: preserve the 369-tail contact while using the available
        # endpoint slack.  The last safe deterministic predictor is 3.6e-4.
        far, _endpoint = verifier.contact_positions(roots)
        contacts = (far,)
        base = verifier.feature(roots, contacts)
        gradient, jacobian = derivatives(
            verifier, roots, contacts, base, args.difference_step
        )
        direction = tangent(gradient, jacobian)
        branch_roots = roots.copy()
        branch_score = score
        for distance in (1e-4, 2e-4, 3e-4, 3.4e-4, 3.6e-4):
            trial = roots + distance * direction
            exact = verifier.exact_score(trial)
            events.append(
                {"event": "bootstrap_trial", "distance": distance, "score": exact}
            )
            if exact < best_score:
                best_roots, best_score = trial, exact
                save_best(verifier, incumbent_score, best_roots, best_score, events)
            if exact < branch_score:
                branch_roots, branch_score = trial, exact
        roots = branch_roots

    distances = tuple(
        value
        for value in (1e-7, 3e-7, 1e-6, 2e-6, 3e-6, 5e-6, 8e-6,
                      1e-5, 2e-5, 3e-5, 5e-5, 1e-4, 2e-4, 3e-4, 4e-4, 5e-4, 6e-4,
                      8e-4, 1e-3, 1.3e-3, 1.6e-3, 2e-3)
        if value <= args.max_distance
    )
    for stage in range(args.stages):
        far, endpoint = verifier.contact_positions(roots)
        contacts = (far, endpoint) if args.constraint_mode == "both" else (far,)
        base = verifier.feature(roots, contacts)
        gradient, jacobian = derivatives(
            verifier, roots, contacts, base, args.difference_step
        )
        direction = tangent(gradient, jacobian)
        current_score = verifier.exact_score(roots)
        stage_best = (current_score, roots.copy())
        for distance in distances:
            try:
                trial, feature, error = corrected_trial(
                    verifier,
                    roots,
                    contacts,
                    base,
                    jacobian,
                    direction,
                    distance,
                )
                exact = verifier.exact_score(trial)
            except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
                continue
            event = {
                "event": "continuation_trial",
                "stage": stage,
                "distance": distance,
                "surrogate_score": feature.score,
                "score": exact,
                "contact_error": error.tolist(),
            }
            events.append(event)
            print(json.dumps(event), flush=True)
            if exact < stage_best[0]:
                stage_best = (exact, trial.copy())
            if exact < best_score:
                best_score, best_roots = exact, trial.copy()
                save_best(verifier, incumbent_score, best_roots, best_score, events)
        if stage_best[0] >= current_score - 1e-13:
            break
        roots = stage_best[1]

    save_best(verifier, incumbent_score, best_roots, best_score, events)
    print(
        json.dumps(
            {
                "score": best_score,
                "improvement": incumbent_score - best_score,
                "gate_cleared": best_score < incumbent_score - 1e-6,
                "verifier_sha256": verifier.verifier_hash,
                "payload": str(ROOT / "payloads" / "uncertainty-k25.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
