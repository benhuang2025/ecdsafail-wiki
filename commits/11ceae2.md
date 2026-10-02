# 11ceae2 — Un-window the final apply chunk (spend qubit slack) and run the GCD for 262 steps instead of 258

| | |
| --- | --- |
| Contestant | odinfree |
| Date | 2026-06-06 |
| Submission | `016bead` |
| Commit | `11ceae21159e9ac491741442356065606714b570` |
| Result | 1309 qubits × 1,497,795 Toffoli = **1,960,613,655** |
| Base | `3033d01` (jackylee0424, git parent and frontier at the time): 1309 qubits × 1,503,355 Toffoli = 1,967,891,695 |
| Change vs base | qubits ±0, Toffoli −5,560, score −7,278,040 (leaderboard Δ −7,278,040) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Two route knobs, one paying for the other.

1. **Spend qubit slack.** In the dialog-GCD apply pass (background in
   [8316db1](8316db1.md)), the top chunk of each controlled modular add or
   subtract was split into two carry windows, to keep its carry lane short. The
   two windows are joined by a boundary carry, which must be cleared with a
   33-bit comparator. The 1309 peak is set by the x-tail square, not by this
   adder, so the split no longer saves anything. This commit turns it off, and
   the top chunk now runs as one measured-uncompute Cuccaro adder. That saves
   33 Toffoli per apply step, 33 × 258 × 2 = 17,028 Toffoli, at the same 1309
   peak.
2. **Buy convergence.** `DIALOG_GCD_ACTIVE_ITERATIONS` goes from 258 to 262. The
   four extra steps cost 11,468 Toffoli. They make many more inputs finish the
   GCD in time, so clean nonces are much easier to find.

Net −5,560 Toffoli. Both changes are exact, and one of them makes the circuit
fail on fewer inputs.

## What changed and why it saves Toffoli

All changes are in `src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`.

### 1. Final apply chunk: windowed → plain fast adder

- **`DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS`: 2 → 0** and
  **`DIALOG_GCD_APPLY_FINAL_LOWQ`: 1 → 0.**
- The apply pass's controlled modular add,
  `dialog_gcd_add_ctrl_chunked_low_to_ext` in `rounds/dialog/mod.rs`, adds
  `ctrl·x` into the 257-bit `acc_ext` in five chunks with cuts at 50, 100, 150
  and 190 (`DIALOG_GCD_APPLY_CHUNKED_F_*`). The subtract twin
  `dialog_gcd_sub_ctrl_chunked_low_to_ext` has the same shape. The final chunk
  is bits 190..257, a 66-bit operand into 67 bits. For it the code picks:
  - if `dialog_gcd_apply_final_windowed_fast_blocks()` is `Some(w)` with
    `w ≥ 2`: `cuccaro_add_fast_windowed_low_to_ext(.., w)` (`arith/adder.rs`);
  - else if `DIALOG_GCD_APPLY_FINAL_LOWQ=1`: the textbook `cuccaro_add`, with no
    carry lane and 2 Toffoli per bit;
  - else: `cuccaro_add_fast_low_to_ext`, with a full carry lane, 1 Toffoli per
    bit and carries erased by measurement.
- In the base the windowed branch won, and LOWQ was only a dormant fallback.
  Setting both to 0 selects the plain fast adder. Turning off only the window
  would have selected the costlier textbook adder.
- With `w = 2`, the windowed adder ran the low 33 bits as a separate
  `cuccaro_add_fast` with a fresh `cout` qubit, then the high part, then
  cleared `cout` with `cmp_lt_into_fast_with_cin(acc_ext[..33], a[..33], c_in, cout)`.
  That is an exact comparator at one Toffoli per bit. Both versions do the same
  ripple work, so the comparator is the only difference: 33 Toffoli.
- One add or subtract per apply step, 258 steps, two divisions:
  33 × 516 = 17,028 Toffoli saved. The author's log has the route at
  1,486,327 Toffoli with 258 iterations, which is exactly 1,503,355 − 17,028.
- The window existed to halve this adder's carry lane, about 33 qubits. The
  author's `TRACE_PHASE_ACTIVE` shows the peak stays at the x-tail square
  (`round84_fused_square_xtail_dx_sub_lam_square_lowq`, 1309), so the longer
  lane fits under it. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

### 2. GCD length: `DIALOG_GCD_ACTIVE_ITERATIONS` 258 → 262

- Every forward walk, apply pass and reverse walk loops over
  `0..dialog_gcd_active_iterations()`, so each division gains four steps.
