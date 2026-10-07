# 9db31da — Walk cap 1173 → 1172 on the q73d tree: re-fitted per-cell bridge/room table, exact shared pair carry in pack5, and jackylee0424's own compare/fold sells

| | |
| --- | --- |
| Contestant | jackylee0424 |
| Date | 2026-10-05 |
| Submission | `73c5e2a` |
| Commit | `9db31da9a0971a2185e54d12d9441c36838aba40` |
| Result | 1172 qubits × 945,335 Toffoli = **1,107,932,620** |
| Base | `e3fd358` (git parent and frontier at the time, dysnasia's q73d re-roll): 1173 qubits × 944,566 Toffoli = 1,107,975,918 |
| Change vs base | qubits −1, Toffoli +769, score −43,298 (leaderboard Δ −43,298) |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [skywalk-gcd](../concepts/skywalk-gcd.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [transcript-codecs](../concepts/transcript-codecs.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **B**: two new data tables are copied from the commit; the patch covers `heo_carry.rs` and `mod.rs` |

## Summary

This commit takes one qubit off the Skywalk circuit. The walk cap
`HEO_PIN_PP_WALK_MAX_QUBITS` goes from 1173 to 1172, and the peak follows it.
Every chunked add that is sized against the cap now has one wire less to
work with, so it needs more chunks or more in-place bridge stages. That costs
Toffoli. Three things pay for it:

- **A new per-cell bridge/room table** (301 cells, room deltas down to −14)
  re-fitted for the 1172 cap.
- **An exact Toffoli saving in the tape codec.** On the multiply forward
  pass, the second pair of each 5-letter group is packed with a product the
  rail tick has already computed. That pack needs 1 CCX instead of 2.
- **Error sells.** The recipe goes back to jackylee0424's own Q1173 settings
  (his `3161bd2`): the split-fit and modular-erase compares lose 2 bits each,
  one fold band loses 2 bits, and three of dysnasia's q73 buys are dropped.
  dysnasia's two q73d flag-compare sells are also dropped, which is a buy.

The net is +769 Toffoli at one qubit fewer, which still lowers the score by
43,298. The author reports λ = 19.531 ± 0.250, slightly above the 19.5 limit
inherited from 8ee337c, and says so openly.

## What changed and why it saves qubits

### 1. Walk cap: `HEO_PIN_PP_WALK_MAX_QUBITS` 1173 → 1172 (`mod.rs`)

`walk_max_qubits()` in `pingpong.rs` returns this pin plus any per-cell
`K3B_EXTRA_ROOM`. Each payload cell's chunked 256-bit add is laid out under
`walk_max_qubits() − active_qubits()`, and so are the windowed fit adds. With
one wire less of room, some cells need an extra chunk boundary (one more
measured carry erase) or more bridge stages (see below). Both cost Toffoli.
See [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).

### 2. Per-cell bridge/room table: `q73a_k3b_retune.txt` (189 rows) → `cap1172_bridge_room_profile_probe.txt` (301 rows)

- `k3b_cell()` in `heo_carry.rs` reads a table of lines
  `idx bridge room tick dir` when `SKYX_K3B_RETUNE` is set. For the cell with
  call index `idx` it does two things:
  - It sets the cell pin `K3B_BRIDGE`. `bridge::enter()` uses it to shift the
    cell's I35 bridge budget. A bridge is an in-place Cuccaro carry stage
    inside the measured ripple ("Each in-place stage trades one extra CCX
    for one fewer owned carry wire", `bridge.rs`).
  - It adds `room` to `K3B_EXTRA_ROOM`, which raises or lowers the cap
    inside that cell only.
- The commit switches the `include_str!` to the new file. It also widens the
  assert on `room` from `-8..=8` to `-16..=16`, with the comment "widened for
  the extended negative-room grid (cap-probe regridx)".
- The new table covers 301 cells (174 division, 127 multiply), against 189
  before. Bridge deltas: 230 × +0, 41 × +1, 11 × +2, 5 × +3, 14 × −1. Room
  deltas run from −14 to +3, and 180 rows are negative. The old table's
  rooms ran from −4 to +2.
- The table is generated data. It decides, cell by cell, where to spend
  extra CCX on bridges and where to hold a cell below the cap, so that the
  whole walk fits in 1172.

### 3. Exact shared pair carry (`EXACT_PAIR_CARRY`, `heo_carry.rs`)

`build()` sets `EXACT_PAIR_CARRY=1` after installing the recipe. Background:
the tape packs each 5-letter group with `pack3` (letters 0–2) and `pack5`
(letters 3–4, through `pair_pack`). See
[transcript-codecs](../concepts/transcript-codecs.md). The existing
"v025 A-2" share already lets the forward tick at letter u % 5 == 1 keep its
first carry instead of erasing it with `hmr`. The next tick turns it into the
product that `pack3` needs, which replaces a bit-0 Fredkin.

The commit extends this to `pack5` on the multiply forward pass (`mulfwd`):

- `forward_tick`: `keep_low` is now also true at u % 5 == 3. The product
  returned by the tick at u % 5 == 4 goes into a new per-group slot,
  `Tape.outer_shared[g]`.
- `pack5`: when `outer_shared[g]` holds a product, it calls the new
  `pair_pack_shared(h4, l4, h5, l5, p)` instead of `pair_pack`.
  - `pair_pack` costs one CCX plus a Fredkin, so 2 CCX.
  - `pair_pack_shared` costs one CCX. It then measures the shared product
    `p` out with `hmr` and stores the outcome bit in the new
    `Group.m_pair`. The doc comment says "Outputs match ordinary pair_pack
    on all 9."
- `pair_unpack` takes the pending `m_pair`. It applies the phase repair
  `z_if(anc, m); cz_if(anc, l1, m)` on the AND it computes anyway, so the
  repair is Clifford. `unpack3` asserts that no `m_pair` is pending.

So each shared group saves one CCX per shot. The submission note calls them
"78 exact outer pair-carry groups". See
[measurement-uncompute](../concepts/measurement-uncompute.md).

### 4. Recipe values (`install_skywalk_submission_recipe`, `mod.rs`)

All of these match jackylee0424's previous submission `3161bd2`, except the
cap.

| knob | e3fd358 (q73d) | 9db31da | effect |
| --- | --- | --- | --- |
| `HEO_FIT_K` | 21 | 19 | sell 2 bits on every windowed boundary erase of fit adds |
| `HEO_PIN_ERASE_COMPARE` | 22 | 20 | sell 2 bits on the overflow-carry erase of each shell modular add/sub |
| `HEO_PIN_PP_FOLD_PROFILE` | `…,19:-5,…` | `…,19:-7,…` | sell 2 fold-window bits on cells at walk width 19–24 |
| `TERMINAL_FW` | 40 | 42 | buy 2 fold bits in the terminal pair cell of each leg |
| `GO_CHUNK` | `0-49:a:0,0-399:-1` | `0-399:-1` | drops q73a's buy, so proxy rounds 0–49 also run the chunk compare 1 bit narrower |
| `GO_CELLB` | `…,mul:105-194:1,mul:25-49:1` | `…,mul:105-194:1` | drops q73b's +1 on multiply cells 25–49 (a sell) |
| `GO_CELLF` | `…,mul:150-224:-1,mul:345-420:-1` | `mul:225-344:1,div:250-299:-1` | drops q73d's two flag sells (a buy) |

- `go_slice` returns the first matching entry, so `0-49:a:0` used to cancel
  the −1 on proxy rounds 0–49.
- The q73c and q73d comment blocks are removed.
- `HEO_PIN_PP_FOLD_WIDEN` stays at 112. Every compare cut above is a measured
  erase with a top-k phase compare, about 0.5 executed Toffoli per bit per
  site. See [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
  and [modular-fold](../concepts/modular-fold.md).

### 5. Rewrite rows: `q73d_rewrite.txt` (105 rows) → `cap1172_exact_rows.txt` (46 rows)

- The loader is unchanged. It finds the unique global shift under which
  every row names an unconditioned CCX, then replaces each CCX by its CX
  chain. See [dead-gate-strip](../concepts/dead-gate-strip.md).
- The new file has 43 rows in the square's op range, one at op 16,991 and
  two after op 9.2M.
- 59 fewer rows means about 59 more CCX per shot than q73d's table removed.
- The comment above the loader still says "q73b package rows: 105 rows". It
  is stale. `q73d_rewrite.txt` and `q73a_k3b_retune.txt` stay in the tree,
  unused.

### 6. Tail nonce

`TAIL_NONCE` goes from 25700399837515 to 281309007763416.

## Why it is still correct, and what it risks

- **The pair carry is exact.** The pack produces the same group encoding,
  and the measured product's phase is repaired on unpack. A slip would show
  up as a **phase** or **ancilla** failure on many shots, not a rare one.
- **The cap and the bridge/room table are exact.** They change layout and
  scratch, not values.
- **The recipe sells are probabilistic.**
  - Narrower erase compares (`HEO_FIT_K`, `ERASE_COMPARE`, `GO_CHUNK`,
    `GO_CELLB`) double their tie error per bit, which shows up as **phase**
    failures.
  - The narrower fold band raises the chance of a dropped carry, which
    shows up as a **classical** failure.
  - Restoring the q73d flag bits and widening `TERMINAL_FW` buy some of
    that back.
- **λ.** The author measured 19.531 ± 0.250 over 256 full 9,024-shot packets.
  The point estimate is above the 19.5 limit in the inherited 8ee337c note,
  and the note discloses and apologises for this. Clean nonces are rarer at
  this λ.
- The shipped nonce `281309007763416` draws a clean island: 0 classical,
  0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The goal and the result are one qubit fewer: the cap moves and the
per-cell room table is re-fitted to fit under it. That is
ancilla-lifetime / venting, like other cap cuts paid for with Toffoli. The
runner-up was comparator/width truncation, because most of the Toffoli that
pays for the cut comes from compare and fold sells. The pair carry is a
smaller, exact scratch-reuse lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout e3fd358 -- src/point_add`.
   - This is the git parent, and the author's real starting tree. The
     commit contains `q73d_rewrite.txt`, which exists only from `7c1a800`
     on, so the author started from dysnasia's q73d tree, not from q73c.
   - `data/bases.tsv` lists `83d0f70` (q73c), whose diff is one line
     shorter (434 against 435 lines). Diffing against it would wrongly show
     this commit renaming `q73c_rewrite.txt` to `q73d_rewrite.txt` and
     re-keying two rows. That was dysnasia's `7c1a800`. It would also hide
     the fact that this commit drops q73d's `GO_CELLF` sells.
   - `git diff --ignore-cr-at-eol e3fd358 9db31da -- src/point_add` is
     435 lines in 4 files. Without `--ignore-cr-at-eol` it also lists mode
     changes (100644 → 100755) on 97 files, which do not matter.
2. **Copy the two new data tables from the commit:**
   `git checkout 9db31da -- src/point_add/skywalk_data/cap1172_bridge_room_profile_probe.txt src/point_add/skywalk_data/cap1172_exact_rows.txt`.
   These are the 301-row bridge/room table and the 46 rewrite rows
   described above.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It covers `heo_carry.rs` and `mod.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol 9db31da -- src/point_add`
   should print nothing, apart from file modes.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. `build()` clears
   the process environment and then installs the pinned recipe, so `HEO_*`,
   `GO_*`, `SKY_*`, `PP_*` and `SUB4_*` overrides have no effect. Do not set
   them anyway. Expect:
   - 1172 qubits
   - 945,335 average Toffoli (945,335.112 before rounding, by the submission
     note)
   - score 1,107,932,620
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `281309007763416` and an identical
op stream.

### Patch

```diff
diff --git a/src/point_add/heo_carry.rs b/src/point_add/heo_carry.rs
old mode 100644
new mode 100755
index 2e7e422..53133c3
--- a/src/point_add/heo_carry.rs
+++ b/src/point_add/heo_carry.rs
@@ -1904,8 +1904,8 @@ fn k3b_cell<R>(c: &mut Builder, dir: &str, t: usize, proxy: usize, body: impl Fn
     let retune = RETUNE.get_or_init(|| {
         let mut map = HashMap::new();
         if std::env::var("SKYX_K3B_RETUNE").is_ok() {
-            // Embedded: the official runner denies file reads at build time, so the table is compiled in like the other skywalk_data files.
-            for line in include_str!("skywalk_data/q73a_k3b_retune.txt").lines().filter(|l| !l.trim().is_empty()) {
+            let text = include_str!("skywalk_data/cap1172_bridge_room_profile_probe.txt");
+            for line in text.lines().filter(|l| !l.trim().is_empty()) {
                 let f: Vec<&str> = line.split_whitespace().collect();
                 assert_eq!(f.len(),5);
                 let id: usize = f[0].parse().unwrap();
@@ -1913,7 +1913,7 @@ fn k3b_cell<R>(c: &mut Builder, dir: &str, t: usize, proxy: usize, body: impl Fn
                 let room: isize = f[2].parse().unwrap();
                 let tick: usize = f[3].parse().unwrap();
                 assert!(["+0","+1","+2","+3","-1","-2","0"].contains(&bridge.as_str()));
-                assert!((-8..=8).contains(&room));
+                assert!((-16..=16).contains(&room)); // widened for the extended negative-room grid (cap-probe regridx)
                 assert!(map.insert(id,(bridge,room,tick,f[4].to_string())).is_none());
             }
         }
@@ -2049,11 +2049,13 @@ struct Group {
     b1: QubitId,
     b0: QubitId,
     m_g: Option<BitId>,
+    m_pair: Option<BitId>,
 }
 
 struct Tape {
     /// v025 A-2: per group, the shared product `h2 * typ3` waiting for that group's pack3.
     shared: Vec<Option<QubitId>>,
+    outer_shared: Vec<Option<QubitId>>,
     raw: Vec<Option<(QubitId, QubitId)>>,
     groups: Vec<Option<Group>>,
     /// RB-1 L-T0: the codec starts at letter `off` (group g = letters 5g+off..5g+off+4); letters below `off`
@@ -2068,7 +2070,7 @@ fn dirty_cell(c:&mut Builder,tape:&Tape,t:usize,body:impl FnOnce(&mut Builder)){
         let raw = tape.raw.iter().filter(|x| x.is_some()).count();
         let p3 = tape.groups.iter().filter(|g| g.as_ref().is_some_and(|g| g.state == GState::P3)).count();
         let p5 = tape.groups.iter().filter(|g| g.as_ref().is_some_and(|g| g.state == GState::P5)).count();
-        let sh = tape.shared.iter().filter(|x| x.is_some()).count();
+        let sh = tape.shared.iter().filter(|x| x.is_some()).count() + tape.outer_shared.iter().filter(|x|x.is_some()).count();
         let tw = 2 * raw + 5 * p3 + 8 * p5 + sh;
         eprintln!("R3_CENSUS t={t} live={} raw={raw} p3={p3} p5={p5} shared={sh} tape_wires={tw} rest={}", c.active_qubits(), c.active_qubits() as usize - tw - 512);
     }
@@ -2105,9 +2107,21 @@ fn pair_pack(c: &mut Builder, h1: QubitId, l1: QubitId, h2: QubitId, l2: QubitId
     c.free_bit(m);
     c.free(anc);
 }
-fn pair_unpack(c: &mut Builder, h1: QubitId, l1: QubitId, h2: QubitId, l2: QubitId) {
+/// Exact shared pair compressor (bdff8c8 exact-arithmetic-v2). Outputs match ordinary pair_pack on all 9.
+/// The product measurement is repaired on pair_unpack's already computed AND.
+fn pair_pack_shared(c: &mut Builder, a: QubitId, b: QubitId, cc: QubitId, d: QubitId, p: QubitId) -> (QubitId, BitId) {
+    let h=c.alloc_qubit(); c.ccx(a,cc,h);
+    c.cx(p,b); c.cx(a,b); c.cx(h,b);
+    c.cx(a,cc); c.cx(p,d);
+    let m=c.alloc_bit(); c.hmr(a,m); c.z_if(h,m); c.cz_if(cc,d,m); c.free_bit(m); c.free(a);
+    let deferred=c.alloc_bit(); c.hmr(p,deferred); c.free(p);
+    (h,deferred)
+}
+
+fn pair_unpack(c: &mut Builder, h1: QubitId, l1: QubitId, h2: QubitId, l2: QubitId, m_pair: Option<BitId>) {
     let anc = c.alloc_qubit();
     c.ccx(h2, l2, anc);
+    if let Some(m)=m_pair { c.z_if(anc,m); c.cz_if(anc,l1,m); c.free_bit(m); }
     c.cx(anc, h1);
     c.cx(anc, l2);
     fredkin(c, anc, l1, l2);
@@ -2124,7 +2138,7 @@ impl Tape {
         Self::with_offset(r, 0)
     }
     fn with_offset(r: usize, off: usize) -> Self {
-        Tape { shared: vec![None; (r - off).div_ceil(5)], raw: vec![None; r], groups: vec![None; (r - off).div_ceil(5)], off }
+        Tape { outer_shared: vec![None; (r - off).div_ceil(5)], shared: vec![None; (r - off).div_ceil(5)], raw: vec![None; r], groups: vec![None; (r - off).div_ceil(5)], off }
     }
     /// Group of letter `u` (u >= off).
     fn gid(&self, u: usize) -> usize {
@@ -2140,7 +2154,7 @@ impl Tape {
         let (h3, l3) = to_hl(c, self.raw[t0 + 2].take().unwrap());
         if truthy("HEO_CODEC_SYNTH") {
             let [a2,a1,a0,h3,l3]=codec_synth::pack_compatible_shared(c,[h1,l1,h2,l2,h3,l3],self.shared[g].take());
-            self.groups[g]=Some(Group{state:GState::P3,synth:true,a2,a1,a0,h3,l3,b2:a2,b1:a2,b0:a2,m_g:None});
+            self.groups[g]=Some(Group{state:GState::P3,synth:true,a2,a1,a0,h3,l3,b2:a2,b1:a2,b0:a2,m_g:None,m_pair:None});
             return;
         }
         assert!(self.shared[g].is_none(), "shared product needs the synthesized codec");
@@ -2155,7 +2169,7 @@ impl Tape {
         c.cz_if(h3, l3, m);
         c.free_bit(m);
         c.free(fwire);
-        self.groups[g] = Some(Group { state: GState::P3, synth: false, a2, a1, a0, h3, l3, b2: a2, b1: a2, b0: a2, m_g: None });
+        self.groups[g] = Some(Group { state: GState::P3, synth: false, a2, a1, a0, h3, l3, b2: a2, b1: a2, b0: a2, m_g: None, m_pair: None });
     }
     fn pack5(&mut self, c: &mut Builder, g: usize) {
         let t0 = 5 * g + self.off;
@@ -2163,7 +2177,12 @@ impl Tape {
         let (h5, l5) = to_hl(c, self.raw[t0 + 4].take().unwrap());
         let mut grp = self.groups[g].take().unwrap();
         assert_eq!(grp.state, GState::P3);
-        pair_pack(c, h4, l4, h5, l5);
+        let h4=if let Some(p)=self.outer_shared[g].take() {
+            assert!(grp.m_pair.is_none());
+            let (h,m)=pair_pack_shared(c,h4,l4,h5,l5,p); grp.m_pair=Some(m);
+            eprintln!("PAIR_CARRY_PACK group={g} t0={t0} op={}",c.op_count());
+            h
+        } else { pair_pack(c,h4,l4,h5,l5); h4 };
         let (gw, b2, b1, b0) = (h4, l4, h5, l5);
         for (x, y) in [(grp.a2, b2), (grp.h3, b1), (grp.l3, b0)] {
             fredkin(c, gw, x, y);
@@ -2215,7 +2234,7 @@ impl Tape {
             fredkin(c, gw, x, y);
         }
         let (h4, l4, h5, l5) = (gw, grp.b2, grp.b1, grp.b0);
-        pair_unpack(c, h4, l4, h5, l5);
+        pair_unpack(c, h4, l4, h5, l5, grp.m_pair.take());
         self.raw[t0 + 3] = Some(from_hl(c, h4, l4));
         self.raw[t0 + 4] = Some(from_hl(c, h5, l5));
         grp.state = GState::P3;
@@ -2225,6 +2244,7 @@ impl Tape {
         let t0 = 5 * g + self.off;
         let grp = self.groups[g].take().unwrap();
         assert_eq!(grp.state, GState::P3);
+        assert!(grp.m_pair.is_none());
         if grp.synth {
             let ([h1,l1,h2,l2,h3,l3],q)=codec_synth::unpack_compatible_retained(c,[grp.a2,grp.a1,grp.a0,grp.h3,grp.l3],REVERSE_CODEC_CAPTURE.with(|v|v.get()));
             assert!(self.shared[g].is_none());self.shared[g]=q;
@@ -2240,7 +2260,8 @@ impl Tape {
         c.cx(fwire, grp.l3);
         fredkin(c, fwire, grp.a1, grp.h3);
         fredkin(c, fwire, grp.a0, grp.l3);
-        pair_unpack(c, fwire, grp.a2, grp.a1, grp.a0);
+        assert!(grp.m_pair.is_none());
+        pair_unpack(c, fwire, grp.a2, grp.a1, grp.a0, None);
         self.raw[t0] = Some(from_hl(c, fwire, grp.a2));
         self.raw[t0 + 1] = Some(from_hl(c, grp.a1, grp.a0));
         self.raw[t0 + 2] = Some(from_hl(c, grp.h3, grp.l3));
@@ -2290,7 +2311,7 @@ impl Tape {
         }
     }
     fn all_consumed(&self) -> bool {
-        self.shared.iter().all(Option::is_none) && self.raw.iter().all(Option::is_none) && self.groups.iter().all(|g| g.is_none() || g.as_ref().unwrap().state == GState::Raw)
+        self.outer_shared.iter().all(Option::is_none) && self.shared.iter().all(Option::is_none) && self.raw.iter().all(Option::is_none) && self.groups.iter().all(|g| g.is_none() || g.as_ref().unwrap().state == GState::Raw)
     }
 }
 
@@ -3138,7 +3159,8 @@ fn forward_tick(c: &mut Builder, cfg: &HeoConfig, k: &CarryCfg, w: &mut Walk, x:
             let mul_leg = label == "mulfwd" || (label == "divfwd" && env_bool("GO_DIVFWD_SHARE", false) && std::env::var("GO_DIVFWD_SHARE_T").map_or(true, |v| v.split(',').any(|x| x.trim().parse::<usize>().ok() == Some(t))));
             let shared_on = mul_leg && env_bool("HEO_CARRY_CODEC", false) && truthy("HEO_CODEC_SYNTH");
             let u = t.checked_sub(w.tape.off);
-            let keep_low = shared_on && u.is_some_and(|u| u % 5 == 1) && t + 2 < cfg.rounds();
+            let pair_share = env_bool("EXACT_PAIR_CARRY",false) && label=="mulfwd";
+            let keep_low = shared_on && u.is_some_and(|u| u % 5 == 1 || (pair_share && u % 5 == 3)) && t + 2 < cfg.rounds();
             let pl = w.pending_low.take();
             let prior = pl.map(|q| (q, w.tape.get(t - 1).1));
             let (nr, typ, s, retained, shared) = {
@@ -3153,8 +3175,13 @@ fn forward_tick(c: &mut Builder, cfg: &HeoConfig, k: &CarryCfg, w: &mut Walk, x:
             w.pending_low = retained;
             if let Some(q) = shared {
                 let g = w.tape.gid(t);
-                assert!(w.tape.shared[g].is_none(), "shared product already pending for group {g}");
-                w.tape.shared[g] = Some(q);
+                if pair_share && u.is_some_and(|u|u%5==4) {
+                    assert!(w.tape.outer_shared[g].is_none(),"outer shared product already pending {g}");
+                    w.tape.outer_shared[g]=Some(q);
+                } else {
+                    assert!(w.tape.shared[g].is_none(), "shared product already pending for group {g}");
+                    w.tape.shared[g] = Some(q);
+                }
             }
             w.rails = Some(nr);
             if o0e {
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
old mode 100644
new mode 100755
index c414d8e..67c48f8
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -151,7 +151,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "25700399837515",
+        "TAIL_NONCE" => "281309007763416",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -277,13 +277,13 @@ fn install_skywalk_submission_recipe() {
         ("HEO_SCHEDULE", "carry"),
         ("HEO_SEED", "base"),
         ("HEO_FIT_MODE", "win"),
-        ("HEO_FIT_K", "21"),
+        ("HEO_FIT_K", "19"),
         ("HEO_ZONE", "1"),
         ("HEO_R2D", "382"),
         ("HEO_R2M", "370"),
         ("HEO_R1M", "99"),
         ("HEO_CARRY_SEED", "fd"),
-        ("HEO_PIN_PP_WALK_MAX_QUBITS", "1173"),
+        ("HEO_PIN_PP_WALK_MAX_QUBITS", "1172"),
         ("HEO_LT0", "1"),
         ("HEO_BW", "inv"),
         ("HEO_LT0_MUL", "1"),
@@ -326,7 +326,7 @@ fn install_skywalk_submission_recipe() {
         ("FD_COORD_LOW_ONE", "1"),
         ("HEO_PIN_FOLD_GUARD", "20"),
         ("HEO_PIN_PP_FOLD_WIDEN", "112"),
-        ("HEO_PIN_PP_FOLD_PROFILE", "56:0,38:-1,32:-1,25:-5,19:-5,0:-5"),
+        ("HEO_PIN_PP_FOLD_PROFILE", "56:0,38:-1,32:-1,25:-5,19:-7,0:-5"),
         ("PP_DROP_EXACT_LEAD", "1"),
         ("PP_DROP_EXACT_LEAD_DIR", "mul"),
         ("HEO_RAIL_TOP_RELEASE", "1"),
@@ -348,7 +348,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_PIN_PP_RETAIN_LATE_WIDEN", "0"),
         ("HEO_PIN_PP_N_CAPR", "621-648:18,649-665:16,350-399:20,450-499:20,150-199:20,50-99:20,200-349:20,500-549:20"),
         ("HEO_PIN_SQ_ASM_TAIL", "18"),
-        ("HEO_PIN_ERASE_COMPARE", "22"),
+        ("HEO_PIN_ERASE_COMPARE", "20"),
         ("HEO_PIN_PP_DROP_EXACT_LEAD_WIDEN", "0"),
         ("HEO_PIN_PP_FLAG_WIDEN_DIV", "30"),
         ("GO_JLB", "616-698:m:-1"),
@@ -369,7 +369,7 @@ fn install_skywalk_submission_recipe() {
         ("HEO_REVERSE_CARRY_CODEC", "1"),
         ("SKYWALK_MERGED_HIGH_STREAM", "3"),
         ("TERMINAL_PAIR", "1"),
-        ("TERMINAL_FW", "40"),
+        ("TERMINAL_FW", "42"),
         ("HEO_CELL_HELPER_S1", "1"),
         ("BACK_SEAM_FUSE", "3"),
         ("HEO_S1_OUTPUT_ALIAS", "1"),
@@ -394,12 +394,12 @@ fn install_skywalk_submission_recipe() {
         // sky8 package (frozen-sky8, GO p7f): split carry window K=21, FOLD_WIDEN 68 (above), GO r6 per-cell
         // compare re-balance (div ticks 150-155 dB -1, mul ticks 225-344 dF +1), iA.100 envelopes (heo.rs).
         ("HEO_SPLIT_K", "21"),
-        ("GO_CELLB", "div:150-155:-1,div:220-329:-1,mul:105-194:1,mul:25-49:1"),
-        ("GO_CELLF", "mul:225-344:1,div:250-299:-1,mul:150-224:-1,mul:345-420:-1"),
+        ("GO_CELLB", "div:150-155:-1,div:220-329:-1,mul:105-194:1"),
+        ("GO_CELLF", "mul:225-344:1,div:250-299:-1"),
         // sky9 package (frozen-sky9, 19.5 Lambda limit): multiply batch route skipped at t = R-2 (B6), one
         // chunk compare bit fewer on rounds 0-399 (go_slice GO_CHUNK), 65 rewrite rows re-keyed to this op stream.
         ("HEO_MB_SKIP2", "1"),
-        ("GO_CHUNK", "0-49:a:0,0-399:-1"),
+        ("GO_CHUNK", "0-399:-1"),
         // sky10 package (frozen-sky10, 19.5 Lambda limit): FIT_K 22, ERASE_COMPARE 22, SQ_ASM_TAIL 18 and FOLD_GUARD 20
         // are set in place above; 52 SAT-proven square rows re-keyed to this op stream.
         // sky12 package (frozen-sky12, 19.5 Lambda limit): GO_CELLB adds div ticks 220-329 dB -1 and mul ticks 105-194
@@ -433,12 +433,6 @@ fn install_skywalk_submission_recipe() {
         // q73b package (Round Q73-S1 sell, 19.5 Lambda limit): q73a with GO_CELLB mul ticks 25-49 instead of 0-49 (above;
         // -16.7 T for +0.0235 Lambda); the 105 q73a rows kept, the 2 late outside rows re-proved at their shifted
         // positions (q73b_rewrite.txt).
-        // q73c package (Round Q73-S2 sell, 19.5 Lambda limit): q73b with HEO_PIN_PP_FOLD_WIDEN 112 instead of 128 (above;
-        // -28.3 T model, confirmed Lambda 19.336 +- 0.032 on 16,384 nonces); the 105 rows re-ported to the w112 op stream
-        // (q73c_rewrite.txt).
-        // q73d package (Round Q73-S7 sell, 19.5 Lambda limit): q73c with GO_CELLF mul ticks 150-224 and 345-420 dF -1
-        // (above; -16 T model, gates 19.240 and 19.276 on 4,096 nonces each); the 105 q73c rows, the 2 late outside rows
-        // re-proved by SAT at their shifted positions (q73d_rewrite.txt).
         ("GO_FLAG", "0-63:4"),
         ("SKY_SPLIT_TRIM_LAST", "1"),
     ] { std::env::set_var(name, value); }
@@ -447,7 +441,7 @@ fn install_skywalk_submission_recipe() {
     std::env::set_var("HEO_PROXY_ENVELOPE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/env_front07_R393_clamp.txt"));
     std::env::set_var("HEO_CELL_WINDOWS", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/windows_full_safe_mulB64.tsv"));
     std::env::set_var("K3B_CELL_OVR", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/ovr_v025_lamneutral.txt"));
-    std::env::set_var("SKYX_K3B_RETUNE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/q73a_k3b_retune.txt"));
+    std::env::set_var("SKYX_K3B_RETUNE", concat!(env!("CARGO_MANIFEST_DIR"), "/src/point_add/skywalk_data/cap1172_bridge_room_profile_probe.txt"));
 }
 
 /// sky8 submission: every setting of the circuit is pinned in code (the recipe above, the compiled-in
@@ -465,6 +459,7 @@ fn clear_process_env() {
 pub fn build() -> Vec<Op> {
     clear_process_env();
     install_skywalk_submission_recipe();
+    std::env::set_var("EXACT_PAIR_CARRY", "1");
     if std::env::var_os("SKYWALK_SQUARE_HIGH_PROBE").is_some(){square::high_probe();std::process::exit(0);}
     if std::env::var_os("SKYWALK_MODDIV_ADAPTER_PROBE").is_some(){moddiv_adapter::probe();std::process::exit(0);}
     let mut ops = build_point_add();
@@ -506,10 +501,10 @@ pub fn build() -> Vec<Op> {
         // B7 (K3a): measurement absorption, an exact generic post-pass (off = byte-identical).
         ops = mabsorb::absorb(ops);
     }
-    // SKY_REWRITE (q73d package rows: 105 rows on the q73d op stream, the q73c rows with the 2 late outside rows re-proved by SAT at their shifted positions, compiled in): replace SAT-proved linear-span CCX by CX chains.
+    // SKY_REWRITE (q73b package rows: 105 rows proved exact by SAT on the q73b op stream, compiled in): replace SAT-proved linear-span CCX by CX chains.
     // Lines: "widx c1 c2 t cst w1,w2,..|-" against this exact op stream (asserted).
     {
-        let text = include_str!("skywalk_data/q73d_rewrite.txt");
+        let text = include_str!("skywalk_data/cap1172_exact_rows.txt");
         let mut rows: Vec<(usize, u64, u64, u64, bool, Vec<u64>)> = text.lines().filter(|l| !l.trim().is_empty()).map(|l| {
             let f: Vec<&str> = l.split_whitespace().collect();
             let ws = if f[5] == "-" { vec![] } else { f[5].split(',').map(|x| x.parse().unwrap()).collect() };
```

