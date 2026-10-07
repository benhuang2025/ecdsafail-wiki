# f904fca — Sky19: in-place carry bridges on 10 late division cells, and the terminal cells' fold window 50→40 (TERMINAL_FW)

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-10-03 |
| Submission | `94dce10` |
| Commit | `f904fca46374d1af02a72e03279381eed3f760b2` |
| Result | 1174 qubits × 943,880 Toffoli = **1,108,115,120** |
| Base | `d1608a3` (git parent, the author's sky18 nonce re-roll): 1174 qubits × 943,915 Toffoli = 1,108,156,210 |
| Change vs base | qubits ±0, Toffoli −35, score −41,090 (leaderboard Δ −41,090) |
| Family | Dead-Code and Redundancy Elimination → fold/carry truncation |
| Concepts | [modular-fold](../concepts/modular-fold.md), [skywalk-gcd](../concepts/skywalk-gcd.md), [adders-and-carries](../concepts/adders-and-carries.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: the new rewrite table is copied from the commit; the patch covers the rest |

## Summary

Sky19 does two things.

- It repeats sky17's bridge move ([`284e2b0`](284e2b0.md)) on the division
  leg. Nine new `HEO_PIN_I35_PROFILE` entries give 10 division cells (ticks
  287–356) a budget of 2 or 4 in-place carry bridges. Those cells can then
  lay out their chunked add with fewer approximate chunk boundaries.
- It narrows the fold window of the two terminal cells from 50 to 40 bits.
  These are the last cell of each leg, which `terminal_pair` replaces.

The SAT rewrite table is re-proved for the new op stream (56 → 62 rows). The
net is −35 Toffoli at 1174 qubits, and the author reports λ up 0.019.

## What changed and why it saves Toffoli

All circuit changes are pins in `install_skywalk_submission_recipe()`,
`src/point_add/mod.rs`.

1. **`HEO_PIN_I35_PROFILE`: nine division entries added.** How the profile
   works is in the sky17 note [`284e2b0`](284e2b0.md). In short:
   - an entry `round:0:b` gives every division cell whose proxy round is
     `round` a budget of `b` bridges;
   - the cell sizes its chunk layout for `room + b`;
   - each chunk add that comes up `missing ≤ b` wires short uses `missing`
     in-place Cuccaro stages, one extra CCX each.

   The ticks are my mapping through the proxy envelope and the pinned width
   schedule:

   | proxy round | bridges 0 → | division ticks |
   | --- | --- | --- |
   | 516, 518 | 2 | 287, 288–289 |
   | 554, 560, 564, 569, 574 | 2 | 308, 312, 315, 318, 321 |
   | 597 | 2 | 334 |
   | 633 | 4 | 356 |

   The submission note lists these as "ticks 516, 518, …". They are proxy
   rounds, not ticks.
2. **`TERMINAL_FW`: 50 → 40.**
   - `cell_div` and `cell_mul` in `heo_carry.rs` replace the last cell of each
     leg (`t + 1 == cfg.rounds()`) with `pingpong::terminal_pair(…, fw, …)`,
     reading `fw` from `TERMINAL_FW`.
   - `terminal_pair` runs `terminal_fold_early` on `z[..fw]`, which folds the
     `f`-multiple into `z[1..fw]` with `width_composition::direct_add`. That
     uses one `fold_step` per bit, and any carry past bit `fw` is dropped.
   - So 10 fewer bits removes 10 fold stages at each of the two sites. By my
     reading that is about one Toffoli per bit, so roughly −20 Toffoli per
     shot. This is an estimate.
   - Sky14 ([`cc530e2`](cc530e2.md)) noted that the terminal cells keep their
     own window and do not follow `PP_FOLD_PROFILE`. This is the first change
     to that window.
3. **SAT rewrite rows: `sky18_rewrite.txt` (56 rows) → `sky19_rewrite.txt`
   (62 rows).**
   - The commit comment says "62 SAT-proven rows re-proved on this op stream".
   - In the file, 61 rows sit in the square (ops 4.60M–5.18M) and one at op
     16,991, near the start of the stream. 22 rows name the same wires as a
     sky18 row, all at an index shift of −635.
   - Six more rows are worth about −6 Toffoli on every shot.
   - The loader is unchanged. See
     [dead-gate-strip](../concepts/dead-gate-strip.md). `sky18_rewrite.txt`
     stays in the tree, unused.
4. **Tail nonce**: `TAIL_NONCE` goes from 18000769990959 to 19500303292604.

The diff alone does not fix how the −35 Toffoli splits between the bridges and
the terminal window. The author priced both together: −52 T on their paired
nonces.

## Why it is still correct, and what it risks

- **The bridges are exact.** Each in-place stage computes the same carry and
  restores its operand. They change only which chunk boundaries the 10 cells
  repair approximately. A wrong boundary repair shows up as a **phase**
  failure.
- **The terminal window is a truncation.** A carry that escapes past bit 40
  leaves a wrong field element in the final payload, which shows up as a
  **classical** failure. The submission note calls it "a direct
  error-for-score trade".
- The submission note gives λ 19.231 ± 0.032 on 16,384 nonces (est + 2 SE
  19.295), against 19.212 for sky18, inside the 19.5 limit that the code
  comment cites.
- The rewrite rows are exact on reachable states if their proofs hold. The
  build asserts only that each row still names its CCX.
- The shipped nonce `19500303292604` draws a clean island: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The terminal window is the only lever whose saving can be counted from the
diff (about 20 fold stages). It is a fold-window narrowing: fold/carry
truncation. The runner-up was in-place mutation for the division bridges,
which is how sky17 is classified. If the bridges turned out to be the larger
share, that would be the better label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout d1608a3 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol d1608a3 f904fca -- src/point_add` is
   74 lines in 2 files.
2. **Copy the new rewrite table from the commit:**
   `git checkout f904fca -- src/point_add/skywalk_data/sky19_rewrite.txt`.
   It holds the 62 SAT rows described above.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol f904fca -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. `build()` clears
   the process environment and then installs the pinned recipe, so `HEO_*`,
   `GO_*`, `SKY_*`, `PP_*`, `TLM_*` and `SUB4_*` overrides have no effect. Do
   not set them anyway. Expect:
   - 1174 qubits
   - 943,880 average Toffoli (rounded)
   - score 1,108,115,120
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `19500303292604` and an identical op
stream. [`cf13eba`](cf13eba.md) keeps this circuit and only re-rolls the
nonce.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 41aa4d3..d570740 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "18000769990959",
+        "TAIL_NONCE" => "19500303292604",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -294,7 +294,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_LR1", "1"),
         ("HEO_PIN_SQ_SPARSE_CORRECTION", "1"),
         ("HEO_PIN_SQ_LEND_RETAINED_ANDS", "3"),
-        ("HEO_PIN_I35_PROFILE", "501:1:2,504:1:2,509:1:1,513:1:1,518:1:1,523:1:1,528:1:1,533:1:1,577:1:1,583:1:1,589:1:1,591:1:1,594:1:1,600:0:1,602:0:1,614:1:1,620:1:1,624:1:2,629:1:2,631:1:2,633:1:2,636:1:2,638:1:3,640:0:1,642:0:1,642:1:3,644:0:1,644:1:3,646:0:1,646:1:3,663:1:3,670:1:3,672:0:1,673:0:1,673:1:3,674:0:1,675:0:1,676:0:1,677:0:1,678:0:1,679:0:1,679:1:3,680:0:1,681:0:1,682:0:1,683:0:1,684:0:1,685:0:1,686:0:1,687:0:1,687:1:3,688:0:1,689:0:1,690:0:1,691:0:1,692:0:1,693:0:1,694:0:1,695:0:1,696:0:1,697:0:1,698:0:1,698:1:3"),
+        ("HEO_PIN_I35_PROFILE", "501:1:2,504:1:2,509:1:1,513:1:1,516:0:2,518:0:2,518:1:1,523:1:1,528:1:1,533:1:1,554:0:2,560:0:2,564:0:2,569:0:2,574:0:2,577:1:1,583:1:1,589:1:1,591:1:1,594:1:1,597:0:2,600:0:1,602:0:1,614:1:1,620:1:1,624:1:2,629:1:2,631:1:2,633:0:4,633:1:2,636:1:2,638:1:3,640:0:1,642:0:1,642:1:3,644:0:1,644:1:3,646:0:1,646:1:3,663:1:3,670:1:3,672:0:1,673:0:1,673:1:3,674:0:1,675:0:1,676:0:1,677:0:1,678:0:1,679:0:1,679:1:3,680:0:1,681:0:1,682:0:1,683:0:1,684:0:1,685:0:1,686:0:1,687:0:1,687:1:3,688:0:1,689:0:1,690:0:1,691:0:1,692:0:1,693:0:1,694:0:1,695:0:1,696:0:1,697:0:1,698:0:1,698:1:3"),
         ("HEO_HEAD_LIFO_N", "2"),
         ("HEO_DIV_LIFO_N", "2"),
         ("HEO_MULB_LIFO_N", "2"),
@@ -369,7 +369,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_REVERSE_CARRY_CODEC", "1"),
         ("SKYWALK_MERGED_HIGH_STREAM", "3"),
         ("TERMINAL_PAIR", "1"),
-        ("TERMINAL_FW", "50"),
+        ("TERMINAL_FW", "40"),
         ("HEO_CELL_HELPER_S1", "1"),
         ("BACK_SEAM_FUSE", "3"),
         ("HEO_S1_OUTPUT_ALIAS", "1"),
@@ -419,6 +419,8 @@ fn install_skywalk_submission_recipe() {
         // unchanged, so the same 62 sky16 rows stay exact.
         // sky18 package (frozen-sky18, 19.5 Lambda limit): HEO_PIN_ERASE_COMPARE 20, HEO_PIN_PP_FOLD_WIDEN 128 and a 56:0 top
         // band on HEO_PIN_PP_FOLD_PROFILE (above); 56 SAT-proven rows re-proved on this op stream (sky18_rewrite.txt).
+        // sky19 package (frozen-sky19, 19.5 Lambda limit): HEO_PIN_I35_PROFILE adds division-walk bridges (R_D) and TERMINAL_FW
+        // goes from 50 to 40 (above); 62 SAT-proven rows re-proved on this op stream (sky19_rewrite.txt).
     ] { std::env::set_var(name, value); }
     std::env::set_var("HEO_ENVELOPE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-0.txt"));
     std::env::set_var("HEO_ENVELOPE_MUL", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-1.txt"));
@@ -483,10 +485,10 @@ pub fn build() -> Vec<Op> {
         // B7 (K3a): measurement absorption, an exact generic post-pass (off = byte-identical).
         ops = mabsorb::absorb(ops);
     }
-    // SKY_REWRITE (sky18 package rows: 56 rows proved exact by SAT on the sky18 op stream, compiled in): replace SAT-proved linear-span CCX by CX chains.
+    // SKY_REWRITE (sky19 package rows: 62 rows proved exact by SAT on the sky19 op stream, compiled in): replace SAT-proved linear-span CCX by CX chains.
     // Lines: "widx c1 c2 t cst w1,w2,..|-" against this exact op stream (asserted).
     {
-        let text = include_str!("skywalk_data/sky18_rewrite.txt");
+        let text = include_str!("skywalk_data/sky19_rewrite.txt");
         let mut rows: Vec<(usize, u64, u64, u64, bool, Vec<u64>)> = text.lines().filter(|l| !l.trim().is_empty()).map(|l| {
             let f: Vec<&str> = l.split_whitespace().collect();
             let ws = if f[5] == "-" { vec![] } else { f[5].split(',').map(|x| x.parse().unwrap()).collect() };
```

