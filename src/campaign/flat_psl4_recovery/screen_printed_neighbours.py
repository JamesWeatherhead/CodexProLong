#!/usr/bin/env python3
"""Screen length-adjusted variants of published PSL-4 hexadecimal codes.

This is deliberately separate from the closed Hamming-radius search around the
Arena incumbent: every candidate is generated from an independently published
PSL-4 code of length 69, 70, 71, or 72.  A uniform FFT grid ranks candidates;
the top candidates are then evaluated by the unchanged frozen live verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import tempfile
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
VERIFIER_SHA256 = "ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2"
VERIFIER = CAMPAIGN / "state" / "problems" / "flat-polynomials" / f"{VERIFIER_SHA256}.py"
LEADER_SCORE = 1.2807274949642549
GATE_SCORE = LEADER_SCORE - 1e-6

# Leukhin--Potekhin, Optimal Peak Sidelobe Level Sequences up to Length 74
# (EuRAD 2013), Table III: highest-merit-factor representative at each N.
# Dimitrov--Baitcheva--Nikolov, IEEE Access 2021, Table 6: independent
# heuristically reached PSL-optimal representative at each N.
# Nunn--Coxson, Best-Known Autocorrelation Peak Sidelobe Levels (2008),
# supplies a third independently published N=71 representative.
# Coxson--Russo, Optimal-Peak-Sidelobe Polyphase Codes (2025), Table 4.3,
# supplies an additional N=69/N=70 historical representative pair.
SOURCES = {
    "leukhin_potekhin_2013_n69": (69, "0292582AC6A767CC03"),
    "leukhin_potekhin_2013_n70": (70, "01C2FFD4AF33356596"),
    "leukhin_potekhin_2013_n71": (71, "12493BE76A5EE2A3F1"),
    "leukhin_potekhin_2013_n72": (72, "27C8D6E165A71577FE"),
    "dimitrov_2021_n69": (69, "18ff3eb05d654b6665"),
    "dimitrov_2021_n70": (70, "2b5aae6765e79b600f"),
    "dimitrov_2021_n71": (71, "8cea0ff5e92cb9726"),
    "dimitrov_2021_n72": (72, "dbcf036102615ab2a"),
    "nunn_coxson_2008_n71": (71, "63383AB6B452ED93FE"),
    "coxson_russo_2025_n69": (69, "0231C08FDA5A0D9355"),
    "coxson_russo_2025_n70": (70, "1A133B4E3093EDD57E"),
}


def decode_hex(n: int, value: str) -> tuple[int, ...]:
    bits = f"{int(value, 16):0{n}b}"
    if len(bits) != n:
        raise ValueError(f"{value} does not fit the declared length {n}")
    return tuple(1 if bit == "0" else -1 for bit in bits)


def candidates() -> dict[tuple[int, ...], list[str]]:
    out: dict[tuple[int, ...], list[str]] = {}
    for label, (n, value) in SOURCES.items():
        base = decode_hex(n, value)
        if n == 70:
            out.setdefault(base, []).append(f"{label}:direct")
        elif n == 69:
            for pos in range(70):
                for sign in (-1, 1):
                    candidate = base[:pos] + (sign,) + base[pos:]
                    out.setdefault(candidate, []).append(f"{label}:insert:{pos}:{sign}")
        elif n == 71:
            for pos in range(71):
                candidate = base[:pos] + base[pos + 1 :]
                out.setdefault(candidate, []).append(f"{label}:delete:{pos}")
        elif n == 72:
            for i, j in itertools.combinations(range(72), 2):
                candidate = tuple(v for k, v in enumerate(base) if k not in (i, j))
                out.setdefault(candidate, []).append(f"{label}:delete:{i},{j}")
        else:
            raise AssertionError(n)
    return out


def load_evaluate():
    actual = hashlib.sha256(VERIFIER.read_bytes()).hexdigest()
    if actual != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash changed: {actual}")
    spec = importlib.util.spec_from_file_location("flat_live_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to import verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grid", type=int, default=8192)
    parser.add_argument("--exact-top", type=int, default=24)
    parser.add_argument("--chunk", type=int, default=256)
    parser.add_argument("--out", type=Path, default=HERE / "printed_neighbour_screen.json")
    args = parser.parse_args()

    generated = candidates()
    items = list(generated)
    surrogate: list[tuple[float, int]] = []
    norm = np.sqrt(71.0)
    for start in range(0, len(items), args.chunk):
        block = np.asarray(items[start : start + args.chunk], dtype=np.float64)
        # FFT samples the same unit circle; coefficient order only conjugates/
        # rotates values and therefore preserves the maximum modulus.
        values = np.fft.fft(block, n=args.grid, axis=1)
        scores = np.max(np.abs(values), axis=1) / norm
        surrogate.extend((float(score), start + offset) for offset, score in enumerate(scores))
    surrogate.sort()

    evaluate = load_evaluate()
    exact = []
    for approx, index in surrogate[: args.exact_top]:
        coefficient_tuple = items[index]
        payload = {"coefficients": list(coefficient_tuple)}
        score = float(evaluate(payload))
        exact.append(
            {
                "source_operations": generated[coefficient_tuple],
                "surrogate_score": approx,
                "score": score,
                "gap_to_gate": score - GATE_SCORE,
                "clears_gate": score < GATE_SCORE,
                "payload_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
                "payload": payload,
            }
        )
    exact.sort(key=lambda row: row["score"])
    record = {
        "source_count": len(SOURCES),
        "unique_candidate_count": len(items),
        "surrogate_grid": args.grid,
        "exact_replay_count": len(exact),
        "verifier_path": str(VERIFIER),
        "verifier_sha256": VERIFIER_SHA256,
        "leader_score": LEADER_SCORE,
        "gate_score": GATE_SCORE,
        "best": exact[0],
        "exact": exact,
    }
    atomic_json(args.out, record)
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
