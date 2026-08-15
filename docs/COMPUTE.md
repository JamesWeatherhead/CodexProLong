# Running the ten live frontiers on this Mac

The campaign machine is a 16-inch 2024 MacBook Pro (`Mac16,5`) with an Apple
M4 Max: 12 performance CPU cores, 4 efficiency CPU cores, a 40-core GPU,
48 GB of unified memory, 546 GB/s memory bandwidth, and Metal 4. The local
toolchain already includes Metal/MPS, Accelerate-backed NumPy and SciPy,
PyTorch with MPS, OR-Tools CP-SAT, HiGHS, CVXPY/SCS, PySAT, CaDiCaL,
CryptoMiniSat, and Kissat.

This inventory and the scheduling plan below were checked with Exa against
primary documentation: Apple’s
[machine specifications](https://support.apple.com/en-us/121554),
[Metal compute guide](https://developer.apple.com/documentation/metal/performing-calculations-on-a-gpu),
[Metal Performance Shaders](https://developer.apple.com/documentation/metalperformanceshaders),
[Accelerate](https://developer.apple.com/documentation/accelerate), and
[vDSP FFT](https://developer.apple.com/documentation/accelerate/fast-fourier-transforms),
plus the official [CP-SAT guide](https://developers.google.com/optimization/cp/cp_solver)
and [HiGHS parallel guidance](https://ergo-code.github.io/HiGHS/stable/parallel/).
Exa is the research/search tool here; Codex still writes, runs, and audits the
problem-specific programs.

## What “flat out” means

All ten lanes stay logically alive as resumable queues, but they do not run as
ten unconstrained processes. Apple silicon shares power and memory bandwidth
between CPU and GPU, so oversubscription can reduce completed, verified work.
The high-throughput schedule is:

1. Run one exclusive GPU class: either Flat Polynomials’ empirically validated
   two-stream Metal engine **or** one C2/C3 MPS/FFT campaign.
2. Alongside it, cap CPU work at roughly 10–12 runnable workers in total,
   leaving capacity for GPU dispatch, the OS, checkpointing, and fresh-process
   verifier replays.
3. Give Difference Bases up to 12 CP-SAT workers when CPU-exclusive and about
   8 when geometry shards share the machine. Keep HiGHS at 8 or fewer threads;
   prefer several isolated one-thread searches when independence matters.
4. Run geometry multistarts as single-threaded shards so nested BLAS workers do
   not multiply invisibly. Rotate the Edges-v-Triangles SDP work into its own
   CPU-heavy epochs.
5. Benchmark isolated CPU, isolated GPU, and combined throughput before fixing
   a long schedule. Utilization percentage is not the objective; verified
   candidates per hour is.

| Live frontier | Dominant local workload |
|---|---|
| Circle Packing | Single-thread contact-graph realizations and exact CPU replay |
| Circles in a Rectangle | Sharded topology/continuation solves on CPU |
| Difference Bases | CPU-exclusive CP-SAT and bitset verification |
| Edges vs Triangles | Rotating HiGHS/SDP and exact dynamic-programming blocks |
| Flat Polynomials | Two detached Metal enumeration streams plus CPU reference checks |
| Heilbronn Triangles | High-precision continuation, branch search, and interval checks on CPU |
| Min Distance Ratio | Contact-cell continuation and exact arithmetic on CPU |
| Second Autocorrelation | Exclusive MPS/FFT population epochs at native resolution |
| Third Autocorrelation | Exclusive MPS/FFT epigraph and topology-birth epochs |
| Thomson n=282 | Sharded Riemannian/Newton topology searches with high-precision replay |

Each long job writes immutable shards, resumable checkpoints, and independent
receipts. A killed process or expired Codex context should cost only the active
shard, never the research history.

## Preflight and safety gates

At the August 15 audit the Mac was at 5% battery, discharging in Low Power
mode, with 193 GiB of SSD space free, so no new maximum-load campaign was
launched. Before sustained work:

- connect its power adapter and select AC
  [High Power mode](https://support.apple.com/en-us/101613);
- use a hard, ventilated surface within Apple’s
  [safe operating temperatures](https://support.apple.com/en-us/102336);
- watch `memory_pressure`, `pmset -g therm`, Activity Monitor, and free disk;
- reduce concurrency on serious/critical thermal pressure or sustained memory
  pressure, and stop before checkpoint space becomes tight.

The aim is to hold the machine near its **safe sustained throughput**, not to
overheat it. Thermal throttling, swapping, or a corrupted receipt is slower
than a deliberately bounded queue.
