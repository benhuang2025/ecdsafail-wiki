# bdff8c8 — Sky9: one fewer chunk-boundary compare bit on every cell with proxy round 0–399 (GO_CHUNK), plus HEO_MB_SKIP2 and re-keyed rewrite rows

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-09-30 |
| Submission | `100467c` |
| Commit | `bdff8c86d3066e6190b3f8ca37e734846aa6e868` |
| Result | 1174 qubits × 944,903 Toffoli = **1,109,316,122** |
| Base | `4ea960f` (the author's sky8): 1174 qubits × 945,828 Toffoli = 1,110,402,072 |
| Change vs base | qubits ±0, Toffoli −925, score −1,085,950 |
| Leaderboard Δ | −669,180, measured against the frontier at the time, `70148ce` (jackylee0424, 1174 × 945,473), which is the git parent but **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [skywalk-gcd](../concepts/skywalk-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: the new rewrite table is copied from the commit; the patch covers the rest |

## Summary

This commit builds on the author's own sky8, not on the frontier `70148ce`.
It makes three changes:
1. It takes `HEO_MB_SKIP2` from [`800ba12`](800ba12.md). That skips the
   multiply batch's 256-bit route at t = R − 2.
2. It adds one new broad sell: `GO_CHUNK = "0-399:-1"`. Every payload cell
   whose proxy round is at most 399 loses one bit of its chunk-boundary carry
   compare. In this recipe those are the cells at ticks 0–219 of both legs.
3. It re-keys the SAT rewrite rows to the new op stream (65 rows), so their
   saving is kept, where 70148ce had dropped it.

The code comment says the package is tuned up to a "19.5 Lambda limit". The
net is −925 Toffoli against sky8 and −570 against the frontier `70148ce`, at
1174 qubits.

## What changed and why it saves Toffoli

All circuit changes are in `src/point_add/mod.rs`:

1. **`GO_CHUNK = "0-399:-1"`** (new pin in `install_skywalk_submission_recipe()`).
   - It is read by `go_slice("GO_CHUNK", round, b'a')` in `mod.rs`, which
     `chunk_compare(round)` in `pingpong.rs` adds to the compare width. The
     hook was already in the tree; only the pin is new.
   - `go_slice` parses `lo-hi:delta` or `lo-hi:dir:delta`. It returns the
     delta of the **first** entry whose inclusive range holds `round`. Unlike
     `go_cell_delta`, it does not sum entries. Here there is one entry, valid
     for both directions.
   - `chunk_compare(round)` is the width of each **chunk-boundary carry
     erase** in a payload cell's chunked 256-bit add. The erase is `hmr` on
     the boundary carry, then, only if the outcome is 1, a phase compare of
     the top `k` bits of the chunk's sum and addend.
   - The width is `PP_REPLAY_CHUNK_COMPARE (21) + chunk-shape band + dB + GO_CHUNK`.
     `chunk_layout` reads the flat `replay_chunk_compare()`, so the shift
     changes the compare width, not where the chunks are cut.
   - For Skywalk cells, `round` is the cell's proxy round, `proxy_round(esw)`
     on the fixed proxy envelope `env_front07_R393_clamp.txt`. Proxy round 399
     is walk width 123. Tick 219 has proxy round 395 and tick 220 has proxy
     round 400. So the −1 applies to the division and multiply cells at ticks
     0–219.
   - Every chunk boundary in those roughly 440 cells (220 ticks × 2 legs)
     compares one fewer bit. That is about 0.5 executed Toffoli per boundary,
     because the compare runs only on outcome 1. This is a narrower window: a
     sell.
2. **`HEO_MB_SKIP2 = 1`** (new pin). In the multiply leg's trailing batch, the
   payload `route(s, Sig, Del)` at `t + 2 == r` is skipped. That route is 256
   controlled swaps, so about 256 CCX. It is the identity except on walks that
   park exactly at tick R. See [`800ba12`](800ba12.md).
3. **SAT rewrite rows: `sky8_p7f_rewrite.txt` (67 rows) → `sky9_rewrite.txt`
   (65 rows).**
   - The comment says: "sky8 rows c1 + c2 transferred to the sky9 op stream".
   - Comparing the files, 11 of the 65 rows name the same wires as a sky8 row,
     10 at an op-index shift of −8,076 and one at the same index. The others name different wires.
   - The loader is unchanged. It finds the one global shift under which every
     row names a matching unconditioned CCX, asserts that it is unique, and
     replaces each CCX with its CX chain. It does not re-check the proofs. See
     [dead-gate-strip](../concepts/dead-gate-strip.md).
   - Two fewer rows costs about 2 Toffoli.
   - `sky8_p7f_rewrite.txt` stays in the tree, unused.
4. **Tail nonce**: `TAIL_NONCE` goes from 8000042289598 to 9000851329353.

Not changed from sky8: `HEO_PIN_PP_CHUNK_SHAPE` stays `…,0:-4` (800ba12's
`0:-5` is not taken), and `GO_CELLB` stays `div:150-155:-1`.

Rough accounting (my estimate): MB_SKIP2 is about −256, and the rows about
+2. That leaves about −670 for `GO_CHUNK`.

## Why it is still correct, and what it risks

- **GO_CHUNK is probabilistic.** It doubles the top-k tie error of every
  boundary erase in the cells at ticks 0–219. A wrong compare leaves a wrong
  phase, so it shows up as a **phase** failure. It touches about half of all
  cells, so it is the largest λ spend in the package.
- **MB_SKIP2 is λ-priced.** On a walk that parks exactly at tick R, the
  payload comes out wrong. That shows up as a **classical** failure.
- **The rewrite rows** are exact on reachable states if their offline proofs
  hold. A row that is stale but still matches its CCX by wires would be
  caught as a classical or phase failure.
- The comment states a 19.5 λ limit, the "limiting contract" of the Skywalk
  author (see [skywalk-gcd](../concepts/skywalk-gcd.md)). The shipped nonce
  `9000851329353` draws a clean island: 0 classical, 0 phase and 0 ancilla
  failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The largest piece, and the only new lever, is a one-bit cut of a compare
window over half the cells. That is comparator/width truncation. The runner-up
is dead-gate/self-inverse removal for `HEO_MB_SKIP2`, which is 800ba12's idea.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 4ea960f -- src/point_add`.
   - Do not start from the git parent `70148ce`. That is jackylee0424's merge
     of sky8 and 800ba12.
   - Against the parent, the diff is 900 lines in 4 files. It deletes the two
     unused sky5 envelopes (787 lines), restores the `SKY_REWRITE` block, and
     reverts jackylee0424's edits: the chunk shape `0:-5` back to `0:-4`, and
     `GO_CELLB` `153-155` back to `150-155`.
   - Against `4ea960f`, `git diff --ignore-cr-at-eol 4ea960f bdff8c8 -- src/point_add`
     is 75 lines in 2 files.
2. **Copy the new rewrite table from the commit:**
   `git checkout bdff8c8 -- src/point_add/skywalk_data/sky9_rewrite.txt`.
   It holds the 65 SAT rows described above.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol bdff8c8 -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. `build()` clears
   the process environment and then installs the pinned recipe, so `HEO_*`,
   `GO_*`, `SKY_*`, `PP_*` and `SUB4_*` overrides have no effect. Do not set
   them anyway. Expect:
   - 1174 qubits
   - 944,903 average Toffoli (rounded)
   - score 1,109,316,122
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9000851329353` and an identical op
stream. Any other change needs a new nonce hunt and re-keyed rewrite rows.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index cb9d240..aa42aa6 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "8000042289598",
+        "TAIL_NONCE" => "9000851329353",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -395,6 +395,10 @@ fn install_skywalk_submission_recipe() {
         ("HEO_SPLIT_K", "21"),
         ("GO_CELLB", "div:150-155:-1"),
         ("GO_CELLF", "mul:225-344:1"),
+        // sky9 package (frozen-sky9, 19.5 Lambda limit): multiply batch route skipped at t = R-2 (B6), one
+        // chunk compare bit fewer on rounds 0-399 (go_slice GO_CHUNK), 65 rewrite rows re-keyed to this op stream.
+        ("HEO_MB_SKIP2", "1"),
+        ("GO_CHUNK", "0-399:-1"),
     ] { std::env::set_var(name, value); }
     std::env::set_var("HEO_ENVELOPE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-0.txt"));
     std::env::set_var("HEO_ENVELOPE_MUL", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-1.txt"));
@@ -459,10 +463,10 @@ pub fn build() -> Vec<Op> {
         // B7 (K3a): measurement absorption, an exact generic post-pass (off = byte-identical).
         ops = mabsorb::absorb(ops);
     }
-    // SKY_REWRITE (sky8 package rows: GO p7f rwf, 67 rows, compiled in): replace SAT-proved linear-span CCX by CX chains.
+    // SKY_REWRITE (sky9 package rows: sky8 rows c1 + c2 transferred to the sky9 op stream, 65 rows, compiled in): replace SAT-proved linear-span CCX by CX chains.
     // Lines: "widx c1 c2 t cst w1,w2,..|-" against this exact op stream (asserted).
     {
-        let text = include_str!("skywalk_data/sky8_p7f_rewrite.txt");
+        let text = include_str!("skywalk_data/sky9_rewrite.txt");
         let mut rows: Vec<(usize, u64, u64, u64, bool, Vec<u64>)> = text.lines().filter(|l| !l.trim().is_empty()).map(|l| {
             let f: Vec<&str> = l.split_whitespace().collect();
             let ws = if f[5] == "-" { vec![] } else { f[5].split(',').map(|x| x.parse().unwrap()).collect() };
```

