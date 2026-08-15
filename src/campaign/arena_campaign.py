#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "state"
DEFAULT_BASE = "https://einsteinarena.com"
DEFAULT_AGENT = "CodexProLong"
DEFAULT_IMAGE = "einsteinarena-verifier:2026-08-14"
INLINE_LIMIT = 1_800_000


class CampaignError(RuntimeError):
    pass


class HttpCampaignError(CampaignError):
    def __init__(self, status: int, method: str, path: str, response_body: str):
        self.status = status
        self.method = method
        self.path = path
        self.response_body = response_body
        super().__init__(f"HTTP {status} for {method} {path}: {response_body}")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _event_hash(record: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in record.items() if key != "hash"}
    return sha256_bytes(canonical_bytes(unsigned))


def read_events(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    previous = "0" * 64
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CampaignError(f"corrupt journal line {index}: {exc}") from exc
        if event.get("sequence") != index:
            raise CampaignError(f"journal sequence mismatch at line {index}")
        if event.get("previous_hash") != previous:
            raise CampaignError(f"journal chain mismatch at line {index}")
        if event.get("hash") != _event_hash(event):
            raise CampaignError(f"journal hash mismatch at line {index}")
        previous = event["hash"]
        events.append(event)
    return events


def append_event(state_dir: Path, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        events = read_events(state_dir)
        previous = events[-1]["hash"] if events else "0" * 64
        event: dict[str, Any] = {
            "sequence": len(events) + 1,
            "timestamp": utc_now(),
            "type": event_type,
            "payload": payload,
            "previous_hash": previous,
        }
        event["hash"] = _event_hash(event)
        with (state_dir / "events.jsonl").open("ab") as handle:
            handle.write(canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event


def http_json(
    base: str,
    method: str,
    path: str,
    *,
    body: Any | None = None,
    token: str | None = None,
    timeout: int = 60,
) -> Any:
    url = path if path.startswith("https://") else base.rstrip("/") + path
    headers = {"Accept": "application/json", "User-Agent": "einsteinarena-campaign/1"}
    data = None
    if body is not None:
        data = canonical_bytes(body)
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read(4096).decode("utf-8", "replace")
        raise HttpCampaignError(exc.code, method, path, raw) from exc
    except urllib.error.URLError as exc:
        raise CampaignError(f"network error for {method} {path}: {exc.reason}") from exc
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CampaignError(f"non-JSON response for {method} {path}") from exc


def get_problem(base: str, slug: str) -> dict[str, Any]:
    detail = http_json(base, "GET", f"/api/problems/{urllib.parse.quote(slug)}")
    if not isinstance(detail, dict) or "verifier" not in detail:
        raise CampaignError(f"invalid problem response for {slug}")
    return {"slug": slug, **detail}


def get_leaderboard(base: str, problem_id: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"problem_id": problem_id, "limit": 100})
    rows = http_json(base, "GET", f"/api/leaderboard?{query}")
    if not isinstance(rows, list):
        raise CampaignError(f"invalid leaderboard response for problem {problem_id}")
    return rows


def _threads(base: str, slug: str, sort: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"sort": sort, "limit": 20, "offset": 0})
    rows = http_json(base, "GET", f"/api/problems/{urllib.parse.quote(slug)}/threads?{query}")
    return rows if isinstance(rows, list) else rows.get("items", [])


def score_of(row: dict[str, Any]) -> float | None:
    for key in ("bestScore", "score", "best_score"):
        if row.get(key) is not None:
            return float(row[key])
    return None


def agent_of(row: dict[str, Any]) -> str | None:
    for key in ("agentName", "agent_name", "agent"):
        if row.get(key) is not None:
            return str(row[key])
    return None


def snapshot(base: str, state_dir: Path, agent_name: str) -> dict[str, Any]:
    listed = http_json(base, "GET", "/api/problems")
    if not isinstance(listed, list):
        raise CampaignError("invalid problems response")
    result: dict[str, Any] = {
        "generated_at": utc_now(),
        "base_url": base,
        "agent_name": agent_name,
        "problems": {},
    }
    for item in listed:
        slug = item["slug"]
        detail = get_problem(base, slug)
        verifier = detail.pop("verifier")
        verifier_hash = sha256_bytes(verifier.encode("utf-8"))
        problem_dir = state_dir / "problems" / slug
        verifier_path = problem_dir / f"{verifier_hash}.py"
        detail_path = problem_dir / f"{verifier_hash}.json"
        if not verifier_path.exists():
            atomic_write(verifier_path, verifier.encode("utf-8"), 0o600)
        stored_detail = {**detail, "verifier_sha256": verifier_hash}
        atomic_write(detail_path, canonical_bytes(stored_detail) + b"\n", 0o600)

        leaderboard = get_leaderboard(base, int(detail["id"]))
        ours = next(((index, row) for index, row in enumerate(leaderboard, start=1) if agent_of(row) == agent_name), None)
        leader = leaderboard[0] if leaderboard else None
        result["problems"][slug] = {
            "id": detail["id"],
            "title": detail.get("title"),
            "scoring": detail.get("scoring"),
            "minImprovement": detail.get("minImprovement", 0),
            "evaluationMode": detail.get("evaluationMode"),
            "solutionSchema": detail.get("solutionSchema"),
            "verifier_sha256": verifier_hash,
            "verifier_path": str(verifier_path.relative_to(state_dir)),
            "detail_path": str(detail_path.relative_to(state_dir)),
            "leader": leader,
            "leaderboard": leaderboard,
            "our_rank": ours[0] if ours else None,
            "our_entry": ours[1] if ours else None,
            "threads_top": _threads(base, slug, "top"),
            "threads_recent": _threads(base, slug, "recent"),
        }

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot_path = state_dir / "snapshots" / f"{stamp}.json"
    payload = canonical_bytes(result) + b"\n"
    atomic_write(snapshot_path, payload, 0o600)
    atomic_write(state_dir / "latest.json", payload, 0o600)
    append_event(state_dir, "snapshot", {
        "snapshot": str(snapshot_path.relative_to(state_dir)),
        "problem_count": len(result["problems"]),
        "first_places": sum(1 for p in result["problems"].values() if p["our_rank"] == 1),
    })
    return result


def load_latest(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "latest.json"
    if not path.exists():
        raise CampaignError("no snapshot; run snapshot first")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_candidate(candidate: Any, schema: Any) -> None:
    if not isinstance(candidate, dict) or not candidate:
        raise CampaignError("candidate must be a non-empty JSON object")
    if isinstance(schema, dict):
        missing = sorted(set(schema) - set(candidate))
        if missing:
            raise CampaignError(f"candidate is missing schema keys: {', '.join(missing)}")

    nodes = [candidate]
    seen = 0
    while nodes:
        value = nodes.pop()
        seen += 1
        if seen > 5_000_000:
            raise CampaignError("candidate contains too many JSON nodes")
        if isinstance(value, dict):
            nodes.extend(value.values())
        elif isinstance(value, list):
            nodes.extend(value)
        elif isinstance(value, bool) or value is None or isinstance(value, str):
            continue
        elif isinstance(value, (int, float)):
            if not math.isfinite(float(value)):
                raise CampaignError("candidate contains a non-finite number")
        else:
            raise CampaignError(f"candidate contains unsupported value type {type(value).__name__}")


def load_candidate(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    try:
        artifact = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CampaignError(f"invalid candidate JSON: {exc}") from exc
    candidate = artifact.get("solution") if isinstance(artifact, dict) and isinstance(artifact.get("solution"), dict) else artifact
    if not isinstance(candidate, dict):
        raise CampaignError("candidate or candidate.solution must be a JSON object")
    return candidate, canonical_bytes(candidate), sha256_bytes(raw)


def clears_gate(score: float, best: float | None, scoring: str, gate: float) -> bool:
    if best is None:
        return True
    if scoring == "maximize":
        return score > best if gate == 0 else score >= best + gate
    if scoring == "minimize":
        return score < best if gate == 0 else score <= best - gate
    raise CampaignError(f"unknown scoring direction: {scoring}")


def margin(score: float, best: float | None, scoring: str) -> float | None:
    if best is None:
        return None
    return score - best if scoring == "maximize" else best - score


def run_verifier(verifier_path: Path, candidate_path: Path, image: str, timeout: int) -> tuple[float, str]:
    runner = ROOT / "verifier_runner.py"
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "256", "--memory", "8g", "--cpus", "6",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=1g",
        "--env", "HOME=/tmp", "--env", "OPENBLAS_NUM_THREADS=6",
        "--env", "OMP_NUM_THREADS=6", "--env", "MKL_NUM_THREADS=6",
        "--mount", f"type=bind,src={verifier_path.resolve()},dst=/input/verifier.py,readonly",
        "--mount", f"type=bind,src={candidate_path.resolve()},dst=/input/candidate.json,readonly",
        "--mount", f"type=bind,src={runner.resolve()},dst=/runner/verifier_runner.py,readonly",
        image, "python", "/runner/verifier_runner.py", "/input/verifier.py", "/input/candidate.json",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise CampaignError(f"verifier timed out after {timeout}s") from exc
    stdout = completed.stdout.strip().splitlines()
    if not stdout:
        raise CampaignError(f"verifier produced no result (exit {completed.returncode}): {completed.stderr[-2000:]}")
    try:
        result = json.loads(stdout[-1])
    except json.JSONDecodeError as exc:
        raise CampaignError(f"invalid verifier output: {completed.stdout[-2000:]}") from exc
    if completed.returncode != 0 or not result.get("ok"):
        raise CampaignError(f"verifier rejected candidate: {result.get('error')}\n{completed.stderr[-2000:]}")
    return float(result["score"]), completed.stderr[-4000:]


def verify(
    state_dir: Path,
    slug: str,
    candidate_path: Path,
    *,
    image: str,
    timeout: int,
    snapshot_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest = snapshot_data or load_latest(state_dir)
    if slug not in latest["problems"]:
        raise CampaignError(f"unknown problem in snapshot: {slug}")
    problem = latest["problems"][slug]
    candidate, candidate_bytes, artifact_hash = load_candidate(candidate_path)
    validate_candidate(candidate, problem.get("solutionSchema"))
    verifier_path = state_dir / problem["verifier_path"]
    if sha256_bytes(verifier_path.read_bytes()) != problem["verifier_sha256"]:
        raise CampaignError("cached verifier hash mismatch")
    run_path = candidate_path
    temporary_path: Path | None = None
    if candidate_bytes != candidate_path.read_bytes():
        temporary_dir = state_dir / "tmp"
        temporary_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix="candidate-", suffix=".json", dir=temporary_dir)
        temporary_path = Path(temporary_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(candidate_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        run_path = temporary_path
    try:
        score, diagnostics = run_verifier(verifier_path, run_path, image, timeout)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    leader_score = score_of(problem["leader"]) if problem.get("leader") else None
    gate = float(problem.get("minImprovement") or 0)
    receipt = {
        "verified_at": utc_now(),
        "slug": slug,
        "problem_id": problem["id"],
        "candidate_path": str(candidate_path.resolve()),
        "candidate_sha256": sha256_bytes(candidate_bytes),
        "artifact_sha256": artifact_hash,
        "candidate_bytes": len(candidate_bytes),
        "verifier_sha256": problem["verifier_sha256"],
        "score": score,
        "scoring": problem["scoring"],
        "leader_agent": agent_of(problem["leader"]) if problem.get("leader") else None,
        "leader_score": leader_score,
        "min_improvement": gate,
        "margin": margin(score, leader_score, problem["scoring"]),
        "clears_first_place_gate": clears_gate(score, leader_score, problem["scoring"], gate),
        "diagnostics_tail": diagnostics,
    }
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt_path = state_dir / "receipts" / slug / f"{stamp}-{receipt['candidate_sha256'][:12]}.json"
    atomic_write(receipt_path, canonical_bytes(receipt) + b"\n", 0o600)
    receipt["receipt_path"] = str(receipt_path)
    append_event(state_dir, "verify", {key: receipt[key] for key in (
        "slug", "candidate_sha256", "verifier_sha256", "score", "leader_score",
        "margin", "clears_first_place_gate",
    )})
    return receipt


def load_credentials() -> tuple[str, str]:
    token = os.environ.get("EINSTEIN_ARENA_API_KEY")
    agent = os.environ.get("EINSTEIN_ARENA_AGENT", DEFAULT_AGENT)
    if token:
        return token, agent
    path = Path.home() / ".config" / "einsteinarena" / "credentials.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignError(f"cannot read EinsteinArena credentials from {path}") from exc
    token = data.get("api_key") or data.get("token")
    agent = data.get("agent") or data.get("name") or agent
    if not token:
        raise CampaignError("EinsteinArena credential file has no API key")
    return str(token), str(agent)


def upload_large(base: str, token: str, payload: bytes) -> str:
    grant = http_json(base, "POST", "/api/solutions/upload-url", body={}, token=token)
    for key in ("clientToken", "blobKey", "uploadUrl"):
        if not grant.get(key):
            raise CampaignError(f"blob grant omitted {key}")
    request = urllib.request.Request(
        grant["uploadUrl"], data=payload, method="PUT",
        headers={
            "Authorization": f"Bearer {grant['clientToken']}",
            "Content-Type": "application/json",
            "x-api-version": "7",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise CampaignError(f"blob upload failed with HTTP {exc.code}: {exc.read(2048).decode('utf-8', 'replace')}") from exc
    return str(grant["blobKey"])


def submit(
    base: str,
    state_dir: Path,
    slug: str,
    candidate_path: Path,
    *,
    image: str,
    timeout: int,
) -> dict[str, Any]:
    token, agent_name = load_credentials()
    pinned = load_latest(state_dir)
    if slug not in pinned.get("problems", {}):
        raise CampaignError(f"problem {slug} is not present in the reviewed snapshot")
    pinned_hash = pinned["problems"][slug]["verifier_sha256"]
    live = get_problem(base, slug)
    verifier = live.pop("verifier")
    verifier_hash = sha256_bytes(verifier.encode("utf-8"))
    if verifier_hash != pinned_hash:
        raise CampaignError(
            f"live verifier changed from {pinned_hash} to {verifier_hash}; "
            "run snapshot and review the change before submitting"
        )
    leaderboard = get_leaderboard(base, int(live["id"]))
    live_problem_dir = state_dir / "problems" / slug
    verifier_path = live_problem_dir / f"{verifier_hash}.py"
    detail_path = live_problem_dir / f"{verifier_hash}.json"
    if not verifier_path.exists():
        atomic_write(verifier_path, verifier.encode("utf-8"), 0o600)
    atomic_write(detail_path, canonical_bytes({**live, "verifier_sha256": verifier_hash}) + b"\n", 0o600)
    leader = leaderboard[0] if leaderboard else None
    live_snapshot = {
        "generated_at": utc_now(), "base_url": base, "agent_name": agent_name,
        "problems": {slug: {
            "id": live["id"], "title": live.get("title"), "scoring": live["scoring"],
            "minImprovement": live.get("minImprovement", 0),
            "solutionSchema": live.get("solutionSchema"), "verifier_sha256": verifier_hash,
            "verifier_path": str(verifier_path.relative_to(state_dir)),
            "detail_path": str(detail_path.relative_to(state_dir)),
            "leader": leader, "leaderboard": leaderboard,
        }},
    }
    receipt = verify(state_dir, slug, candidate_path, image=image, timeout=timeout, snapshot_data=live_snapshot)
    if not receipt["clears_first_place_gate"]:
        raise CampaignError(
            f"refusing submission: score {receipt['score']} does not clear live leader "
            f"{receipt['leader_score']} by gate {receipt['min_improvement']}"
        )
    candidate, payload, _artifact_hash = load_candidate(candidate_path)
    mode = "inline" if len(payload) <= INLINE_LIMIT else "blob"
    attempt = append_event(state_dir, "submission_attempt", {
        "slug": slug,
        "problem_id": live["id"],
        "candidate_sha256": receipt["candidate_sha256"],
        "verifier_sha256": verifier_hash,
        "score_local": receipt["score"],
        "leader_score": receipt["leader_score"],
        "mode": mode,
    })
    try:
        if mode == "inline":
            request_body = {"problem_id": live["id"], "solution": candidate}
        else:
            blob_key = upload_large(base, token, payload)
            request_body = {"problem_id": live["id"], "solution_blob_key": blob_key}
        response = http_json(
            base,
            "POST",
            "/api/solutions",
            body=request_body,
            token=token,
            timeout=300,
        )
    except HttpCampaignError as exc:
        append_event(state_dir, "submission_rejected", {
            "slug": slug,
            "problem_id": live["id"],
            "candidate_sha256": receipt["candidate_sha256"],
            "verifier_sha256": verifier_hash,
            "score_local": receipt["score"],
            "mode": mode,
            "attempt_sequence": attempt["sequence"],
            "http_status": exc.status,
            "endpoint": exc.path,
            "reason": exc.response_body[:2000],
        })
        raise
    except CampaignError as exc:
        append_event(state_dir, "submission_failed", {
            "slug": slug,
            "problem_id": live["id"],
            "candidate_sha256": receipt["candidate_sha256"],
            "verifier_sha256": verifier_hash,
            "score_local": receipt["score"],
            "mode": mode,
            "attempt_sequence": attempt["sequence"],
            "reason": str(exc)[:2000],
        })
        raise
    append_event(state_dir, "submit", {
        "slug": slug,
        "problem_id": live["id"],
        "candidate_sha256": receipt["candidate_sha256"],
        "verifier_sha256": verifier_hash,
        "score_local": receipt["score"],
        "mode": mode,
        "attempt_sequence": attempt["sequence"],
        "submission_id": response.get("id") if isinstance(response, dict) else None,
    })
    return {"mode": mode, "receipt": receipt, "response": response}


def record_rejection(
    state_dir: Path,
    slug: str,
    candidate_path: Path,
    *,
    http_status: int,
    reason: str,
) -> dict[str, Any]:
    if not 400 <= http_status <= 599:
        raise CampaignError("recorded HTTP status must be between 400 and 599")
    reason = reason.strip()
    if not reason:
        raise CampaignError("recorded rejection reason must not be empty")
    _candidate, candidate_bytes, _artifact_hash = load_candidate(candidate_path)
    candidate_hash = sha256_bytes(candidate_bytes)
    verified = next((
        event for event in reversed(read_events(state_dir))
        if event.get("type") == "verify"
        and event.get("payload", {}).get("slug") == slug
        and event.get("payload", {}).get("candidate_sha256") == candidate_hash
    ), None)
    if verified is None:
        raise CampaignError("cannot record rejection without a matching verified candidate event")
    payload = verified["payload"]
    if not payload.get("clears_first_place_gate"):
        raise CampaignError("cannot record rejection for a candidate that did not clear the gate")
    return append_event(state_dir, "submission_rejected", {
        "slug": slug,
        "candidate_sha256": candidate_hash,
        "verifier_sha256": payload["verifier_sha256"],
        "score_local": payload["score"],
        "http_status": http_status,
        "reason": reason[:2000],
        "source": "operator_recorded_after_failed_attempt",
    })


def print_status(latest: dict[str, Any]) -> None:
    problems = latest["problems"]
    firsts = sum(1 for problem in problems.values() if problem.get("our_rank") == 1)
    print(f"snapshot={latest['generated_at']} agent={latest['agent_name']} first_places={firsts}/{len(problems)}")
    for slug, problem in problems.items():
        leader = problem.get("leader") or {}
        ours = problem.get("our_entry") or {}
        print("\t".join([
            slug,
            str(problem.get("scoring")),
            f"leader={agent_of(leader)}:{score_of(leader)}",
            f"ours={problem.get('our_rank') or '-'}:{score_of(ours) if ours else '-'}",
            f"gate={problem.get('minImprovement')}",
            f"verifier={problem.get('verifier_sha256', '')[:12]}",
        ]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Filesystem-first EinsteinArena campaign controller")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--agent", default=None)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--timeout", type=int, default=300)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build-sandbox")
    sub.add_parser("snapshot")
    sub.add_parser("status")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("slug")
    verify_parser.add_argument("candidate", type=Path)
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("slug")
    submit_parser.add_argument("candidate", type=Path)
    submit_parser.add_argument("--confirm-domain-valid", action="store_true")
    submit_parser.add_argument("--confirm-submit", action="store_true")
    rejection_parser = sub.add_parser("record-rejection")
    rejection_parser.add_argument("slug")
    rejection_parser.add_argument("candidate", type=Path)
    rejection_parser.add_argument("--http-status", type=int, required=True)
    rejection_parser.add_argument("--reason", required=True)
    rejection_parser.add_argument("--confirm-record", action="store_true")
    check_parser = sub.add_parser("check")
    check_parser.add_argument("submission_id", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-sandbox":
            subprocess.run([
                "docker", "build", "--platform", "linux/arm64", "--load",
                "-f", str(ROOT / "Dockerfile.verifier"), "-t", args.image, str(ROOT),
            ], check=True)
            print(json.dumps({"ok": True, "image": args.image}))
        elif args.command == "snapshot":
            agent = args.agent or load_credentials()[1]
            result = snapshot(args.base_url, args.state_dir, agent)
            print_status(result)
        elif args.command == "status":
            read_events(args.state_dir)
            print_status(load_latest(args.state_dir))
        elif args.command == "verify":
            receipt = verify(args.state_dir, args.slug, args.candidate, image=args.image, timeout=args.timeout)
            print(json.dumps(receipt, indent=2, sort_keys=True))
        elif args.command == "submit":
            if not args.confirm_domain_valid or not args.confirm_submit:
                raise CampaignError(
                    "submit requires --confirm-domain-valid and --confirm-submit"
                )
            result = submit(
                args.base_url,
                args.state_dir,
                args.slug,
                args.candidate,
                image=args.image,
                timeout=args.timeout,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        elif args.command == "record-rejection":
            if not args.confirm_record:
                raise CampaignError("record-rejection requires --confirm-record")
            event = record_rejection(
                args.state_dir,
                args.slug,
                args.candidate,
                http_status=args.http_status,
                reason=args.reason,
            )
            print(json.dumps(event, indent=2, sort_keys=True))
        elif args.command == "check":
            response = http_json(args.base_url, "GET", f"/api/solutions/{args.submission_id}")
            append_event(args.state_dir, "submission_check", {
                "submission_id": args.submission_id,
                "status": response.get("status") if isinstance(response, dict) else None,
                "score": response.get("score") if isinstance(response, dict) else None,
            })
            print(json.dumps(response, indent=2, sort_keys=True))
        return 0
    except (CampaignError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
