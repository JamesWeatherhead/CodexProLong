#!/usr/bin/env python3
"""Exact beam search for a sparse patch on the relative-graph frontier.

Relative difference sets omit a forbidden subgroup.  The literature repairs
that defect by adjoining a smaller difference basis on the subgroup.  After
embedding into the integers, the defect is carry-dependent rather than a
literal subgroup, so this program grows an unrestricted sparse patch.  At
each node every legal point that can repair the current first gap is
enumerated exactly; no coordinate radius or incumbent Singer block is used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from exact import (
    ROOT,
    atomic_json,
    difference_bits,
    first_missing,
    load_live,
    normalized,
    replay,
    sha256_json,
)
from relative_graph_search import Parameters, construct


SOURCE = ROOT / "checkpoints" / "relative_graph.json"
CHECKPOINT = ROOT / "checkpoints" / "sparse_patch.json"
BEST = ROOT / "candidates" / "sparse_patch_best.json"


@dataclass(frozen=True)
class Node:
    values: tuple[int, ...]
    bits: int

    @property
    def coverage(self) -> int:
        return first_missing(self.bits) - 1

    @property
    def score(self) -> Fraction:
        return Fraction(len(self.values) ** 2, self.coverage)

    @property
    def key(self) -> tuple[int, int, int]:
        # Prefix is primary.  Broad difference count breaks plateaus, while a
        # smaller span avoids gratuitously remote repair points.
        return (self.coverage, self.bits.bit_count(), -self.values[-1])


def extend(node: Node, added: int) -> Node:
    values = normalized([*node.values, added])
    bits = node.bits
    for old in node.values:
        bits |= 1 << abs(added - old)
    # Translation normalization does not change differences or bits.
    return Node(tuple(values), bits)


def children(node: Node) -> list[Node]:
    gap = node.coverage + 1
    present = set(node.values)
    additions = set()
    for value in node.values:
        additions.add(value + gap)
        additions.add(value - gap)
    unique: dict[str, Node] = {}
    for added in additions:
        if added in present:
            continue
        child = extend(node, added)
        if child.coverage < gap:
            raise RuntimeError("gap-forced child failed to cover its forced gap")
        digest = sha256_json({"set": list(child.values)})
        previous = unique.get(digest)
        if previous is None or child.key > previous.key:
            unique[digest] = child
    return list(unique.values())


def receipt(node: Node, live: dict[str, Any]) -> dict[str, Any]:
    result = replay(node.values, live)
    result.pop("payload")
    result["difference_count"] = node.bits.bit_count()
    result["span"] = node.values[-1]
    return result


def write_best(node: Node, live: dict[str, Any], depth: int) -> None:
    result = replay(node.values, live)
    atomic_json(
        BEST,
        {
            "schema": 1,
            "source": str(SOURCE.relative_to(ROOT)),
            "depth": depth,
            "verifier_sha256": live["verifier_sha256"],
            "receipt": {key: value for key, value in result.items() if key != "payload"},
            "payload": result["payload"],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--beam", type=int, default=8)
    parser.add_argument("--max-additions", type=int, default=24)
    args = parser.parse_args()
    if min(args.beam, args.max_additions) < 1:
        raise SystemExit("budgets must be positive")

    live = load_live()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    if source["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("relative-graph source uses a different verifier")
    # Raw coverage favors larger primes even when they are much farther from
    # their size-dependent gate.  The patch seed instead maximizes exact
    # coverage / required_coverage, with literal coverage as tie-breaker.
    source_record = max(
        source["records"],
        key=lambda record: (
            Fraction(record["coverage"], record["required_coverage"]),
            record["coverage"],
        ),
    )
    parameters = Parameters.from_dict(source_record["parameters"])
    source_values = construct(parameters)
    source_replay = replay(source_values, live)
    if source_replay["payload_sha256"] != source_record["payload_sha256"]:
        raise RuntimeError("relative-graph checkpoint cannot reconstruct its seed")
    initial = Node(tuple(source_values), difference_bits(source_values))
    beam = [initial]
    global_best = initial
    records = [{"depth": 0, **receipt(initial, live)}]

    for depth in range(1, args.max_additions + 1):
        candidates: dict[str, Node] = {}
        expanded = 0
        for node in beam:
            for child in children(node):
                expanded += 1
                digest = sha256_json({"set": list(child.values)})
                previous = candidates.get(digest)
                if previous is None or child.key > previous.key:
                    candidates[digest] = child
        if not candidates:
            break
        beam = sorted(candidates.values(), key=lambda node: node.key, reverse=True)[: args.beam]
        best = beam[0]
        if best.key > global_best.key:
            global_best = best
            write_best(best, live, depth)
        record = {
            "depth": depth,
            "parents": min(args.beam, len(beam)),
            "children_evaluated": expanded,
            **receipt(best, live),
        }
        records.append(record)
        state = {
            "schema": 1,
            "source_payload_sha256": source_record["payload_sha256"],
            "source_parameters": source_record["parameters"],
            "verifier_sha256": live["verifier_sha256"],
            "leader_score": live["leader_score"],
            "gate_score": live["gate_score"],
            "beam_width": args.beam,
            "max_additions": args.max_additions,
            "records": records,
            "best": receipt(global_best, live),
            "complete": False,
        }
        atomic_json(CHECKPOINT, state)
        print(json.dumps(record, sort_keys=True), flush=True)
        if record["gate_cleared"]:
            state["complete"] = True
            state["conclusion"] = "exact verifier-valid gate-clearer found"
            atomic_json(CHECKPOINT, state)
            return 0

    state = {
        "schema": 1,
        "source_payload_sha256": source_record["payload_sha256"],
        "source_parameters": source_record["parameters"],
        "verifier_sha256": live["verifier_sha256"],
        "leader_score": live["leader_score"],
        "gate_score": live["gate_score"],
        "beam_width": args.beam,
        "max_additions": args.max_additions,
        "records": records,
        "best": receipt(global_best, live),
        "complete": True,
        "gate_cleared": False,
        "conclusion": (
            "The exhaustive first-gap birth beam on the relative-graph seed "
            "did not clear the exact live gate within the stated depth."
        ),
    }
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state["best"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
