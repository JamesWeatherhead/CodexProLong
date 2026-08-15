#!/usr/bin/env python3
"""Standard-library replay of the portable gamma-monodromy packet."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
STRICT_GATE = 0.036529890880030155
PREPUBLICATION_TARGET_MANIFEST_SHA256 = (
    "73eeb34b478c50cd468011812c83e267987f51a2889079ef56a5a29108f06e50"
)
REFLECTION_LABELS = (10, 7, 6, 3, 9, 8, 2, 1, 5, 4, 0)
REQUIRED_PUBLIC_FILES = {
    "bounded_result.json",
    "derived_inputs.json",
    "incumbent_krawczyk.json",
    "public_replay.py",
    "replay_receipt.json",
    "target_manifest.json",
}


def load_json(name: str) -> dict[str, object]:
    value = json.loads((HERE / name).read_text())
    if not isinstance(value, dict):
        raise TypeError(f"{name} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_publication_manifest() -> bool:
    path = HERE / "PUBLICATION_MANIFEST.json"
    if not path.exists():
        return False
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != "heilbronn-gamma-monodromy-publication-v1":
        raise AssertionError("unexpected publication manifest schema")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise AssertionError("publication files must be a list")
    observed = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise AssertionError("publication entry must be {path,bytes,sha256}")
        relative = entry["path"]
        candidate_relative = Path(relative)
        if candidate_relative.is_absolute() or ".." in candidate_relative.parts:
            raise AssertionError(f"unsafe publication path: {relative}")
        candidate = HERE / candidate_relative
        if not candidate.is_file():
            raise AssertionError(f"missing publication file: {relative}")
        if candidate.stat().st_size != entry["bytes"]:
            raise AssertionError(f"size mismatch: {relative}")
        if sha256_file(candidate) != entry["sha256"]:
            raise AssertionError(f"hash mismatch: {relative}")
        observed.add(relative)
    if not REQUIRED_PUBLIC_FILES <= observed:
        raise AssertionError("publication allowlist omits a replay dependency")
    return True


def decode(values: list[list[float]]) -> list[complex]:
    return [complex(real, imag) for real, imag in values]


def expand(values: Sequence[object]) -> list[tuple[object, object]]:
    x = values
    return [
        (x[0], 0),
        (x[1], 0),
        (x[2], x[3]),
        (x[4], x[5]),
        (x[6], x[7]),
        (0, x[8]),
        (x[9], x[10]),
        (x[11], 1 - x[11]),
        (0, x[12]),
        (x[13], x[14]),
        (x[15], 1 - x[15]),
    ]


def determinant(
    points: Sequence[tuple[object, object]], triple: tuple[int, int, int]
):
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    return (bj - bi) * (ck - ci) - (cj - ci) * (bk - bi)


def evaluate(
    values: Sequence[complex],
    triples: Sequence[tuple[int, int, int]],
    signs: dict[tuple[int, int, int], int],
) -> list[complex]:
    points = expand(values)
    return [signs[triple] * determinant(points, triple) - values[16] for triple in triples]


def maximum_abs(values: Sequence[complex]) -> float:
    return max(abs(value) for value in values)


def metrics(values: Sequence[complex], triples: Sequence[tuple[int, int, int]]) -> dict[str, object]:
    imaginary = max(abs(value.imag) for value in values)
    result: dict[str, object] = {
        "maximum_imaginary_part": imaginary,
        "real": imaginary <= 1e-9,
    }
    if imaginary > 1e-9 or not all(
        math.isfinite(value.real) and math.isfinite(value.imag) for value in values
    ):
        result.update({"intended_domain": False, "score": None})
        return result
    real_values = [value.real for value in values]
    points = expand(real_values)
    slacks = [coordinate for point in points for coordinate in (*point, 1 - sum(point))]
    distances = [
        math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1])
        for i in range(11)
        for j in range(i + 1, 11)
    ]
    all_triples = itertools.combinations(range(11), 3)
    score = min(abs(determinant(points, triple)) for triple in all_triples)
    intended = min(slacks) >= -1e-10 and min(distances) > 1e-9
    result.update(
        {
            "minimum_domain_slack": min(slacks),
            "minimum_pair_distance": min(distances),
            "score": score,
            "system_z": real_values[-1],
            "intended_domain": intended,
            "gate_clearing": intended and score > STRICT_GATE,
        }
    )
    return result


def close(left: float | None, right: float | None, tolerance: float = 2e-10) -> bool:
    if left is None or right is None:
        return left is right
    return abs(float(left) - float(right)) <= tolerance * max(1.0, abs(float(right)))


def verify_metrics(stored: dict[str, object], computed: dict[str, object]) -> None:
    for key in ("real", "intended_domain", "gate_clearing"):
        if key in stored and stored[key] != computed.get(key):
            raise AssertionError(f"metric mismatch: {key}")
    for key in (
        "maximum_imaginary_part",
        "minimum_domain_slack",
        "minimum_pair_distance",
        "score",
        "system_z",
    ):
        if key in stored and not close(stored[key], computed.get(key)):
            raise AssertionError(f"metric mismatch: {key}")


def reflect_triple(triple: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(sorted(REFLECTION_LABELS[index] for index in triple))


def canonical_exchange(
    outgoing: tuple[int, int, int], incoming: tuple[int, int, int]
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    pair = (outgoing, incoming)
    reflected = (reflect_triple(outgoing), reflect_triple(incoming))
    return min(pair, reflected)


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction

    def __post_init__(self) -> None:
        if self.lo > self.hi:
            raise ValueError("reversed interval")

    @classmethod
    def point(cls, value: Fraction | int) -> "Interval":
        q = Fraction(value)
        return cls(q, q)

    def __add__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        return Interval(self.lo + rhs.lo, self.hi + rhs.hi)

    __radd__ = __add__

    def __neg__(self) -> "Interval":
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        return self + (-rhs)

    def __rsub__(self, other: "Interval" | Fraction | int) -> "Interval":
        return Interval.point(other) - self

    def __mul__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        products = (
            self.lo * rhs.lo,
            self.lo * rhs.hi,
            self.hi * rhs.lo,
            self.hi * rhs.hi,
        )
        return Interval(min(products), max(products))

    __rmul__ = __mul__

    def max_abs(self) -> Fraction:
        return max(abs(self.lo), abs(self.hi))


def fraction_matrix_rank(matrix: list[list[Fraction]]) -> int:
    work = [row[:] for row in matrix]
    rows = len(work)
    rank = 0
    for column in range(len(work[0])):
        pivot = next((row for row in range(rank, rows) if work[row][column]), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row == rank or not work[row][column]:
                continue
            factor = work[row][column]
            work[row] = [
                left - factor * right for left, right in zip(work[row], work[rank])
            ]
        rank += 1
        if rank == rows:
            break
    return rank


def jacobian_interval(
    box: Sequence[Interval],
    active: Sequence[tuple[int, int, int]],
    signs: dict[tuple[int, int, int], int],
) -> list[list[Interval]]:
    points = expand(box)
    zero = Interval.point(0)
    result = []
    for triple in active:
        i, j, k = triple
        bi, ci = points[i]
        bj, cj = points[j]
        bk, ck = points[k]
        sign = signs[triple]
        point_grad = [[zero, zero] for _ in range(11)]
        point_grad[i] = [sign * (cj - ck), sign * (bk - bj)]
        point_grad[j] = [sign * (ck - ci), sign * (bi - bk)]
        point_grad[k] = [sign * (ci - cj), sign * (bj - bi)]
        grad = [zero for _ in range(17)]
        grad[0] = point_grad[0][0]
        grad[1] = point_grad[1][0]
        grad[2:4] = point_grad[2]
        grad[4:6] = point_grad[3]
        grad[6:8] = point_grad[4]
        grad[8] = point_grad[5][1]
        grad[9:11] = point_grad[6]
        grad[11] = point_grad[7][0] - point_grad[7][1]
        grad[12] = point_grad[8][1]
        grad[13:15] = point_grad[9]
        grad[15] = point_grad[10][0] - point_grad[10][1]
        grad[16] = Interval.point(-1)
        result.append(grad)
    return result


def exact_krawczyk_check(
    certificate: dict[str, object],
    active: Sequence[tuple[int, int, int]],
    signs: dict[tuple[int, int, int], int],
) -> dict[str, object]:
    center = [Fraction(value) for value in certificate["center"]]
    preconditioner = [
        [Fraction(value) for value in row] for row in certificate["preconditioner"]
    ]
    radius = Fraction(certificate["radius"])
    box = [Interval(value - radius, value + radius) for value in center]
    center_points = expand(center)
    f_center = [
        signs[triple] * determinant(center_points, triple) - center[16]
        for triple in active
    ]
    jac_box = jacobian_interval(box, active, signs)
    rank = fraction_matrix_rank(preconditioner)
    term = [
        -sum(preconditioner[i][k] * f_center[k] for k in range(17))
        for i in range(17)
    ]
    matrix: list[list[Interval]] = []
    for i in range(17):
        row = []
        for j in range(17):
            product = Interval.point(0)
            for k in range(17):
                product += preconditioner[i][k] * jac_box[k][j]
            row.append(Interval.point(1 if i == j else 0) - product)
        matrix.append(row)
    ratios = []
    for i in range(17):
        bound = abs(term[i]) + radius * sum(entry.max_abs() for entry in matrix[i])
        ratios.append(bound / radius)
    maximum_ratio = max(ratios)
    z_upper = center[16] + radius
    gate = Fraction(str(STRICT_GATE))
    certified = rank == 17 and maximum_ratio < 1
    return {
        "preconditioner_exact_rank": rank,
        "strict_inclusion": certified,
        "maximum_krawczyk_ratio_fraction": (
            f"{maximum_ratio.numerator}/{maximum_ratio.denominator}"
        ),
        "maximum_krawczyk_ratio_decimal": float(maximum_ratio),
        "maximum_center_residual_fraction": str(max(abs(value) for value in f_center)),
        "z_upper_fraction": f"{z_upper.numerator}/{z_upper.denominator}",
        "z_upper_decimal": float(z_upper),
        "strict_gate_fraction": f"{gate.numerator}/{gate.denominator}",
        "z_box_strictly_below_gate": z_upper < gate,
        "certified_unique_real_root_in_box": certified,
        "certified_root_cannot_clear_gate": certified and z_upper < gate,
    }


def canonical_hash(value: object) -> str:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def build_receipt() -> dict[str, object]:
    fixture = load_json("derived_inputs.json")
    target_manifest = load_json("target_manifest.json")
    bounded = load_json("bounded_result.json")
    certificate = load_json("incumbent_krawczyk.json")

    if sha256_file(HERE / "derived_inputs.json") != target_manifest["inputs"][
        "derived_inputs"
    ]["sha256"]:
        raise AssertionError("derived-input hash mismatch")
    if target_manifest["inputs"]["private_source_provenance"] != fixture[
        "private_source_provenance"
    ] or target_manifest["inputs"]["corpus_audit_claims"] != fixture[
        "corpus_audit_claims"
    ]:
        raise AssertionError("target provenance projection mismatch")
    private_hashes = {
        record["logical_id"]: record["sha256"]
        for record in fixture["private_source_provenance"]
    }
    bounded_inputs = bounded["inputs"]
    if (
        bounded_inputs["seed_sha256"] != private_hashes["incumbent_seed_best_json"]
        or bounded_inputs["pseudo_results_sha256"]
        != private_hashes["pseudo_arclength_results_jsonl"]
        or bounded_inputs["target_manifest_sha256"]
        != PREPUBLICATION_TARGET_MANIFEST_SHA256
    ):
        raise AssertionError("historical bounded-run provenance mismatch")
    active = tuple(tuple(triple) for triple in certificate["system"]["active_triples"])
    active_signs = certificate["system"]["signs"]
    signs = dict(zip(active, active_signs))
    seed = [complex(float(value)) for value in fixture["incumbent_center"]["decimal_values"]]
    seed_points = expand(seed)
    for triple in itertools.combinations(range(11), 3):
        value = determinant(seed_points, triple).real
        if value == 0:
            raise AssertionError("derived seed has an indeterminate orientation")
        signs[triple] = 1 if value > 0 else -1
    if [signs[triple] for triple in active] != active_signs:
        raise AssertionError("certificate signs disagree with derived seed")

    records = fixture["unresolved_exchange_records"]
    if len(records) != 619 or len({tuple(row) for row in records}) != 619:
        raise AssertionError("derived exchange records are not exactly 619 unique rows")
    pseudo_codes = fixture["status_codebooks"]["pseudo_status"]
    reflection_codes = fixture["status_codebooks"]["reflection_status"]
    fixture_rows = {}
    for row in records:
        outgoing_index, i, j, k, pseudo_code, reflection_code = row
        if not (0 <= outgoing_index < len(active)):
            raise AssertionError("invalid outgoing active-equation index")
        if not (0 <= pseudo_code < len(pseudo_codes)) or not (
            0 <= reflection_code < len(reflection_codes)
        ):
            raise AssertionError("invalid derived status code")
        pair = (active[outgoing_index], (i, j, k))
        fixture_rows[pair] = (pseudo_codes[pseudo_code], reflection_codes[reflection_code])
    fixture_pairs = set(fixture_rows)
    target_rows = target_manifest["targets"]
    if len(target_rows) != 619:
        raise AssertionError("target manifest does not contain 619 rows")
    target_pairs = {
        (tuple(target["outgoing"]), tuple(target["incoming"]))
        for target in target_rows
    }
    if fixture_pairs != target_pairs or len(target_pairs) != len(target_rows):
        raise AssertionError("target inventory mismatch")
    if {target["inventory_index"] for target in target_rows} != set(range(619)):
        raise AssertionError("target inventory indices are not a permutation of 0..618")
    for target in target_rows:
        pair = (tuple(target["outgoing"]), tuple(target["incoming"]))
        if fixture_rows[pair] != (
            target["pseudo_status"],
            target["reflection_status"],
        ):
            raise AssertionError("target status projection mismatch")
    computed_unresolved = Counter(status[0] for status in fixture_rows.values())
    computed_reflection = Counter(status[1] for status in fixture_rows.values())
    status_counts = target_manifest["status_counts"]
    if dict(computed_unresolved) != status_counts["unresolved"] or dict(
        computed_reflection
    ) != status_counts["reflection_counterpart"]:
        raise AssertionError("target status aggregate mismatch")
    private_counts = fixture["private_run_aggregates"]
    if private_counts["unresolved"] != status_counts["unresolved"] or private_counts[
        "reflection_counterpart"
    ] != status_counts["reflection_counterpart"]:
        raise AssertionError("private aggregate projection mismatch")
    orbits = {canonical_exchange(*pair) for pair in target_pairs}
    if len(orbits) != 334:
        raise AssertionError("reflection orbit count is not 334")

    base_rhs = decode(bounded["generic_base"]["rhs"])
    generic_residuals = []
    generic_roots = []
    for encoded in bounded["generic_roots"]:
        root = decode(encoded)
        generic_roots.append(root)
        residual = maximum_abs(
            [left - right for left, right in zip(evaluate(root, active, signs), base_rhs)]
        )
        generic_residuals.append(residual)
    if max(generic_residuals) > 2e-9:
        raise AssertionError("generic root residual exceeds replay limit")
    generic_separations = [
        maximum_abs([left - right for left, right in zip(first, second)])
        for first, second in itertools.combinations(generic_roots, 2)
    ]
    minimum_generic_separation = min(generic_separations)
    if any(
        separation <= 2e-7 * max(1.0, maximum_abs(first), maximum_abs(second))
        for separation, (first, second) in zip(
            generic_separations, itertools.combinations(generic_roots, 2)
        )
    ):
        raise AssertionError("stored generic roots are not distinct at clustering tolerance")

    real_incumbent = 0
    legal_incumbent = 0
    successful_incumbent = 0
    for specialization in bounded["incumbent_specializations"]:
        endpoint = decode(specialization["endpoint"])
        residual = maximum_abs(evaluate(endpoint, active, signs))
        if not close(residual, specialization["endpoint_residual"], 2e-9):
            raise AssertionError("incumbent specialization residual mismatch")
        computed = metrics(endpoint, active)
        verify_metrics(specialization["metrics"], computed)
        successful_incumbent += int(
            bool(specialization["track"]["success"] and residual <= 1e-9)
        )
        real_incumbent += int(bool(computed["real"]))
        legal_incumbent += int(bool(computed["intended_domain"]))
    if successful_incumbent != len(bounded["incumbent_specializations"]):
        raise AssertionError("not every incumbent specialization replayed successfully")

    successful_paths = 0
    distinct_roots = 0
    real_successful_paths = 0
    real_successful_roots = 0
    successful_imaginary_parts = []
    gate_clearers = []
    for target_index, target in enumerate(bounded["target_probes"]):
        outgoing = tuple(target["outgoing"])
        incoming = tuple(target["incoming"])
        triples = tuple(triple for triple in active if triple != outgoing) + (incoming,)
        roots: list[list[complex]] = []
        for path_index, path in enumerate(target["paths"]):
            endpoint = decode(path["endpoint"])
            residual = maximum_abs(evaluate(endpoint, triples, signs))
            if not close(residual, path["endpoint_residual"], 2e-8):
                raise AssertionError("target residual mismatch")
            computed = metrics(endpoint, triples)
            verify_metrics(path["metrics"], computed)
            successful = bool(path["track"]["success"] and residual <= 1e-9)
            if successful:
                successful_paths += 1
                real_successful_paths += int(bool(computed["real"]))
                successful_imaginary_parts.append(computed["maximum_imaginary_part"])
                if not any(
                    maximum_abs([left - right for left, right in zip(endpoint, root)])
                    <= 1e-7 * max(1.0, maximum_abs(root))
                    for root in roots
                ):
                    roots.append(endpoint)
                    real_successful_roots += int(bool(computed["real"]))
                if computed.get("gate_clearing"):
                    gate_clearers.append(
                        {"target_index": target_index, "path_index": path_index}
                    )
        distinct_roots += len(roots)
    if real_successful_paths or real_successful_roots:
        raise AssertionError("successful target path unexpectedly reached a real root")
    if gate_clearers or bounded["legal_gate_clearers"]:
        raise AssertionError("packet unexpectedly contains a legal gate clearer")

    stored_payload_hash = certificate.pop("certificate_payload_sha256")
    if canonical_hash(certificate) != stored_payload_hash:
        raise AssertionError("Krawczyk certificate payload hash mismatch")
    exact_check = exact_krawczyk_check(certificate, active, signs)
    if exact_check != certificate["exact_check"]:
        raise AssertionError("exact Krawczyk replay mismatch")
    if not exact_check["certified_root_cannot_clear_gate"]:
        raise AssertionError("incumbent root exclusion did not certify")

    return {
        "schema": "heilbronn-gamma-monodromy-public-replay-v2",
        "status": "PASS",
        "unresolved_targets": len(target_pairs),
        "reflection_orbits": len(orbits),
        "generic_roots_replayed": len(generic_residuals),
        "maximum_generic_root_residual": max(generic_residuals),
        "minimum_generic_root_separation": minimum_generic_separation,
        "incumbent_specializations_replayed": len(bounded["incumbent_specializations"]),
        "successful_incumbent_specializations": successful_incumbent,
        "real_incumbent_specializations": real_incumbent,
        "intended_domain_incumbent_specializations": legal_incumbent,
        "target_systems_replayed": len(bounded["target_probes"]),
        "target_paths_replayed": sum(len(target["paths"]) for target in bounded["target_probes"]),
        "successful_target_paths": successful_paths,
        "distinct_successful_target_roots": distinct_roots,
        "real_successful_target_paths": real_successful_paths,
        "real_successful_target_roots": real_successful_roots,
        "minimum_successful_target_maximum_imaginary_part": min(
            successful_imaginary_parts
        ),
        "legal_gate_clearers": 0,
        "strict_gate": STRICT_GATE,
        "exact_krawczyk": exact_check,
    }


def main() -> int:
    receipt = build_receipt()
    stored = load_json("replay_receipt.json")
    if stored != receipt:
        raise AssertionError("stored replay receipt is stale")
    runtime = {
        **receipt,
        "publication_manifest_verified": verify_publication_manifest(),
    }
    print(json.dumps(runtime, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
