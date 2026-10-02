# e75ea5c — Cap the GCD branch comparator at 55 bits

| | |
| --- | --- |
| Contestant | 10d9e |
| Date | 2026-06-03 |
| Submission | `c279c0e` |
| Commit | `e75ea5cfc06e3fddf841726a30d8fd202ff36a63` |
| Result | 1434 qubits × 1,726,993 Toffoli = **2,476,507,962** |
| Base | `2bd707e` (git parent and frontier at the time, aburan28): 1434 qubits × 1,728,069 Toffoli = 2,478,050,946 |
| Change vs base | qubits ±0, Toffoli −1,076, score −1,542,984 (leaderboard Δ −1,542,984) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The circuit change is one constant. Each dialog-GCD step decides `u > v` from
only the top bits of `u` and `v`. The per-step width is
`min(schedule + 5, active_width, cap)`, and this commit lowers the cap from
56 to 55. On the 269 steps where the cap binds, the comparator loses one bit.
It runs four times per step at one Toffoli per bit: 4 × 269 = 1,076 Toffoli,
exactly the measured change. Qubits are unchanged. The author found the clean
reroll pair (2, 562) with a purpose-built local island-search tool.

The commit also adds a 122-line session note. It describes that tool, a
measured menu of one-knob cuts, and an exact breakdown of the 1434-qubit peak.

## What changed and why it saves Toffoli

1. **`src/point_add/mod.rs`, `configure_ecdsafail_submission_route()`:
   `DIALOG_GCD_COMPARE_BITS` 56 → 55.**
   - `dialog_gcd_compare_bits_for_step(step, active_width)` returns
     `min(DIALOG_GCD_PA9024_COMPARE_SCHEDULE[step] + 5, active_width, DIALOG_GCD_COMPARE_BITS)`.
   - Recomputing the table over this tree's 395 steps (width margin 26), the
     55 cap binds on 269 steps (steps 48 to 322). The summed compare width
     drops from 19,170 to 18,901 bits.
   - The comparator is the hosted branch-bit
     `ccx_cmp_lt_into_fast_borrowed_carries`, one Toffoli per bit. It runs in
     the forward and reverse transcript passes of both GCD passes:
     4 × 269 = 1,076 Toffoli.
   - See [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md).
2. **Reroll pair: `DIALOG_REROLL` 694,534 → 2, `DIALOG_POST_SUB_REROLL`
   579,110 → 562.** These are the identity `X;X` counts that only re-draw the
   9,024 test inputs.
3. **New note `src/point_add/memory/2026-06-03-island-search-tool-and-landability-wall.md`**
   (not code). It records:
   - **An island search tool**, `src/bin/island_search.rs`, which was not
     submitted. The reroll pairs only insert `X;X` runs at two fixed op
     indices, so the tool builds the op stream once and splices in each
     candidate `(r, p)` in memory. It hashes the stream in bulk to get the
     Fiat–Shamir seed, and evaluates the test inputs in batches, stopping at
     the first failure. It reports about 4 candidates per second on a 12-core
     Mac, roughly 6× faster than rebuilding each candidate.
   - **The "landability wall".** Each truncation step at this frontier adds
     about 6 to 9 failing shots per draw, so roughly 1 in 20,000 to 50,000
     pairs is clean. That is why reroll counts in the hundreds of thousands
     appear (for example [`2bd707e`](2bd707e.md)).
   - **A one-knob cut menu** measured on `5d2f6cf`. For example, width margin
     25 gives 1,724,985 Toffoli, and width margin 24 is judged hopeless.
   - **The exact peak.** The 1434 live qubits are `tx` 256 + `ty` 256 + `u`
     256 + compressed log 660 (132 blocks × 5) + raw block 6, with no body
     transient. Six phases co-bind at that level. This confirms that the log
     width sets the peak, as used in [`f42ce5c`](f42ce5c.md). See
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

## Why it is still correct, and what it risks

The truncated comparison is approximate. When `u` and `v` agree on their top
55 compared bits it can return the wrong `u > v`. The step then takes the
wrong GCD branch, which shows up as a classical failure, or as phase or
ancilla garbage when the reverse pass no longer mirrors the forward pass. One
bit fewer roughly doubles the per-step risk on the 269 affected steps.

