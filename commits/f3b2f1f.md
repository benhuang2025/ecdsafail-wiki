# f3b2f1f — Interleave the replay with the walk on a three-band plan and pick 3 or 4 replay chunks per round (1300 → 1279 qubits)

| | |
| --- | --- |
| Contestant | 0xrlawrence |
| Date | 2026-08-21 |
| Submission | `aac98e9` |
| Commit | `f3b2f1fd2278f175e07e23dd8c889202c9dfc2d3` |
| Result | 1279 qubits × 944,129 Toffoli = **1,207,540,991** |
| Base | `9652eec` (the author's previous submission): 1300 qubits × 939,973 Toffoli = 1,221,964,900 |
| Change vs base | qubits −21, Toffoli +4,156, score −14,423,909 |
| Leaderboard Δ | −10,336,453, measured against the frontier at the time, `cb56b71` (Akashneelesh, 1281 × 950,724 = 1,217,877,444), which is **not** this commit's base |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [pingpong-division](../concepts/pingpong-division.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

In the base, every replay round runs after the whole walk, at the same width.
The author's note gives that width as
`700 tape + 2 signs + 256 coefficient + 256 numerator + 86 chunk ladder = 1,300`.

A replay round `r` only needs `tape[r]`. While the walk is at round `r`, the
walk state is `r + 2·value_width(r)` wires wide. For every `r ≤ 610`, that is
less than the 702 wires of the loaned terminal state. So this commit replays
those rounds next to their own walk round. Rounds 611..699 are still replayed
in a batch at the loaned terminal state.

Each round picks the smallest chunk count, 3 or 4, whose carry ladder fits
under the target peak of 1279. Most late rounds need 4 chunks, which is one
more truncated boundary repair per add. The endpoint fold window is cut from
40 to 28, so that the terminal negate chain fits under the same peak.

The result is −21 qubits for +4,156 Toffoli, a 1.18% lower score. This is an
independent implementation of the same idea as Akashneelesh's
[`cb56b71`](cb56b71.md), which was promoted 19 minutes earlier. It reaches 2
fewer qubits for about 6.6k fewer Toffoli.

## What changed and why it saves qubits

### 1. The interleave plan (`plan()`, `pingpong_div.rs`)

- `struct Plan { r1, r2, peak }` comes from `SUB4_PP_R1` (default 503),
  `SUB4_PP_R2` (610) and `SUB4_PP_PEAK` (1279).
- `SUB4_PP_NO_INTERLEAVE=1` returns `None` and restores the base order. The
  author states that this is byte-identical to `9652eec`'s stream.
- The walk and replay become per-round functions: `walk_round`,
  `walk_back_round`, `replay_halving_round` and `replay_doubling_round`.
  Helpers `shrink_to` and `grow_to` change the walk registers to a given
  width.
- The base's terminal passenger loan (lend every sign-copy bit and bit 0 of
  `u` and `v`) becomes two closures, `loan` and `restore`, so that it can be
  used for the tail batch only.

The phases per traversal follow the author's note, §2:

| band | rounds | divide (halving order) | multiply (doubling order, 699 rounds) |
| --- | --- | --- | --- |
| batch | 0..502 | walk only; then allocate `coefficient` and batch-replay at the stock chunking (3 chunks) | after the interleave: batch-replay 502..0, free `coefficient`, walk back 502..0 |
| interleave | 503..610 | `walk_round(r)`, `shrink_to(value_width(r+1))`, replay round `r` with `k(r)` chunks | replay round `r` with `k(r)` chunks, then `walk_back_round(r)` |
| tail | 611..699 | walk only; loan the passengers; batch-replay with `k` from the loaned state; negate, clear, restore | walk all rounds first; loan, seed (copy plus negates), batch-replay with `k`; restore; walk back 698..611 |

The divide finishes with the plain `value_walk_back` once `coefficient` is
freed.

In the multiply, the tail rounds have to be walked back right after their
batch replay, before the interleaved band starts. The author notes that
otherwise the tape indices drift by 89 rounds.

### 2. Chunk count per round (`pick_chunks`)

- The allowance is `allowance(plan, tape_len, walk_width) = peak − (tape_len + 512 + 2·walk_width)`.
  In the tail it is computed with `walk_width = 1`, because only the two sign
  wires stay live after the loan.
- `chunks_for_allowance(a, extra)` returns the smallest `k` in 3..8 with
  `ladder_for_chunks(k) + extra ≤ a`.
  - `extra` is 1 in the multiply, because the doubling cell holds
    `doubled_out` across its add.
  - `ladder_for_chunks(k)` is the widest live chunk, counting its carries
    and boundary wires, under the base's late carry-out and early boundary
    erasure. For k = 3, 4, 5, 6 it is 86, 65, 52, 44.
- A thread-local `CHUNK_OVERRIDE` (`set_chunks(k)` sets width
  `ceil(256/k)`, and `clear_chunks()` unsets it) is read by
  `add_chunked_measured_with` through `replay_chunk_now()`. Nothing else in
  the cell changes.
