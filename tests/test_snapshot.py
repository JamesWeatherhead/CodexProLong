from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "snapshot_campaign.py"
SPEC = importlib.util.spec_from_file_location("snapshot_campaign", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SnapshotTests(unittest.TestCase):
    def test_prolong_sources_are_explicit_and_private_state_is_forbidden(self) -> None:
        required = {
            "PROLONG_MEMORY.md",
            "prolong",
            "prolong_codex.py",
            "prolong_memory.py",
            "tests/test_prolong_codex.py",
            "tests/test_prolong_memory.py",
        }
        self.assertTrue(required.issubset(set(MODULE.ROOT_SOURCE_FILES)))
        for value in (
            "state/memory/trajectory.jsonl",
            "state/memory/head.json",
            "state/memory/sessions/x/session.json",
            "lane/turn-1.codex.jsonl",
            "lane/turn-1.stderr.jsonl",
        ):
            self.assertTrue(MODULE.is_private_memory_path(Path(value)))
        self.assertFalse(MODULE.is_private_memory_path(Path("state/events.jsonl")))

    def test_format_score(self) -> None:
        self.assertEqual(MODULE.format_score(None), "—")
        self.assertEqual(MODULE.format_score(0), "0")
        self.assertEqual(MODULE.format_score(1e-6), "1e-06")

    def test_disclosure_is_not_counted_as_domain_valid(self) -> None:
        latest = {
            "generated_at": "2026-08-15T00:00:00Z",
            "problems": {
                "tammes-problem": {
                    "title": "Tammes",
                    "scoring": "maximize",
                    "minImprovement": 1e-8,
                    "leader": {"agentName": "CodexProLong", "bestScore": 1.0, "rank": 1, "submissions": 1},
                    "our_entry": {"agentName": "CodexProLong", "bestScore": 1.0, "rank": 1, "submissions": 1},
                    "our_rank": 1,
                    "verifier_sha256": "a" * 64,
                },
                "valid": {
                    "title": "Valid",
                    "scoring": "minimize",
                    "minImprovement": 0,
                    "leader": {"agentName": "CodexProLong", "bestScore": 0.0, "rank": 1, "submissions": 1},
                    "our_entry": {"agentName": "CodexProLong", "bestScore": 0.0, "rank": 1, "submissions": 1},
                    "our_rank": 1,
                    "verifier_sha256": "b" * 64,
                },
                "prime-number-theorem": {
                    "title": "Prime Number Theorem",
                    "scoring": "maximize",
                    "minImprovement": 1e-6,
                    "leader": {"agentName": "CodexProLong", "bestScore": 0.99, "rank": 1, "submissions": 1},
                    "our_entry": {"agentName": "CodexProLong", "bestScore": 0.99, "rank": 1, "submissions": 1},
                    "our_rank": 1,
                    "verifier_sha256": "c" * 64,
                },
                "kissing-number-d12": {
                    "title": "Kissing d12",
                    "scoring": "minimize",
                    "minImprovement": 0,
                    "leader": {"agentName": "Other", "bestScore": 2.0, "rank": 1, "submissions": 1},
                    "our_entry": None,
                    "our_rank": None,
                    "verifier_sha256": MODULE.VERIFIED_BLOCKED["kissing-number-d12"]["verifier_sha256"],
                },
                "kissing-number-d11": {
                    "title": "Kissing d11",
                    "scoring": "minimize",
                    "minImprovement": 0,
                    "leader": {"agentName": "Other", "bestScore": 0.0, "rank": 1, "submissions": 1},
                    "our_entry": None,
                    "our_rank": None,
                    "verifier_sha256": MODULE.VERIFIED_BLOCKED["kissing-number-d11"]["verifier_sha256"],
                },
                "live-problem": {
                    "title": "Live",
                    "scoring": "maximize",
                    "minImprovement": 1e-8,
                    "leader": {"agentName": "Other", "bestScore": 1.0, "rank": 1, "submissions": 1},
                    "our_entry": None,
                    "our_rank": None,
                    "verifier_sha256": "d" * 64,
                },
            },
        }
        result = MODULE.public_frontier(latest)
        self.assertEqual(result["platform_first_places"], 3)
        self.assertEqual(result["domain_valid_first_places"], 1)
        numerical = next(
            row for row in result["problems"] if row["slug"] == "prime-number-theorem"
        )
        self.assertEqual(numerical["integrity"], "numerical-certificate")
        blocked = {
            row["slug"]: row
            for row in result["problems"]
            if row["integrity"] == "domain-valid-blocked"
        }
        self.assertEqual(set(blocked), {"kissing-number-d11", "kissing-number-d12"})
        self.assertEqual(
            blocked["kissing-number-d11"]["verified_blocked"]["reason_code"],
            "objective-floor-and-ordinal-ranking",
        )
        self.assertEqual(blocked["kissing-number-d12"]["verified_blocked"]["score"], 0.0)
        self.assertEqual(result["blocked_lanes"], 2)
        self.assertEqual(result["live_frontiers"], 1)
        self.assertEqual(result["rankable_benchmarks"], 4)
        status = MODULE.status_markdown(result)
        self.assertIn("score floor reached; later ties cannot rank #1", status)
        self.assertIn("score `0` verified; submissions disabled", status)
        self.assertIn("BLOCKED_LANES.md", status)
        self.assertEqual(
            MODULE.snapshot_summary(result, 123),
            "snapshot OK: 3/4 rankable lanes led, 1 domain-valid leaders, "
            "1 live frontiers, 2 blocked, 123 mirrored files",
        )

    def test_frontier_receipt_keeps_binary_artifact_suffix(self) -> None:
        source = Path("/tmp/campaign")
        c3 = MODULE.frontier_artifact_destination("third-autocorrelation-inequality", source)
        graphon = MODULE.frontier_artifact_destination("edges-vs-triangles", source)
        self.assertEqual(c3.suffix, ".npy")
        self.assertEqual(graphon.suffix, ".json")

    def test_portable_campaign_path_strips_host_prefix(self) -> None:
        source = Path("/Users/example/EinsteinArena/campaign")
        value = "/Users/example/EinsteinArena/campaign/c3_root/run/best.npy"
        self.assertEqual(MODULE.portable_campaign_path(value, source), "campaign/c3_root/run/best.npy")

    def test_portable_json_recurses_without_rewriting_urls(self) -> None:
        source = Path("/Users/example/EinsteinArena/campaign")
        value = {
            "path": "/Users/example/EinsteinArena/campaign/lane/receipt.json",
            "nested": [
                "/Users/example/EinsteinArena/campaign/cache/source.bin",
                "https://example.com/source.bin",
            ],
        }
        self.assertEqual(
            MODULE.portable_json(value, source),
            {
                "path": "campaign/lane/receipt.json",
                "nested": [
                    "campaign/cache/source.bin",
                    "https://example.com/source.bin",
                ],
            },
        )

    def test_portable_json_preserves_paperclip_virtual_paths(self) -> None:
        source = Path("/Users/example/EinsteinArena/campaign")
        value = {
            "paperclip": "/papers/arx_1701.00541/content.lines",
            "temporary": "/tmp/private-search/result.json",
        }
        self.assertEqual(
            MODULE.portable_json(value, source),
            {
                "paperclip": "/papers/arx_1701.00541/content.lines",
                "temporary": "result.json",
            },
        )

    def test_publication_allowlist_accepts_list_schema(self) -> None:
        entries = [{"path": "README.md", "sha256": "a" * 64, "bytes": 1}]
        self.assertEqual(MODULE.publication_allowlist({"include": entries}), entries)

    def test_publication_allowlist_normalizes_files_schema(self) -> None:
        self.assertEqual(
            MODULE.publication_allowlist(
                {"files": {"README.md": {"sha256": "b" * 64, "bytes": 2}}}
            ),
            [{"path": "README.md", "sha256": "b" * 64, "bytes": 2}],
        )

    def test_publication_allowlist_accepts_files_list_schema(self) -> None:
        entries = [
            {"path": "README.md", "sha256": "a" * 64, "bytes": 12},
            {"path": "receipt.json", "sha256": "b" * 64, "bytes": 34},
        ]
        self.assertEqual(MODULE.publication_allowlist({"files": entries}), entries)

    def test_publication_allowlist_normalizes_include_object_schema(self) -> None:
        publication = {
            "include": {
                "README.md": {"sha256": "a" * 64, "bytes": 12},
                "receipt.json": {"sha256": "b" * 64, "bytes": 34},
            }
        }
        self.assertEqual(
            MODULE.publication_allowlist(publication),
            [
                {"path": "README.md", "sha256": "a" * 64, "bytes": 12},
                {"path": "receipt.json", "sha256": "b" * 64, "bytes": 34},
            ],
        )

    def test_publication_allowlist_accepts_payload_schema(self) -> None:
        entries = [
            {"path": "README.md", "sha256": "a" * 64, "bytes": 12},
            {"path": "receipt.json", "sha256": "b" * 64, "bytes": 34},
        ]
        self.assertEqual(MODULE.publication_allowlist({"payload": entries}), entries)

    def test_relative_file_set_is_packet_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary) / "src" / "campaign" / "analysis" / "packet"
            (packet / "configs").mkdir(parents=True)
            (packet / "README.md").write_text("packet\n", encoding="utf-8")
            (packet / "configs" / "run.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(
                MODULE.relative_file_set(packet),
                {Path("README.md"), Path("configs/run.json")},
            )

    def test_exact_publication_paths_accepts_self_allowlisted_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            packet = source / "analysis" / "lane" / "public_packet"
            packet.mkdir(parents=True)
            readme = packet / "README.md"
            readme.write_text("portable\n", encoding="utf-8")
            manifest = packet / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "allowlist": [
                            {
                                "path": "README.md",
                                "sha256": MODULE.sha256(readme),
                                "bytes": readme.stat().st_size,
                            },
                            {"path": "manifest.json", "sha256": None, "bytes": None},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            relative = Path("analysis/lane/public_packet/manifest.json")
            self.assertEqual(
                MODULE.exact_publication_paths(source, relative, MODULE.sha256(manifest)),
                [
                    Path("analysis/lane/public_packet/README.md"),
                    Path("analysis/lane/public_packet/manifest.json"),
                ],
            )

    def test_exact_publication_paths_rejects_unlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            packet = source / "analysis" / "lane" / "public_packet"
            packet.mkdir(parents=True)
            manifest = packet / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "allowlist": [
                            {"path": "manifest.json", "sha256": None, "bytes": None}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (packet / "extra.txt").write_text("not allowlisted\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "file-set mismatch"):
                MODULE.exact_publication_paths(
                    source,
                    Path("analysis/lane/public_packet/manifest.json"),
                    MODULE.sha256(manifest),
                )

    def test_exact_publication_paths_accepts_detached_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            packet = source / "analysis" / "lane" / "publication"
            packet.mkdir(parents=True)
            readme = packet / "README.md"
            readme.write_text("portable\n", encoding="utf-8")
            manifest = packet / "PUBLICATION_MANIFEST.json"
            manifest.write_text(
                json.dumps(
                    {
                        "payload": [
                            {
                                "path": "README.md",
                                "sha256": MODULE.sha256(readme),
                                "bytes": readme.stat().st_size,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            relative = Path("analysis/lane/publication/PUBLICATION_MANIFEST.json")
            self.assertEqual(
                MODULE.exact_publication_paths(
                    source,
                    relative,
                    MODULE.sha256(manifest),
                    require_self_entry=False,
                ),
                [
                    Path("analysis/lane/publication/README.md"),
                    Path("analysis/lane/publication/PUBLICATION_MANIFEST.json"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
