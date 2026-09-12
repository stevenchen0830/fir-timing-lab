# IC Design walkthrough: what ran and what is still missing

This is an RTL-to-early-placement timing study with reproducible functional
verification. The following teaches the complete IC sequence **without implying
that the unexecuted downstream stages have passed**.

| Stage | Input → output | This project's implementation / judgement |
| --- | --- | --- |
| Specification | image/kernel/throughput requirements → contract | 4 pixels/beat, 10-bit RGBA, nonnegative symmetric weights sum128; validated sizes listed in architecture |
| Microarchitecture | contract → bank mapping / transaction model | coefficient rotation, row bypass, four stripes, related clock boundary, MAC/credit variants |
| RTL verification | generated RTL + math TB → logs/status | Python finite reference, four-state units, 134-frame full runs, negative tests |
| Synthesis | RTL + SS Liberty → mapped netlist/statistics | Yosys/ABC; bounded scripts, fixed1ns, explicit exclusions, structural buffering |
| Floorplan | netlist + LEF → floorplan.odb | single-lane fixed die/core; IO layer M3H/M2V; no SRAM macros placed |
| Placement | floorplan → placed.odb/def | density .45, seed42, legal placement; coarse estimated RC |
| CTS | placed data + generated-clock SDC → propagated clock tree | NOT performed for these new candidates; no measured post-CTS skew |
| Routing | CTS/ECO DB → GRT then DRT | NOT performed; candidates failed timing/PPA promotion gates |
| RCX | final route + qualified rule set → SPEF | BLOCKED: no qualified matching extraction flow supplied |
| STA/PPA | final data + all supported PVT/RC + activity → matrix | only zero-wire/coarse-placement probes exist; not final MMMC |
| Physical checks | final netlist/layout/decks → DRC/LVS/antenna/EM/IR | not complete; no tapeout claim |

## 1. Architecture first: throughput is not frequency

The new arithmetic uses the bound 1023×128+64<2^17. Narrowing is valid only under
the weight contract. The maximum49-tap operation still requires broad parallel
compute; deeper pipelines trade delay for more state, clock load and area.

Stalled deep32 uses32 enabled MAC cycles. Credit deep32 runs freely but buffers
completed output; observed system latency also includes frame startup, related
memory scheduling and FIFO waiting. A single universal cycle latency would be misleading.

## 2. Synthesis: mapping and ICG are evidence, not configuration labels

Recorded tools: Yosys0.68+ a5af9d690 and OpenROAD26Q3-1499 g46ab99414e.
This new runner maps sequential cells through dfflibmap and logic through ABC;
it does not run the earlier project's ORFS ICG experiment. Do not copy the old
“32/34 ICG” counts here. Establish cell counts from this run's stat.json and
netlist if making any new mapping claim.

Compare the same library, ABC constraints, register boundaries, load, activity and
mapping topology. The full hierarchical core mapping is not numerically comparable
to simply multiplying a flattened one-lane result by16.

## 3. Floorplan / placement: a controlled sensitivity test

The fixed die is1620×1620µm; core is1600×1600µm. Density .45 is a global-placement
setting, not a promise of fixed initial utilization across unequal netlist areas.
This controlled setup isolates part of the sensitivity to structural changes,
but can penalize high-area candidates.

Read placement legality and timing together. There is no routing congestion/DRC=0
claim in this new experiment. Coarse RC can reveal that the critical path has moved
to advance/enable or completion fanout, but cannot predict a certified final Fmax.

## 4. CTS and the slow-memory boundary

A generated clock must be derived from the same source with the actual edge
sequence and duty cycle. Command setup/hold and read capture must remain timed.
The RTL's /3 edge schedule is checked in functional simulation; post-CTS arrival,
skew, clock gating/pulse width, reset recovery/removal still need implementation evidence.

A gated/free-running or core/memory clock boundary can make min paths worse even
when setup improves. Never replace this analysis with asynchronous false paths.

## 5. GRT, DRT and RCX are different

GRT allocates approximate routing resources and estimates interconnect.
DRT assigns legal detailed shapes/vias and repairs geometric routing violations.
RCX extracts resistance/capacitance from the routed geometry using qualified rules.

A post-placement estimate is neither GRT nor DRT; even a repaired GRT database
is not final SPEF evidence. After any buffer/resize ECO, route/extract/recheck again.
The delivered scripts stop at early placement because the current candidates
failed promotion and the physical assets are not qualified.

## 6. STA / PPA acceptance matrix

For each supported mode/PVT/RC and every required path group, final acceptance
would require setup and hold WNS≥0, TNS=0, zero violating endpoints, no unexpected
unconstrained paths, clean slew/cap/fanout, valid reset/clock checks and guardband.
Separate executed failure from missing evidence (UNKNOWN/BLOCKED).

Current single-lane assumptions are fixed absolute budgets; reducing uncertainty
would change the model, not accelerate the circuit. Core-only STA leaves external
IO unqualified. Vectorless activity .1/duty .5 excludes realistic workload and
SRAM power, so power results are comparative estimates only.

## 7. Reproducibility and checkpoints

Every stage must link source hash, model hash, tool identity, exact command,
output view and result status. Runners save stages.json, logs and written databases;
no mtime backdating is used. Detailed commands and time/RSS limits are in reproduction.md.

There is no automatic "resume all the way to GDS" entry point in this repository.
The permitted next step is another measured architecture comparison. A final
physical candidate requires improved full-core timing/PPA and qualified matching
GDS/RC/SRAM/physical checks before long routing is justified.

