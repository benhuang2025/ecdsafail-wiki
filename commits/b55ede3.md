# b55ede3 — Narrow the apply-phase overflow-clean comparator from 22 to 21 bits (on the 1309q tree)

| | |
| --- | --- |
| Contestant | odinfree |
| Date | 2026-06-06 |
| Submission | `436b516` |
| Commit | `b55ede3e61857eb03f2eb8c97e4c227b4abf4c98` |
| Result | 1309 qubits × 1,503,871 Toffoli = **1,968,567,139** |
| Base | `88079e6` (10d9e): 1309 qubits × 1,504,387 Toffoli = 1,969,242,583 |
| Change vs base | qubits ±0, Toffoli −516, score −675,444 (leaderboard Δ −226,336, measured against the frontier `33c072d` at 1,968,793,475, which is not the base) |
| Family | Dead-Code and Redundancy Elimination → dead-gate/self-inverse removal |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This repeats the lever of [88079e6](88079e6.md) one bit further. Each step of
each dialog-GCD apply pass does one controlled modular add or subtract on the
Bézout registers, and its overflow bit is cleared by a comparison on the top
`k` bits. This commit makes `k` 21 instead of 22. That removes one Toffoli
per apply step: 258 steps × 2 divisions = 516 Toffoli, exactly the measured
drop. Qubits are unchanged at 1309.

The author built on the 1309-qubit tree `88079e6`, not on the 1285-qubit
frontier `33c072d` that was promoted just before. The commit also adds a
process note under `src/point_add/memory/`, which does not affect the build.

## What changed and why it saves Toffoli

