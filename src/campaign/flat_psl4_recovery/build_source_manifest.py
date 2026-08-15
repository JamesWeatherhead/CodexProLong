#!/usr/bin/env python3
"""Build the frozen SHA-256 manifest for public GET-only recovery sources."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
FROZEN_AT = "2026-08-15T04:59:19Z"

METADATA = {
    "arquivo_signalslab_1779.json": {
        "url": "https://arquivo.pt/textsearch?versionHistory=signalslab.marstu.net%2F%3Fpage_id%3D1779&maxItems=50",
        "evidence": "Arquivo.pt exact target query: estimated_nr_results=0.",
    },
    "coxson_russo_2025_search.json": {
        "url": "https://books.google.com/books?jscmd=SearchWithinVolume2&q=1A133B4E3093EDD57E&vid=2s_BEQAAQBAJ",
        "evidence": "Google Books snippet for Table 4.3, including the N=69 and N=70 hexadecimal representatives.",
    },
    "leukhin_2017_full_sets_counts.pdf": {
        "url": "https://uzmu.phys.msu.ru/file/2017/6/1760902.pdf",
        "evidence": "Independent table of complete-class counts: N=69:248, N=70:72, N=71:115, N=72:107.",
    },
    "leukhin_2018_branch_bound.pdf": {
        "url": "https://nbpublish.com/library_get_pdf.php?id=25273",
        "evidence": "Describes the exhaustive branch-and-bound computation and points to the thematic results site; it does not print the complete classes.",
    },
    "nunn_coxson_2008.pdf": {
        "url": "https://www.norbertwiener.umd.edu/crowds/documents/best_known_binary.pdf",
        "evidence": "Table 1 prints the independent length-71 PSL-4 representative 63383AB6B452ED93FE.",
    },
    "potekhin_autoreferat_01007860659.pdf": {
        "url": "https://new-disser.ru/_avtoreferats/01007860659.pdf",
        "evidence": "Public dissertation abstract: reports complete optimal sets through N=80; states that the dissertation appendices contain examples, not the complete class dump.",
    },
    "potekhin_dissercat.html": {
        "url": "https://www.dissercat.com/content/sintez-i-analiz-optimalnykh-binarnykh-posledovatelnostei",
        "evidence": "184-page thesis metadata, contents, four appendices, OCR introduction, and public-abstract link.",
    },
    "potekhin_rsl_record_01007860659.html": {
        "url": "https://search.rsl.ru/ru/record/01007860659",
        "evidence": "RSL record and full-scan pathname; access notice limits the 184-page scan to RSL/virtual reading rooms.",
    },
    "pslrk_LowPslCodes_91ddd173.xml": {
        "url": "https://raw.githubusercontent.com/Gluttton/PslRK/91ddd173e221073f90086d7a0163bdedcc6b5e6b/Reports/LowPslCodes.xml",
        "evidence": "Pinned public sequence catalog; contains one length-70 PSL-4 row, id 25ecc4b1cf6c122a81.",
    },
    "pslrk_github_forks.json": {
        "url": "https://api.github.com/repos/Gluttton/PslRK/forks?per_page=100",
        "evidence": "Four public forks enumerated.",
    },
    "pslrk_github_issues.json": {
        "url": "https://api.github.com/repos/Gluttton/PslRK/issues?state=all&per_page=100",
        "evidence": "All public issues; no attachment or complete N=70 table.",
    },
    "pslrk_github_repo.json": {
        "url": "https://api.github.com/repos/Gluttton/PslRK",
        "evidence": "Repository metadata for the pinned bare mirror.",
    },
    "pslrk_gitlab_project.json": {
        "url": "https://gitlab.com/api/v4/projects/1142711",
        "evidence": "GitLab mirror metadata; no forks or additional branches.",
    },
    "pslrk_fork_buchankr_master.json": {
        "url": "https://api.github.com/repos/buchankr/PslRK/commits/master",
        "evidence": "Fork head e6b19abc33308ed6750867bc618044f1bcc575d1.",
    },
    "pslrk_fork_chiefstone_master.json": {
        "url": "https://api.github.com/repos/chiefstone/PslRK/commits/master",
        "evidence": "Fork head matches upstream 91ddd173e221073f90086d7a0163bdedcc6b5e6b.",
    },
    "pslrk_fork_kumaparmphdeit_master.json": {
        "url": "https://api.github.com/repos/kumaparmphdeit/PslRK/commits/master",
        "evidence": "Fork head matches upstream 91ddd173e221073f90086d7a0163bdedcc6b5e6b.",
    },
    "pslrk_fork_vkd0726_master.json": {
        "url": "https://api.github.com/repos/vkd0726/PslRK/commits/master",
        "evidence": "Fork head matches upstream 91ddd173e221073f90086d7a0163bdedcc6b5e6b.",
    },
    "seta_2014_search.json": {
        "url": "https://books.google.com/books?jscmd=SearchWithinVolume2&q=01C2FFD4AF33356596&vid=BYdxBQAAQBAJ",
        "evidence": "Zero-result exact-code query in the SETA 2014 volume; the chapter exposes examples/counts but no downloadable class table.",
    },
    "signalslab_binary_20140305.warc.gz": {
        "url": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2014-10/segments/1393999675992/warc/CC-MAIN-20140305060755-00099-ip-10-183-142-35.ec2.internal.warc.gz",
        "request_header": "Range: bytes=173331446-173340135",
        "evidence": "Common Crawl gzip member for the binary landing page; no result attachment URL.",
    },
    "signalslab_sitemap_20140409045140.html": {
        "url": "https://web.archive.org/web/20140409045140id_/http://signalslab.marstu.net/?page_id=1165",
        "evidence": "Wayback sitemap proving PSL-4 target page_id=1779 under the binary/minmax hierarchy.",
    },
}


def atomic_json(path: Path, value: object) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    actual = {path.name for path in SOURCES.iterdir() if path.is_file()}
    expected = set(METADATA)
    if actual != expected:
        raise RuntimeError(
            f"source set mismatch; missing={sorted(expected-actual)} extra={sorted(actual-expected)}"
        )

    artifacts = []
    for name in sorted(METADATA):
        path = SOURCES / name
        data = path.read_bytes()
        artifacts.append(
            {
                "path": str(path.relative_to(HERE)),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                **METADATA[name],
            }
        )
    manifest = {
        "frozen_at": FROZEN_AT,
        "policy": "All remote requests were GET-only; no accounts, posts, votes, submissions, purchases, or author contact.",
        "pslrk_bare_mirror": {
            "path": "cache/PslRK.git",
            "remote": "https://github.com/Gluttton/PslRK.git",
            "head": "91ddd173e221073f90086d7a0163bdedcc6b5e6b",
            "low_psl_codes_blob": "b370f908f5553a242b1bf4af794b1bc6a8d71e28",
            "fsck_unreachable_objects": 0,
        },
        "artifacts": artifacts,
    }
    atomic_json(HERE / "source_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
