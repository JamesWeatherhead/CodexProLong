# Dependency and platform boundaries

## Replay and scanning

- CPython 3.11 through 3.13.
- Standard library only.
- Any POSIX, Windows, or macOS host with a case-sensitive or
  case-preserving filesystem.
- No network, accelerator, environment credential, or repository state is
  accessed.

## Numeric tests

- CPython 3.11 through 3.13.
- NumPy `>=2.0,<3`.
- SciPy `>=1.14,<2` (`scipy.signal.oaconvolve` and
  `scipy.optimize.minimize`).
- CPU float64. Tests use generated vectors of at most 383 cells and do not
  allocate a native-grid array.

The publication check was run on CPython 3.12.13, NumPy 2.5.2, SciPy 1.18.0,
and macOS 26.5.1 arm64.

## H100 preflight and plan

- Linux x86_64.
- CPython 3.12.
- NumPy 2.5.2.
- SciPy 1.18.0.
- PyTorch 2.13.0 built with CUDA support.
- One NVIDIA H100 with at least 80 GB reported device memory.

`h100_preflight.py` only validates versions, configs, CUDA visibility, model
name, and memory. It never starts optimization and never imports a verifier.
The phase plan assumes an omitted private acceptance adapter that is already
authorized and independently hash-pinned; this packet provides no such code
or byte payload.

Apple MPS was used only for the bounded local pilot. No cross-device bitwise
reproducibility is claimed. CPU float64 scoring is the numerical reference;
accelerator FFT/autograd values are proposal diagnostics only.
