# Verification: commands, assertions and evidence

## What is actually tested

| Layer | Test | Acceptance / limitation |
| --- | --- | --- |
| Math | verification/reference_model.py | 117 finite architecture crosschecks; not an unbounded proof |
| Arithmetic | test_mac.py | 6000 cycles; independent integer golden; randomized advance/valid, max/zero pixels, disabled-tap X, 5 resets |
| Credit | test_credit.py | 6200 cycles; independent ordered transaction scoreboard, long output stall/fill, reset, drain |
| Negative control | test_credit.py --onehot --negative | injected zero one-hot state must trigger CREDIT_ONEHOT_CORRUPTION and nonzero simulator exit |
| Complete FIR | run_frames.py --suite full | 134 frames, all25 odd kernels, width24/27/1440 and baseline sizes, random pressure, runtime resets |
| Boundary | striped_memory_model.svh + RTL assertions | nominal generated-clock period/duty, command windows, no stale reset transaction, no sustained-output bubble |
| Evidence | verify_results.py | 31 archived file hashes and recorded statuses; NOT rerunning STA |

Full-frame Verilator is two-state. It does not prove X propagation safety; the
separate Icarus arithmetic/credit tests retain four-state comparisons.
Coverage counters and directed checks are not code/branch/toggle coverage.

## Minimal unit reproduction

```bash
python3 experiments/fir_core_opt/test_mac.py --variant deep32 --latency 32 \
  --out "$HOME/fir-runs/mac32-001"
python3 experiments/fir_core_opt/test_credit.py --onehot \
  --out "$HOME/fir-runs/credit-unit-001"
python3 experiments/fir_core_opt/test_credit.py --onehot --negative \
  --out "$HOME/fir-runs/credit-negative-001"
```

Expected positive markers: MAC_GOLDEN_PASS / CREDIT_GOLDEN_PASS, runner exit0.
Expected negative: simulator exits nonzero with CREDIT_ONEHOT_CORRUPTION;
runner returns0 only after confirming this exact failure. Compilation failure or
timeout is not accepted as successful fault detection.

Example failures:
- VALID_ALIGNMENT: enable/valid pipeline is misaligned;
- MAC_MISMATCH: arithmetic width, coefficient alignment or disabled data leaked;
- CREDIT_DATA_ORDER: loss, duplication or output reordering;
- CREDIT_CAPACITY: reserved/stored accounting inconsistent;
- RESET_STALE_TRANSACTION: reset released stale work;
- BOUNDARY_COMMAND_SETUP/HOLD: nominal command phase contract violated.

Do not delete assertions, lower input coverage or relax constraints to turn a
failed test green. Preserve the failing seed, generated source and logs first.

## Complete-frame acceptance

Use the commands in reproduction.md. Expected full summary:
```json
{
  "status": "FRAME_FUNCTIONAL_PASS_NOT_STA",
  "frames": 134,
  "errors": 0,
  "physical_status": "NOT_RUN"
}
```

Each compile/frames command must also show pass=true, no timeout, and expected
output markers. Historical comparisons differ across microarchitectures because
latency changes the random-stimulus consumption schedule; all variants still
execute the same frame suite. Counts are not independently interchangeable across engines.

The delayed SRAM model uses 1.8 ns tCO. It is an original behavioral model, not
a redistributed TSMC macro and not a qualified min/max PVT interface budget.
A +SLOW_DATA option exists in the integrated runner to demonstrate timing-model
mismatch; its failure is diagnostic, never evidence of silicon timing signoff.

## What this new repository does NOT claim

No new UVM signoff, formal end-to-end proof, mapped-netlist equivalence proof, SDF
gate-level regression, physical CDC/RDC signoff, or real SRAM timing coverage has
been completed for these new candidates. Earlier ASAP7/v4 audits in the parent
project cannot be transplanted as proofs of the new multirate/deep32 RTL.

The testbench checks reset cancel/recovery, but asynchronous-reset recovery/removal
still requires correctly constrained implementation STA.

## Evidence provenance

experiments/fir_core_opt/results/ contains immutable historical RTL logs and
numerical EDA summaries. manifest.sha256 protects that snapshot. Runtime-specific
absolute paths in historical JSONs are provenance, not required installation paths.

The public repository deliberately omits vendor raw timing artifacts; screen_summary.json
contains reported metrics and hashes. Consequently:
- anyone can validate the archived public file integrity and rerun functional tests;
- only a user with matching authorized models can independently rerun the private screen;
- comparing hashes cannot establish that a missing private report was correct.

CI runs the library-free gate on push/PR and publishes its test output. A separate
manual workflow can run the full candidate regression. CI does not run a TSMC
physical flow and a green badge must not be interpreted as timing closure.

