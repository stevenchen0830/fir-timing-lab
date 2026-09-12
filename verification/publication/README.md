# Fresh publication verification — 2026-09-12

Executed from the new fir-timing-lab source directory, not inferred from old logs.

- Full deep32 one-hot-credit candidate: **134 frames, 6,331,544 component checks, 0 errors**.
- Verilator 5.050: compilation173.826s, simulation280.545s on this host.
- Python reference,31 historical hashes, buffer tests,6000-cycle MAC,6200-cycle
  one-hot credit and injected-corruption negative control all passed.
- Generated RTL top and testbench hashes match the archived corresponding candidate.
- No TSMC model is used by these functional tests.

Only functional logs/JSONs are included here. Simulator binaries and compiled
C++ outputs are excluded. Absolute runtime paths are retained for provenance.
The full-frame test ran before the publication runner's final snapshot-function
extraction; the generator and testbench contents remain unchanged. The standalone
RTL-generation command was tested after refactoring; CI exercises that final entry point.

manifest.sha256 is relative to this directory. Validate it with:
```bash
python3 tools/verify_publication.py
```

This is functional reproducibility evidence, not timing or physical signoff.