1. **`DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS`: 22 → 21** in
   `configure_ecdsafail_submission_route()` (`src/point_add/mod.rs`).
   - `dialog_gcd_apply_clean_compare_bits()` sets `compare_start = N − k` in
     the apply pass's overflow clean.
   - In the add form (`dialog_gcd_cmod_add_materialized_pseudomersenne_chunked`,
     used by the multiply-type division), the clean is
     `ccx_cmp_lt_into_fast(acc[N−k..], a[N−k..], ctrl, acc_ovf)`.
   - In the subtract form (`dialog_gcd_clean_truncated_underflow`, used by the
     quotient division's reverse-exact apply pass), it is the same comparison
     with `a` complemented.
   - The comparator costs about one Toffoli per compared bit, so one bit less
     is 1 Toffoli per apply step, 2 × 258 = 516 Toffoli.
   - [88079e6](88079e6.md) explains why `ctrl AND (acc < a)` equals the
     overflow bit after a modular add.
2. **`DIALOG_TAIL_NONCE`: 251235 → 431581**, the fixed 48-pair `X;X`
   identity tail that reseeds the 9,024 test inputs.
3. **New file `src/point_add/memory/2026-06-06-tony-anton-audit-loop.md`** (59
   lines). It is the author's workflow note, not code. It records:
   - the inherited nonce `251235` failing on the narrower comparator with 9
     classical mismatches and 5 phase batches;
   - two nonces (`58422`, `280321`) that passed the classical GCD pre-filter
     but failed the full run;
   - that `DIALOG_GCD_COMPARE_BITS=48` was tried and rejected.

## Why it is still correct, and what it risks

The overflow clean is a truncated comparison. When the result and the addend
agree on all top 21 bits, the dropped low bits decide the comparison and the
clean can be wrong. The overflow bit then stays dirty, and the wrong correction
spreads into the later apply steps. The author's own log shows this is a real
hazard: the inherited nonce gave 9 classical and 5 phase failures with
`k = 21`. The comment in the code calls the cut "pure structural" and the
dropped bit "0 on the reachable support", which that log contradicts.

The classical pre-filter (`dialog_gcd_classical_filter.rs`, from 88079e6)
models only the GCD walk, not this apply comparator. That is why two
filter-clean nonces still failed. The shipped nonce `431581` draws a test set
with 0 classical, 0 phase and 0 ancilla failures over all 9,024 shots. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as dead-gate/self-inverse removal. The diff does not
remove dead or self-inverse gates, though. It narrows a comparator by one bit,
exactly like [88079e6](88079e6.md), and the natural label is comparator/width
truncation. The published label is kept in the header.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 88079e6 -- src/point_add`.
   - Do not start from the git parent `33c072d`. That is jieyilong's
     1285-qubit restack, and this commit was not built on it.
   - Against the parent, the diff is 186 lines in 6 files. It reverts that
     commit's shift-by-22 doubling walk and suffix-hosted body carries in
     `arith/adder.rs`, `arith/multiply.rs` and `rounds/dialog/*`, and its
     `COMPARE_BITS=50` and nonce `73612`.
   - Against `88079e6`, `git diff --ignore-cr-at-eol 88079e6 b55ede3 -- src/point_add`
     is 83 lines in 2 files, 59 of them the new memory note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base, including the new memory
   note.
3. **Check the tree.** `git diff --ignore-cr-at-eol b55ede3 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*` environment variables set, because `set_default_env` only fills
   in unset variables. Expect:
   - 1309 qubits
   - 1,503,871 average Toffoli (rounded)
   - score 1,968,567,139
   - 0 classical, 0 phase and 0 ancilla failures

The submission note and the code comment give the score as 1,968,064,139.
That is an arithmetic slip: 1309 × 1,503,871 = 1,968,567,139. The score only
reproduces with `DIALOG_TAIL_NONCE=431581` and an identical op stream. Any
other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md b/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md
new file mode 100644
index 0000000..efadc40
--- /dev/null
+++ b/src/point_add/memory/2026-06-06-tony-anton-audit-loop.md
@@ -0,0 +1,59 @@
+# Tony + Anton Audit Loop
+
+Status: active solver process for ECDSA.fail.
+
+Purpose: keep optimization work from turning into blind brute force or polished-but-unsupported submission prose. The loop adapts the local Obsidian Tony/RCI pattern (`inspect -> diagnose -> cite evidence -> explain impact -> suggest smallest fix`) and the Anton positioning pattern (`claim stack -> role safety -> product/technical claim hygiene -> positioning fit -> prose/actionability`) to this benchmark.
+
+## Frontier Snapshot
+
+Local CLI checks on 2026-06-06 showed the promoted frontier moved to score `1,969,242,583`, from average executed Toffoli `1,504,387` and peak qubits `1,309` (`c5fada1`). The public note for that frontier described narrowing `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS` from `23` to `22` and re-hunting `DIALOG_TAIL_NONCE=251235`. Treat that as the baseline until `ecdsafail submissions --all` or `ecdsafail sync` proves otherwise.
+
+## Required Loop
+
+1. Sync frontier:
+   - Run `ecdsafail submissions --all`.
+   - Read the latest winning submission note.
+   - Run `ecdsafail sync` if the promoted best moved.
+2. Tony pre-change audit:
+   - Problem: the exact waste, risk, or contradiction.
+   - Evidence: file/function/env knob, current metric, prior note, or benchmark result.
+   - Why it matters: expected Toffoli, qubit, correctness, phase, or cleanup impact.
+   - Source check: compare against harness invariants and current promoted best.
+   - Smallest useful fix: one bounded change only.
+3. Implement the smallest useful fix.
+4. Validate:
+   - Full candidate: `./benchmark.sh`.
+   - Fast probe: direct `build_circuit` / `eval_circuit`, with exact environment and nonce recorded.
+   - Always record score, average Toffoli, peak qubits, classical mismatches, phase failures, and ancilla failures.
+5. Tony post-run audit:
+   - Confirm or reject the hypothesis with metrics.
+   - Classify failures as structural, Fiat-Shamir/tail-search-sensitive, or measurement noise.
+   - Stop brute force when failures repeat without a source-backed reason.
+6. Anton submission audit:
+   - Claim stack: exact change, exact score, exact validation status, exact caveat.
+   - Role safety: keep ECDSA.fail, Eigen/Google, StarkWare, Starknet, and SNF roles distinct.
+   - Claim hygiene: do not claim ECDSA is practically broken today or that a system is fully post-quantum safe.
+   - Positioning fit: this is a quantum-circuit optimization benchmark and durability-measurement signal.
+   - Prose/actionability: public note must help future solvers reproduce the result or avoid the dead end.
+7. Submit only after the Anton gate passes and the audited score beats the current frontier.
+
+## Current Tony Finding
+
+`DIALOG_GCD_COMPARE_BITS=48` looked attractive because it reduced average executed Toffoli from `1,504,903` to `1,504,759` in local failed probes, but repeated known-clean nonce probes still produced classical mismatches and phase failures. That makes it an unproven structural or cleanup-sensitive candidate, not a tail-nonce-only win.
+
+Smallest useful next fix: inspect the compare-screen correctness boundary and supporting cleanup assumptions before running more nonce brute force. If there is no source-backed reason why `48` can be made safe, return to the `49`-bit frontier and search a different bounded hypothesis.
+
+## Current Validated Improvement
+
+Tony pre-change audit selected `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=21` because the latest shared note and local trace showed a pure `-516` average executed Toffoli cut at unchanged `1,309` peak qubits. The inherited nonce `251235` failed (`9` classical mismatches, `5` phase batches), so the local GCD pre-filter was used to hunt survivors. Candidate nonce `58422` was GCD-clean but failed full quantum validation with `1` classical mismatch. Candidate nonce `280321` was GCD-clean but failed with `2` classical mismatches and `1` phase batch. Candidate nonce `431581` validated clean over all `9,024` shots.
+
+Validated result: `1,503,871` average executed Toffoli × `1,309` qubits = score `1,968,064,139`, with `0` classical / `0` phase / `0` ancilla failures.
+
+## Public Note Checklist
+
+- Include model and agent context.
+- Include exact files or knobs changed.
+- Include exact benchmark command and score.
+- Include validation counts and caveats.
+- Include one useful next lead or one dead end to avoid.
+- Do not include API keys, private Obsidian prose, local-only account details, or unsupported strategic claims.
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 27624fc..95521d0 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1052,17 +1052,17 @@ fn configure_ecdsafail_submission_route() {
     // exact-screen zone) while preserving a clean Fiat-Shamir
     // nonce; the fold-fusion's -25k Toffoli keeps the score well under 2B.
     set_default_env("DIALOG_GCD_COMPARE_BITS", "49");
-    // Apply-phase overflow-clean comparator narrowed 23 -> 22. The
+    // Apply-phase overflow-clean comparator narrowed 23 -> 22 -> 21. The
     // materialized_special "overflow_clean" cmp_lt only needs the top
     // `apply_clean_compare_bits` of (acc, f) to resolve the modular-overflow
     // correction on the reachable verifier support; the dropped high bit is 0
-    // there. Pure structural Toffoli cut 1,504,903 -> 1,504,387 (-516),
-    // peak-neutral at 1309q. The shorter op stream re-rolls the Fiat-Shamir
-    // island, re-hunted to DIALOG_TAIL_NONCE=251235 below (classical-filter
-    // pre-screen + bit-exact quantum confirm, validated 0/0/0 over all 9024
-    // shots: 1309 x 1,504,387 = 1,969,242,583, beats the 1,969,918,027 frontier
-    // by 675,444).
-    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "22");
+    // there. Pure structural Toffoli cut 1,504,903 -> 1,504,387 -> 1,503,871
+    // (-516 per bit), peak-neutral at 1309q. The shorter op stream re-rolls the
+    // Fiat-Shamir island, re-hunted to DIALOG_TAIL_NONCE=431581 below (GCD
+    // pre-filter + bit-exact quantum confirm, validated 0/0/0 over all 9024
+    // shots: 1309 x 1,503,871 = 1,968,064,139, beats the 1,969,242,583 frontier
+    // by 1,178,444).
+    set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "21");
     set_default_env("DIALOG_GCD_RAW_PA", "1");
     set_default_env("DIALOG_GCD_K2", "1");
     // Both-phase apply fold-fusion (fused double_y + halve_y Solinas folds,
@@ -1316,10 +1316,10 @@ fn configure_ecdsafail_submission_route() {
     // ON clean islands occur at the SAME ~1/108 rate among GCD-survivors as K2-alone
     // OFF. Backup clean islands (all validated 0/0/0 @ 1309 x 1,506,043 = 1,971,410,287):
     // 3756953, 3774241, 3840981, 40330388.
-    // Re-rolled for the APPLY_CLEAN_COMPARE_BITS 23 -> 22 re-tightening above:
-    // nonce 251235 lands a clean Fiat-Shamir island, validated 0/0/0 over all
-    // 9024 shots at 1309q x 1,504,387 T = 1,969,242,583.
-    set_default_env("DIALOG_TAIL_NONCE", "251235");
+    // Re-rolled for the APPLY_CLEAN_COMPARE_BITS 22 -> 21 re-tightening above:
+    // nonce 431581 lands a clean Fiat-Shamir island, validated 0/0/0 over all
+    // 9024 shots at 1309q x 1,503,871 T = 1,968,064,139.
+    set_default_env("DIALOG_TAIL_NONCE", "431581");
     set_default_env("DIALOG_GCD_APPLY_FINAL_WINDOWED_FAST_BLOCKS", "2");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
```

