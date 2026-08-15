# Bounded forced-bundle reference pilot

- Classification: `bounded_reference_pilot_not_frontier_coverage`.
- Best exact reference score: `0.7156018568597433`.
- Strict live gate: `0.9635981105820289`; gap `0.24799625372228562`.
- Multi-lag bundle branches per step: `8`.
- Frozen verifier SHA-256: `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
- Checkpoint SHA-256: `32f3e85f848da524de2c78de31062d2020c251272ef3e635eb4a4d541c76a5c3`.
- Input candidate arrays: none. Every member is regenerated from its motif seed.
- Reproduction: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python campaign/analysis/second_autocorrelation_forced_bundle_population/forced_bundle.py pilot --n 4095 --population 4 --steps 4 --branches 8 --separation 5 --ridge-loss 0.005 --seed 20260815 --run-dir campaign/analysis/second_autocorrelation_forced_bundle_population/runs/REPLAY`.
- Decision: tool validation only; do not verify, submit, post, or claim frontier coverage.
