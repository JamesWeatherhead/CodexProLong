#!/usr/bin/env python3
"""Solver-free verification of the retained same-support weak dual."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
PAYLOAD = (
    REPOSITORY
    / "campaign/discrete/prime_number_theorem/reach_extend_127849_fullrange.json"
)
CHECKPOINT = (
    REPOSITORY
    / "campaign/discrete/prime_number_theorem/checkpoints/reach_extend_127849_global.json"
)
DUAL = HERE / "same_support_dual.json"
RECEIPT = HERE / "same_support_upper_receipt.json"
KEY_PACKET = HERE / "same_support_keys.json"
PAYLOAD_SHA256 = "d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1"
CHECKPOINT_SHA256 = "72411372498cdf78b40f14c8dff30a91ce16f7c573c6bc5dd26fc89471220907"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if PAYLOAD.exists() and sha256_file(PAYLOAD) != PAYLOAD_SHA256:
        raise RuntimeError("payload hash mismatch")
    if CHECKPOINT.exists() and sha256_file(CHECKPOINT) != CHECKPOINT_SHA256:
        raise RuntimeError("checkpoint hash mismatch")
    dual = json.loads(DUAL.read_text())
    receipt = json.loads(RECEIPT.read_text())
    if dual["payload_sha256"] != PAYLOAD_SHA256:
        raise RuntimeError("dual payload provenance mismatch")
    if dual["checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise RuntimeError("dual checkpoint provenance mismatch")
    rows = list(map(int, dual["rows"]))
    lambdas = [Decimal(value) for value in dual["multipliers"]]
    if len(rows) != len(lambdas) or any(value < 0 for value in lambdas):
        raise RuntimeError("invalid nonnegative dual vector")
    key_packet = json.loads(KEY_PACKET.read_text())
    if key_packet["source_payload_sha256"] != PAYLOAD_SHA256:
        raise RuntimeError("key-packet provenance mismatch")
    keys = list(map(int, key_packet["keys"]))
    if PAYLOAD.exists():
        payload_keys = sorted(map(int, json.loads(PAYLOAD.read_text())["partial_function"]))
        if keys != payload_keys:
            raise RuntimeError("portable key packet differs from the source payload")
    if len(keys) != 2_000 or 1 in keys:
        raise RuntimeError("unexpected payload support")

    with localcontext() as context:
        context.prec = 80
        epsilon = Decimal("1e-70")
        residual_abs_upper = Decimal(0)
        for key in keys:
            center = Decimal(key).ln() / Decimal(key)
            center += sum(
                lam * Decimal(-(row % key)) / Decimal(key)
                for row, lam in zip(rows, lambdas)
                if lam
            )
            residual_abs_upper += abs(center) + epsilon
        ceiling = Decimal(10) * residual_abs_upper + sum(lambdas, Decimal(0))

    recorded = Decimal(receipt["weak_duality_score_ceiling_decimal"])
    if ceiling != recorded:
        raise RuntimeError(f"dual ceiling mismatch: {ceiling} != {recorded}")
    gate = Decimal(receipt["historical_gate"])
    if not ceiling < gate:
        raise RuntimeError("retained dual does not close the historical gate")
    print(
        json.dumps(
            {
                "verified": True,
                "master_rows": len(rows),
                "score_ceiling": str(ceiling),
                "historical_gate": str(gate),
                "gap": str(ceiling - gate),
                "dual_sha256": sha256_file(DUAL),
                "verifier_executed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
