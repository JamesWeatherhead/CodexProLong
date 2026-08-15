#!/usr/bin/env python3
"""Create an exhaustive, append-only snapshot of EinsteinArena's public corpus.

Only GET requests are issued.  Every HTTP response is preserved as a gzipped,
content-addressed raw object, while normalized records make constructions and
discussion content convenient to consume without loading a whole endpoint
page.  A coverage report records both what was captured and the limits of the
public API.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BASE = "https://einsteinarena.com"
ROOT = Path(__file__).resolve().parent
PAGE_SIZE = 100
STATIC_PATHS = ("/skill.md", "/heartbeat.md", "/changelog.md", "/")


class CrawlError(RuntimeError):
    """Raised when a required public endpoint cannot be archived."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n")


def gzip_bytes(payload: bytes) -> bytes:
    # mtime=0 makes the compressed object reproducible across snapshots.
    import io

    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", compresslevel=6, mtime=0) as handle:
        handle.write(payload)
    return output.getvalue()


class Archiver:
    def __init__(self, root: Path, base: str, delay: float) -> None:
        self.root = root
        self.base = base.rstrip("/")
        self.delay = delay
        self.entries: list[dict[str, Any]] = []
        self.last_request_at = 0.0

    def _store_object(self, payload: bytes, suffix: str = "body") -> dict[str, Any]:
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path("objects") / "sha256" / digest[:2] / f"{digest}.{suffix}.gz"
        target = self.root / relative
        if not target.exists():
            atomic_bytes(target, gzip_bytes(payload))
        return {
            "sha256": digest,
            "bytes": len(payload),
            "object": str(relative),
        }

    def store_record(self, kind: str, identifier: str, value: object) -> dict[str, Any]:
        payload = canonical_json(value)
        stored = self._store_object(payload, suffix="json")
        return {"kind": kind, "id": identifier, **stored}

    def fetch(
        self,
        route: str,
        *,
        params: dict[str, object] | None = None,
        allow_statuses: set[int] | None = None,
        expect_json: bool = True,
    ) -> tuple[int, Any | bytes, dict[str, Any]]:
        url = self.base + route
        if params:
            url += "?" + urllib.parse.urlencode(params)
        allowed = allow_statuses or {200}
        retries = 0
        while True:
            wait = self.delay - (time.monotonic() - self.last_request_at)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json,text/markdown,text/html;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "identity",
                    "User-Agent": "CodexProLong-public-corpus/1.0 (+research snapshot)",
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    status = int(response.status)
                    body = response.read()
                    headers = dict(response.headers.items())
            except urllib.error.HTTPError as exc:
                status = int(exc.code)
                body = exc.read()
                headers = dict(exc.headers.items()) if exc.headers else {}
            except (TimeoutError, urllib.error.URLError) as exc:
                if retries >= 5:
                    raise CrawlError(f"GET {url} failed after retries: {exc}") from exc
                time.sleep(min(30.0, 2.0**retries))
                retries += 1
                continue
            self.last_request_at = time.monotonic()
            if status == 429 or 500 <= status < 600:
                if retries >= 5:
                    raise CrawlError(f"GET {url} repeatedly returned HTTP {status}")
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
                try:
                    pause = float(retry_after) if retry_after else min(30.0, 2.0**retries)
                except ValueError:
                    pause = min(30.0, 2.0**retries)
                time.sleep(max(1.0, pause))
                retries += 1
                continue
            stored = self._store_object(body)
            entry = {
                "sequence": len(self.entries) + 1,
                "fetched_at": datetime.now(UTC).isoformat(),
                "method": "GET",
                "url": url,
                "status": status,
                "content_type": headers.get("Content-Type") or headers.get("content-type"),
                "etag": headers.get("ETag") or headers.get("etag"),
                "last_modified": headers.get("Last-Modified") or headers.get("last-modified"),
                **stored,
            }
            self.entries.append(entry)
            if status not in allowed:
                preview = body[:200].decode("utf-8", errors="replace")
                raise CrawlError(f"GET {url} returned HTTP {status}: {preview}")
            if not expect_json or status != 200:
                return status, body, entry
            try:
                return status, json.loads(body), entry
            except json.JSONDecodeError as exc:
                raise CrawlError(f"GET {url} did not return JSON") from exc


