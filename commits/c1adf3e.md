# c1adf3e — Lend the two constant bit-0 walk wires to the pool during each interleaved walk add (1264 → 1263 qubits)

| | |
| --- | --- |
| Contestant | REgonLevy |
| Date | 2026-08-31 |
| Submission | `03f96be` |
| Commit | `c1adf3e5ba699b56d081e26247e4505d9f9dfeb1` |
| Result | 1263 qubits × 903,396 Toffoli = **1,140,989,148** |
| Base | `708d567` (git parent, the author's previous submission): 1264 qubits × 903,381 Toffoli = 1,141,873,584 |
| Change vs base | qubits −1, Toffoli +15, score −884,436 (leaderboard Δ −884,436) |
| Family | Register and Scratch Allocation → scratch/ancilla reuse |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [pingpong-division](../concepts/pingpong-division.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The ping-pong walk registers `u` and `v` always hold odd numbers, so their
bit 0 is always 1. Each walk round adds the source into the target. Before
the add both bit-0 wires are 1, and after it the target's bit 0 is 0, since
odd plus odd is even. The adder's only gates on those wires are a few CXs
whose effect is known in advance.

This commit (the "LOW0" loan) clears both bit-0 wires with an X, gives them
back to the qubit pool for the length of the add, and restores them after.
The add's carry ladder can then use those two wire ids. The interleaved walk
adds sit at the circuit's peak, so the realised peak drops from 1264 to 1263
qubits, for 15 extra average Toffoli. The idea is the same as
[`522d002`](522d002.md), which lends these wires across the replay batches;
here they are lent across the walk adds themselves. Most of the remaining
diff is default-off instrumentation.

## What changed and why it saves qubits

All circuit changes are in `src/point_add/pingpong_div.rs`.

1. **`walk_round` (forward walk round).** Unless `SUB4_PP_LOW0_LOAN_OFF` is
   set:
   ```
   b.x(source[0]); b.free(source[0]);   // source[0] was 1 -> now |0>, back to the pool
   b.x(target[0]); b.free(target[0]);   // target[0] was 1 -> now |0>, back to the pool
   signed_add_wrapping_sigma(_split)(…, low0 = true)
   b.reacquire(target[0]);              // the sum's bit 0 is 0, so |0> is already right
   b.reacquire(source[0]); b.x(source[0]);
   ```
   Then the halving rotation runs as before.
2. **`walk_back_round` (reverse walk round)** does the mirror image:
   - After the rotation is undone, `target[0]` is 0 and `source[0]` is 1. It
     frees `target[0]`, and X-clears and frees `source[0]`.
   - The reverse add runs with `low0 = true`.
   - It then reacquires both wires and sets them back to 1, since the
     restored target is odd again.
3. **The adders.** `signed_add_wrapping_sigma`, `_sigma_split` and the
   dispatcher `signed_add_wrapping` get a `low0` flag. With it set, they skip
   the only three gates that touch bit 0: the sign sandwich
   `cx(sign, target[0])` before and after, and the bit-0 sum
   `cx(source[0], target[0])`.
   - Their net effect on bit 0 is already known (1 + 1 → 0), and the carry
     out of bit 0 is already taken as a constant: the callers pass
     `target0_is_one`, and the sigma adder computes its first carries with
     Clifford gates only.
   - So the wires do not need to exist during the add. See
     [adders-and-carries](../concepts/adders-and-carries.md).
4. **Where it applies.**
   - In the shipped plan, `walk_round` drives the divide's forward walk and
     `walk_back_round` drives the multiply's walk-back. These are exactly the
     walks that run interleaved with the replay, where the tape, both
     coefficient registers and the walk add's carry ladder are all live
     together.
   - The non-interleaved `value_walk` and `value_walk_back` pass
     `low0 = false` and are unchanged.
   - Two pool wires at the binding instant are enough to bring the measured
     peak down by one. See
     [venting-and-wire-loans](../concepts/venting-and-wire-loans.md) and
     [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
5. **Toffoli +15.** No CCX is added, and the chunk-ladder budgets are
   computed from tape length and register widths, not from the live count,
   so the layouts do not change. The small rise comes from the new nonce's
   test draw.
6. **Default-off additions, no effect on the shipped stream.**
   - `SUB4_TRACE_PLAN` / `_WIDTH` / `_LATE` / `_WALK` / `_PEAK` traces.
   - `late_replay_walk_w()`: the late batch's walk-width argument, which
     defaults to the old literal 1.
   - `SUB4_PP_SOLVER_PEAK_SAFE`, a peak-aware chunk-layout re-solve.
   - A brace-only restructure and comment in `fused_fold_maskfree`.
   - About 215 lines of `B0_PLATEAU` / `B0_SNAP` allocator-census
     instrumentation in `mod.rs`.
7. **Tail nonce** in `mod.rs`: 25000185239798 → 3009322982643.
   `mod.rs.bak`, an uncompiled backup, is refreshed to a near-copy of the
   new `mod.rs`.

## Why it is still correct, and what it risks

- **Exact.** The loan relies on one invariant: walk operands are odd. The
  round-0 lift establishes it, and every round keeps it, because
  `(odd ± odd)/2` with the sum ≡ 2 mod 4 is odd again.
- Under it, the X that clears each wire, the skipped CXs, and the restoring X
  reproduce exactly the bit-0 values the old gates produced. No gate's
  function changes, only which wire ids the carries receive.
- If the invariant failed on some input, `free` would reset a 1. That leaves
  phase garbage, or a classical mismatch after the restore. It cannot fail
  for a walk that is otherwise on track.
- The shipped nonce draws a clean set: 0 classical, 0 phase and 0 ancilla
  failures.

## Classification rationale

Wires with a provably constant value are lent to the pool as scratch for the
adder's carries and restored afterwards. That is scratch/ancilla reuse, the
same mechanism as `522d002`'s replay loan, applied to the walk add.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 708d567 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 708d567 c1adf3e -- src/point_add` is
   612 lines in 3 files. About 430 of them are instrumentation in `mod.rs`
   and the refreshed `mod.rs.bak`.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol c1adf3e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`,
   `B0_*` or trace environment variables set. Expect:
   - 1263 qubits
   - 903,396 average Toffoli (rounded)
   - score 1,140,989,148
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3009322982643` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a05f695..97cc8da 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -154,6 +154,17 @@ pub struct B0Census {
     pub printed: bool,
 
     pub phase_filter: Option<String>,
+
+    // QUBIT-seat instrumentation (env-gated, default-off, byte-neutral):
+    // B0_PLATEAU_MIN: log every alloc/free event with active >= min (op, active, phase)
+    // B0_SNAP_AT: dump owner histogram at first event with op >= each listed index
+    // B0_SNAP_LEVEL/K: dump histogram every K-th event with active == level
+    pub plateau_min: u32,
+    pub plateau_log: Vec<(usize, u32, &'static str)>,
+    pub snap_at: Vec<usize>,
+    pub snap_level: Option<u32>,
+    pub snap_k: usize,
+    pub snap_count: usize,
 }
 
 #[derive(Clone, Copy)]
@@ -220,6 +231,25 @@ impl B {
                         win_lo: lo,
                         win_hi: hi,
                         phase_filter: std::env::var("B0_PHASE").ok().filter(|s| !s.is_empty()),
+                        plateau_min: std::env::var("B0_PLATEAU_MIN")
+                            .ok()
+                            .and_then(|v| v.parse::<u32>().ok())
+                            .unwrap_or(0),
+                        snap_at: std::env::var("B0_SNAP_AT")
+                            .ok()
+                            .map(|v| {
+                                v.split(',')
+                                    .filter_map(|t| t.trim().parse::<usize>().ok())
+                                    .collect()
+                            })
+                            .unwrap_or_default(),
+                        snap_level: std::env::var("B0_SNAP_LEVEL")
+                            .ok()
+                            .and_then(|v| v.parse::<u32>().ok()),
+                        snap_k: std::env::var("B0_SNAP_K")
+                            .ok()
+                            .and_then(|v| v.parse::<usize>().ok())
+                            .unwrap_or(256),
                         ..Default::default()
                     },
                     _ => B0Census::default(),
@@ -330,6 +360,48 @@ impl B {
         }
     }
     fn record_phase_active(&mut self) {
+        if let Some(spec) = std::env::var_os("B0_SNAP_AT") {
+            let want: std::collections::HashSet<usize> = spec
+                .to_string_lossy()
+                .split(',')
+                .filter_map(|s| s.trim().parse().ok())
+                .collect();
+            if want.contains(&self.current_ops_len()) {
+                let mut hist: std::collections::HashMap<(&'static str, &'static str, u32), u32> =
+                    std::collections::HashMap::new();
+                for v in self.b0.owner.values() {
+                    *hist.entry(*v).or_insert(0) += 1;
+                }
+                let mut rows: Vec<((&'static str, &'static str, u32), u32)> = hist.into_iter().collect();
+                rows.sort_by(|a, b| b.1.cmp(&a.1));
+                eprintln!(
+                    "B0_SNAP_AT ops={} active={} phase={} n_live={}",
+                    self.current_ops_len(),
+                    self.active_qubits,
+                    self.phase,
+                    rows.iter().map(|(_, c)| c).sum::<u32>()
+                );
+                for ((phase, file, line), cnt) in rows.iter().take(12) {
+                    eprintln!("B0_SNAP_OWN count={cnt} phase={phase} caller={file}:{line}");
+                }
+                if std::env::var("B0_WIRE_DUMP").is_ok() {
+                    let filter = std::env::var("B0_WIRE_DUMP_FILTER").unwrap_or_default();
+                    let mut ids: Vec<(u64, &'static str, &'static str, u32)> = Vec::new();
+                    for (&qid, &(p, f, l)) in self.b0.owner.iter() {
+                        ids.push((qid, p, f, l));
+                    }
+                    ids.sort();
+                    for (qid, p, f, l) in &ids {
+                        let site = format!("{}:{}", f, l);
+                        if filter.is_empty() || site.contains(&filter) {
+                            eprintln!("B0_SNAP_WIRE id={qid} phase={p} caller={site}");
+                        }
+                    }
+                    eprintln!("B0_SNAP_IDS_MIN={} MAX={}", ids.first().unwrap().0, ids.last().unwrap().0);
+                }
+                eprintln!("B0_SNAP_END");
+            }
+        }
         self.record_active_timeline();
         if std::env::var("TRACE_PHASE_ACTIVE").is_ok() {
             let entry = self.phase_active_max.entry(self.phase).or_insert(0);
@@ -379,6 +451,31 @@ impl B {
             self.b0_print();
             return;
         }
+        if self.b0.plateau_min > 0 && self.active_qubits >= self.b0.plateau_min {
+            self.b0
+                .plateau_log
+                .push((cur, self.active_qubits, self.phase));
+        }
+        if let Some(level) = self.b0.snap_level {
+            if self.active_qubits == level {
+                self.b0.snap_count += 1;
+                if self.b0.snap_count % self.b0.snap_k == 0 {
+                    self.b0_dump_hist(cur, "level_kth");
+                }
+            }
+        }
+        if !self.b0.snap_at.is_empty() {
+            let mut fired: Vec<usize> = Vec::new();
+            for (i, at) in self.b0.snap_at.iter().enumerate() {
+                if cur >= *at {
+                    self.b0_dump_hist(*at, "at");
+                    fired.push(i);
+                }
+            }
+            for i in fired.into_iter().rev() {
+                self.b0.snap_at.remove(i);
+            }
+        }
         if cur >= self.b0.win_lo && self.active_qubits > self.b0.best_active {
             if let Some(f) = &self.b0.phase_filter {
                 if !self.phase.contains(f.as_str()) {
@@ -396,6 +493,124 @@ impl B {
         if self.b0.enabled && !self.b0.printed {
             self.b0_print();
         }
+        self.b0_plateau_report();
+    }
+    fn b0_dump_hist(&self, op_idx: usize, tag: &str) {
+        let snap = &self.b0.owner;
+        let mut hist: std::collections::HashMap<(&'static str, &'static str, u32), u32> =
+            std::collections::HashMap::new();
+        for v in snap.values() {
+            *hist.entry(*v).or_insert(0) += 1;
+        }
+        let mut rows: Vec<((&'static str, &'static str, u32), u32)> = hist.into_iter().collect();
+        rows.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
+        eprintln!(
+            "B0_SNAP_BEGIN tag={tag} ops={op_idx} active={} phase={} n_live={} n_groups={}",
+            self.active_qubits,
+            self.phase,
+            snap.len(),
+            rows.len()
+        );
+        for ((phase, file, line), cnt) in &rows {
+            eprintln!("B0_SNAP_OWN count={cnt} phase={phase} caller={file}:{line}");
+        }
+        if std::env::var("B0_WIRE_DUMP").is_ok() {
+            let filter = std::env::var("B0_WIRE_DUMP_FILTER").unwrap_or_default();
+            let mut ids: Vec<(u64, &'static str, &'static str, u32)> = Vec::new();
+            for (&qid, &(p, f, l)) in snap.iter() {
+                ids.push((qid, p, f, l));
+            }
+            ids.sort();
+            let mut prev: Option<(u64, &'static str, u32)> = None;
+            for (qid, p, f, l) in &ids {
+                if let Some((pq, pf, pl)) = prev {
+                    if pq + 1 != *qid || pf != *p || pl != *l {
+                        eprintln!("B0_SNAP_GROUP_SEP after_id={pq}");
+                    }
+                }
+                prev = Some((*qid, *p, *l));
+                let site = format!("{}:{}", f, l);
+                if filter.is_empty() || site.contains(&filter) || site.contains("reacquire") {
+                    eprintln!("B0_SNAP_WIRE id={qid} phase={p} caller={site}");
+                }
+            }
+            eprintln!("B0_SNAP_IDS_MIN={} MAX={}", ids.first().unwrap().0, ids.last().unwrap().0);
+        }
+        eprintln!("B0_SNAP_END");
+    }
+    fn b0_plateau_report(&self) {
+        if self.b0.plateau_min == 0 {
+            return;
+        }
+        let log = &self.b0.plateau_log;
+        if log.is_empty() {
+            return;
+        }
+        let mut by_level: std::collections::BTreeMap<u32, usize> =
+            std::collections::BTreeMap::new();
+        for &(_, a, _) in log {
+            *by_level.entry(a).or_insert(0) += 1;
+        }
+        let max_level = *by_level.keys().last().unwrap();
+        eprintln!(
+            "B0_PLATEAU_BEGIN min={} n_events={} max_level={} ops=[{},{}]",
+            self.b0.plateau_min,
+            log.len(),
+            max_level,
+            log.first().unwrap().0,
+            log.last().unwrap().0
+        );
+        for (level, cnt) in by_level.iter().rev() {
+            eprintln!("B0_PLATEAU_LEVEL level={level} count={cnt}");
+        }
+        // per-phase stats at max level
+        let mut ph: std::collections::BTreeMap<&'static str, (usize, usize, usize)> =
+            std::collections::BTreeMap::new();
+        for &(op, a, p) in log {
+            if a == max_level {
+                let e = ph.entry(p).or_insert((usize::MAX, 0, 0));
+                e.0 = e.0.min(op);
+                e.1 = e.1.max(op);
+                e.2 += 1;
+            }
+        }
+        for (p, (f, l, c)) in &ph {
+            eprintln!(
+                "B0_PLATEAU_PHASE phase={p} count={c} ops=[{f},{l}]"
+            );
+        }
+        if std::env::var("B0_PLATEAU_EVENTS").is_ok() {
+            for &(op, a, p) in log {
+                if a == max_level {
+                    eprintln!("B0_PLATEAU_EVENT ops={op} phase={p}");
+                }
+            }
+        }
+        if std::env::var("B0_PLATEAU_EVENTS_ALL").is_ok() {
+            for &(op, a, p) in log {
+                eprintln!("B0_PLATEAU_EVENT_ALL ops={op} level={a} phase={p}");
+            }
+        }
+        // runs of max-level events (consecutive log entries at max_level)
+        let mut run_start = None;
+        let mut runs: Vec<(usize, usize, usize)> = Vec::new();
+        for (i, &(op, a, _)) in log.iter().enumerate() {
+            if a == max_level && run_start.is_none() {
+                run_start = Some((i, op));
+            } else if a != max_level {
+                if let Some((si, so)) = run_start.take() {
+                    runs.push((so, log[i - 1].0, i - si));
+                }
+            }
+        }
+        if let Some((si, so)) = run_start {
+            runs.push((so, log.last().unwrap().0, log.len() - si));
+        }
+        eprintln!("B0_PLATEAU_RUNS n_runs={}", runs.len());
+        for (f, l, c) in runs.iter().take(64) {
+            eprintln!("B0_PLATEAU_RUN events={c} ops=[{f},{l}]");
+        }
+        eprintln!("B0_PLATEAU_END");
     }
     fn b0_print(&mut self) {
         self.b0.printed = true;
@@ -2608,7 +2823,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(25000185239798);
+            .unwrap_or(3009322982643);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/mod.rs.bak b/src/point_add/mod.rs.bak
index ee35043..49de98c 100644
--- a/src/point_add/mod.rs.bak
+++ b/src/point_add/mod.rs.bak
@@ -154,6 +154,17 @@ pub struct B0Census {
     pub printed: bool,
 
     pub phase_filter: Option<String>,
+
+    // QUBIT-seat instrumentation (env-gated, default-off, byte-neutral):
+    // B0_PLATEAU_MIN: log every alloc/free event with active >= min (op, active, phase)
+    // B0_SNAP_AT: dump owner histogram at first event with op >= each listed index
+    // B0_SNAP_LEVEL/K: dump histogram every K-th event with active == level
+    pub plateau_min: u32,
+    pub plateau_log: Vec<(usize, u32, &'static str)>,
+    pub snap_at: Vec<usize>,
+    pub snap_level: Option<u32>,
+    pub snap_k: usize,
+    pub snap_count: usize,
 }
 
 #[derive(Clone, Copy)]
@@ -220,6 +231,25 @@ impl B {
                         win_lo: lo,
                         win_hi: hi,
                         phase_filter: std::env::var("B0_PHASE").ok().filter(|s| !s.is_empty()),
+                        plateau_min: std::env::var("B0_PLATEAU_MIN")
+                            .ok()
+                            .and_then(|v| v.parse::<u32>().ok())
+                            .unwrap_or(0),
+                        snap_at: std::env::var("B0_SNAP_AT")
+                            .ok()
+                            .map(|v| {
+                                v.split(',')
+                                    .filter_map(|t| t.trim().parse::<usize>().ok())
+                                    .collect()
+                            })
+                            .unwrap_or_default(),
+                        snap_level: std::env::var("B0_SNAP_LEVEL")
+                            .ok()
+                            .and_then(|v| v.parse::<u32>().ok()),
+                        snap_k: std::env::var("B0_SNAP_K")
+                            .ok()
+                            .and_then(|v| v.parse::<usize>().ok())
+                            .unwrap_or(256),
                         ..Default::default()
                     },
                     _ => B0Census::default(),
@@ -330,6 +360,48 @@ impl B {
         }
     }
     fn record_phase_active(&mut self) {
+        if let Some(spec) = std::env::var_os("B0_SNAP_AT") {
+            let want: std::collections::HashSet<usize> = spec
+                .to_string_lossy()
+                .split(',')
+                .filter_map(|s| s.trim().parse().ok())
+                .collect();
+            if want.contains(&self.current_ops_len()) {
+                let mut hist: std::collections::HashMap<(&'static str, &'static str, u32), u32> =
+                    std::collections::HashMap::new();
+                for v in self.b0.owner.values() {
+                    *hist.entry(*v).or_insert(0) += 1;
+                }
+                let mut rows: Vec<((&'static str, &'static str, u32), u32)> = hist.into_iter().collect();
+                rows.sort_by(|a, b| b.1.cmp(&a.1));
+                eprintln!(
+                    "B0_SNAP_AT ops={} active={} phase={} n_live={}",
+                    self.current_ops_len(),
+                    self.active_qubits,
+                    self.phase,
+                    rows.iter().map(|(_, c)| c).sum::<u32>()
+                );
+                for ((phase, file, line), cnt) in rows.iter().take(12) {
+                    eprintln!("B0_SNAP_OWN count={cnt} phase={phase} caller={file}:{line}");
+                }
+                if std::env::var("B0_WIRE_DUMP").is_ok() {
+                    let filter = std::env::var("B0_WIRE_DUMP_FILTER").unwrap_or_default();
+                    let mut ids: Vec<(u64, &'static str, &'static str, u32)> = Vec::new();
+                    for (&qid, &(p, f, l)) in self.b0.owner.iter() {
+                        ids.push((qid, p, f, l));
+                    }
+                    ids.sort();
+                    for (qid, p, f, l) in &ids {
+                        let site = format!("{}:{}", f, l);
+                        if filter.is_empty() || site.contains(&filter) {
+                            eprintln!("B0_SNAP_WIRE id={qid} phase={p} caller={site}");
+                        }
+                    }
+                    eprintln!("B0_SNAP_IDS_MIN={} MAX={}", ids.first().unwrap().0, ids.last().unwrap().0);
+                }
+                eprintln!("B0_SNAP_END");
+            }
+        }
         self.record_active_timeline();
         if std::env::var("TRACE_PHASE_ACTIVE").is_ok() {
             let entry = self.phase_active_max.entry(self.phase).or_insert(0);
@@ -379,6 +451,31 @@ impl B {
             self.b0_print();
             return;
         }
+        if self.b0.plateau_min > 0 && self.active_qubits >= self.b0.plateau_min {
+            self.b0
+                .plateau_log
+                .push((cur, self.active_qubits, self.phase));
+        }
+        if let Some(level) = self.b0.snap_level {
+            if self.active_qubits == level {
+                self.b0.snap_count += 1;
+                if self.b0.snap_count % self.b0.snap_k == 0 {
+                    self.b0_dump_hist(cur, "level_kth");
+                }
+            }
+        }
+        if !self.b0.snap_at.is_empty() {
+            let mut fired: Vec<usize> = Vec::new();
+            for (i, at) in self.b0.snap_at.iter().enumerate() {
+                if cur >= *at {
+                    self.b0_dump_hist(*at, "at");
+                    fired.push(i);
+                }
+            }
+            for i in fired.into_iter().rev() {
+                self.b0.snap_at.remove(i);
+            }
+        }
         if cur >= self.b0.win_lo && self.active_qubits > self.b0.best_active {
             if let Some(f) = &self.b0.phase_filter {
                 if !self.phase.contains(f.as_str()) {
@@ -396,6 +493,124 @@ impl B {
         if self.b0.enabled && !self.b0.printed {
             self.b0_print();
         }
+        self.b0_plateau_report();
+    }
+    fn b0_dump_hist(&self, op_idx: usize, tag: &str) {
+        let snap = &self.b0.owner;
+        let mut hist: std::collections::HashMap<(&'static str, &'static str, u32), u32> =
+            std::collections::HashMap::new();
+        for v in snap.values() {
+            *hist.entry(*v).or_insert(0) += 1;
+        }
+        let mut rows: Vec<((&'static str, &'static str, u32), u32)> = hist.into_iter().collect();
+        rows.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
+        eprintln!(
+            "B0_SNAP_BEGIN tag={tag} ops={op_idx} active={} phase={} n_live={} n_groups={}",
+            self.active_qubits,
+            self.phase,
+            snap.len(),
+            rows.len()
+        );
+        for ((phase, file, line), cnt) in &rows {
+            eprintln!("B0_SNAP_OWN count={cnt} phase={phase} caller={file}:{line}");
+        }
+        if std::env::var("B0_WIRE_DUMP").is_ok() {
+            let filter = std::env::var("B0_WIRE_DUMP_FILTER").unwrap_or_default();
+            let mut ids: Vec<(u64, &'static str, &'static str, u32)> = Vec::new();
+            for (&qid, &(p, f, l)) in snap.iter() {
+                ids.push((qid, p, f, l));
+            }
+            ids.sort();
+            let mut prev: Option<(u64, &'static str, u32)> = None;
+            for (qid, p, f, l) in &ids {
+                if let Some((pq, pf, pl)) = prev {
+                    if pq + 1 != *qid || pf != *p || pl != *l {
+                        eprintln!("B0_SNAP_GROUP_SEP after_id={pq}");
+                    }
+                }
+                prev = Some((*qid, *p, *l));
+                let site = format!("{}:{}", f, l);
+                if filter.is_empty() || site.contains(&filter) || site.contains("reacquire") {
+                    eprintln!("B0_SNAP_WIRE id={qid} phase={p} caller={site}");
+                }
+            }
+            eprintln!("B0_SNAP_IDS_MIN={} MAX={}", ids.first().unwrap().0, ids.last().unwrap().0);
+        }
+        eprintln!("B0_SNAP_END");
+    }
+    fn b0_plateau_report(&self) {
+        if self.b0.plateau_min == 0 {
+            return;
+        }
+        let log = &self.b0.plateau_log;
+        if log.is_empty() {
+            return;
+        }
+        let mut by_level: std::collections::BTreeMap<u32, usize> =
+            std::collections::BTreeMap::new();
+        for &(_, a, _) in log {
+            *by_level.entry(a).or_insert(0) += 1;
+        }
+        let max_level = *by_level.keys().last().unwrap();
+        eprintln!(
+            "B0_PLATEAU_BEGIN min={} n_events={} max_level={} ops=[{},{}]",
+            self.b0.plateau_min,
+            log.len(),
+            max_level,
+            log.first().unwrap().0,
+            log.last().unwrap().0
+        );
+        for (level, cnt) in by_level.iter().rev() {
+            eprintln!("B0_PLATEAU_LEVEL level={level} count={cnt}");
+        }
+        // per-phase stats at max level
+        let mut ph: std::collections::BTreeMap<&'static str, (usize, usize, usize)> =
+            std::collections::BTreeMap::new();
+        for &(op, a, p) in log {
+            if a == max_level {
+                let e = ph.entry(p).or_insert((usize::MAX, 0, 0));
+                e.0 = e.0.min(op);
+                e.1 = e.1.max(op);
+                e.2 += 1;
+            }
+        }
+        for (p, (f, l, c)) in &ph {
+            eprintln!(
+                "B0_PLATEAU_PHASE phase={p} count={c} ops=[{f},{l}]"
+            );
+        }
+        if std::env::var("B0_PLATEAU_EVENTS").is_ok() {
+            for &(op, a, p) in log {
+                if a == max_level {
+                    eprintln!("B0_PLATEAU_EVENT ops={op} phase={p}");
+                }
+            }
+        }
+        if std::env::var("B0_PLATEAU_EVENTS_ALL").is_ok() {
+            for &(op, a, p) in log {
+                eprintln!("B0_PLATEAU_EVENT_ALL ops={op} level={a} phase={p}");
+            }
+        }
+        // runs of max-level events (consecutive log entries at max_level)
+        let mut run_start = None;
+        let mut runs: Vec<(usize, usize, usize)> = Vec::new();
+        for (i, &(op, a, _)) in log.iter().enumerate() {
+            if a == max_level && run_start.is_none() {
+                run_start = Some((i, op));
+            } else if a != max_level {
+                if let Some((si, so)) = run_start.take() {
+                    runs.push((so, log[i - 1].0, i - si));
+                }
+            }
+        }
+        if let Some((si, so)) = run_start {
+            runs.push((so, log.last().unwrap().0, log.len() - si));
+        }
+        eprintln!("B0_PLATEAU_RUNS n_runs={}", runs.len());
+        for (f, l, c) in runs.iter().take(64) {
+            eprintln!("B0_PLATEAU_RUN events={c} ops=[{f},{l}]");
+        }
+        eprintln!("B0_PLATEAU_END");
     }
     fn b0_print(&mut self) {
         self.b0.printed = true;
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index af4b779..3c30f90 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -126,6 +126,16 @@ fn replay_chunk() -> usize {
     tuned_window("SUB4_PP_REPLAY_CHUNK", &SLOT, 96)
 }
 
+fn late_replay_walk_w() -> usize {
+    static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
+    tuned_window("SUB4_PP_LATE_REPLAY_WALK_W", &SLOT, 1)
+}
+
+fn solver_peak_safe() -> bool {
+    static SLOT: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
+    *SLOT.get_or_init(|| std::env::var_os("SUB4_PP_SOLVER_PEAK_SAFE").is_some())
+}
+
 fn replay_chunk_compare() -> usize {
     static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
     // BAKE (2026-08-23): 21, not 20 -- measured +1,190.84 T, peak 1275
@@ -357,6 +367,9 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
             value_walk_back(b, &mut u, &mut v, std::mem::take(&mut tape), None, None);
         }
         (PingPongDirection::Divide, Some(plan)) => {
+            if std::env::var_os("SUB4_TRACE_PLAN").is_some() {
+                eprintln!("TRACE_PLAN div r1={} r2={} peak={} rounds={}", plan.r1, plan.r2, plan.peak, rounds);
+            }
             // Halving order matches the forward walk.
             phase(b, "pp_div_walk", "pp_mul_walk");
             tape = Vec::with_capacity(rounds);
@@ -375,6 +388,10 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
             // it before the batch replay costs the same ops and takes two
             // wires off the batch's footprint.
             if plan.r1 < rounds {
+                if std::env::var_os("SUB4_TRACE_WIDTH").is_some() {
+                    eprintln!("TRACE_WIDTH pre-batch shrink r1={} value_width={} u.len()={} ops={}",
+                        plan.r1, value_width(plan.r1), u.len(), b.ops.len());
+                }
                 shrink_to(b, &mut u, &mut v, value_width(plan.r1));
             }
             coefficient = b.alloc_qubits(N);
@@ -426,7 +443,14 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
                 tape.push(walk_round(b, &mut u, &mut v, r, rounds));
             }
             let loans = loan(b, &u, &v);
-            set_chunks(pick_chunks(&plan, tape.len() - sign1_charge, 1));
+            let late_ladder = pick_chunks(&plan, tape.len() - sign1_charge, late_replay_walk_w());
+            if std::env::var_os("SUB4_TRACE_LATE").is_some() {
+                eprintln!(
+                    "TRACE_LATE tape_len={} sign1_charge={} u_len={} v_len={} ladder={}",
+                    tape.len(), sign1_charge, u.len(), v.len(), late_ladder
+                );
+            }
+            set_chunks(late_ladder);
             for r in (plan.r2 + 1).max(plan.r1)..rounds {
                 replay_halving_round(b, r, tape[r], &coefficient, numerator);
             }
@@ -1320,6 +1344,7 @@ fn signed_add_wrapping_sigma_split(
     target0_is_one: bool,
     low: usize,
     top_skip: bool,
+    low0: bool,
 ) {
     let n = source.len();
     debug_assert_eq!(n, target.len());
@@ -1327,6 +1352,9 @@ fn signed_add_wrapping_sigma_split(
     let top_skip = top_skip && n >= 6;
 
     for &q in target {
+        if low0 && q == target[0] {
+            continue;
+        }
         b.cx(sign, q);
     }
 
@@ -1367,7 +1395,9 @@ fn signed_add_wrapping_sigma_split(
         b.x(c_lo[0]);
     }
     b.cx(sign, c_lo[0]);
-    b.cx(source[0], target[0]);
+    if !low0 {
+        b.cx(source[0], target[0]);
+    }
     b.free_vec(&c_lo[..low - 1]);
 
     // High chunk: positions low..n, carry-in `boundary`. REPORT5 §3: on a
@@ -1483,6 +1513,9 @@ fn signed_add_wrapping_sigma_split(
     b.free(boundary);
 
     for &q in target {
+        if low0 && q == target[0] {
+            continue;
+        }
         b.cx(sign, q);
     }
 }
@@ -1500,6 +1533,7 @@ fn signed_add_wrapping_sigma(
     target: &[QubitId],
     target0_is_one: bool,
     top_skip: bool,
+    low0: bool,
 ) {
     let n = source.len();
     assert_eq!(n, target.len());
@@ -1523,6 +1557,9 @@ fn signed_add_wrapping_sigma(
     let top_skip = top_skip && n >= 6;
 
     for &q in target {
+        if low0 && q == target[0] {
+            continue;
+        }
         b.cx(sign, q);
     }
 
@@ -1635,10 +1672,15 @@ fn signed_add_wrapping_sigma(
         b.x(source[1]);
     }
     b.cx(source[1], target[1]);
-    b.cx(source[0], target[0]);
+    if !low0 {
+        b.cx(source[0], target[0]);
+    }
     b.free_vec(&carries);
 
     for &q in target {
+        if low0 && q == target[0] {
+            continue;
+        }
         b.cx(sign, q);
     }
 }
@@ -1650,9 +1692,10 @@ fn signed_add_wrapping(
     target: &[QubitId],
     target0_is_one: bool,
     top_skip: bool,
+    low0: bool,
 ) {
     if std::env::var_os("SUB4_PINGPONG_GENERIC_WALK").is_none() {
-        return signed_add_wrapping_sigma(b, sign, source, target, target0_is_one, top_skip);
+        return signed_add_wrapping_sigma(b, sign, source, target, target0_is_one, top_skip, low0);
     }
     for &q in target {
         b.cx(sign, q);
@@ -1860,10 +1903,31 @@ fn walk_round(
     let sign = b.alloc_qubit();
     b.cx(target[1], sign);
     b.cx(source[1], sign);
+    let low0 = std::env::var_os("SUB4_PP_LOW0_LOAN_OFF").is_none();
+    if low0 {
+        // Loan the odd passengers across the add.  `source[0]` is provably 1
+        // and `target[0]` is 1 before the add and 0 after, so the adder's only
+        // [0] gates (the two sandwich CXs and the bit-0 sum CX) are redundant
+        // and the wires can sit in the free pool through the carry ladder.
+        b.x(source[0]);
+        b.free(source[0]);
+        b.x(target[0]);
+        b.free(target[0]);
+    }
     let top_skip = walk_top_skip(round, rounds);
-    match walk_low_chunk(round, width) {
-        Some(low) => signed_add_wrapping_sigma_split(b, sign, source, target, true, low, top_skip),
-        None => signed_add_wrapping(b, sign, source, target, true, top_skip),
+    let low_chunk = walk_low_chunk(round, width);
+    if std::env::var_os("SUB4_TRACE_WALK").is_some() {
+        eprintln!("TRACE_WALK phase={} round={} width={} low={:?} active={}",
+            b.phase, round, width, low_chunk, b.active_qubits);
+    }
+    match low_chunk {
+        Some(low) => signed_add_wrapping_sigma_split(b, sign, source, target, true, low, top_skip, low0),
+        None => signed_add_wrapping(b, sign, source, target, true, top_skip, low0),
+    }
+    if low0 {
+        b.reacquire(target[0]);
+        b.reacquire(source[0]);
+        b.x(source[0]);
     }
     for i in 0..width - 1 {
         b.swap(target[i], target[i + 1]);
@@ -1910,10 +1974,25 @@ fn walk_back_round(
         b.swap(target[i], target[i + 1]);
     }
     b.x(sign);
+    let low0 = std::env::var_os("SUB4_PP_LOW0_LOAN_OFF").is_none();
+    if low0 {
+        // The rotation undo leaves `target[0]` at 0 and `source[0]` at 1, and
+        // the reverse add returns `target[0]` to 1: the same loan as the
+        // forward walk, zero Toffoli, zero phase.
+        b.free(target[0]);
+        b.x(source[0]);
+        b.free(source[0]);
+    }
     let top_skip = walk_top_skip(round, rounds);
     match walk_low_chunk(round, width) {
-        Some(low) => signed_add_wrapping_sigma_split(b, sign, source, target, false, low, top_skip),
-        None => signed_add_wrapping(b, sign, source, target, false, top_skip),
+        Some(low) => signed_add_wrapping_sigma_split(b, sign, source, target, false, low, top_skip, low0),
+        None => signed_add_wrapping(b, sign, source, target, false, top_skip, low0),
+    }
+    if low0 {
+        b.reacquire(target[0]);
+        b.x(target[0]);
+        b.reacquire(source[0]);
+        b.x(source[0]);
     }
     b.x(sign);
     b.cx(target[1], sign);
@@ -2099,7 +2178,7 @@ fn value_walk(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, rounds: usi
         let sign = b.alloc_qubit();
         b.cx(target[1], sign);
         b.cx(source[1], sign);
-        signed_add_wrapping(b, sign, source, target, true, walk_top_skip(round, rounds));
+        signed_add_wrapping(b, sign, source, target, true, walk_top_skip(round, rounds), false);
         tape.push(sign);
 
         for i in 0..width - 1 {
@@ -2153,7 +2232,6 @@ fn value_walk_back(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, tape:
             continue;
         }
 
-        let sign = tape[round];
         let (source, target) = if round.is_multiple_of(2) {
             (&u[..width], &v[..width])
         } else {
@@ -2163,8 +2241,9 @@ fn value_walk_back(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, tape:
         for i in (0..width - 1).rev() {
             b.swap(target[i], target[i + 1]);
         }
+        let sign = tape[round];
         b.x(sign);
-        signed_add_wrapping(b, sign, source, target, false, walk_top_skip(round, rounds));
+        signed_add_wrapping(b, sign, source, target, false, walk_top_skip(round, rounds), false);
         b.x(sign);
         b.cx(target[1], sign);
         b.cx(source[1], sign);
@@ -2242,6 +2321,9 @@ fn chunk_add(
     }
 
     let owned = num_carries - usize::from(carry_out.is_some());
+    if std::env::var_os("SUB4_TRACE_PEAK").is_some() && b.active_qubits + owned as u32 + 10 >= b.peak_qubits {
+        eprintln!("TRACE_PEAK chunk_add width={} owned={} active={} peak={} ops={}", width, owned, b.active_qubits, b.peak_qubits, b.ops.len());
+    }
     let mut carries = b.alloc_qubits(owned);
     if let Some(carry) = carry_out {
         carries.push(carry);
@@ -2357,7 +2439,7 @@ fn add_chunked_measured_with(
 ) -> Option<QubitId> {
     let n = addend.len();
     let final_carry = carry_out.is_some() || late_carry_out;
-    let bounds = match ladder_target_now() {
+    let mut bounds = match ladder_target_now() {
         None => chunk_bounds(n, replay_chunk()),
         Some(v) => match legacy_width(v) {
             Some(width) => chunk_bounds(n, width),
@@ -2365,6 +2447,28 @@ fn add_chunked_measured_with(
                 .unwrap_or_else(|| chunk_bounds(n, n.div_ceil(12))),
         },
     };
+    // Binding-aware re-solve: the realized footprint of this add is the
+    // pre-active plus (ladder - 1).  When that would hit the realized peak
+    // (1264), re-run the solver with a target one below the standard ladder,
+    // so the realized footprint drops by one.  Non-binding rounds keep the
+    // cheapest layout, byte-identically to the base.
+    if solver_peak_safe() {
+        if let Some(v) = ladder_target_now() {
+            if legacy_width(v).is_none() {
+                let sizes: Vec<usize> = bounds.iter().map(|&(lo, hi)| hi - lo).collect();
+                let ladder = layout_ladder(&sizes, final_carry);
+                if b.active_qubits as usize + ladder >= 1264 {
+                    if std::env::var_os("SUB4_TRACE_PEAK").is_some() {
+                        eprintln!("TRACE_PEAK solver_peak_safe refit ladder={} -> {} ops={}",
+                            ladder, ladder.saturating_sub(1), b.ops.len());
+                    }
+                    if let Some(tight) = chunk_layout(n, ladder.saturating_sub(1), final_carry) {
+                        bounds = tight;
+                    }
+                }
+            }
+        }
+    }
     let legacy = std::env::var_os("SUB4_PP_LEGACY_CHUNK_ORDER").is_some();
     let erase = |b: &mut B, carry: QubitId, lo: usize, hi: usize| {
         let width = hi - lo;
@@ -2479,7 +2583,15 @@ fn fused_fold_maskfree(
     // The final carry is needed only as an XOR into the top output bit. Emit
     // it directly there, matching the exact terminal stage used by the split
     // walk adder, and retain carry wires only through position width - 3.
+    // SUB4_PP_FOLD_TERMINAL3: stop the chain one position earlier still and
+    // close the top three sum bits in a three-position terminal stage.  The
+    // last ladder CCX moves into the stage, so the Toffoli count is
+    // unchanged; the staged middle carry rides in `carries[1]` after that
+    // wire's own reverse step retires it early.
     let num_carries = width - 3;
+    if std::env::var_os("SUB4_TRACE_PEAK").is_some() && b.active_qubits + num_carries as u32 + 10 >= b.peak_qubits {
+        eprintln!("TRACE_PEAK fold width={} num_carries={} active={} peak={} ops={}", width, num_carries, b.active_qubits, b.peak_qubits, b.ops.len());
+    }
     let carries = b.alloc_qubits(num_carries);
 
     for offset in 0..num_carries {
@@ -2512,26 +2624,28 @@ fn fused_fold_maskfree(
         }
     }
 
-    let i = width - 2;
-    let previous = carries.last().copied().unwrap_or(first_carry);
-    let selectors = controls(i);
-    if selectors.is_empty() {
-        b.cx(previous, acc[i]);
-        b.ccx(previous, acc[i], acc[width - 1]);
-        b.cx(previous, acc[width - 1]);
-    } else {
-        let operand = selectors[0];
-        for &control in &selectors[1..] {
-            b.cx(control, operand);
-        }
-        b.cx(previous, operand);
-        b.cx(previous, acc[i]);
-        b.ccx(operand, acc[i], acc[width - 1]);
-        b.cx(previous, acc[width - 1]);
-        b.cx(previous, operand);
-        b.cx(operand, acc[i]);
-        for &control in selectors[1..].iter().rev() {
-            b.cx(control, operand);
+    {
+        let i = width - 2;
+        let previous = carries.last().copied().unwrap_or(first_carry);
+        let selectors = controls(i);
+        if selectors.is_empty() {
+            b.cx(previous, acc[i]);
+            b.ccx(previous, acc[i], acc[width - 1]);
+            b.cx(previous, acc[width - 1]);
+        } else {
+            let operand = selectors[0];
+            for &control in &selectors[1..] {
+                b.cx(control, operand);
+            }
+            b.cx(previous, operand);
+            b.cx(previous, acc[i]);
+            b.ccx(operand, acc[i], acc[width - 1]);
+            b.cx(previous, acc[width - 1]);
+            b.cx(previous, operand);
+            b.cx(operand, acc[i]);
+            for &control in selectors[1..].iter().rev() {
+                b.cx(control, operand);
+            }
         }
     }
     for control in controls(width - 1) {
```

