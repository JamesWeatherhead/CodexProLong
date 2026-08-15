# Thomson N=282 scar/dislocation escape

This lane tests genuine contact-graph changes directly on the frozen N=282
incumbent. It never reads, enumerates, or splits an N=72 source.

`search.py` derives the incumbent spherical Delaunay triangulation, enumerates
legal 2-2 flips, deduplicates labeled paths into exact graph-isomorphism
classes, realizes each flip across the Delaunay wall, and releases the points
with tangent-coordinate Coulomb L-BFGS. The frozen score is transcribed
literally from verifier SHA-256
`4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af`;
the verifier module is hashed but never dynamically executed.

The frozen run is `runs/20260815T_THOMSON_SCAR_V2`. It retains 49 deterministic
mutation paths spanning 44 exact graph classes, at two flip amplitudes. All 98
relaxed trials returned to the incumbent topology. The best score is float
dust at `37147.29441846225`, still `9.999857866205275e-7` above the strict gate
`37147.29441746226`.

The result closes only the enumerated local scar, glide, extension, and neutral
dipole paths under the stated deterministic relaxation. It is not a global
optimality proof.

Publication note: `best_candidate.json`, the frozen Arena snapshot, research
corpus, and all third-party source bodies are excluded. Original packet code
and prose are released under the packet-local MIT `LICENSE`.
