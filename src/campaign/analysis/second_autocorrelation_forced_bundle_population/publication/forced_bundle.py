#!/usr/bin/env python3
"""Clean-room reference machinery for a forced multi-lag C2 bundle.

This is a CPU reference and bounded-pilot implementation, not the production
H100 loop.  It never loads a candidate array.  The production plan uses the
same branch formula, ridge-balancing step, and simplex dual bundle model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import oaconvolve


LANE = Path(__file__).resolve().parent
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
PUBLIC_LEADER = 0.963588110582029
STRICT_GATE = 0.9635981105820289


@dataclass(frozen=True)
class MotifSpec:
    seed: int
    n: int
    orientation: int
    relative_period: float
    jitter_fraction: float
    chirp: float
    terminal_mass: float
    gap_start: float
    gap_end: float
    secondary_fraction: float
    subteeth: int
    background_fraction: float


def convolve(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if max(a.size, b.size) <= 1024:
        return np.convolve(a, b)
    return oaconvolve(a, b, mode="full")


def normalize(f: np.ndarray) -> np.ndarray:
    f = np.maximum(np.asarray(f, dtype=np.float64), 0.0)
    total = float(np.sum(f))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("positive finite mass required")
    return f / total


def score_parts(f: np.ndarray) -> dict[str, Any]:
    f = normalize(f)
    g = convolve(f, f)
    h = float(2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:]))
    mass = float(np.sum(g))
    peak_index = int(np.argmax(g))
    peak = float(g[peak_index])
    score = h / (3.0 * mass * peak)
    return {
        "f": f,
        "g": g,
        "h": h,
        "mass": mass,
        "peak_index": peak_index,
        "peak": peak,
        "score": score,
    }


def branch_value(parts: dict[str, Any], lag: int) -> float:
    g = parts["g"]
    if not 0 <= lag < g.size or g[lag] <= 0.0:
        raise ValueError("branch lag must have positive convolution value")
    return float(parts["h"] / (3.0 * parts["mass"] * g[lag]))


def lag_gradient(f: np.ndarray, lag: int) -> np.ndarray:
    n = f.size
    indices = lag - np.arange(n)
    valid = (indices >= 0) & (indices < n)
    result = np.zeros(n, dtype=np.float64)
    result[valid] = 2.0 * f[indices[valid]]
    return result


def branch_gradients(parts: dict[str, Any], lags: list[int]) -> np.ndarray:
    """Gradients of log(H/(3 sum(f)^2 g[lag])) in log-height coordinates."""

    f = parts["f"]
    g = parts["g"]
    h = float(parts["h"])
    q = 4.0 * g
    q[:-1] += g[1:]
    q[1:] += g[:-1]
    q_cross = convolve(q, f[::-1])
    grad_h = 2.0 * q_cross[f.size - 1 : 2 * f.size - 1]
    grad_log_h = grad_h / h
    # sum(f)=1 after normalization. The scale terms cancel exactly after the
    # log-height chain rule, but retaining them makes the formula auditable.
    grad_log_mass = 2.0 * np.ones_like(f)
    output = []
    for lag in lags:
        grad_f = grad_log_h - grad_log_mass - lag_gradient(f, lag) / g[lag]
        mean = float(np.dot(f, grad_f))
        output.append(f * (grad_f - mean))
    return np.stack(output)


def select_separated_lags(
    g: np.ndarray,
    count: int,
    separation: int,
    oversample: int = 64,
) -> list[int]:
    candidate_count = min(g.size, max(count * oversample, count))
    indices = np.argpartition(g, -candidate_count)[-candidate_count:]
    indices = indices[np.argsort(g[indices])[::-1]]
    selected: list[int] = []
    for index in indices:
        value = int(index)
        if all(abs(value - prior) >= separation for prior in selected):
            selected.append(value)
            if len(selected) == count:
                return selected
    for index in indices:
        value = int(index)
        if value not in selected:
            selected.append(value)
            if len(selected) == count:
                break
    return selected


def project_simplex(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64)
    ordered = np.sort(values)[::-1]
    cumulative = np.cumsum(ordered) - 1.0
    rho_candidates = ordered - cumulative / np.arange(1, values.size + 1) > 0.0
    rho = int(np.nonzero(rho_candidates)[0][-1])
    theta = cumulative[rho] / float(rho + 1)
    return np.maximum(values - theta, 0.0)


def simplex_bundle_weights(
    gradients: np.ndarray,
    slacks: np.ndarray,
    eta: float,
    iterations: int = 400,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve min_a b.a + eta/2 ||sum_i a_i grad_i||^2 on the simplex."""

    gram = gradients @ gradients.T
    eigen_max = float(np.linalg.eigvalsh(gram)[-1])
    step = 1.0 / max(eta * eigen_max, 1e-18)
    alpha = np.zeros(len(slacks), dtype=np.float64)
    alpha[int(np.argmin(slacks))] = 1.0
    for _ in range(iterations):
        gradient = slacks + eta * (gram @ alpha)
        updated = project_simplex(alpha - step * gradient)
        if np.linalg.norm(updated - alpha) <= 1e-13:
            alpha = updated
            break
        alpha = updated
    direction = eta * (alpha @ gradients)
    return alpha, direction