def paginated(
    archive: Archiver,
    route: str,
    *,
    base_params: dict[str, object] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    offset = 0
    for _ in range(10_000):
        params = dict(base_params or {})
        params.update({"limit": PAGE_SIZE, "offset": offset})
        _, value, entry = archive.fetch(route, params=params)
        if not isinstance(value, list):
            raise CrawlError(f"paginated endpoint {route} returned a non-list")
        pages.append(entry)
        rows.extend(value)
        if len(value) < PAGE_SIZE:
            return rows, pages
        offset += len(value)
    raise CrawlError(f"pagination safety limit reached for {route}")


def problem_slug_from_thread(thread: dict[str, Any], id_to_slug: dict[int, str]) -> str | None:
    raw = thread.get("problemId")
    try:
        return id_to_slug.get(int(raw))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--request-delay", type=float, default=0.05)
    parser.add_argument("--thread-tail-probe", type=int, default=100)
    parser.add_argument("--solution-tail-probe", type=int, default=100)
    parser.add_argument(
        "--skip-solution-status-scan",
        action="store_true",
        help="Skip the public /api/solutions/{id} retained-row audit.",
    )
    args = parser.parse_args()
    if args.request_delay < 0:
        raise CrawlError("request delay cannot be negative")

    started = datetime.now(UTC)
    snapshot_name = started.strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = args.root / "snapshots" / snapshot_name
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    archive = Archiver(args.root, args.base_url, args.request_delay)

    static_refs: dict[str, dict[str, Any]] = {}
    for route in STATIC_PATHS:
        _, _, entry = archive.fetch(route, expect_json=False)
        static_refs[route] = entry

    _, activity, activity_ref = archive.fetch("/api/activity")
    _, listed, problems_ref = archive.fetch("/api/problems")
    if not isinstance(listed, list):
        raise CrawlError("/api/problems returned a non-list")

    problems: dict[str, dict[str, Any]] = {}
    discovered_threads: set[int] = set()
    best_solution_rows: dict[int, dict[str, Any]] = {}
    id_to_slug: dict[int, str] = {}

    for listed_problem in sorted(listed, key=lambda row: int(row["id"])):
        slug = str(listed_problem["slug"])
        problem_id = int(listed_problem["id"])
        id_to_slug[problem_id] = slug
        _, detail, detail_ref = archive.fetch(f"/api/problems/{urllib.parse.quote(slug)}")
        _, leaderboard, leaderboard_ref = archive.fetch(
            "/api/leaderboard", params={"problem_id": problem_id, "limit": PAGE_SIZE}
        )
        _, solutions, solutions_ref = archive.fetch(
            "/api/solutions/best", params={"problem_id": problem_id, "limit": PAGE_SIZE}
        )
        if not isinstance(solutions, list) or not isinstance(leaderboard, list):
            raise CrawlError(f"invalid leaderboard or solutions response for {slug}")
        solution_records = []
        for solution in solutions:
            solution_id = int(solution["id"])
            best_solution_rows[solution_id] = solution
            solution_records.append(archive.store_record("solution", str(solution_id), solution))

        thread_lists: dict[str, Any] = {}
        for ordering in ("recent", "top"):
            rows, pages = paginated(
                archive,
                f"/api/problems/{urllib.parse.quote(slug)}/threads",
                base_params={"sort": ordering},
            )
            ids = [int(row["id"]) for row in rows]
            discovered_threads.update(ids)
            thread_lists[ordering] = {"ids": ids, "pages": pages}

        verifier = str(detail.get("verifier", ""))
        problems[slug] = {
            "id": problem_id,
            "listed": listed_problem,
            "detail_ref": detail_ref,
            "detail_record": archive.store_record("problem", slug, detail),
            "verifier_sha256": hashlib.sha256(verifier.encode("utf-8")).hexdigest(),
            "leaderboard": leaderboard,
            "leaderboard_ref": leaderboard_ref,
            "solution_count": len(solutions),
            "solution_page_ref": solutions_ref,
            "solutions": solution_records,
            "thread_lists": thread_lists,
        }

    # Enumerate the small integer thread namespace as a completeness audit.
    max_thread = max(discovered_threads, default=0)
    consecutive_tail_misses = 0
    last_thread_probed = 0
    thread_details: dict[int, dict[str, Any]] = {}
    thread_scan_limit = max_thread + max(0, args.thread_tail_probe)
    for thread_id in range(1, thread_scan_limit + 1):
        last_thread_probed = thread_id
        status, value, ref = archive.fetch(
            f"/api/threads/{thread_id}", allow_statuses={200, 404}
        )
        if status == 200:
            if not isinstance(value, dict):
                raise CrawlError(f"thread {thread_id} returned a non-object")
            thread_details[thread_id] = value
            discovered_threads.add(thread_id)
            consecutive_tail_misses = 0
        elif thread_id > max_thread:
            consecutive_tail_misses += 1
            if consecutive_tail_misses >= args.thread_tail_probe:
                break

    threads: dict[str, dict[str, Any]] = {}
    reply_rows: dict[int, dict[str, Any]] = {}
    for thread_id in sorted(discovered_threads):
        detail = thread_details.get(thread_id)
        if detail is None:
            _, detail, _ = archive.fetch(f"/api/threads/{thread_id}")
        replies, reply_pages = paginated(archive, f"/api/threads/{thread_id}/replies")
        for reply in replies:
            reply_rows[int(reply["id"])] = reply
        slug = problem_slug_from_thread(detail, id_to_slug)
        threads[str(thread_id)] = {
            "problem_slug": slug,
            "detail": archive.store_record("thread", str(thread_id), detail),
            "reply_count": len(replies),
            "reply_pages": reply_pages,
            "replies": [
                archive.store_record("reply", str(reply["id"]), reply) for reply in replies
            ],
        }

    solution_statuses: dict[str, dict[str, Any]] = {}
    solution_scan = {
        "enabled": not args.skip_solution_status_scan,
        "max_observed_solution_id": max(best_solution_rows, default=0),
        "last_probed_id": 0,
        "retained_status_rows": 0,
    }
    if not args.skip_solution_status_scan and best_solution_rows:
        max_solution = max(best_solution_rows)
        scan_limit = max_solution + max(0, args.solution_tail_probe)
        tail_misses = 0
        for solution_id in range(1, scan_limit + 1):
            status, value, ref = archive.fetch(
                f"/api/solutions/{solution_id}", allow_statuses={200, 404}
            )
            solution_scan["last_probed_id"] = solution_id
            if status == 200:
                solution_statuses[str(solution_id)] = {
                    "record": archive.store_record("solution_status", str(solution_id), value),
                    "response_ref": ref,
                }
                tail_misses = 0
            elif solution_id > max_solution:
                tail_misses += 1
                if tail_misses >= args.solution_tail_probe:
                    break
        solution_scan["retained_status_rows"] = len(solution_statuses)

    # Build a useful agent index from every public appearance; no profile API exists.
    agent_stats: dict[str, Counter[str]] = defaultdict(Counter)
    for record in problems.values():
        for row in record["leaderboard"]:
            agent_stats[str(row["agentName"])]["leaderboard_rows"] += 1
    for row in best_solution_rows.values():
        agent_stats[str(row["agentName"])]["solution_rows"] += 1
    for thread in thread_details.values():
        agent_stats[str(thread["agentName"])]["threads"] += 1
    for reply in reply_rows.values():
        agent_stats[str(reply["agentName"])]["replies"] += 1
    if isinstance(activity, list):
        for row in activity:
            name = row.get("agentName")
            if name:
                agent_stats[str(name)]["recent_activity_rows"] += 1

    finished = datetime.now(UTC)
    coverage = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
        "mode": "public_get_only",
        "problem_count": len(problems),
        "problem_ids": sorted(id_to_slug),
        "thread_count": len(threads),
        "reply_count": len(reply_rows),
        "best_solution_count": len(best_solution_rows),
        "agent_name_count": len(agent_stats),
        "http_response_count": len(archive.entries),
        "http_status_counts": dict(sorted(Counter(e["status"] for e in archive.entries).items())),
        "solution_status_scan": solution_scan,
        "thread_scan": {
            "max_listed_id": max_thread,
            "last_probed_id": last_thread_probed,
            "tail_probe": args.thread_tail_probe,
        },
        "public_api_limits": [
            "The best-solutions endpoint is capped at 100 rows and has no offset parameter.",
            "Only currently retained, evaluated constructions are exposed with solution data.",
            "Pending, rejected, deleted, pruned, hidden, and private records are not public corpus data.",
            "There is no public agent-profile endpoint; agents.json is derived from public appearances.",
            "Search results are truncated derivatives of the fully captured threads/replies and were not used for enumeration.",
        ],
    }

    manifest = {
        "schema_version": 1,
        "base_url": args.base_url,
        "snapshot": snapshot_name,
        "static": static_refs,
        "activity_ref": activity_ref,
        "problems_ref": problems_ref,
        "problems": problems,
        "threads": threads,
        "solution_statuses": solution_statuses,
        "agents": {name: dict(sorted(counts.items())) for name, counts in sorted(agent_stats.items())},
        "coverage": coverage,
        "responses": archive.entries,
    }
    atomic_json(snapshot_dir / "manifest.json", manifest)
    atomic_json(snapshot_dir / "coverage.json", coverage)
    atomic_json(snapshot_dir / "agents.json", manifest["agents"])

    latest = args.root / "latest.json"
    atomic_json(
        latest,
        {
            "snapshot": snapshot_name,
            "manifest": str((snapshot_dir / "manifest.json").relative_to(args.root)),
            "coverage": str((snapshot_dir / "coverage.json").relative_to(args.root)),
            "manifest_sha256": hashlib.sha256(
                (snapshot_dir / "manifest.json").read_bytes()
            ).hexdigest(),
            "completed_at": finished.isoformat(),
        },
    )
    print(json.dumps(coverage, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
