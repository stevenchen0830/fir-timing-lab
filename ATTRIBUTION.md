# Attribution and license boundary

Copyright 2026 Shuochen Shi. Original RTL and experiment infrastructure in this
repository are released under the MIT license in LICENSE.

The frozen FIR front end, Python reference, verification testbench and subsequent
microarchitecture experiments originate from the author's
[vfir-7nm-rtl2gds](https://github.com/stevenchen0830/vfir-7nm-rtl2gds) work.
This repository is a focused research snapshot, not an upstream EDA tool.

Tools used (not authored here and not relicensed by this repository):

- [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD), including OpenSTA;
- [OpenROAD-flow-scripts](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts), the local build environment used for the recorded tool binaries;
- [Yosys](https://github.com/YosysHQ/yosys) and ABC;
- [Icarus Verilog](https://github.com/steveicarus/iverilog);
- [Verilator](https://github.com/verilator/verilator);
- Python and GNU build/runtime tools.

TSMC/vendor PDKs and SRAM assets are NOT covered by this MIT license and are NOT
included. The private model interface only names required files and records hashes
and the experiment's mapping exclusions. A hash, a cell-name exclusion list, and
a numerical experiment result do not grant permission to use a vendor library.

No third-party person or organization is represented as a Git contributor merely
because their tools were used. Contributions are established by actual commits.

