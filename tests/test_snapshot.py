from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "snapshot_campaign.py"
SPEC = importlib.util.spec_from_file_location("snapshot_campaign", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SnapshotTests(unittest.TestCase):
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
            },
        }
        result = MODULE.public_frontier(latest)
        self.assertEqual(result["platform_first_places"], 3)
        self.assertEqual(result["domain_valid_first_places"], 1)
        numerical = next(
            row for row in result["problems"] if row["slug"] == "prime-number-theorem"
        )
        self.assertEqual(numerical["integrity"], "numerical-certificate")
        blocked = next(row for row in result["problems"] if row["slug"] == "kissing-number-d12")
        self.assertEqual(blocked["integrity"], "domain-valid-blocked")
        self.assertEqual(blocked["verified_blocked"]["score"], 0.0)

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


if __name__ == "__main__":
    unittest.main()