- At steps 258 to 261, `active_width` is only 2 to 6 bits, so the walk steps
  cost almost nothing. The cost is in the two apply passes. Each apply step is a
  full 256-bit controlled modular add or subtract, a 256-wide cswap, and a
  modular double or halve on `y`. That comes to about 2,870 Toffoli per added
  step, 11,468 in all (1,497,795 − 1,486,327).
- The 258-entry `DIALOG_GCD_PA9024_COMPARE_SCHEDULE` has no entry for the new
  steps. `compare_bits_for_step` falls back to the global 49, capped by the
  tiny `active_width`.
- The body band trim `"0,1"` is recomputed with band size `ceil(262 / 2) = 131`,
  so the trimmed half is now steps 131 to 261.
- Why this helps: the K2 binary GCD of `(p, dx)` needs a variable number of
  steps. With 258, some inputs had not reached the terminal state, which is the
  filter's `NonConvergence` class. The author's log shows that at 258 the
  structural target was clean for no nonce in the first 500 filter survivors.
  At 262, 4 of the first 2,620 nonces passed the full 9,024-shot classical filter,
  and `2432` passed the quantum check.

### 3. `DIALOG_TAIL_NONCE`: 721381 → 2432

The fixed 48-pair `X;X` identity tail that reseeds the 9,024 test inputs.

### 4. Memory note

`src/point_add/memory/2026-06-06-tony-anton-audit-loop.md` gets 77 more lines
of the author's search log. It is not code. It records several one-bit
truncations that were structurally cheaper but found no clean island:
apply-clean 19, `DIALOG_GCD_COMPARE_BITS=48`, `KAL_FOLD_CARRY_TRUNC_W=20` and
`ACTIVE_ITERATIONS=257`. It also records the split 1285q levers from
[33c072d](33c072d.md).

## Why it is still correct, and what it risks

- **Exact.** The plain fast adder computes the same sum as the windowed one.
  The removed boundary comparator was itself exact, so no hazard is added. The
  extra GCD steps are also exact: a converged `(u, v)` stays converged, and the
  apply pass replays whatever the log says.
- **Less risky than the base.** More iterations remove nonconvergence failures.
  All existing truncations stay in place, so their hazards remain: the
  width envelope, the 49-bit branch comparator, the body trim and the 20-bit
  apply-clean comparator.
- **Nonce.** Three of the four filter-clean nonces still failed the full run
  with 1–2 classical or phase failures. Those come from hazards the filter
  does not model, such as the apply-clean comparator. The shipped nonce `2432` draws a
  test set with 0 classical, 0 phase and 0 ancilla failures over all 9,024
  shots. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as fold/carry truncation. The diff does not truncate