def apply_log_step(f: np.ndarray, direction: np.ndarray, scale: float) -> np.ndarray:
    update = np.clip(scale * direction, -0.35, 0.35)
    proposal = f * np.exp(update)
    return normalize(proposal)


def ridge_balance(
    f: np.ndarray,
    separation: int,
    max_score_loss: float = 5e-3,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Move toward a switching surface of two separated convolution maxima."""

    initial = score_parts(f)
    lags = select_separated_lags(initial["g"], 2, separation)
    leader, runner = lags
    gap = float(math.log(initial["g"][leader] / initial["g"][runner]))
    grad_difference_f = (
        lag_gradient(initial["f"], runner) / initial["g"][runner]
        - lag_gradient(initial["f"], leader) / initial["g"][leader]
    )
    mean = float(np.dot(initial["f"], grad_difference_f))
    grad_difference_z = initial["f"] * (grad_difference_f - mean)
    squared_norm = float(np.dot(grad_difference_z, grad_difference_z))
    if gap <= 1e-15 or squared_norm <= 1e-30:
        return initial["f"], {
            "status": "already_balanced",
            "lags": lags,
            "initial_gap": gap,
            "final_gap": gap,
            "score": initial["score"],
        }
    raw_direction = (gap / squared_norm) * grad_difference_z
    raw_direction /= max(1.0, float(np.max(np.abs(raw_direction))) / 0.35)

    best_f = initial["f"]
    best_parts = initial
    best_gap = gap
    best_scale = 0.0
    for scale in (1.0, 0.75, 0.5, 0.25, 0.125, 0.0625):
        proposal = apply_log_step(initial["f"], raw_direction, scale)
        parts = score_parts(proposal)
        fixed_gap = abs(float(math.log(parts["g"][leader] / parts["g"][runner])))
        if parts["score"] >= initial["score"] * (1.0 - max_score_loss) and fixed_gap < best_gap:
            best_f = proposal
            best_parts = parts
            best_gap = fixed_gap
            best_scale = scale
    return best_f, {
        "status": "balanced" if best_scale else "loss_guard_rejected",
        "lags": lags,
        "initial_gap": gap,
        "final_gap": best_gap,
        "scale": best_scale,
        "initial_score": initial["score"],
        "score": best_parts["score"],
    }


def bundle_step(
    f: np.ndarray,
    branch_count: int,
    separation: int,
    balance_scale: float = 8.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    parts = score_parts(f)
    lags = select_separated_lags(parts["g"], branch_count, separation)
    gradients = branch_gradients(parts, lags)
    slacks = np.log(parts["peak"] / parts["g"][lags])
    gram_diagonal = np.einsum("ij,ij->i", gradients, gradients)
    reference_slack = max(float(np.quantile(slacks, 0.75)), 1e-10)
    reference_norm = max(float(np.median(gram_diagonal)), 1e-18)
    eta = balance_scale * reference_slack / reference_norm
    alpha, direction = simplex_bundle_weights(gradients, slacks, eta)
    direction /= max(1.0, float(np.max(np.abs(direction))) / 0.25)

    accepted_f = parts["f"]
    accepted = parts
    accepted_scale = 0.0
    for scale in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
        proposal = apply_log_step(parts["f"], direction, scale)
        proposal_parts = score_parts(proposal)
        if proposal_parts["score"] > accepted["score"]:
            accepted_f = proposal
            accepted = proposal_parts
            accepted_scale = scale
            break
    return accepted_f, {
        "lags": lags,
        "slacks": slacks.tolist(),
        "alpha": alpha.tolist(),
        "effective_bundle_size": int(np.sum(alpha > 1e-3)),
        "eta": eta,
        "accepted_scale": accepted_scale,
        "score_before": parts["score"],
        "score_after": accepted["score"],
    }


def raised_cosine(width: int) -> np.ndarray:
    width = max(int(width), 1)
    if width == 1:
        return np.ones(1, dtype=np.float64)
    x = np.linspace(-math.pi, math.pi, width)
    return 0.08 + 0.92 * (0.5 + 0.5 * np.cos(x))


def add_tooth(f: np.ndarray, center: int, width: int, amplitude: float) -> None:
    profile = raised_cosine(width) * amplitude
    nominal_start = center - width // 2
    nominal_stop = nominal_start + profile.size
    start = max(0, nominal_start)
    stop = min(f.size, nominal_stop)
    if stop <= start:
        return
    profile_start = start - nominal_start
    f[start:stop] += profile[profile_start : profile_start + stop - start]


def make_spec(n: int, seed: int) -> MotifSpec:
    rng = np.random.default_rng(seed)
    return MotifSpec(
        seed=seed,
        n=n,
        orientation=1 if rng.random() < 0.5 else -1,
        relative_period=float(rng.uniform(0.00235, 0.00325)),
        jitter_fraction=float(rng.uniform(0.04, 0.22)),
        chirp=float(rng.uniform(-0.12, 0.12)),
        terminal_mass=float(rng.uniform(0.25, 0.33)),
        gap_start=float(rng.uniform(0.69, 0.75)),
        gap_end=float(rng.uniform(0.85, 0.91)),
        secondary_fraction=float(rng.uniform(0.02, 0.12)),
        subteeth=int(rng.integers(10, 19)),
        background_fraction=float(rng.uniform(0.50, 0.78)),
    )


def spike_comb(spec: MotifSpec) -> np.ndarray:
    """Generate an array solely from the declared analytic/random motif spec."""

    rng = np.random.default_rng(spec.seed)
    n = spec.n
    # At production resolution this is about 4.7k--6.5k cells.  The floor
    # keeps bounded pilots structurally faithful instead of degenerating to a
    # one-cell period.
    period = max(64, int(round(n * spec.relative_period)))
    f = np.zeros(n, dtype=np.float64)
    gap_start = int(round(spec.gap_start * n))
    gap_end = int(round(spec.gap_end * n))

    # A coherent macro-period contains many fine teeth. Public primary reports
    # identify the macro comb but do not prescribe this randomly generated
    # within-period template.
    offsets = np.sort(rng.uniform(0.03, 0.97, spec.subteeth))
    template_widths = np.clip(
        rng.lognormal(mean=math.log(0.012), sigma=0.72, size=spec.subteeth),
        0.002,
        0.065,
    )
    template_amplitudes = rng.lognormal(mean=0.0, sigma=0.38, size=spec.subteeth)
    base = int(rng.uniform(0.0, 0.25) * period)
    group = 0
    while base < gap_start:
        fraction = base / max(gap_start, 1)
        local_period = period * (1.0 + spec.chirp * (fraction - 0.5))
        envelope = 0.25 + 1.55 * math.sin(0.5 * math.pi * fraction) ** 1.4
        phase_walk = rng.normal(0.0, 0.08 * spec.jitter_fraction * period)
        for offset, width_fraction, tooth_amplitude in zip(
            offsets, template_widths, template_amplitudes, strict=True
        ):
            center = int(round(base + offset * local_period + phase_walk))
            width = max(1, int(round(width_fraction * period)))
            amplitude = envelope * tooth_amplitude * float(rng.lognormal(0.0, 0.09))
            add_tooth(f, center, width, amplitude)
        group += 1
        group_jitter = rng.normal(0.0, spec.jitter_fraction * period)
        base += max(2, int(round(local_period + group_jitter)))

    # A denser terminal comb plus a narrow spike. Its total mass is fixed only
    # after construction, so no third-party coefficient is encoded here.
    terminal = np.zeros(n, dtype=np.float64)
    terminal_period = max(32, int(round(period * rng.uniform(0.44, 0.68))))
    terminal_offsets = np.sort(rng.uniform(0.02, 0.98, spec.subteeth + 3))
    base = gap_end + int(rng.uniform(0, terminal_period))
    while base < n:
        for offset in terminal_offsets:
            center = int(round(base + offset * terminal_period))
            width = max(1, int(round(rng.lognormal(math.log(0.012), 0.7) * period)))
            amplitude = float(rng.lognormal(mean=0.15, sigma=0.38))
            add_tooth(terminal, center, width, amplitude)
        base += max(2, int(round(terminal_period + rng.normal(0, 0.04 * period))))
    spike_center = min(n - 1, gap_end + max(1, int(0.015 * (n - gap_end))))
    add_tooth(terminal, spike_center, max(1, int(round(0.003 * period))), 25.0)

    # A weak incommensurate secondary lattice breaks accidental periodic locks.
    secondary = np.zeros(n, dtype=np.float64)
    secondary_period = max(5, int(round(period * math.sqrt(2.0))))
    for center in range(secondary_period // 3, gap_start, secondary_period):
        width = max(1, int(round(0.012 * period)))
        add_tooth(secondary, center, width, float(rng.uniform(0.3, 1.0)))

    # A weak dense exploration component emulates a fresh nonnegative random
    # height vector while leaving the coherent spike/comb motif dominant.
    background = rng.lognormal(mean=-0.5, sigma=0.45, size=n)
    background[gap_start:gap_end] = 0.0
    background[gap_end:] *= 0.35
    background /= np.sum(background)

    ramp = f + spec.secondary_fraction * secondary
    if np.sum(ramp) <= 0 or np.sum(terminal) <= 0:
        raise RuntimeError("motif construction failed")
    ramp *= (1.0 - spec.terminal_mass) / np.sum(ramp)
    terminal *= spec.terminal_mass / np.sum(terminal)
    structured = ramp + terminal
    result = (1.0 - spec.background_fraction) * structured + spec.background_fraction * background
    result[gap_start:gap_end] = 0.0
    if spec.orientation < 0:
        result = result[::-1].copy()
    return normalize(result)


def finite_difference_gradient_test() -> dict[str, float]:
    rng = np.random.default_rng(9173)
    f = normalize(rng.uniform(0.2, 1.0, 19))
    parts = score_parts(f)
    lag = select_separated_lags(parts["g"], 2, 2)[1]
    analytic = branch_gradients(parts, [lag])[0]
    direction = rng.normal(size=f.size)
    direction -= np.mean(direction)
    direction /= np.linalg.norm(direction)
    epsilon = 2e-6
    plus = normalize(f * np.exp(epsilon * direction))
    minus = normalize(f * np.exp(-epsilon * direction))
    numerical = (
        math.log(branch_value(score_parts(plus), lag))
        - math.log(branch_value(score_parts(minus), lag))
    ) / (2.0 * epsilon)
    predicted = float(np.dot(analytic, direction))
    relative_error = abs(numerical - predicted) / max(1.0, abs(numerical), abs(predicted))
    return {
        "numerical": numerical,
        "predicted": predicted,
        "relative_error": relative_error,
    }


def exact_two_branch_test() -> dict[str, Any]:
    f = np.zeros(31, dtype=np.float64)
    f[3] = 2.0
    f[20] = 1.0
    parts = score_parts(f)
    lags = select_separated_lags(parts["g"], 3, 2)
    gradients = branch_gradients(parts, lags)
    slacks = np.log(parts["peak"] / parts["g"][lags])
    alpha, _ = simplex_bundle_weights(gradients, slacks, eta=10.0)
    return {
        "lags": lags,
        "lag_values": parts["g"][lags].tolist(),
        "slacks": slacks.tolist(),
        "alpha": alpha.tolist(),
        "effective_bundle_size": int(np.sum(alpha > 1e-3)),
    }


def run_self_test() -> None:
    gradient = finite_difference_gradient_test()
    if gradient["relative_error"] > 2e-7:
        raise AssertionError(gradient)
    two_branch = exact_two_branch_test()
    if two_branch["effective_bundle_size"] < 2:
        raise AssertionError(two_branch)
    spec = make_spec(4095, 11)
    motif = spike_comb(spec)
    gap = motif[int(math.ceil(spec.gap_start * motif.size)) : int(spec.gap_end * motif.size)]
    if np.count_nonzero(gap) != 0:
        raise AssertionError("declared empty-band invariant failed")
    print(
        json.dumps(
            {
                "status": "PASS",
                "finite_difference": gradient,
                "two_branch": two_branch,
                "motif_score": score_parts(motif)["score"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def is_within_lane(path: Path) -> bool:
    try:
        path.resolve().relative_to(LANE)
        return True
    except ValueError:
        return False


def checked_output(path: Path) -> Path:
    resolved = path.resolve()
    if not is_within_lane(resolved):
        raise ValueError("pilot output must remain in the isolated lane")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def event_chain(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous = "0" * 64
    output = []
    for sequence, payload in enumerate(events):
        body = {"sequence": sequence, "previous_sha256": previous, **payload}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        event_sha256 = hashlib.sha256(previous.encode("ascii") + encoded).hexdigest()
        row = {**body, "event_sha256": event_sha256}
        output.append(row)
        previous = event_sha256
    return output


def run_pilot(args: argparse.Namespace) -> None:
    records: list[dict[str, Any]] = []
    final_arrays: list[np.ndarray] = []
    for member in range(args.population):
        spec = make_spec(args.n, args.seed + member)
        f = spike_comb(spec)
        initial_score = score_parts(f)["score"]
        history: list[dict[str, Any]] = []
        for step in range(args.steps):
            f, ridge = ridge_balance(f, args.separation, args.ridge_loss)
            f, bundle = bundle_step(f, args.branches, args.separation)
            history.append({"step": step, "ridge": ridge, "bundle": bundle})
        records.append(
            {
                "member": member,
                "spec": asdict(spec),
                "initial_score": initial_score,
                "final_score": score_parts(f)["score"],
                "history": history,
            }
        )
        final_arrays.append(f)
    best_member = int(np.argmax([row["final_score"] for row in records]))
    report = {
        "schema": 1,
        "classification": "bounded_reference_pilot_not_frontier_coverage",
        "n": args.n,
        "population": args.population,
        "steps": args.steps,
        "coefficient_inputs": [],
        "members": records,
        "best_member": best_member,
        "best_score": records[best_member]["final_score"],
        "public_leader": PUBLIC_LEADER,
        "strict_gate": STRICT_GATE,
        "gap_to_gate": STRICT_GATE - records[best_member]["final_score"],
        "gate_cleared": records[best_member]["final_score"] > STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
    }
    if args.run_dir is None:
        output = checked_output(args.output)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "PASS", "output": str(output), "best_score": report["best_score"]}, indent=2))
        return

    run_dir = checked_output(args.run_dir)
    expected_parent = LANE / "runs"
    if run_dir.parent != expected_parent:
        raise ValueError("canonical run directory must be a direct child of runs/")
    if run_dir.exists():
        raise FileExistsError(f"write-once run already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    checkpoint = run_dir / "best.npy"
    np.save(checkpoint, np.ascontiguousarray(final_arrays[best_member], dtype=np.float64))
    report["checkpoint"] = checkpoint.name
    report["checkpoint_sha256"] = sha256_file(checkpoint)
    report["checkpoint_value_float64_le_sha256"] = hashlib.sha256(
        np.ascontiguousarray(final_arrays[best_member], dtype="<f8").tobytes()
    ).hexdigest()
    report["source_sha256"] = sha256_file(Path(__file__).resolve())
    report["reproduction_command"] = (
        "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "
        "campaign/analysis/second_autocorrelation_forced_bundle_population/forced_bundle.py "
        f"pilot --n {args.n} --population {args.population} --steps {args.steps} "
        f"--branches {args.branches} --separation {args.separation} "
        f"--ridge-loss {args.ridge_loss} --seed {args.seed} "
        "--run-dir campaign/analysis/second_autocorrelation_forced_bundle_population/runs/REPLAY"
    )
    config = {
        "n": args.n,
        "population": args.population,
        "steps": args.steps,
        "branches": args.branches,
        "separation": args.separation,
        "ridge_loss": args.ridge_loss,
        "seed": args.seed,
        "verifier_sha256": VERIFIER_SHA256,
        "coefficient_inputs": [],
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    event_payloads = [{"event": "config", **config}]
    event_payloads.extend(
        {
            "event": "member_complete",
            "member": row["member"],
            "initial_score": row["initial_score"],
            "final_score": row["final_score"],
            "spec": row["spec"],
        }
        for row in records
    )
    event_payloads.append(
        {
            "event": "checkpoint",
            "member": best_member,
            "score": report["best_score"],
            "checkpoint_sha256": report["checkpoint_sha256"],
            "gate_cleared": report["gate_cleared"],
        }
    )
    chained = event_chain(event_payloads)
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in chained)
    )
    report["event_count"] = len(chained)
    report["event_chain_head"] = chained[-1]["event_sha256"]
    (run_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (run_dir / "HANDOFF.md").write_text(
        "# Bounded forced-bundle reference pilot\n\n"
        f"- Classification: `{report['classification']}`.\n"
        f"- Best exact reference score: `{report['best_score']}`.\n"
        f"- Strict live gate: `{STRICT_GATE}`; gap `{report['gap_to_gate']}`.\n"
        f"- Multi-lag bundle branches per step: `{args.branches}`.\n"
        f"- Frozen verifier SHA-256: `{VERIFIER_SHA256}`.\n"
        f"- Checkpoint SHA-256: `{report['checkpoint_sha256']}`.\n"
        "- Input candidate arrays: none. Every member is regenerated from its motif seed.\n"
        f"- Reproduction: `{report['reproduction_command']}`.\n"
        "- Decision: tool validation only; do not verify, submit, post, or claim frontier coverage.\n"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "run_dir": str(run_dir),
                "best_score": report["best_score"],
                "gap_to_gate": report["gap_to_gate"],
                "gate_cleared": report["gate_cleared"],
                "checkpoint_sha256": report["checkpoint_sha256"],
                "event_chain_head": report["event_chain_head"],
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--n", type=int, default=4095)
    pilot.add_argument("--population", type=int, default=4)
    pilot.add_argument("--steps", type=int, default=4)
    pilot.add_argument("--branches", type=int, default=8)
    pilot.add_argument("--separation", type=int, default=5)
    pilot.add_argument("--ridge-loss", type=float, default=5e-3)
    pilot.add_argument("--seed", type=int, default=20260815)
    pilot.add_argument("--output", type=Path, default=LANE / "pilot.json")
    pilot.add_argument("--run-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "self-test":
        run_self_test()
    elif args.command == "pilot":
        run_pilot(args)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