The reroll pair (2, 562) draws a clean set: 9,024 of 9,024 shots pass with
0 classical, 0 phase and 0 ancilla failures. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change narrows an approximate comparator, so
comparator/width truncation fits. The note and the off-tree search tool do
not change the circuit.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 2bd707e -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 2bd707e e75ea5c -- src/point_add` is
   132 lines in 2 files. 122 of them are the new note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base. The tree also carries the 210
   binary `._*` macOS metadata files from [`339fe8d`](339fe8d.md) and
   [`2bd707e`](2bd707e.md), unchanged.
3. **Check the tree.** `git diff --ignore-cr-at-eol e75ea5c -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`,
   `KAL_*`, `KARA_*` or `ROUND84_*` environment variables set, because
   `set_default_env` keeps any value already in the environment. Expect:
   - 1434 qubits
   - 1,726,993 average Toffoli (rounded)
   - score 2,476,507,962
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the reroll pair `DIALOG_REROLL=2`,
`DIALOG_POST_SUB_REROLL=562` and an identical op stream. Any other change
needs a new reroll search.

### Patch

```diff
diff --git a/src/point_add/memory/2026-06-03-island-search-tool-and-landability-wall.md b/src/point_add/memory/2026-06-03-island-search-tool-and-landability-wall.md
new file mode 100644
index 0000000..41305c1
--- /dev/null
+++ b/src/point_add/memory/2026-06-03-island-search-tool-and-landability-wall.md
@@ -0,0 +1,122 @@
+# 2026-06-03 — Fast island search tool + the "landability wall" at 1,729,565 T
+
+## TL;DR
+- Built a **build-once + spliced-reroll + parallel early-exit** local search tool
+  (`src/bin/island_search.rs`, NOT submitted). It reproduces the official eval
+  **exactly** (validated: it recomputes the leader island `cb57 @ r=6458/p=2553`
+  → `0/0/0`, 1434q × 1,729,565 T = 2,480,196,210). ~6× faster than the old
+  build_circuit+eval_circuit multi-process scan (~4 candidates/s on a 12-core mac
+  vs ~0.5/s, 10 threads).
+- **Key obstacle confirmed:** the frontier Toffoli (1,729,565 at 1434q) is a
+  *landability wall*. Every Toffoli-reducing knob is a width/comparator
+  **truncation** that introduces `mm̄ ≈ 6–9` classical-mismatch shots, so a clean
+  0/0/0 Fiat-Shamir island is ~1/20k–1/50k. Promoted submissions show
+  `DIALOG_REROLL` in the 100k+ range → competitors search ~10^5–10^6 seeds.
+  Single machine at ~4/s = ~14k seeds/hr ⇒ the next rung is a **multi-hour grind**.
+  (Searched ~46k candidates across cb56+w25 in one session with **zero** islands.)
+
+## Why the splice trick works (and is submit-safe)
+`DIALOG_REROLL=r` emits `2r` identity `X tx[0]` ops at a fixed point (op index
+`i_r≈1028`); `DIALOG_POST_SUB_REROLL=p` emits `2p` identity `X tx[1]` ops at
+`i_p≈33732`. Everything else is byte-identical across rerolls. So: build the base
+op stream ONCE, find `i_r`/`i_p` by diffing builds at (1,0)/(0,1), then synthesize
+the exact stream for any `(r,p)` by an in-memory iterator chain — no rebuild. The
+splice is byte-exact, so any island found is reproducible by the official
+`DIALOG_REROLL=r DIALOG_POST_SUB_REROLL=p build_circuit`. Speed tricks:
+1. **Bulk hash:** pre-serialize the base to one contiguous 49-B/op buffer
+   (kind:u8 + 6×u64, matching `fiat_shamir_seed`), hash 3 big slices + tiny
+   identity chunks instead of 77M tiny `update()` calls.
+2. **Lazy testgen + early-exit:** read all 9024 xof pairs first (to keep the
+   simulator RNG offset identical to the trusted eval), but compute the expensive
+   EC `mul`s per batch and stop at the first failing batch.
+
+### Usage
+```bash
+cargo build --release --bin island_search
+# search COMPARE_BITS=56 island, 10 threads, r,p in 0..600:
+DIALOG_GCD_COMPARE_BITS=56 ./target/release/island_search 10 0 600 0 600
+# prints "ISLAND r=.. p=.. ... score=.." on first 0/0/0; reproduce + confirm with
+# DIALOG_GCD_COMPARE_BITS=56 DIALOG_REROLL=r DIALOG_POST_SUB_REROLL=p ecdsafail run
+```
+Gotcha: the dev shell runs `set -e -o pipefail`; guard `grep`/`killall` with
+`|| true`. Never `pkill -f island_search` (self-matches the launching shell).
+
+## Single-knob cut menu measured on the current leader base (682c10ab)
+Base = cb57 + apply_clean19 + width26 + sched7 + active395, 1434q × 1,729,565 T.
+Each is ONE knob step (combining two comparator/width truncations BACKFIRES on
+Toffoli per the older FINDINGS). `(0,0)` profile = one sample of mm̄/ph̄.
+
+| knob | env | Toffoli | score (×1434) | (0,0) mm/ph |
+|---|---|---|---|---|
+| **w25** | `DIALOG_GCD_WIDTH_MARGIN=25` | **1,724,985** | **2,473,628,490 (−0.26%)** | 6 / 4 |
+| cb56 | `DIALOG_GCD_COMPARE_BITS=56` | 1,728,485 | 2,478,647,490 (−0.06%) | 7 / 4 |
+| ac18 | `DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS=18` | 1,728,775 | 2,479,063,350 | 9 / 11 |
+| sm6 | `DIALOG_GCD_PA9024_COMPARE_SCHEDULE_MARGIN=6` | 1,729,349 | 2,479,886,466 | 8 / 7 |
+| w24 | `DIALOG_GCD_WIDTH_MARGIN=24` | 1,720,361 | 2,466,997,674 | **17** / 9 (island ~hopeless) |
+
+**w25 is the best target:** biggest single-knob reduction AND lowest `(0,0)`
+failure profile. w24+ cliff (mm̄≈17) makes the island effectively unreachable.
+A w25 island beats the leader by 0.26% and is durable against reroll-grinders’
+exact-config search (they have to find the SAME deep island).
+
+## Peak-qubit structure (for the durable <1434 cut, deferred)
+`TRACE_PHASE_ACTIVE=1` shows peak 1434 is co-bound by **6** phases; next tier is
+**1413** (−21, a big runway, but in the round84-square subsystem):
+- `dialog_gcd_compressed_block_{ipmul,quotient}_reacquire_terminal_u`
+- `dialog_gcd_materialized_special_chunked_raw_{sum,difference}` (apply add/sub)
+- `dialog_gcd_raw_pa_{pair1_quotient,pair2_product}`
+Next: `r84k_z_inv_squares` / `round84_fused_square_xtail_..._lowq` @ 1413.
+Dropping the global peak by 1 needs **all 6** binders to fall to ≤1433 together —
+the reason 1434 is a stable floor many independent solvers converged to. A
+*value-exact* qubit cut would only need a ph-clean island (~1/55, seconds) since
+mm stays 0 — that is the highest-leverage durable win if the 6-binder simultaneity
+can be cracked. Recommend resuming there.
+
+## EXACT peak decomposition (measured this session)
+At peak (first hit at `dialog_gcd_raw_pa_pair1_quotient`, op 51754, very early in
+the pair-1 quotient tobitvector), the 1434 live qubits are EXACTLY:
+```
+tx (factor)        256
+ty (target)        256
+u  (GCD working)   256   (= p at step 0, full width)
+compressed_log     660   (= blocks×BLOCK_BITS = ceil(395/3)=132 × 5)
+raw_block            6   (= 2 × HIGH_TAIL_ALIAS_GROUP_SIZE(3))
+                  ----
+                  1434   (ZERO body transient — BODY_HOST_CIN + LATE_BORROW_UV_HIGH
+                          already fold c_in/gated/carry into existing registers)
+```
+All SIX 1434-binders (pair1_quotient, pair2_product, the two apply
+materialized_special_chunked sum/difference, and the two ipmul/quotient
+reacquire_terminal_u) are the SAME register pattern, so any shrink of the one
+non-fixed register (`compressed_log`) drops the global peak directly.
+
+### Why 1434 is sticky — the full-log-live design is intentional
+`compressed_log` is allocated full (660) up front ON PURPOSE: the GCD body borrows
+the still-`|0>` *future* log blocks as scratch for the gated/carry lanes
+(`DIALOG_GCD_HOST_GATED`, `DIALOG_GCD_LATE_BORROW_UV_HIGH`, future-carry slice =
+`2*active_width-1` slots). That's why there's no separate scratch register and the
+body transient is 0 — but it also pins the full 660-bit log live for the whole
+pass. You can't make the log incremental without losing the free scratch.
+
+### Structural levers, ranked by tractability
+- **BLOCK_BITS 5→4 (−132q, −9%)**: needs ≤16 reachable 3-step branch patterns per
+  block. Encoding is already 5 (⇒ reachable count is in (16,32]), so 4 is almost
+  certainly impossible. GROUP_SIZE=4 (4 steps/block) is the variant to study
+  (round326_b5_exact_cover_terms.rs / ROUND763) — uncertain.
+- **Host `raw_block` (6q) on free future-log slots** like gated (−6q → 1428,
+  ~−0.4%, value-exact ⇒ only needs a ph island ~1/55, fast to land). At the early
+  peak the future log has 655 free `|0>` slots, far more than gated/carry borrow,
+  so room likely exists at every step. HIGHEST-tractability structural win, but
+  still a careful edit to `dialog_gcd_copy_compressed_block_to_raw` + the body
+  borrow accounting; risk of mm/ph/ancilla regressions. NOT attempted yet.
+- **Incremental u-shrink + log (−~200q)**: free u's provably-zero high bits and
+  size the log per step. Conflicts with the future-log-borrow scratch design;
+  major re-architecture. Multi-session.
+- **active_iterations 395→394 (−5q)**: NOT value-exact — adds mm̄ (same
+  landability wall as the Toffoli cuts).
+
+## Recommendation for next session
+1. Resume the w25 (or cb56) island grind with `island_search` — it WILL land given
+   enough seeds; budget ~50k–100k candidates. Run multiple machines / longer.
+2. OR pursue the value-exact <1434 qubit cut (only needs a ph island → fast to
+   land) — bigger, durable, and reroll-grinders can't copy it.
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 7b2694e..025dcd4 100755
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -29940,7 +29940,10 @@ fn configure_ecdsafail_submission_route() {
     // island documented below.
     // Branch comparator 58 -> 57: -1,064 executed Toffoli, peak-neutral at 1434q,
     // stacked on the active395 base. Clean island at REROLL=4959 / POST_SUB=5983.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "56");
+    // Branch comparator 56 -> 55: -1,076 executed Toffoli, peak-neutral at 1434q,
+    // stacked on the active395 base. Clean 0/0/0 island at REROLL=2 / POST_SUB=562
+    // (1434q x 1,726,993 T = 2,476,507,962), found by the local island_search grind.
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "55");
     // Apply-phase cmod-correction comparator tightened 20 -> 19 (-790 executed
     // Toffoli, peak-neutral at 1434q) -- an orthogonal value-exact lever the
     // frontier had dropped, stacked on compare57+active395. Clean island below.
@@ -30079,8 +30082,9 @@ fn configure_ecdsafail_submission_route() {
     set_default_env("DIALOG_GCD_APPLY_CHUNKED_F_CUT2", "130");
     // Active-396 island: compare_bits=58 + apply_clean=21 + schedule margin=8
     // validates 0/0/0 over all 9024 shots at 1438q x 1,736,773 T.
-    set_default_env("DIALOG_REROLL", "694534");
-    set_default_env("DIALOG_POST_SUB_REROLL", "579110");
+    // compare_bits=55 clean 0/0/0 island over all 9024 shots at 1434q x 1,726,993 T.
+    set_default_env("DIALOG_REROLL", "2");
+    set_default_env("DIALOG_POST_SUB_REROLL", "562");
     // Fuse the branch-bit comparator with the b0-controlled log update: derive
     // b0_and_b1 from the in-flight comparator carry instead of materializing a
     // separate cmp qubit and recomputing the comparator for uncompute. Pure
```