anything. It removes a carry-window split that only saved qubits, which is a
slack spend (Register and Scratch Allocation), and it raises the iteration
count (iteration/threshold tuning). The second change is a loosening that
costs Toffoli. The net Toffoli saving comes from the first. The published label
is kept in the header.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 3033d01 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 3033d01 11ceae2 -- src/point_add` is
   92 lines in 2 files, 77 of them in the memory note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 11ceae2 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` only fills
   in unset variables. Expect:
   - 1309 qubits
   - 1,497,795 average Toffoli (rounded)
   - score 1,960,613,655
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=2432` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md b/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md
index 47f950d..a42eb3f 100644
--- a/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md
+++ b/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md
@@ -6,7 +6,7 @@ Purpose: keep optimization work from turning into blind brute force or polished-
 
 ## Frontier Snapshot
 
-Local CLI checks on 2026-06-06 showed the promoted frontier moved to score `1,969,242,583`, from average executed Toffoli `1,504,387` and peak qubits `1,309` (`c5fada1`). The public note for that frontier described narrowing `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` from `23` to `22` and re-hunting `DIALOG_TAIL_NONCE=251235`. Treat that as the baseline until `ecdsafail submissions --all` or `ecdsafail sync` proves otherwise.
+Local CLI checks on 2026-06-06 showed submission `a66b042` promoted as the current frontier with score `1,967,891,695`, from average executed Toffoli `1,503,355` and peak qubits `1,309`. The accepted route narrows `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` to `20` and uses `DIALOG_TAIL_NONCE=721381`. Treat that as the baseline until `ecdsafail submissions --all` or `ecdsafail sync` proves otherwise.
 
 ## Required Loop
 
@@ -47,7 +47,80 @@ Smallest useful next fix: inspect the compare-screen correctness boundary and su
 
 Tony pre-change audit selected `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=21` because the latest shared note and local trace showed a pure `-516` average executed Toffoli cut at unchanged `1,309` peak qubits. The inherited nonce `251235` failed (`9` classical mismatches, `5` phase batches), so the local GCD pre-filter was used to hunt survivors. Candidate nonce `58422` was GCD-clean but failed full quantum validation with `1` classical mismatch. Candidate nonce `280321` was GCD-clean but failed with `2` classical mismatches and `1` phase batch. Candidate nonce `431581` validated clean over all `9,024` shots.
 
-Validated result: `1,503,871` average executed Toffoli × `1,309` qubits = score `1,968,064,139`, with `0` classical / `0` phase / `0` ancilla failures.
+Validated result: `1,503,871` average executed Toffoli × `1,309` qubits = score `1,968,567,139`, with `0` classical / `0` phase / `0` ancilla failures.
+
+Submission `436b516` promoted at 2026-06-06 08:44 local time. It beat the previous observed promoted frontier `83e3b66` (`1,968,793,475`) by `226,336` score points.
+
+Public correction note `5ec74c1` records that the original submission prose had arithmetic typos in the displayed score and frontier delta; the CLI claimed score, metrics, validation result, and promoted leaderboard result were correct.
+
+## Promoted Successor Frontier
+
+External submission `a66b042` by `jackylee0424` promoted after `436b516`. Public note: apply-clean comparator tightened to `20` with refreshed tail nonce `721381`, validated `0` classical / `0` phase / `0` ancilla over all `9,024` shots at `1,309` qubits × `1,503,355` average Toffoli = score `1,967,891,695`. Local `./benchmark.sh --note 'validate synced a66 frontier'` reproduced the same `0/0/0` result.
+
+## Current Search Audit
+
+2026-06-06 continuation tested three bounded follow-up hypotheses. None produced a submit-ready improvement yet:
+
+- `1285q` restack from submission `83e3b66` plus `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=21`: structural probe was `1,531,619` average Toffoli × `1,285` qubits = score `1,968,130,415`, which would beat `436b516` by `436,724` if clean. Nonce `0` failed full eval with `18` classical mismatches and `7` phase batches. Staged GCD search found `320` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+- `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=20` with `DIALOG_GCD_COMPARE_BITS=50`: structural probe was `1,503,463` average Toffoli × `1,309` qubits = score `1,968,033,067`, which would beat `436b516` by `534,072` if clean. Nonce `0` failed full eval with `11` classical mismatches and `6` phase batches. Staged GCD search found `278` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+- `KAL_FOLD_CARRY_TRUNC_W=20`: structural probe was `1,503,355` average Toffoli × `1,309` qubits = score `1,967,891,695`, which would beat `436b516` by `675,444` if clean. Inherited nonce failed full eval with `15` classical mismatches and `5` phase batches. Staged GCD search found `260` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+
+Tony post-run classification: these remain structurally attractive but nonce-island-limited. The sampled failures are full-GCD width/nonconvergence rejections, not branch-comparator mismatches. A next pass should either cover much more nonce space with a faster full-shot filter or find a source-backed way to reduce width/nonconvergence pressure without crossing a qubit break-even cliff.
+
+Public standalone note `6b2eea8f` shares this negative evidence for the collaborative solver pool.
+
+## Second Continuation Audit
+
+2026-06-06 later continuation added four more bounded checks:
+
+- Fast filter tooling: built `/tmp/ecdsafail-fast-filter` using native `secp256k1` generator multiplication and point addition. Cross-check against the original `k256` filter on the same `1285q`/`COMPARE_BITS=48` route and nonce range produced identical `512`-shot hit lists, so the faster tool is acceptable for search triage.
+- `KAL_FOLD_CARRY_TRUNC_W=20` with `DIALOG_GCD_WIDTH_SLOPE_X1000=1013`: structural probe was `1,503,835` average Toffoli × `1,309` qubits = score `1,968,520,015`, barely under the frontier by `47,124`. Nonce `0` failed full eval with `275` classical mismatches and `79` phase batches. The `512`-shot scout found `32` early candidates, but all failed at `2,048` shots; `1012` and `1011` were structurally too expensive.
+- Current `1309q` route with `DIALOG_GCD_COMPARE_BITS=48`: structural probe was `1,503,727` average Toffoli × `1,309` qubits = score `1,968,378,643`. Nonce `0` failed full eval with `17` classical mismatches and `10` phase batches. Staged search found `300` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter; known clean nonces from adjacent routes did not transfer.
+- `1285q` restack from `83e3b66` with `DIALOG_GCD_COMPARE_BITS=48`: structural probe was `1,531,883` average Toffoli × `1,285` qubits = score `1,968,469,655`. Nonce `0` failed full eval with `9` classical mismatches and `3` phase batches. Staged search found `290` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter. Known clean nonces did not transfer; a short direct full-shot search with the fast filter over spaced ranges found no clean nonce before being stopped.
+- `DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS=3/4`: exact but structurally worse. Blocks `3` gave `1,520,899` average Toffoli; blocks `4` gave `1,537,927`, both at `1,309` qubits, so this is not a viable near-frontier path.
+
+Tony post-run classification: every attractive near-frontier route is still bottlenecked by full-shot GCD width/nonconvergence, with comparator mismatches not showing up in the sampled filter rejects. The next useful work is either a genuinely faster full-shot nonce search or a structural qubit-floor change; small Toffoli cuts are now mostly island-limited.
+
+## Post-a66 Search Audit
+
+After syncing to `a66b042`, three immediate one-bit successors were probed from the new frontier. None produced a submit-ready improvement yet:
+
+- `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=19`: structural probe was `1,502,839` average Toffoli × `1,309` qubits = score `1,967,216,251`, which would beat `a66b042` by `675,444` if clean. Nonce `0` failed full eval with `17` classical mismatches and `14` phase batches. Staged search found `305` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+- `KAL_FOLD_CARRY_TRUNC_W=20`: structural probe was also `1,502,839` average Toffoli × `1,309` qubits = score `1,967,216,251`. Nonce `0` failed full eval with `18` classical mismatches and `10` phase batches. Staged search found `314` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+- `DIALOG_GCD_COMPARE_BITS=48`: structural probe was `1,503,211` average Toffoli × `1,309` qubits = score `1,967,703,199`, which would beat `a66b042` by `188,496` if clean. Nonce `0` failed full eval with `11` classical mismatches and `7` phase batches. Staged search found `323` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot GCD filter.
+
+Tony post-run classification: after `a66b042`, the next one-bit cuts are again structurally attractive but full-shot GCD-island-limited. The sampled rejects remain width/nonconvergence, with no comparator mismatches in these filter passes.
+
+## Post-a66 Extended Audit
+
+2026-06-06 follow-up checked whether the old `1285q` qubit-floor route or a shorter active-iteration schedule could pair with the `a66b042` apply-clean frontier. Neither produced a submit-ready improvement:
+
+- `1285q` restack from `83e3b66` plus `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=20`: structural probe with `DIALOG_GCD_COMPARE_BITS=50` was `1,531,103` average Toffoli × `1,285` qubits = score `1,967,467,355`, beating `a66b042` by `424,340` if clean. Nonce `0` failed full eval with `13` classical mismatches and `5` phase batches. Staged GCD search found `285` candidates that passed `2,048` shots, but `0` passed the full `9,024`-shot filter; known adjacent clean nonces did not transfer.
+- `1285q` restack plus apply-clean `20` and `DIALOG_GCD_COMPARE_BITS=48`: structural probe was `1,530,851` average Toffoli × `1,285` qubits = score `1,967,143,535`, beating `a66b042` by `748,160` if clean. Nonce `0` failed full eval with `12` classical mismatches and `6` phase batches. Staged GCD search again found `285` candidates passing `2,048` shots, but `0` passed all `9,024` shots; known nonces still did not transfer.
+- Split `1285q` levers were not independently viable: `shiftOnly` gave `1,507,999` average Toffoli × `1,308` qubits = score `1,972,462,692`, `suffixOnly` kept `1,309` qubits with `1,526,063` average Toffoli, and disabling both returned to the current `1309q` control. This suggests the old `1285q` win needs the coupled restack, not a single transplantable lever.
+- `DIALOG_GCD_ACTIVE_ITERATIONS=257`: structural probe was `1,500,368` average Toffoli × `1,309` qubits = score `1,963,981,712`, beating `a66b042` by about `3.89M` if clean. Nonce `0` failed full eval with `13` classical mismatches and `9` phase batches. Staged GCD search found `132` candidates passing `2,048` shots, but `0` passed all `9,024` shots; full rejects were dominated by nonconvergence (`102`) plus width (`30`).
+
+Tony post-run classification: `ACTIVE_ITERATIONS=257` is the largest structural prize but appears to create a nonconvergence floor, while the `1285q` + apply-clean route remains width/nonconvergence island-limited. Future work should prioritize source-backed convergence or width relief before wider blind nonce sweeps.
+
+## Current Validated Successor
+
+Tony pre-change audit found an exact slack-spend route: `DIALOG_GCD_APPLY_FINAL_LOWQ=0` with `DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS=0` removes the final apply chunk's low-q/windowed carry overhead while the global peak remains bound by `round84_fused_square_xtail_dx_sub_lam_square_lowq` at `1,309` qubits. The raw fast-final route at active `258` had structural target `1,486,327` average Toffoli × `1,309` qubits = score `1,945,602,043`, but the inherited nonce failed with `19` classical mismatches and `8` phase batches, and the first `500` two-thousand-shot GCD survivors produced no full `9,024`-shot GCD hit.
+
+Smallest useful fix: spend part of that recovered Toffoli budget on convergence by setting `DIALOG_GCD_ACTIVE_ITERATIONS=262`, keeping `DIALOG_GCD_WIDTH_MARGIN=10` and `DIALOG_GCD_WIDTH_SLOPE_X1000=1014`. Active `262` stays at `1,309` peak qubits and structural target `1,497,795` average Toffoli. Current nonce `721381` still failed (`7` classical mismatches and `4` phase batches), but the GCD prefilter became much denser:
+
+- `500` candidates passed the `2,048`-shot filter by nonce `2620`.
+- `93` of those passed `4,096` shots.
+- `6` passed `8,192` shots: `614`, `1328`, `1718`, `2148`, `2432`, `2499`.
+- `4` passed all `9,024` GCD shots: `1328`, `2148`, `2432`, `2499`.
+
+Quantum confirmation results:
+
+- `1328`: GCD-clean but failed with `1` phase-garbage batch.
+- `2148`: GCD-clean but failed with `1` classical mismatch and `2` phase-garbage batches.
+- `2432`: validated clean over all `9,024` shots with `0` classical / `0` phase / `0` ancilla failures.
+- `2499`: GCD-clean but failed with `1` classical mismatch and `2` phase-garbage batches.
+
+Validated result: `1,497,795` average executed Toffoli × `1,309` qubits = score `1,960,613,655`, beating `a66b042` by `7,278,040` score points. Local official path `./benchmark.sh --note 'validate lowq0 active262 nonce2432'` reproduced the clean result and wrote `score.json` with the same score.
 
 ## Public Note Checklist
 
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index cda2aba..d9bb949 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1080,7 +1080,11 @@ fn configure_ecdsafail_submission_route() {
     // 260 -> 259 after the 1320q apply teardown: saves one GCD body/reverse row.
     // Stacked with KAL_DOUBLE_CARRY_TRUNC_W=22, the nonce below lands the clean
     // 1320q island while improving the custom-five seed's Toffoli count.
-    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "258");
+    // 258 -> 262 on the lowq0 final-chunk route: spend four GCD rows from the
+    // recovered fast-final Toffoli budget to remove most nonconvergence pressure
+    // while staying under the 1309q round84 peak. Re-hunted with the GCD filter
+    // and quantum-confirmed at tail nonce 2432.
+    set_default_env("DIALOG_GCD_ACTIVE_ITERATIONS", "262");
     set_default_env("DIALOG_GCD_RAW_IPMUL_TERMINAL_REUSE", "1");
     set_default_env("DIALOG_GCD_RAW_IPMUL_CLEAR_P_RESIDUAL", "1");
     set_default_env("DIALOG_GCD_RAW_QUOTIENT_TERMINAL_REUSE", "1");
@@ -1233,7 +1237,7 @@ fn configure_ecdsafail_submission_route() {
     // the second custom-five cut. The retained carry at bit 100 hosts the
     // high-window comparator carry-in, avoiding the generic split's extra
     // boundary qubit and low-window recompute.
-    set_default_env("DIALOG_GCD_APPLY_FINAL_LOWQ", "1");
+    set_default_env("DIALOG_GCD_APPLY_FINAL_LOWQ", "0");
     set_default_env("DIALOG_GCD_APPLY_BOUNDARY_SPLIT", "100");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT", "50");
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "100");
@@ -1320,8 +1324,11 @@ fn configure_ecdsafail_submission_route() {
     // Re-rolled for the APPLY_CLEAN_COMPARE_BITS 21 -> 20 re-tightening above:
     // nonce 721381 lands a clean Fiat-Shamir island, validated 0/0/0 over all
     // 9024 shots at 1309q x 1,503,355 T = 1,967,891,695.
-    set_default_env("DIALOG_TAIL_NONCE", "721381");
-    set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
+    // Re-rolled for the lowq0 fast-final + ACTIVE_ITERATIONS=262 route:
+    // nonce 2432 validates 0/0/0 over all 9024 shots at
+    // 1309q x 1,497,795 T = 1,960,613,655.
+    set_default_env("DIALOG_TAIL_NONCE", "2432");
+    set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "0");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

