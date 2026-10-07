# ed31e8e — Q73b: 105 SAT rewrite rows on the 1173-qubit stream, paid for with a λ buy-back stack and a re-picked per-cell bridge/room table

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-10-04 |
| Submission | `68fea77` |
| Commit | `ed31e8e63ba69d26e05b40cc524f1890dacf8081` |
| Result | 1173 qubits × 944,602 Toffoli = **1,108,018,146** |
| Base | `3161bd2` (git parent, jackylee0424's Q1173): 1173 qubits × 944,620 Toffoli = 1,108,039,260 |
| Change vs base | qubits ±0, Toffoli −18, score −21,114 (leaderboard Δ −21,114) |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [dead-gate-strip](../concepts/dead-gate-strip.md), [skywalk-gcd](../concepts/skywalk-gcd.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [adders-and-carries](../concepts/adders-and-carries.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: the per-cell table and two rewrite tables are copied from the commit; the patch covers the rest |

## Summary

dysnasia moves their own sky line to 1173 qubits. They take two pieces from
jackylee0424's Q1173 commit [`3161bd2`](3161bd2.md): the walk cap of 1173
with its reset bridge profile, and the per-cell bridge/room table. The table
is re-picked. jackylee0424's tree was at λ ≈ 19.73, above the 19.5 limit the
sky line keeps. So this commit also buys error back with six pins, and it
replaces jackylee0424's 11 rewrite rows with 105 SAT-proved rows on the new
stream.

Against the base, the 94 extra rewrite rows save about 94 Toffoli on every
shot. The buy-back and the table re-pick spend most of that, and the net is
−18 Toffoli at 1173 qubits. The author reports λ 19.281, back under 19.5.

The author started from their own unpublished sky21 tree (sky20 plus a
69-row table), not from `3161bd2`. Several pins below therefore read as
reverting jackylee0424's values. Seen from the author's own line, `HEO_FIT_K`
21, `TERMINAL_FW` 40 and the `19:-5` fold band never changed.

## What changed and why it saves Toffoli

### 1. SAT rewrite rows: `q1173_exact_rows.txt` (11 rows) → `q73b_rewrite.txt` (105 rows)

- The `build()` block goes back to the sky loader: it finds the unique
  global op shift under which every row names an unconditioned CCX, then
  replaces each CCX with its CX chain (plus an X if the row says so).
  jackylee0424's fixed-index loader and its `assert_eq!(rows.len(), 11)` are
  removed.
- In the file, 102 rows sit in the square (ops 4.6M–5.2M). The other 3 are at
  op 17,033, near the start of the stream, and at ops 9,252,285 and 9,254,348,
  in the multiply leg's head batch. Two rows name the same wires as an
  11-row entry.
- The submission note describes the pipeline:
  - a span screen of 262K shots, then 2M shots, each with a negative control;
  - an exact SAT proof, with square rows anchored at the square entry and
    "every wire that is not provably zero there, every classical bit and every
    measurement outcome" left free, and windowed proofs for outside rows;
  - only UNSAT rows kept.
- Each row turns one CCX into CNOTs, so 94 more rows are about −94 Toffoli
  on every shot. See [dead-gate-strip](../concepts/dead-gate-strip.md).
- `sky21_rewrite.txt` (69 rows, from the author's sky21 tree) is added but
  never loaded. The code comment names the loaded file `q73a_rewrite.txt`;
  the file is `q73b_rewrite.txt`.

### 2. Per-cell bridge/room table: `cap1173_bridge_room_profile_v2.txt` (141 entries) → `q73a_k3b_retune.txt` (189 entries)

- The `k3b_cell` code is the same as in `3161bd2`, except that it now only
  loads the table when `SKYX_K3B_RETUNE` is set. The recipe sets it, so the
  table is live.
- The format is unchanged: `idx bridge room tick dir`. `bridge` sets the
  cell's `K3B_BRIDGE` pin, relative to the I35 profile, and `room` adds to
  its `K3B_EXTRA_ROOM`, its own cap offset. See [`3161bd2`](3161bd2.md).
- Against jackylee0424's table:
  - 5 entries are dropped: division ticks 388–391 (`-1` bridge) and multiply
    tick 220 (`+1`);
  - 18 are changed, for example division tick 385 `-1` → `+1` and multiply
    ticks 221–225 room −1 → −4;
  - 53 are added. 37 of them lower room by 1 to 4 (multiply ticks 159–173,
    218–230, 269–273, 306–310 and 337; division ticks 287–291 and 315–321).
    The other 16 change bridges: +1 on division ticks 273–286 (8 cells), +2 on
    division ticks 313, 314 and 316, +1 on multiply ticks 343 and 345, and −1
    on multiply ticks 313, 340 and 342.
- I checked every positive room entry against `ovr_v025_lamneutral.txt`, as
  for `3161bd2`. None lifts a cell above 1173.
- The submission note explains the re-pick. Under the 1173 cap, "the late
  division cells 384-392 gained one hot B replay site (about one phase event
  per nonce)". The re-pick "holds the replay-site counts of those cells at
  the sky20 trace", which "bought about 0.48 Lambda for about 11 T".

### 3. λ buy-back pins (`install_skywalk_submission_recipe()`)

The tick ranges are my mapping through the proxy envelope and the pinned
width schedule.

| knob | change vs base | sites | direction |
| --- | --- | --- | --- |
| `HEO_FIT_K` | 19 → 21 | windowed boundary erases of the room-fitted adds | buy, 2 bits |
| `HEO_PIN_ERASE_COMPARE` | 20 → 22 | overflow-carry erase of each shell modular add/sub | buy, 2 bits |
| `HEO_PIN_PP_FOLD_WIDEN` | 112 → 128 | fold window of ticks 60–69, both legs | buy, 1 bit |
| `HEO_PIN_PP_FOLD_PROFILE` | `19:-7` → `19:-5` | fold window of ticks 366–373, both legs | buy, 2 bits |
| `GO_CELLB` | adds `mul:25-49:1` | chunk-boundary compares of multiply cells at ticks 25–49 | buy, 1 bit |
| `GO_CHUNK` | `0-399:-1` → `0-49:a:0,0-399:-1` | chunk compares at proxy rounds 0–49 (ticks 0–27), both legs | buy, 1 bit |
| `TERMINAL_FW` | 42 → 40 | the two `terminal_pair` fold windows | sell, 2 bits |

- `go_slice` returns the first entry whose range holds the round. So
  `0-49:a:0` takes sky9's −1 off proxy rounds 0–49 on both legs.
- `GO_CELLB` is keyed on ticks, through `go_cell_delta`. See
  [`84e78ce`](84e78ce.md).
- The submission note lists the buys as the "Lambda buy-back to fit the 19.5
  limit". It also reports one sell inside them: the `GO_CELLB` band starts at
  tick 25, not 0, which it prices at "-16.7 T for +0.0235 Lambda".
- Each compare bit costs about 0.5 executed Toffoli per site, and each fold
  bit about 1 Toffoli per cell. See
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
  and [modular-fold](../concepts/modular-fold.md).

### 4. Inert or unchanged

- `GO_FLAG 0-63:4` and `SKY_SPLIT_TRIM_LAST 1` move from `build()` into the
  recipe list. They have the same values and the same effect.
- `K3B_CELL_TRACE` is no longer set (it only printed to stderr). A new
  `K3B_OPS` trace is off unless that variable is set.
- `HEO_PIN_PP_WALK_MAX_QUBITS` stays at 1173, and `HEO_PIN_I35_PROFILE` stays
  at the sky16 profile `3161bd2` used.
- The mode changes that `3161bd2` made are reverted to 100644.
- `TAIL_NONCE`: 281303256604719 → 23500078439729.

## Why it is still correct, and what it risks

- **The rewrite rows are exact** on reachable states if their proofs hold. The
  author reports identical mism, phase and failb with and without rows on 32
  paired nonces. The build asserts only that each row names its CCX.
- **The buys remove error.** Each about halves (one bit) or quarters (two
  bits) the error of the sites it touches. Wrong compares show up as
  **phase** failures, and escaped fold carries as **classical** failures.
- **The `TERMINAL_FW` sell and the table re-pick move error around.** The
  author priced them on paired nonces.
- The submission note gives λ 19.281 ± 0.032 on 16,384 nonces (est + 2 SE
  19.345), inside the 19.5 limit that the code comment cites. jackylee0424
  reported about 19.73 for the base.
- The shipped nonce `23500078439729` draws a clean island: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Against the base, the only lever that lowers Toffoli without spending λ is the
94 extra offline SAT-proved CCX → CX rows, about −94 T. The pins mostly buy λ
back at a Toffoli cost. SAT rows are classified as host-derived / classical
specialization, as in [`0642f52`](0642f52.md). The runner-up was
comparator/width truncation, for the buy-back stack. Against the author's own
lineage this is really a Q1174 → Q1173 port, but that qubit was already won
by the base.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 3161bd2 -- src/point_add`. The base is the git
   parent. The author's real starting tree (sky21) was never submitted. Its
   nearest accepted ancestor, `d6dd7ef`, is farther from this commit (424
   changed lines against 367).
   `git diff --ignore-cr-at-eol 3161bd2 ed31e8e -- src/point_add` lists 96
   files. 90 of them change only their mode.
2. **Delete the two files this commit removes**, using the `rm` command
   above the patch below.
3. **Copy the new data files from the commit:**
   `git checkout ed31e8e -- src/point_add/skywalk_data/q73a_k3b_retune.txt src/point_add/skywalk_data/q73b_rewrite.txt src/point_add/skywalk_data/sky21_rewrite.txt`.
   They are the 189-entry per-cell table, the 105 rewrite rows, and the
   unused 69-row sky21 table.
4. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `heo_carry.rs` and `mod.rs`. The mode-only changes of
   the other files are left out, and they do not affect the build.
5. **Check the tree.** `git diff --ignore-cr-at-eol ed31e8e -- src/point_add`
   should show no content changes (mode lines aside).
6. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. `build()` clears
   the process environment and then installs the pinned recipe, so `HEO_*`,
   `GO_*`, `SKY_*`, `SKYX_*`, `PP_*`, `TLM_*` and `SUB4_*` overrides have no
   effect. Do not set them anyway. Expect:
   - 1173 qubits
   - 944,602 average Toffoli (rounded)
   - score 1,108,018,146
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `23500078439729` and an identical op
stream.

### Patch

Delete these files first:

```sh
rm src/point_add/skywalk_data/cap1173_bridge_room_profile_v2.txt \
   src/point_add/skywalk_data/q1173_exact_rows.txt
```

```diff
diff --git a/src/point_add/heo_carry.rs b/src/point_add/heo_carry.rs
old mode 100755
new mode 100644
index 9075abb..2e7e422
--- a/src/point_add/heo_carry.rs
+++ b/src/point_add/heo_carry.rs
@@ -1898,20 +1898,24 @@ fn k3b_cell<R>(c: &mut Builder, dir: &str, t: usize, proxy: usize, body: impl Fn
     if let Some(v) = ovr.get(&idx) {
         pins.extend(v.iter().cloned());
     }
-    // Frozen cap1173 bridge/room profile, measured in this source epoch.
+    // SKYX_K3B_RETUNE (sky-x4 research hook): per-cell K3B_BRIDGE / K3B_EXTRA_ROOM retune file, lines
+    // `idx bridge room tick dir` (format of jackylee0424's cap1173_bridge_room_profile_v2.txt, 3161bd20). Unset = no change.
     static RETUNE: OnceLock<HashMap<usize,(String,isize,usize,String)>> = OnceLock::new();
     let retune = RETUNE.get_or_init(|| {
         let mut map = HashMap::new();
-        for line in include_str!("skywalk_data/cap1173_bridge_room_profile_v2.txt").lines() {
-            let f: Vec<&str> = line.split_whitespace().collect();
-            assert_eq!(f.len(),5);
-            let id: usize = f[0].parse().unwrap();
-            let bridge = f[1].to_string();
-            let room: isize = f[2].parse().unwrap();
-            let tick: usize = f[3].parse().unwrap();
-            assert!(["+0","+1","+2","+3","-1","-2","0"].contains(&bridge.as_str()));
-            assert!((-8..=8).contains(&room));
-            assert!(map.insert(id,(bridge,room,tick,f[4].to_string())).is_none());
+        if std::env::var("SKYX_K3B_RETUNE").is_ok() {
+            // Embedded: the official runner denies file reads at build time, so the table is compiled in like the other skywalk_data files.
+            for line in include_str!("skywalk_data/q73a_k3b_retune.txt").lines().filter(|l| !l.trim().is_empty()) {
+                let f: Vec<&str> = line.split_whitespace().collect();
+                assert_eq!(f.len(),5);
+                let id: usize = f[0].parse().unwrap();
+                let bridge = f[1].to_string();
+                let room: isize = f[2].parse().unwrap();
+                let tick: usize = f[3].parse().unwrap();
+                assert!(["+0","+1","+2","+3","-1","-2","0"].contains(&bridge.as_str()));
+                assert!((-8..=8).contains(&room));
+                assert!(map.insert(id,(bridge,room,tick,f[4].to_string())).is_none());
+            }
         }
         map
     });
@@ -1949,8 +1953,11 @@ fn k3b_cell<R>(c: &mut Builder, dir: &str, t: usize, proxy: usize, body: impl Fn
     let room = h7::cap().saturating_sub(live as usize);
     let before = c.report_totals();
     let s0 = c.k3b_sites;
+    let op0 = c.op_count();
     let (out, cpeak) = c.r3_peak(body);
     if std::env::var_os("R3_PEAK").is_some() { eprintln!("R3_PEAK {idx} {cpeak}"); }
+    // K3B_OPS=1: builder op range of this cell (pre-simplifier; maps phcen error sites to cells).
+    if std::env::var_os("K3B_OPS").is_some() { eprintln!("K3B_OPS {idx} {dir} {t} {op0} {}", c.op_count()); }
     let after = c.report_totals();
     let s1 = c.k3b_sites;
     if set {
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
old mode 100755
new mode 100644
index 956588b..fe46a31
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "281303256604719",
+        "TAIL_NONCE" => "23500078439729",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -277,7 +277,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_SCHEDULE", "carry"),
         ("HEO_SEED", "base"),
         ("HEO_FIT_MODE", "win"),
-        ("HEO_FIT_K", "19"),
+        ("HEO_FIT_K", "21"),
         ("HEO_ZONE", "1"),
         ("HEO_R2D", "382"),
         ("HEO_R2M", "370"),
@@ -325,8 +325,8 @@ fn install_skywalk_submission_recipe() {
         ("FD_COORD_FUSE", "1"),
         ("FD_COORD_LOW_ONE", "1"),
         ("HEO_PIN_FOLD_GUARD", "20"),
-        ("HEO_PIN_PP_FOLD_WIDEN", "112"),
-        ("HEO_PIN_PP_FOLD_PROFILE", "56:0,38:-1,32:-1,25:-5,19:-7,0:-5"),
+        ("HEO_PIN_PP_FOLD_WIDEN", "128"),
+        ("HEO_PIN_PP_FOLD_PROFILE", "56:0,38:-1,32:-1,25:-5,19:-5,0:-5"),
         ("PP_DROP_EXACT_LEAD", "1"),
         ("PP_DROP_EXACT_LEAD_DIR", "mul"),
         ("HEO_RAIL_TOP_RELEASE", "1"),
@@ -348,7 +348,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_PIN_PP_RETAIN_LATE_WIDEN", "0"),
         ("HEO_PIN_PP_N_CAPR", "621-648:18,649-665:16,350-399:20,450-499:20,150-199:20,50-99:20,200-349:20,500-549:20"),
         ("HEO_PIN_SQ_ASM_TAIL", "18"),
-        ("HEO_PIN_ERASE_COMPARE", "20"),
+        ("HEO_PIN_ERASE_COMPARE", "22"),
         ("HEO_PIN_PP_DROP_EXACT_LEAD_WIDEN", "0"),
         ("HEO_PIN_PP_FLAG_WIDEN_DIV", "30"),
         ("GO_JLB", "616-698:m:-1"),
@@ -369,7 +369,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_REVERSE_CARRY_CODEC", "1"),
         ("SKYWALK_MERGED_HIGH_STREAM", "3"),
         ("TERMINAL_PAIR", "1"),
-        ("TERMINAL_FW", "42"),
+        ("TERMINAL_FW", "40"),
         ("HEO_CELL_HELPER_S1", "1"),
         ("BACK_SEAM_FUSE", "3"),
         ("HEO_S1_OUTPUT_ALIAS", "1"),
@@ -394,12 +394,12 @@ fn install_skywalk_submission_recipe() {
         // sky8 package (frozen-sky8, GO p7f): split carry window K=21, FOLD_WIDEN 68 (above), GO r6 per-cell
         // compare re-balance (div ticks 150-155 dB -1, mul ticks 225-344 dF +1), iA.100 envelopes (heo.rs).
         ("HEO_SPLIT_K", "21"),
-        ("GO_CELLB", "div:150-155:-1,div:220-329:-1,mul:105-194:1"),
+        ("GO_CELLB", "div:150-155:-1,div:220-329:-1,mul:105-194:1,mul:25-49:1"),
         ("GO_CELLF", "mul:225-344:1,div:250-299:-1"),
         // sky9 package (frozen-sky9, 19.5 Lambda limit): multiply batch route skipped at t = R-2 (B6), one
         // chunk compare bit fewer on rounds 0-399 (go_slice GO_CHUNK), 65 rewrite rows re-keyed to this op stream.
         ("HEO_MB_SKIP2", "1"),
-        ("GO_CHUNK", "0-399:-1"),
+        ("GO_CHUNK", "0-49:a:0,0-399:-1"),
         // sky10 package (frozen-sky10, 19.5 Lambda limit): FIT_K 22, ERASE_COMPARE 22, SQ_ASM_TAIL 18 and FOLD_GUARD 20
         // are set in place above; 52 SAT-proven square rows re-keyed to this op stream.
         // sky12 package (frozen-sky12, 19.5 Lambda limit): GO_CELLB adds div ticks 220-329 dB -1 and mul ticks 105-194
@@ -421,12 +421,27 @@ fn install_skywalk_submission_recipe() {
         // band on HEO_PIN_PP_FOLD_PROFILE (above); 56 SAT-proven rows re-proved on this op stream (sky18_rewrite.txt).
         // sky19 package (frozen-sky19, 19.5 Lambda limit): HEO_PIN_I35_PROFILE adds division-walk bridges (R_D) and TERMINAL_FW
         // goes from 50 to 40 (above); 62 SAT-proven rows re-proved on this op stream (sky19_rewrite.txt).
+        // sky20 package (frozen-sky20, 19.5 Lambda limit): HEO_PIN_PP_FOLD_PROFILE band 19 goes from -4 to -5 and
+        // HEO_PIN_PP_FOLD_WIDEN from 128 to 112 (above); 61 SAT-proven rows re-proved on this op stream (sky20_rewrite.txt).
+        // sky21 package (frozen-sky21, 19.5 Lambda limit): the sky20 knobs unchanged plus 8 new SAT-proven rows from a fresh
+        // census of this op stream (6 square, 2 outside), 69 rows in all (sky21_rewrite.txt).
+        // q73a package (frozen-q73a, Q1173, 19.5 Lambda limit): walk cap 1173 (HEO_PIN_PP_WALK_MAX_QUBITS above), the
+        // jackylee0424 Q1173 I35 profile (above), a site-constrained per-cell K3B bridge/room retune (q73a_k3b_retune.txt,
+        // read through SKYX_K3B_RETUNE in heo_carry.rs), GO_FLAG 0-63:4 and SKY_SPLIT_TRIM_LAST, and a Lambda buy stack:
+        // GO_CELLB mul 0-49 +1, GO_CHUNK 0-49 a:0, HEO_PIN_PP_FOLD_WIDEN 128, HEO_PIN_ERASE_COMPARE 22 (above);
+        // 105 SAT-proven rows on this op stream (102 square, 3 outside), compiled in (q73a_rewrite.txt).
+        // q73b package (Round Q73-S1 sell, 19.5 Lambda limit): q73a with GO_CELLB mul ticks 25-49 instead of 0-49 (above;
+        // -16.7 T for +0.0235 Lambda); the 105 q73a rows kept, the 2 late outside rows re-proved at their shifted
+        // positions (q73b_rewrite.txt).
+        ("GO_FLAG", "0-63:4"),
+        ("SKY_SPLIT_TRIM_LAST", "1"),
     ] { std::env::set_var(name, value); }
     std::env::set_var("HEO_ENVELOPE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-0.txt"));
     std::env::set_var("HEO_ENVELOPE_MUL", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/extended-middle-1.txt"));
     std::env::set_var("HEO_PROXY_ENVELOPE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/env_front07_R393_clamp.txt"));
     std::env::set_var("HEO_CELL_WINDOWS", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/windows_full_safe_mulB64.tsv"));
     std::env::set_var("K3B_CELL_OVR", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/ovr_v025_lamneutral.txt"));
+    std::env::set_var("SKYX_K3B_RETUNE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/q73a_k3b_retune.txt"));
 }
 
 /// sky8 submission: every setting of the circuit is pinned in code (the recipe above, the compiled-in
@@ -444,9 +459,6 @@ fn clear_process_env() {
 pub fn build() -> Vec<Op> {
     clear_process_env();
     install_skywalk_submission_recipe();
-    std::env::set_var("GO_FLAG", "0-63:4");
-    std::env::set_var("SKY_SPLIT_TRIM_LAST", "1");
-    std::env::set_var("K3B_CELL_TRACE", "1");
     if std::env::var_os("SKYWALK_SQUARE_HIGH_PROBE").is_some(){square::high_probe();std::process::exit(0);}
     if std::env::var_os("SKYWALK_MODDIV_ADAPTER_PROBE").is_some(){moddiv_adapter::probe();std::process::exit(0);}
     let mut ops = build_point_add();
@@ -488,22 +500,35 @@ pub fn build() -> Vec<Op> {
         // B7 (K3a): measurement absorption, an exact generic post-pass (off = byte-identical).
         ops = mabsorb::absorb(ops);
     }
-    // Eleven square identities SAT-proved on this exact Q1173 stream.
+    // SKY_REWRITE (q73b package rows: 105 rows proved exact by SAT on the q73b op stream, compiled in): replace SAT-proved linear-span CCX by CX chains.
+    // Lines: "widx c1 c2 t cst w1,w2,..|-" against this exact op stream (asserted).
     {
-        let text = include_str!("skywalk_data/q1173_exact_rows.txt");
+        let text = include_str!("skywalk_data/q73b_rewrite.txt");
         let mut rows: Vec<(usize, u64, u64, u64, bool, Vec<u64>)> = text.lines().filter(|l| !l.trim().is_empty()).map(|l| {
             let f: Vec<&str> = l.split_whitespace().collect();
             let ws = if f[5] == "-" { vec![] } else { f[5].split(',').map(|x| x.parse().unwrap()).collect() };
             (f[0].parse().unwrap(), f[1].parse().unwrap(), f[2].parse().unwrap(), f[3].parse().unwrap(), f[4] == "1", ws)
         }).collect();
-        assert_eq!(rows.len(), 11);
         rows.sort_by(|a, b| b.0.cmp(&a.0));
+        // The rows are keyed to one op stream; an upstream change shifts the block rigidly.
+        // Find the unique shift d under which every row names its CCX (asserted unique).
+        let hit = |w: usize, c1: u64, c2: u64, t: u64| w < ops.len() && { let o = &ops[w]; o.kind == OperationType::CCX && o.q_target.0 == t
+            && ((o.q_control1.0 == c1 && o.q_control2.0 == c2) || (o.q_control1.0 == c2 && o.q_control2.0 == c1)) };
+        let r0 = rows[0].clone();
+        let mut shifts = Vec::new();
+        for d in -2_000_000isize..=2_000_000 {
+            let w0 = r0.0 as isize + d;
+            if w0 < 0 || !hit(w0 as usize, r0.1, r0.2, r0.3) { continue; }
+            if rows.iter().all(|r| { let w = r.0 as isize + d; w >= 0 && hit(w as usize, r.1, r.2, r.3) }) { shifts.push(d); }
+        }
+        assert!(shifts.len() == 1, "SKY_REWRITE: {} candidate shifts {:?}", shifts.len(), &shifts[..shifts.len().min(5)]);
+        let d = shifts[0];
+        eprintln!("SKY_REWRITE rows={} shift={d}", rows.len());
         for (w, c1, c2, t, cst, ws) in rows {
-            assert!(w < ops.len(), "Q1173_EXACT11 site out of range");
+            let w = (w as isize + d) as usize;
             let o = ops[w];
             assert!(o.kind == OperationType::CCX && o.q_target.0 == t && o.c_condition == crate::circuit::NO_BIT
-                && ((o.q_control1.0 == c1 && o.q_control2.0 == c2) || (o.q_control1.0 == c2 && o.q_control2.0 == c1)),
-                "Q1173_EXACT11 source mismatch at {w}");
+                && ((o.q_control1.0 == c1 && o.q_control2.0 == c2) || (o.q_control1.0 == c2 && o.q_control2.0 == c1)), "SKY_REWRITE mismatch at {w}");
             let mut rep = Vec::new();
             for q in ws { assert!(q != t); let mut x = Op::empty(); x.kind = OperationType::CX; x.q_control1 = QubitId(q); x.q_target = QubitId(t); rep.push(x); }
             if cst { let mut x = Op::empty(); x.kind = OperationType::X; x.q_target = QubitId(t); rep.push(x); }
```

