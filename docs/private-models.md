# Private process inputs — never committed

This repository has no redistribution right for the TSMC/vendor PDK. Users must
obtain their own authorized local copy. There is no download link, license bypass,
credential request, or embedded library.

## Required local view set

A private directory outside this checkout must contain exactly the matching views
under these aliases. Scripts copy only these five files into an **external private**
run directory and hash them before analysis:

| Alias | Usage | Recorded SHA-256 |
| --- | --- | --- |
| slow.lib | SS, 0.9 V, 125°C | c6dc5053db819a3deff380003ac0d0eae695c22b19e5461563e41fe9fc2b41ca |
| typical.lib | TT, 1.0 V, 25°C | f79391e02ee6a159c42428d7276ce9bdaea063090a153b6a9a650cff0f7146e5 |
| fast.lib | FF, 1.1 V, −40°C | 8ee6e41473acd3e875b8d1473185bedc5d78564a4d56001a8af8f04658f75b82 |
| tech.lef | technology/site/layer views, coarse early-placement RC only | SHA recorded per run |
| cells.lef | corresponding standard-cell abstracts | SHA recorded per run |

Exact historical LEF hashes are also provided in
[model_fingerprints.json](../flow/tsmc90/model_fingerprints.json).
File renaming does not make a different process/corner compatible.
Changed Liberty hashes fail closed. A different model requires a separately
reviewed experiment adapter and a new labeled result, not editing the hash to
pretend it reproduced this run.

The scripts generate the actual Tcl/SDC and Yosys input and save tool executable
hashes. Build the recorded tool revisions using their official instructions:
[OpenROAD](https://openroad.readthedocs.io/en/latest/user/Build.html),
[Yosys](https://github.com/YosysHQ/yosys).
We do not distribute those binaries or claim host-independent bit-for-bit numerical determinism.

flow/tsmc90/excluded_cells.json is experiment configuration: cell identifiers
excluded from ABC mapping to avoid unsupported/multi-output mappings. It contains
no Liberty timing tables, geometry, or models and is not a substitute for a library.
input_drive.py verifies logical signatures before experimental cell sizing.

## Scope and assumptions

The single-lane screen uses:
1 ns period; setup/hold uncertainty .150/.030 ns;
input max/min .100/.050 ns; output max/min .100/−.050 ns;
input transition .100 ns; output load .010 pF;
input/global activity .1 and duty .5.
These are **fixed study assumptions**, not SRAM characterization data.

The full-core diagnostic intentionally does not invent external IO delays.
Its register/core subset results must not be presented as unconstrained-endpoint
coverage PASS or full-chip hold/setup PASS.

Placement uses M2 signal/M3 clock coarse LEF RC. That is not a qualified extraction
deck. No matching final GDS, RCX tables, SRAM macro views, LVS/DRC signoff decks or
EM/IR evidence is supplied. Those items remain BLOCKED/UNKNOWN.

## Publication boundary

Allowed: original RTL, generators, testbenches, local-path configuration interface,
hash fingerprints, numerical summaries, original functional logs.

Not published: Liberty, LEF, GDS, SPEF, SDF, ODB/DEF, SPICE/CDL, vendor Verilog/SRAM
models, binaries, foundry manuals, mapped technology netlists, raw vendor-derived
implementation bundles or credentials.

.gitignore reduces accidental staging; tools/check_public_tree.py is an additional
deny-list gate, not legal advice or a license checker. Before publication review
the complete tracked-file list; never force-add private outputs.
