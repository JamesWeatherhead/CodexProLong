# C3 precision/topology escape

This isolated lane audits free discretization length and global cell phase,
short convolution filters, public-solution directions, and finite sign-topology
transplants against the frozen C3 frontier. All acceptance is by literal
float64 `numpy.convolve` under verifier SHA-256
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.

`topology_transplant.py` locks explicitly crossed sign walls in a signed-square
continuation and optionally performs a full-coordinate release. It writes
atomic NumPy checkpoints plus an append-only event journal.