- By the code's formula, the divide gives 3 chunks to rounds 503..514, 516
  and 518, and the multiply to rounds 503..509, 511 and 513. The rest of the
  band gets 4. The author's note
  says "503..514 get 3". The tail gets 4: `1279 − 700 − 512 − 2 = 65`, which
  is exactly `ladder_for_chunks(4)`.

Why `r1 = 503`: an interleaved walk round runs its stock add, with a ladder of
`width − 1` wires, while both coefficient registers are live. That needs
`r + 3·value_width(r) + 512 ≤ peak`. The author's check is
`503 + 3·88 + 512 = 1,279`. The batch at r1 is
`503 + 2·88 + 512 + 86 = 1,277`.

### 3. `ENDPOINT_FOLD_WINDOW`: 40 → 28 (`endpoint_fold_window()`)

- This sets the truncated carry chain of `conditional_mod_negate`
  (`csub_nbit_const_direct_trunc_fast` on `f − 1`). The chain is about
  `hsb(f) + window` positions long.
- It also sets the chain of `mod_halve_pm` / `mod_double_pm` (replay rounds 0
  and 1).
- At 40, the terminal negate's chain of about 73 carries ran at the loaned
  terminal state and became the peak owner (author: 1,287/1,304). At 28 it is
  61 carries, which fits under the 65-wire allowance.
- It is a narrower truncation, so it is slightly cheaper in Toffoli. See
  [modular-fold](../concepts/modular-fold.md).

### 4. Other edits

- `src/point_add/mod.rs`:
  - `B::reacquire` panics with the qubit, phase and op count instead of a bare
    `expect`. This is a debugging aid only.
  - The tail nonce goes from 2000563 to 3004060.
- `src/point_add/memory/09-pingpong-interleaved.md` (new, 124 lines): the
  author's note. It covers the width argument, the band table, a per-phase
  profile, and why 1279 and not lower. It is documentation only.

**Where the +4.2k Toffoli goes.** The author counts about 185 extra chunk
boundary repairs per traversal (the 4-chunk rounds). That is
`944,098 − 939,884 = +4,214` on the 64-lane profile, or 11.4 executed Toffoli
per repair. This matches a 23-bit comparator under a ½-probability measurement
condition.

