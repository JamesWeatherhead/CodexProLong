# EinsteinArena public research corpus

`crawl.py` performs a GET-only, content-deduplicated crawl of every public
problem exposed by EinsteinArena. It captures full problem/verifier details,
100-row leaderboards, every construction exposed by the best-solutions API,
both complete thread orderings, full thread bodies, every paginated reply,
recent activity, and the site's three agent-facing Markdown documents.

Each raw HTTP response is preserved under `objects/sha256/` as a reproducible
gzip object keyed by the SHA-256 of the uncompressed response. Normalized
problem, solution, thread, reply, and solution-status records use the same
object store. Every run writes an immutable `snapshots/<UTC>/manifest.json`, a
machine-readable coverage audit, a derived public agent index, and an atomic
`latest.json` pointer.

Run the full crawl:

```sh
cd /Users/jacweath/EinsteinArena/campaign
../.venv/bin/python research_corpus/crawl.py
```

The crawler deliberately does not attempt to obtain hidden, deleted, pending,
rejected, or private data. The public API caps construction data at 100 rows
per problem and provides no offset; this limitation is recorded in every
coverage report. Search is not used for enumeration because it is a truncated,
rate-limited view of the thread and reply records captured directly.

After a crawl, verify every content hash, verifier hash, pagination set,
thread/reply relationship, and construction/status reference:

```sh
../.venv/bin/python research_corpus/audit.py
```

Build a self-contained SQLite database with the full construction JSON and an
FTS5 index over every thread and reply:

```sh
../.venv/bin/python research_corpus/build_sqlite.py
```

For a literal same-origin web crawl in addition to the research APIs, archive
all rendered problem/thread pages and every linked Next.js deployment asset,
then rebuild SQLite so those bytes are included in `web_pages`:

```sh
../.venv/bin/python research_corpus/crawl_pages.py
../.venv/bin/python research_corpus/build_sqlite.py
```

Example research query:

```sql
SELECT kind, record_id, problem_slug, agent_name,
       snippet(discussion_fts, 5, '[', ']', '…', 18)
FROM discussion_fts
WHERE discussion_fts MATCH 'equioscillation OR plateau';
```
