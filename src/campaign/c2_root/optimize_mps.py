#!/usr/bin/env python3
"""Projected persistent-dual optimization for the two-million-point C2 lane.

Metal float32 is used only to propose directions. Every accepted checkpoint is
rescored with float64 SciPy operations matching the live verifier algebra.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from scipy.signal import oaconvolve


ROOT = Path(__file__).resolve().parent


def exact_score(values: np.ndarray) -> float:
    f = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    convolution = oaconvolve(f, f, mode="full")
    numerator = (
        2.0 * np.dot(convolution, convolution)
        + np.dot(convolution[:-1], convolution[1:])
    ) / 3.0
    return float(numerator / (np.sum(convolution) * np.max(convolution)))


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "leader.npy")
    parser.add_argument("--minutes", type=float, default=20.0)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--check-every", type=int, default=20)
    parser.add_argument("--dual-every", type=int, default=5)
    parser.add_argument("--lr", type=float, default=4e-7)
    parser.add_argument("--beta", type=float, default=2_000.0)
    parser.add_argument("--beta-max", type=float, default=200_000.0)
    parser.add_argument("--dual-rho", type=float, default=0.08)
    parser.add_argument("--noise", type=float, default=2e-8)
    parser.add_argument("--restart-after", type=int, default=4)
    args = parser.parse_args()

    if not torch.backends.mps.is_available():
        raise RuntimeError("Apple Metal is unavailable")
    source = np.maximum(np.load(args.input, allow_pickle=False).astype(np.float64), 0.0)
    source /= np.max(source)
    n = source.size
    length = 2 * n - 1
    nfft = 1 << (length - 1).bit_length()
    device = torch.device("mps")
    generator = np.random.default_rng(args.seed)

    best = source.copy()
    seed_score = exact_score(best)
    best_score = seed_score
    f = torch.tensor(source, dtype=torch.float32, device=device, requires_grad=True)
    optimizer = torch.optim.Adam([f], lr=args.lr)

    def convolution() -> torch.Tensor:
        spectrum = torch.fft.rfft(f, n=nfft)
        return torch.fft.irfft(spectrum * spectrum, n=nfft)[:length]

    with torch.no_grad():
        conv = convolution()
        phi = conv / conv.max()
        dual = torch.softmax(args.beta * phi, dim=0)

    run_dir = ROOT / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_npy(run_dir / "seed.npy", best)
    atomic_npy(run_dir / "best.npy", best)
    events = run_dir / "events.jsonl"
    started = time.monotonic()
    deadline = started + 60.0 * args.minutes
    beta = args.beta
    iteration = 0
    stale_checks = 0
    with events.open("a", encoding="utf-8") as event_handle:
        while time.monotonic() < deadline:
            optimizer.zero_grad(set_to_none=True)
            conv = convolution()
            numerator = (
                2.0 * torch.sum(conv * conv)
                + torch.sum(conv[:-1] * conv[1:])
            ) / 3.0
            mass = torch.sum(f)
            dual_max = torch.sum(dual * conv) / torch.sum(dual)
            objective = torch.log(numerator) - 2.0 * torch.log(mass) - torch.log(dual_max)
            (-objective).backward()
            optimizer.step()

            with torch.no_grad():
                f.clamp_(min=0.0)
                # Scale invariance keeps the dynamic range numerically stable.
                f.div_(f.max())
                if args.noise and iteration and iteration % 100 == 0:
                    noise = generator.uniform(0.0, args.noise, size=n).astype(np.float32)
                    f.add_(torch.from_numpy(noise).to(device))
                    f.div_(f.max())
                if iteration % args.dual_every == 0:
                    conv_now = convolution()
                    phi = conv_now / conv_now.max()
                    fresh = torch.softmax(beta * phi, dim=0)
                    dual.mul_(1.0 - args.dual_rho).add_(fresh, alpha=args.dual_rho)

            if iteration % args.check_every == 0:
                candidate = f.detach().cpu().numpy().astype(np.float64)
                candidate_score = exact_score(candidate)
                gain = candidate_score - best_score
                accepted = gain > 0.0
                if accepted:
                    best = candidate
                    best_score = candidate_score
                    atomic_npy(run_dir / "best.npy", best)
                    stale_checks = 0
                else:
                    stale_checks += 1
                event = {
                    "iteration": iteration,
                    "elapsed_seconds": time.monotonic() - started,
                    "beta": beta,
                    "candidate_score": candidate_score,
                    "best_score": best_score,
                    "gain_from_seed": best_score - seed_score,
                    "accepted": accepted,
                }
                event_handle.write(json.dumps(event, sort_keys=True) + "\n")
                event_handle.flush()
                print(json.dumps(event, sort_keys=True), flush=True)
                if args.restart_after > 0 and stale_checks >= args.restart_after:
                    with torch.no_grad():
                        f.copy_(torch.tensor(best, dtype=torch.float32, device=device))
                    for group in optimizer.param_groups:
                        group["lr"] = max(float(group["lr"]) * 0.7, 2e-8)
                    stale_checks = 0
                beta = min(beta * 1.25, args.beta_max)
            iteration += 1

    summary = {
        "input": str(args.input.resolve()),
        "n": int(n),
        "nfft": int(nfft),
        "iterations": iteration,
        "seed_score": seed_score,
        "best_score": best_score,
        "gain": best_score - seed_score,
        "ended_at": datetime.now(UTC).isoformat(),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