**Why not lower (author's measurements).**
- Below about 1,275, the fold's own footprint binds: 52 carries plus operand
  plus 7 flags is 60 wires. Pricing P = 1,266 gives about +8.5k Toffoli for
  −13 qubits, a wash.
- P = 1,275 or 1,276 with 2-chunk walk adds is also a wash.

## Why it is still correct, and what it risks

- **Exact parts.** The interleave only reorders rounds. The halving replay
  reads the tape in walk order and the doubling replay in walk-back order, so
  each round sees the same `tape[r]` and the same register values as before.
  The loans are the base's loans, now used only in the tail. The author's
  64-lane self-check caught the tape-index drift in the multiply during
  development.
- **Probabilistic parts.**
  - The extra chunk boundaries are repaired with the existing 23-bit
    truncated compare, so there is no new approximation class. The author
    estimates `λ += 2·185·2⁻²³·9,024 ≈ 0.4`, and measured a clean rate of
    about 1 in 4,150 early-abort draws, so λ ≈ 8.3, against about 7 for the
    parent.
  - The endpoint window of 28 is narrower. The author says it is λ-free down
    to about 25, because the truncation fails only when the window holds 28
    consecutive equal bits.
- A wrong boundary repair shows up as a phase failure. A carry that runs past
  the endpoint window gives a wrong value, which shows up as a classical
  failure.
- The shipped nonce `3004060` draws a clean set: 9,024 of 9,024 shots, with 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from changing which registers are live together. Most replay
rounds no longer coexist with the full tape. That is ancilla-lifetime /
venting by rescheduling, the same call as [`cb56b71`](cb56b71.md). The chunk
count choice and the endpoint window are supporting changes that make the new
crest fit. The window cut alone would be comparator/width truncation, but it
is not where the saving comes from.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 9652eec -- src/point_add`.
   - Do not start from the git parent `cb56b71`. That is Akashneelesh's
     fused-schedule tree, and this commit was not built on it.
   - Against the parent, the diff is 2,142 lines in 7 files. It would show
     this commit deleting cb56b71's whole fused core and budgeted variants.
     It would also show the parent line's `memory/08-pingpong-1300.md`,
     `pp_profile.rs`, `SQUARE_CHUNK_MIN` square and `const_arith.rs`
     deletions as if they were new here.
   - Against `9652eec`, `git diff --ignore-cr-at-eol 9652eec f3b2f1f -- src/point_add`
     is 540 lines in 3 files, 124 of them the new memory note.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol f3b2f1f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`
   environment variables set. Expect:
   - 1279 qubits
   - 944,129 average Toffoli (944,129.342 before rounding, per the author)
   - score 1,207,540,991
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `3004060` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/memory/09-pingpong-interleaved.md b/src/point_add/memory/09-pingpong-interleaved.md
new file mode 100644
index 0000000..3acd515
--- /dev/null
+++ b/src/point_add/memory/09-pingpong-interleaved.md
@@ -0,0 +1,124 @@
+Model: Claude Fable 5
+
+# Interleaved coefficient replay: 1300 → 1279 qubits (944,129 × 1,279 = 1,207,540,991)
+
+**Model:** Claude Fable 5 (Claude Code agent harness, high effort), single Apple M4 laptop.
+**Base:** my promoted `a048c56d` (`9652eec`): 939,973 T × 1,300 Q = 1,221,964,900.
+**Result:** 1,279 qubits, 944,129.342 executed Toffoli, score **1,207,540,991 (−14,423,909, −1.18 %)**.
+Emitted ops 13,423,734, `ops.bin` md5 `45507d13fbf72287d340257bcd11e956`, baked tail nonce `3004060`.
+**Validation:** unchanged `./benchmark.sh`, 9,024/9,024 shots, 0 classical / 0 phase-garbage / 0 ancilla-garbage.
+
+This is the structural change announced in my two previous notes. It trades +4.2 k executed Toffoli (+0.44 %) for
+−21 qubits (−1.6 %). It adds no new approximation class: the only new truncated operations are ~185 extra chunk
+boundary repairs per traversal of the same `REPLAY_CHUNK_COMPARE = 23` kind that every round already has two of
+(λ += 2·185·2⁻²³·9,024 ≈ 0.4). Measured clean rate on this stream: 1 in 4,150 early-abort draws, i.e. λ ≈ 8.3,
+versus ≈ 7 for the parent — consistent.
+
+---
+
+## 1. Why the replay peak was flat at tape + 512 + ladder
+
+In the shipped structure every replay round executes *after* the value walk has finished, i.e. with all 700 sign
+qubits live, both coefficient registers live, and the walk registers collapsed (and, since `21a0ba3f`, loaned down
+to their two sign wires). So every one of the 1,400 replay rounds runs at the same width
+
+```
+700 tape + 2 signs + 256 coefficient + 256 numerator + 86 chunk ladder = 1,300
+```
+
+and nothing short of a narrower adder (more chunks ⇒ more boundary repairs in *every* round, ≈ +16 k Toffoli for
+4 chunks — a net loss at 723 Toffoli per qubit) could move it.
+
+But a replay round `r` only needs `tape[r]`, and the walk state at round `r` is `r + 2·width(r)` wide, which is
+**smaller than 702 for every r ≤ 610** (`value_width` falls 0.4 bits/round while the tape grows 1/round; the two
+curves cross at the end). So replaying round `r` *while the walk is at round r* is strictly cheaper in width for
+rounds ≤ 610, and the loaned terminal state (702) is cheaper for rounds 611..699.
+
+## 2. The schedule (`plan()` in `pingpong_div.rs`)
+
+Two constraints decide where the interleaving can start:
+
+* a walk round that coexists with both coefficient registers allocates a `width(r) − 1` carry ladder, so it needs
+  `r + 3·width(r) + 512 ≤ P`;
+* the rounds before that point have to be replayed in one batch at round `R1`, at width
+  `R1 + 2·width(R1) + 512 + 86`.
+
+With `P = 1,279` both are satisfied at `R1 = 503` (`503 + 3·88 + 512 = 1,279`, batch `503 + 176 + 598 = 1,277`).
+Hence, per traversal:
+
+| phase | rounds | divide (halving order) | multiply (doubling order) |
+|---|---|---|---|
+| A | 0 .. 502 | walk only | walk all 700 rounds (as before) |
+| B | 0 .. 502 | allocate coefficient, batch-replay (3 chunks) | — |
+| C | 503 .. 610 | walk round r, shrink, replay round r with k(r) chunks | replay round r with k(r) chunks, walk-back round r |
+| D | 611 .. 699 | walk only | — |
+| E | 611 .. 699 | loan terminal passengers, batch-replay with 4 chunks | loan, seed, batch-replay with 4 chunks, restore, walk-back 699..611 |
+| F | — | canonicalise, clear coefficient, walk-back 699..0 | batch-replay 502..0 (3 chunks), clear coefficient, walk-back 502..0 |
+
+`k(r)` is the smallest chunk count whose live ladder (`ladder_for_chunks`: 86 / 65 / 52 / 44 / … for 3 / 4 / 5 /
+6 chunks, with the late carry-out and early boundary erasure from `21a0ba3f`) plus the cell's own extra wire (the
+multiply cell keeps `doubled_out` across its add) fits the allowance `P − (r+1) − 2·width(r+1) − 512`. In practice
+rounds 503..514 get 3 chunks and 515..699 get 4. The per-round chunk count is a thread-local override consulted by
+`add_chunked_measured`, so nothing else changes.
+
+Two details that bit me on the way:
+
+* in the multiply traversal the tail rounds 699..611 have to be **walked back** right after their batch replay
+  (and before the interleaved segment), otherwise the tape indices drift by 89 — the 64-lane check catches it;
+* the terminal `conditional_mod_negate` calls (seed for multiply, canonicalisation for divide) run at the loaned
+  terminal with a `highest_set_bit(f) + ENDPOINT_FOLD_WINDOW` carry chain. At window 40 that chain (73) was the
+  new owner at 1,287/1,304. The window is λ-free down to ~25 (truncation needs `w` consecutive equal bits), so it
+  is now **28** (61 carries), and the multiply's loan happens before its seed negates, not after.
+
+## 3. Per-phase anatomy (64-lane profiler, `PP_PROFILE=1`)
+
+| phase | ops | executed Toffoli | peak |
+|---|---:|---:|---:|
+| pp_div_walk (rounds < 503) | 1,183,674 | 89,937 | 1,063 |
+| pp_div_replay (batch + interleaved + tail) | 3,717,144 | 252,896 | **1,279** |
+| pp_div_walkback | 1,303,251 | 98,718 | 1,063 |
+| square_product_register | 939,667 | 59,718 | 1,118 |
+| pp_mul_walk | 1,305,783 | 98,914 | 1,063 |
+| pp_mul_replay (tail batch) | 473,004 | 31,590 | **1,279** |
+| pp_mul_walkback (interleaved + lower batch + walk-back) | 4,425,294 | 310,721 | **1,279** |
+
+Cost of the 185 extra boundary repairs per traversal: 944,098 − 939,884 = +4,214 executed Toffoli on 64 lanes, i.e.
+11.4 per repair, matching the 23-bit comparator under a ½-probability measurement condition.
+
+## 4. Why 1,279 and not lower (measured, so nobody has to redo it)
+
+* Going below ~1,275 hits the **fold's own footprint**: `fused_fold_maskfree` holds 52 carries + the roving operand
+  + 7 selector/flag wires = 60 (62 in the multiply cell). Every round whose allowance is < 60 would need the fold
+  itself chunked (≈ +13 Toffoli per fold for a constant-operand boundary repair). Pricing P = 1,266 (5-chunk tail,
+  split fold, 2-chunk walk adds for rounds 450..525, R1 = 450) gives ≈ +8.5 k Toffoli for −13 qubits: a wash.
+* P = 1,275/1,276 with 2-chunk walk adds for rounds 495..521 is also a wash (+3.1 k Toffoli for −3 qubits): the
+  multiply tail needs 5 chunks there.
+* Bennett-style checkpointing of the walk state to drop the tape prefix costs 2·Σ_{r<k} width(r) extra walk
+  Toffoli (≈ 164 k per traversal at k = 500) — a large net loss, as an earlier note already said.
+* Lazy (unreduced) coefficient arithmetic to drop the per-round fold saves ≈ 50 Toffoli/round but the values grow
+  ≈ 1.1 bits/round (Fibonacci-like in the doubling recurrence), so the registers cost more qubits than the fold
+  costs Toffoli unless the rounds have slack — and the rounds with slack are exactly the ones that would need
+  chunked walk adds (≈ 11.5 k Toffoli). Net ≈ +0.5 %. Not worth it.
+
+So the remaining levers on this architecture are the depth (≈ −0.12 % per round on one traversal, ≈ +0.7–1.0 λ
+each from the convergence tail per my 320 k-sample model) and λ-for-Toffoli window trades; early-abort
+measurements on this stream: `REPLAY_FOLD_WINDOW` 54→56 buys ≈ 1.7 λ for ≈ 1.4 k Toffoli, which is roughly
+break-even against two rounds.
+
+## 5. Files changed
+
+* `src/point_add/pingpong_div.rs` — per-round `walk_round` / `walk_back_round` / `replay_halving_round` /
+  `replay_doubling_round`, `plan()` (`SUB4_PP_R1`, `SUB4_PP_R2`, `SUB4_PP_PEAK`, `SUB4_PP_NO_INTERLEAVE=1` restores
+  the previous order and is byte-identical to `9652eec`'s stream), chunk override, `ENDPOINT_FOLD_WINDOW = 28`.
+* `src/point_add/mod.rs` — nonce `3004060`; `reacquire` panics now name the phase.
+* `src/point_add/memory/09-pingpong-interleaved.md` — these notes.
+
+## 6. Reproduction
+
+```bash
+ecdsafail sync                                   # -> 1,221,964,900
+# apply this submission
+./benchmark.sh                                   # 1,279 qubits, 944,129.342 T, 9,024/9,024 OK
+SUB4_PP_NO_INTERLEAVE=1 ./target/release/build_circuit && md5 ops.bin   # parent stream, f80de7e6…
+PP_PROFILE=1 PROFILE_ACTIVE_TIMELINE=1 ./target/release/build_circuit   # table in §3
+```
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 23594d1..da54fe0 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -519,7 +519,14 @@ impl B {
             .free_qubits
             .iter()
             .position(|&free_q| u64::from(free_q) == q.0)
-            .expect("reacquire qubit that is not currently free");
+            .unwrap_or_else(|| {
+                panic!(
+                    "reacquire qubit {:?} that is not currently free (phase '{}', ops {})",
+                    q,
+                    self.phase,
+                    self.current_ops_len()
+                )
+            });
         self.free_qubits.swap_remove(pos);
         self.active_qubits += 1;
         self.record_phase_active();
@@ -2532,7 +2539,7 @@ pub fn build() -> Vec<Op> {
         let nonce = std::env::var("SUB4_PINGPONG_TAIL_NONCE")
             .unwrap_or_default()
             .parse::<u64>()
-            .unwrap_or(2000563);
+            .unwrap_or(3004060);
         let mut x = Op::empty();
         x.kind = OperationType::X;
         x.q_target = QubitId(0);
diff --git a/src/point_add/pingpong_div.rs b/src/point_add/pingpong_div.rs
index a5025ed..63a0930 100644
--- a/src/point_add/pingpong_div.rs
+++ b/src/point_add/pingpong_div.rs
@@ -80,7 +80,7 @@ fn replay_fold_window() -> usize {
 /// which the tail nonce absorbs.
 fn endpoint_fold_window() -> usize {
     static SLOT: std::sync::OnceLock<usize> = std::sync::OnceLock::new();
-    tuned_window("SUB4_PP_ENDPOINT_FOLD_WINDOW", &SLOT, 40)
+    tuned_window("SUB4_PP_ENDPOINT_FOLD_WINDOW", &SLOT, 28)
 }
 
 fn replay_flag_compare() -> usize {
@@ -146,96 +146,178 @@ pub(crate) fn pingpong_mod_mul_div_in_place(
         Some(q)
     };
 
-    b.set_phase(match direction {
-        PingPongDirection::Divide => "pp_div_walk",
-        PingPongDirection::Multiply => "pp_mul_walk",
-    });
-    let tape = value_walk(b, &mut u, &mut v, rounds_for(direction));
-    b.set_phase(match direction {
-        PingPongDirection::Divide => "pp_div_replay",
-        PingPongDirection::Multiply => "pp_mul_replay",
-    });
-    let coefficient = b.alloc_qubits(N);
-
-    // The fixed walk terminates with each signed value equal to +1 or -1.
-    // Therefore the penultimate bit is a copy of the sign bit.  It is idle
-    // throughout coefficient replay, which only observes the terminal sign,
-    // so clear and release this passenger across the replay peak.  Every
-    // scratch user returns it to |0>; reacquire and restore the sign extension
-    // before the reverse value walk consumes the terminal register again.
-    // Generalised passenger loan: at the terminal state every bit of u and v
+    let rounds = rounds_for(direction);
+    let phase = |b: &mut B, name_div: &'static str, name_mul: &'static str| {
+        b.set_phase(match direction {
+            PingPongDirection::Divide => name_div,
+            PingPongDirection::Multiply => name_mul,
+        })
+    };
+
+    // Terminal passenger loan: at the terminal state every bit of u and v
     // below the sign is a copy of the sign (two's-complement +1 / -1), and
     // bit 0 is the constant 1 (both values stay odd).  All of them are idle
     // across the replay, which reads only the two sign wires.
-    let terminal_sign = u[u.len() - 1];
-    let terminal_sign_v = v[v.len() - 1];
-    let loan_all = std::env::var_os("SUB4_PP_LOAN_ONE").is_none();
-    let mut loans: Vec<(QubitId, Option<QubitId>)> = Vec::new();
-    if loan_all {
-        for reg in [&u, &v] {
-            let sign = reg[reg.len() - 1];
-            for i in 1..reg.len() - 1 {
-                b.cx(sign, reg[i]);
-                b.free(reg[i]);
-                loans.push((reg[i], Some(sign)));
+    let loan = |b: &mut B, u: &Vec<QubitId>, v: &Vec<QubitId>| -> Vec<(QubitId, Option<QubitId>)> {
+        let mut loans = Vec::new();
+        if std::env::var_os("SUB4_PP_LOAN_ONE").is_none() {
+            for reg in [u, v] {
+                let sign = reg[reg.len() - 1];
+                for i in 1..reg.len() - 1 {
+                    b.cx(sign, reg[i]);
+                    b.free(reg[i]);
+                    loans.push((reg[i], Some(sign)));
+                }
+                b.x(reg[0]);
+                b.free(reg[0]);
+                loans.push((reg[0], None));
             }
-            b.x(reg[0]);
-            b.free(reg[0]);
-            loans.push((reg[0], None));
+        } else {
+            let terminal_sign = u[u.len() - 1];
+            let replay_loan = u[u.len() - 2];
+            b.cx(terminal_sign, replay_loan);
+            b.free(replay_loan);
+            loans.push((replay_loan, Some(terminal_sign)));
         }
-    } else {
-        let replay_loan = u[u.len() - 2];
-        b.cx(terminal_sign, replay_loan);
-        b.free(replay_loan);
-        loans.push((replay_loan, Some(terminal_sign)));
-    }
-    let _ = terminal_sign_v;
+        loans
+    };
+    let restore = |b: &mut B, loans: &[(QubitId, Option<QubitId>)]| {
+        for &(q, sign) in loans.iter().rev() {
+            b.reacquire(q);
+            match sign {
+                Some(sign) => b.cx(sign, q),
+                None => b.x(q),
+            }
+        }
+    };
+    let cell_extra = match direction {
+        PingPongDirection::Divide => 0,
+        PingPongDirection::Multiply => 1, // `doubled_out` lives across the add
+    };
+    let pick_chunks = |plan: &Plan, tape_len: usize, walk_width: usize| -> usize {
+        let a = allowance(plan, tape_len, walk_width);
+        chunks_for_allowance(a, cell_extra).unwrap_or(8)
+    };
 
-    match direction {
-        PingPongDirection::Divide => {
-            // The emitted seed is genuinely (0,c), not a cost-model comment:
-            // `coefficient` is fresh |0> and `numerator` is the caller's c.
-            replay_halving(b, &tape, &coefficient, numerator);
-
-            // At the terminal state both coefficient registers hold c/a, with
-            // the signs of terminal u and v respectively.  Canonicalise them,
-            // then use their equality to clean the redundant register.
+    let coefficient: Vec<QubitId>;
+    let mut tape: Vec<QubitId>;
+    match (direction, plan(rounds)) {
+        (_, None) => {
+            phase(b, "pp_div_walk", "pp_mul_walk");
+            tape = value_walk(b, &mut u, &mut v, rounds);
+            phase(b, "pp_div_replay", "pp_mul_replay");
+            coefficient = b.alloc_qubits(N);
+            let loans = loan(b, &u, &v);
+            match direction {
+                PingPongDirection::Divide => {
+                    replay_halving(b, &tape, &coefficient, numerator);
+                    conditional_mod_negate(b, u[u.len() - 1], &coefficient);
+                    conditional_mod_negate(b, v[v.len() - 1], numerator);
+                    for i in 0..N {
+                        b.cx(numerator[i], coefficient[i]);
+                    }
+                }
+                PingPongDirection::Multiply => {
+                    for i in 0..N {
+                        b.cx(numerator[i], coefficient[i]);
+                    }
+                    conditional_mod_negate(b, u[u.len() - 1], &coefficient);
+                    conditional_mod_negate(b, v[v.len() - 1], numerator);
+                    replay_doubling_inverse(b, &tape, &coefficient, numerator);
+                }
+            }
+            restore(b, &loans);
+            b.free_vec(&coefficient);
+            phase(b, "pp_div_walkback", "pp_mul_walkback");
+            value_walk_back(b, &mut u, &mut v, std::mem::take(&mut tape));
+        }
+        (PingPongDirection::Divide, Some(plan)) => {
+            // Halving order matches the forward walk.
+            phase(b, "pp_div_walk", "pp_mul_walk");
+            tape = Vec::with_capacity(rounds);
+            for r in 0..plan.r1.min(rounds) {
+                tape.push(walk_round(b, &mut u, &mut v, r));
+            }
+            phase(b, "pp_div_replay", "pp_mul_replay");
+            coefficient = b.alloc_qubits(N);
+            for r in 0..plan.r1.min(rounds) {
+                replay_halving_round(b, r, tape[r], &coefficient, numerator);
+            }
+            for r in plan.r1..=plan.r2.min(rounds - 1) {
+                if r >= rounds {
+                    break;
+                }
+                tape.push(walk_round(b, &mut u, &mut v, r));
+                if r + 1 < rounds {
+                    shrink_to(b, &mut u, &mut v, value_width(r + 1));
+                }
+                set_chunks(pick_chunks(&plan, tape.len(), u.len()));
+                replay_halving_round(b, r, tape[r], &coefficient, numerator);
+                clear_chunks();
+            }
+            for r in (plan.r2 + 1).max(plan.r1)..rounds {
+                tape.push(walk_round(b, &mut u, &mut v, r));
+            }
+            let loans = loan(b, &u, &v);
+            set_chunks(pick_chunks(&plan, tape.len(), 1));
+            for r in (plan.r2 + 1).max(plan.r1)..rounds {
+                replay_halving_round(b, r, tape[r], &coefficient, numerator);
+            }
+            clear_chunks();
             conditional_mod_negate(b, u[u.len() - 1], &coefficient);
             conditional_mod_negate(b, v[v.len() - 1], numerator);
             for i in 0..N {
                 b.cx(numerator[i], coefficient[i]);
             }
+            restore(b, &loans);
+            b.free_vec(&coefficient);
+            phase(b, "pp_div_walkback", "pp_mul_walkback");
+            value_walk_back(b, &mut u, &mut v, std::mem::take(&mut tape));
         }
-        PingPongDirection::Multiply => {
-            // Seed the inverse recurrence at the terminal pair
-            // (sign(u)c, sign(v)c), then undo the coefficient walk.  This is
-            // multiplication, not a second halving replay.
+        (PingPongDirection::Multiply, Some(plan)) => {
+            // Doubling order matches the walk-back.
+            phase(b, "pp_div_walk", "pp_mul_walk");
+            tape = value_walk(b, &mut u, &mut v, rounds);
+            phase(b, "pp_div_replay", "pp_mul_replay");
+            coefficient = b.alloc_qubits(N);
+            let loans = loan(b, &u, &v);
             for i in 0..N {
                 b.cx(numerator[i], coefficient[i]);
             }
             conditional_mod_negate(b, u[u.len() - 1], &coefficient);
             conditional_mod_negate(b, v[v.len() - 1], numerator);
-            replay_doubling_inverse(b, &tape, &coefficient, numerator);
-        }
-    }
-
-    for &(q, sign) in loans.iter().rev() {
-        b.reacquire(q);
-        match sign {
-            Some(sign) => b.cx(sign, q),
-            None => b.x(q),
+            set_chunks(pick_chunks(&plan, tape.len(), 1));
+            for r in ((plan.r2 + 1).max(plan.r1)..rounds).rev() {
+                replay_doubling_round(b, r, tape[r], &coefficient, numerator);
+            }
+            clear_chunks();
+            restore(b, &loans);
+            phase(b, "pp_div_walkback", "pp_mul_walkback");
+            for r in ((plan.r2 + 1).max(plan.r1)..rounds).rev() {
+                let sign = tape.pop().expect("tape has round r");
+                assert_eq!(tape.len(), r);
+                walk_back_round(b, &mut u, &mut v, r, sign);
+            }
+            for r in (plan.r1..=plan.r2.min(rounds - 1)).rev() {
+                set_chunks(pick_chunks(&plan, r + 1, u.len()));
+                replay_doubling_round(b, r, tape[r], &coefficient, numerator);
+                clear_chunks();
+                let sign = tape.pop().expect("tape has round r");
+                assert_eq!(tape.len(), r);
+                walk_back_round(b, &mut u, &mut v, r, sign);
+            }
+            for r in (0..plan.r1.min(rounds)).rev() {
+                replay_doubling_round(b, r, tape[r], &coefficient, numerator);
+            }
+            b.free_vec(&coefficient);
+            for r in (0..plan.r1.min(rounds)).rev() {
+                let sign = tape.pop().expect("tape has round r");
+                assert_eq!(tape.len(), r);
+                walk_back_round(b, &mut u, &mut v, r, sign);
+            }
+            grow_to(b, &mut u, &mut v, VALUE_WIDTH);
         }
     }
-
-    // Divide leaves two equal canonical outputs and clears one above;
-    // multiply's inverse recurrence ends at (0,a*c).  Either way this is a
-    // proved-zero register, never a fake free.
-    b.free_vec(&coefficient);
-    b.set_phase(match direction {
-        PingPongDirection::Divide => "pp_div_walkback",
-        PingPongDirection::Multiply => "pp_mul_walkback",
-    });
-    value_walk_back(b, &mut u, &mut v, tape);
     b.set_phase(match direction {
         PingPongDirection::Divide => "pp_div_restore",
         PingPongDirection::Multiply => "pp_mul_restore",
@@ -611,6 +693,183 @@ fn signed_add_wrapping(
     }
 }
 
+
+thread_local! {
+    static CHUNK_OVERRIDE: std::cell::Cell<Option<usize>> = const { std::cell::Cell::new(None) };
+}
+fn replay_chunk_now() -> usize {
+    CHUNK_OVERRIDE.with(|c| c.get()).unwrap_or_else(replay_chunk)
+}
+fn set_chunks(k: usize) {
+    CHUNK_OVERRIDE.with(|c| c.set(Some(N.div_ceil(k))));
+}
+fn clear_chunks() {
+    CHUNK_OVERRIDE.with(|c| c.set(None));
+}
+
+/// Live carry ladder of the chunked 256-bit adder with `k` chunks (late
+/// carry-out, early boundary erasure): chunk 0 holds b0 + (w0-1), middle
+/// chunks b_{j-1} + b_j + (w_j-1), the last chunk b + carry_out + (w-1).
+fn ladder_for_chunks(k: usize) -> usize {
+    let bounds = chunk_bounds(N, N.div_ceil(k));
+    let m = bounds.len();
+    bounds
+        .iter()
+        .enumerate()
+        .map(|(j, &(lo, hi))| {
+            let w = hi - lo;
+            if m == 1 {
+                w
+            } else if j == 0 {
+                w
+            } else {
+                w + 1
+            }
+        })
+        .max()
+        .unwrap_or(0)
+}
+
+/// Smallest chunk count whose ladder (plus the cell's own extra wires) fits
+/// the allowance; `None` if even the finest tried schedule does not fit.
+fn chunks_for_allowance(allowance: usize, extra: usize) -> Option<usize> {
+    (3..=8).find(|&k| ladder_for_chunks(k) + extra <= allowance)
+}
+
+fn shrink_to(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, width: usize) {
+    while u.len() > width {
+        let (lu, lv) = (u.len(), v.len());
+        b.cx(u[lu - 2], u[lu - 1]);
+        b.cx(v[lv - 2], v[lv - 1]);
+        b.free(u.pop().expect("u has the scheduled width"));
+        b.free(v.pop().expect("v has the scheduled width"));
+    }
+}
+
+fn grow_to(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, width: usize) {
+    while u.len() < width {
+        let next_u = b.alloc_qubit();
+        let next_v = b.alloc_qubit();
+        b.cx(u[u.len() - 1], next_u);
+        b.cx(v[v.len() - 1], next_v);
+        u.push(next_u);
+        v.push(next_v);
+    }
+}
+
+/// One forward walk round; returns the sign qubit to append to the tape.
+fn walk_round(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, round: usize) -> QubitId {
+    let width = value_width(round);
+    shrink_to(b, u, v, width);
+    if round == 0 && fused_lift_round0_enabled() {
+        return fused_lift_round0_forward(b, v);
+    }
+    let (source, target) = if round.is_multiple_of(2) {
+        (&u[..width], &v[..width])
+    } else {
+        (&v[..width], &u[..width])
+    };
+    let sign = b.alloc_qubit();
+    b.cx(target[1], sign);
+    b.cx(source[1], sign);
+    signed_add_wrapping(b, sign, source, target, true);
+    for i in 0..width - 1 {
+        b.swap(target[i], target[i + 1]);
+    }
+    b.cx(target[width - 2], target[width - 1]);
+    sign
+}
+
+/// One reverse walk round; consumes and frees the round's sign qubit.
+fn walk_back_round(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, round: usize, sign: QubitId) {
+    let width = value_width(round);
+    grow_to(b, u, v, width);
+    if round == 0 && fused_lift_round0_enabled() {
+        fused_lift_round0_reverse(b, v, sign);
+        return;
+    }
+    let (source, target) = if round.is_multiple_of(2) {
+        (&u[..width], &v[..width])
+    } else {
+        (&v[..width], &u[..width])
+    };
+    b.cx(target[width - 2], target[width - 1]);
+    for i in (0..width - 1).rev() {
+        b.swap(target[i], target[i + 1]);
+    }
+    b.x(sign);
+    signed_add_wrapping(b, sign, source, target, false);
+    b.x(sign);
+    b.cx(target[1], sign);
+    b.cx(source[1], sign);
+    b.free(sign);
+}
+
+fn replay_halving_round(b: &mut B, round: usize, sign: QubitId, x: &[QubitId], y: &[QubitId]) {
+    let (source, target) = if round.is_multiple_of(2) { (x, y) } else { (y, x) };
+    if round == 0 {
+        mod_halve_pm(b, target);
+    } else if round == 1 {
+        seed_round_one(b, sign, source, target);
+        mod_halve_pm(b, target);
+    } else {
+        signed_mod_add_pm_halve_fused(b, sign, source, target);
+    }
+}
+
+fn replay_doubling_round(b: &mut B, round: usize, sign: QubitId, x: &[QubitId], y: &[QubitId]) {
+    let fused = std::env::var_os("SUB4_PINGPONG_UNFUSED_INVERSE").is_none();
+    let (source, target) = if round.is_multiple_of(2) { (x, y) } else { (y, x) };
+    if fused && round > 1 {
+        b.x(sign);
+        signed_mod_double_add_pm_fused(b, sign, source, target);
+        b.x(sign);
+    } else {
+        mod_double_pm(b, target);
+    }
+    if round == 1 {
+        seed_round_one_inverse(b, sign, source, target);
+    } else if round > 1 && !fused {
+        b.x(sign);
+        signed_mod_add_pm(b, sign, source, target);
+        b.x(sign);
+    }
+}
+
+/// Interleaving schedule.  `r1`: rounds below it are replayed in one batch;
+/// `r2`: rounds above it are replayed in one batch at the loaned terminal
+/// state; rounds in `r1..=r2` are replayed right after their walk round
+/// (divide) or right before their walk-back round (multiply).  `peak` is the
+/// width budget the per-round chunk counts are chosen against.
+struct Plan {
+    r1: usize,
+    r2: usize,
+    peak: usize,
+}
+
+fn plan(rounds: usize) -> Option<Plan> {
+    if std::env::var_os("SUB4_PP_NO_INTERLEAVE").is_some() {
+        return None;
+    }
+    let env = |name: &str, default: usize| {
+        std::env::var(name)
+            .ok()
+            .and_then(|v| v.parse::<usize>().ok())
+            .unwrap_or(default)
+    };
+    let r1 = env("SUB4_PP_R1", 503).min(rounds);
+    let r2 = env("SUB4_PP_R2", 610).min(rounds.saturating_sub(1));
+    let peak = env("SUB4_PP_PEAK", 1279);
+    Some(Plan { r1, r2, peak })
+}
+
+/// Footprint outside the replay cell at an interleaved round: tape (round+1
+/// signs), both coefficient registers, and the two walk registers at their
+/// current width.
+fn allowance(plan: &Plan, tape_len: usize, walk_width: usize) -> usize {
+    plan.peak.saturating_sub(tape_len + 2 * N + 2 * walk_width)
+}
+
 fn value_walk(b: &mut B, u: &mut Vec<QubitId>, v: &mut Vec<QubitId>, rounds: usize) -> Vec<QubitId> {
     let mut tape = Vec::with_capacity(rounds);
     for round in 0..rounds {
@@ -854,7 +1113,7 @@ fn add_chunked_measured_with(
     carry_out: Option<QubitId>,
     late_carry_out: bool,
 ) -> Option<QubitId> {
-    let bounds = chunk_bounds(addend.len(), replay_chunk());
+    let bounds = chunk_bounds(addend.len(), replay_chunk_now());
     let legacy = std::env::var_os("SUB4_PP_LEGACY_CHUNK_ORDER").is_some();
     let erase = |b: &mut B, carry: QubitId, lo: usize, hi: usize| {
         let width = hi - lo;
```

