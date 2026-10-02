# cde752d — Cut the trailmix peak to 1156 with chunk-4 folds, temp-free zero-chunk erases and per-call reserves, paid for by late-tail apply skips

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-21 |
| Submission | `66503c1` |
| Commit | `cde752dffd45a197142395b3c52b5058e0a83f73` |
| Result | 1156 qubits × 1,381,234 Toffoli = **1,596,706,504** |
| Base | `f8e215b` (gopikannappan): 1159 qubits × 1,378,242 Toffoli = 1,597,382,478 |
| Change vs base | qubits −3, Toffoli +2,992, score −675,974 |
| Leaderboard Δ | −349,136, measured against the frontier at the time, `9af02f7` (gnuchev, 1159 × 1,377,960 = 1,597,055,640), which is **not** this commit's base |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The commit trades Toffoli for qubits, as jieyilong's [`6ba606a`](6ba606a.md)
did a few hours earlier (1157), and goes one qubit further. It has two halves.

**Peak cut, 1159 → 1156.**
- The headroom target drops by 3.
- The chunked `+f` folds in the GCD apply use 4-bit chunks instead of 5.
- The boundary erase of a fold chunk with no addend bits no longer builds a
  temporary copy of the (all-zero) addend.
- New per-call reserve overrides keep every local peak under 1156.

All of this costs Toffoli, because fewer carries get a clean, measurement-vented
ancilla.

**Late-tail apply relaxations, to win some Toffoli back.** In the last one or
two GCD iterations, the apply steps now assume that the GCD has already
finished:
- the inverse-apply swap of the last step is skipped;
- the forward-apply swap of the second step is skipped;
- in the last step of both directions, the `s2`-controlled second doubling is
  dropped.

Together these remove about 1,000 Toffoli (256 + 256 + 2 × ~260). They are wrong only on inputs whose
GCD is still working in those iterations, and the nonce hunt dodges those.

The net is +2,992 Toffoli for −3 qubits. That lowers the score by 675,974,
because 3/1159 of the score (about 4.1 M) is more than 2,992 × 1156 (about
3.5 M).

## What changed and why it lowers qubits

All defaults are new `set_default_env` lines in `build()`, `src/point_add/mod.rs`.

**A. Peak cut**

1. **`TLM_TARGET_Q` 1159 → 1156.** This is the headroom that caps the clean
   carry counts of the hybrid adders, cout adders, `+f` windows and fused folds
   (`target_qubit_headroom`). See
   [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
2. **`TLM_FOLD_CHUNK_FORCE=4`** (`fused.rs`, `fused_fold`).
   - Fold-schedule codes `< 0` select `add_mf_fold_chunked(…, chunk)`. Every
     such code in `FOLD_SCHED` is −5, so the base used 5-bit chunks.
   - Forcing 4 shrinks every per-chunk temporary: `s − 1` internal carries,
     and the `s`-wide addend temp and comparator chain of the boundary erase.
     The cost is more boundaries, each with its own carry and measured erase.
3. **`TLM_FOLD_BOUNDARY_ZERO_DIRECT=1`** (`fused.rs`, `fold_boundary_erase`).
   - The fold's addend `(e + 2d)·f` has set bits only in its low part, so the
     higher chunks have every `ctl[i] = None`.
   - For such a chunk, the base still allocated an `s`-qubit `temp`, wrote the
     (all-zero) addend into it, and ran the gated erase on `(y, temp)`.
   - New `fold_boundary_erase_zero_direct(y, cin, carry)` does this instead:
     - `hmr` the boundary carry;
     - under the outcome bit, run a carry chain over `y` and `cin` alone, which
       recomputes the carry of `y + cin` against a zero addend;
     - apply the phase fix, then unwind the chain with `hmr` + `cz_if_bit`.
   - No `temp` register is needed, so `s` fewer wires are live during the
     erase. See [measurement-uncompute](../concepts/measurement-uncompute.md).
4. **Per-call reserve overrides.**
   - `TLM_TARGET_FOLD_CALL_RESERVE_OVERRIDES` is new in `fold_call_reserve`.
     It wins over the existing `TLM_TARGET_FOLD_CALL_RESERVES`. Defaults are set
     for calls 173–186, 254–259 and 327–340, mostly 3, with 256/257 at 11, 254
     at 5 and 259 at 20.
   - `TLM_TARGET_FFG_CALL_RESERVE_OVERRIDES` is new in `add_f_window`
     (`arith.rs`). It replaces the `+f` window reserve for calls 181–262 (3 to
     11) and 340–362 (10 or 11).
   - The `fused.rs` parser is refactored into `env_index_value` to read both
     maps.
   - A larger reserve leaves more free wires for the call's own temporaries,
     with fewer clean carries.

**B. Late-tail apply relaxations** (`src/point_add/trailmix_ludicrous/gcd.rs`)

New helpers `apply_fwd_cswap_skip`, `apply_inv_cswap_skip`,
`apply_fwd_s2_zero` and `apply_inv_s2_zero` each test `i + last_n >= ITERS`.
The forward one also keeps the legacy `TLM_APPLY_FWD_FIRST_CSWAP_SKIP` test.

5. **`TLM_APPLY_INV_CSWAP_SKIP_LAST=1`.** The inverse apply runs inside
   `forward_gcd_jump` for `i = 0 … 257`, so this is its last step.
   - Skipping that step's 256 cswaps is the identity unless the GCD has not
     finished. The step's flag is `swp = subtracted AND (v < u)`, and it is 0
     whenever `v` reaches 0 there.
   - This is the same skip as [`6ba606a`](6ba606a.md) and
     [`9af02f7`](9af02f7.md), written fresh. Saves 256.
6. **`TLM_APPLY_FWD_CSWAP_SKIP_LAST=2`.** The forward apply runs in
   `reverse_gcd_jump` for `i = 257 … 0`, so `i = 257` and `i = 256` are its
   first two steps.
   - `i = 257` was already skipped, and is exact because `y = 0` there
     ([`5c34dd1`](5c34dd1.md)).
   - `i = 256` is new. Its swap is a no-op only if GCD step 256 did not swap,
     which holds when the GCD had finished by then. Saves 256.
7. **`TLM_APPLY_FWD_S2_ZERO_LAST=1` and `TLM_APPLY_INV_S2_ZERO_LAST=1`.** At
   `i = 257` (`i != 0`), the apply's `y ← y·2·(1+s2)` (`fused_double_cdouble`)
   or its inverse is replaced by the new `fused_double_only` /
   `fused_double_only_reverse` in `fused.rs`.
   - The new functions do one free swap-chain shift and one `+f` fold
     controlled by the single overflow bit (`fused_fold_e_only`, which calls
     `add_f_window`).
   - They drop the 257 `s2`-controlled `cswap`s of the second shift and the
     two-bit `(e + 2d)·f` fold controls. That saves about 260 Toffoli per
     direction.
   - Why it is usually right: if the GCD finished before the last step, that
     step has `subtracted = 0`. In the inverse direction the register being
     halved, `tmp`, is already 0. In the forward direction `y` is still 0.
     Doubling 0 by 2 or by 4 gives the same 0, so `s2` does not matter.
   - It is wrong only when the GCD's final subtract lands in step 257 with
     `s2 = 1`.

**C. Nonce:** `DIALOG_TAIL_NONCE` 720008097505 → 9600006009245.

## Why it is still correct, and what it risks

- **Part A is exact.** Fewer clean carries means more in-place carries, which
  are exact. The temp-free erase recomputes the same carry predicate against a
  zero addend. Smaller chunks give the same sum. A bad reserve could only raise
  the qubit count. The run reaches 1156, so every call fits.
- **Part B is probabilistic.** Items 6 and 7 assume that the GCD has finished
  by iteration 256 or 257. An input whose binary GCD still swaps at step 256,
  or still subtracts with `s2 = 1` at step 257, now gets a wrong `λ` or `y`.
  That shows up as a classical failure, or as a phase failure through the later
  measured erasures.
- The author's note says these tail depths were chosen to "keep the error
  rate huntable". Deeper skips were backed off: forward 2 and inverse 1 for the
  cswaps, 1 and 1 for `s2`.
- The shipped nonce `9600006009245` draws a clean set: 9,024 of 9,024 shots,
  with 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The census files this as host-derived / classical specialization. That fits
part B: it hard-codes `s2 = 0` and `swp = 0` in the tail steps as if they were
known constants. But the score gain comes from part A, the 3-qubit peak cut,
which costs more Toffoli than part B saves. The diff suggests
Register and Scratch Allocation → ancilla-lifetime / venting (a peak trim)
instead, with the tail skips as a secondary probabilistic truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout f8e215b -- src/point_add`.
   - Do not start from the git parent `9af02f7`. That is gnuchev's tree. It
     adds `pub mod island_search`, the `pub(crate)` filter helpers, and its
     own `TLM_APPLY_INV_FIRST_CSWAP_SKIP` code, with two more nonce rerolls
     in between.
   - Against the parent, the diff (249 lines) would undo those changes.
   - Against `f8e215b`, `git diff --ignore-cr-at-eol f8e215b cde752d -- src/point_add`
     is 219 lines in 4 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol cde752d -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*` or `CONSTPROP_*` environment variables set,
   because they override the defaults in `build()`. Expect:
   - 1156 qubits
   - 1,381,234 average Toffoli (1,381,233.777 before rounding)
   - score 1,596,706,504
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `9600006009245` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index a2f4820..7e52790 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -2027,7 +2027,7 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "720008097505");
+    set_default_env("DIALOG_TAIL_NONCE", "9600006009245");
     // Stack the latest frontier square fold: use shifted-low folding for all
     // square lanes instead of the older `a`-only direct32 ramp shortcut.
     set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
@@ -2037,7 +2037,16 @@ pub fn build() -> Vec<Op> {
     set_default_env("TLM_GRAD_FINAL_NO_COUT", "1");
     set_default_env("TLM_APPLY_FWD_FIRST_CSWAP_SKIP", "1");
     set_default_env("CONSTPROP_MAX_ITERS", "16");
-    set_default_env("TLM_TARGET_Q", "1159");
+    // q1156 chunk4/ffg11/s2safer route (Codex c07bf74 sweep) — peak 1156.
+    set_default_env("TLM_TARGET_Q", "1156");
+    set_default_env("TLM_FOLD_BOUNDARY_ZERO_DIRECT", "1");
+    set_default_env("TLM_FOLD_CHUNK_FORCE", "4");
+    set_default_env("TLM_TARGET_FOLD_CALL_RESERVE_OVERRIDES", "173:3,175:3,177:3,256:11,257:11,336:3,338:3,340:3,176:3,178:3,180:3,254:5,259:20,333:3,335:3,337:3,179:3,181:3,183:3,182:3,184:3,186:3,327:3,329:3,330:3,331:3,332:3,334:3");
+    set_default_env("TLM_TARGET_FFG_CALL_RESERVE_OVERRIDES", "184:4,186:4,188:4,205:6,207:6,209:6,220:7,222:7,224:7,238:8,240:8,242:8,251:9,257:10,262:10,355:10,362:10,359:10,181:3,183:3,185:3,187:4,189:4,191:4,196:5,198:5,200:5,208:6,210:6,212:6,223:7,225:7,227:7,241:8,243:8,245:8,250:9,252:9,190:4,192:4,193:5,194:4,195:5,197:5,199:5,201:5,202:6,203:5,204:6,206:6,211:6,213:6,214:7,215:6,216:7,218:7,226:7,228:8,229:8,230:8,231:8,233:8,244:8,246:8,247:9,253:9,254:10,259:11,358:10,340:11,341:11,342:11,343:11,344:11,345:11,346:11,347:11,348:11,349:11,350:11");
+    set_default_env("TLM_APPLY_FWD_S2_ZERO_LAST", "1");
+    set_default_env("TLM_APPLY_INV_S2_ZERO_LAST", "1");
+    set_default_env("TLM_APPLY_FWD_CSWAP_SKIP_LAST", "2");
+    set_default_env("TLM_APPLY_INV_CSWAP_SKIP_LAST", "1");
     set_default_env("TLM_FOLD_RELEASE_CONTROLS", "1");
     set_default_env("TLM_TARGET_FFG_RESERVE", "9");
     set_default_env(
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index de64575..720750b 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -917,6 +917,11 @@ fn add_f_window(circ: &mut B, ctrl: &QubitId, reg: &[QubitId], lsbs: usize, c: &
         {
             reserve = 8;
         }
+        if let Some(call_reserve) =
+            env_index_value("TLM_TARGET_FFG_CALL_RESERVE_OVERRIDES", call_index)
+        {
+            reserve = call_reserve;
+        }
         headroom.saturating_sub(reserve)
     });
     let scheduled_g = g_sched
diff --git a/src/point_add/trailmix_ludicrous/fused.rs b/src/point_add/trailmix_ludicrous/fused.rs
index 1b23654..f4550ec 100644
--- a/src/point_add/trailmix_ludicrous/fused.rs
+++ b/src/point_add/trailmix_ludicrous/fused.rs
@@ -25,20 +25,24 @@ fn next_fold_call_index() -> usize {
     })
 }
 
-fn fold_call_reserve(index: usize, default: usize) -> usize {
-    std::env::var("TLM_TARGET_FOLD_CALL_RESERVES")
+fn env_index_value(name: &str, index: usize) -> Option<usize> {
+    std::env::var(name)
         .ok()
         .and_then(|value| {
             value
                 .split(',')
                 .filter_map(|item| item.trim().split_once(':'))
-                .find_map(|(call, reserve)| {
+                .find_map(|(call, value)| {
                     (call.parse::<usize>().ok()? == index)
-                        .then(|| reserve.parse::<usize>().ok())
+                        .then(|| value.parse::<usize>().ok())
                         .flatten()
                 })
         })
-        .unwrap_or(default)
+}
+
+fn fold_call_reserve(index: usize, default: usize) -> usize {
+    let base = env_index_value("TLM_TARGET_FOLD_CALL_RESERVES", index).unwrap_or(default);
+    env_index_value("TLM_TARGET_FOLD_CALL_RESERVE_OVERRIDES", index).unwrap_or(base)
 }
 
 /// secp256k1 `(e+2d)*f` combined-fold addend control per low-bit position `p`
@@ -373,6 +377,15 @@ fn fold_chunk_clean(circ: &mut B, ctl: &[Option<QubitId>], y: &[QubitId], cin: O
 /// Gated-erase a boundary carry: materialize the addend into a temp, run the
 /// uncontrolled gated erase on (y, temp), un-materialize.
 fn fold_boundary_erase(circ: &mut B, ctl: &[Option<QubitId>], y: &[QubitId], cin: &QubitId, carry: QubitId) {
+    if std::env::var("TLM_FOLD_BOUNDARY_ZERO_DIRECT")
+        .ok()
+        .as_deref()
+        == Some("1")
+        && ctl.iter().all(Option::is_none)
+    {
+        fold_boundary_erase_zero_direct(circ, y, cin, carry);
+        return;
+    }
     let s = y.len();
     let temp: Vec<QubitId> = (0..s).map(|_| circ.alloc_qubit()).collect();
     for (i, c) in ctl.iter().enumerate() {
@@ -386,6 +399,59 @@ fn fold_boundary_erase(circ: &mut B, ctl: &[Option<QubitId>], y: &[QubitId], cin
     for q in temp { circ.zero_and_free(q); }
 }
 
+fn fold_boundary_erase_zero_direct(circ: &mut B, y: &[QubitId], cin: &QubitId, carry: QubitId) {
+    let n = y.len();
+    assert!(n >= 1, "zero boundary erase needs >= 1 bit");
+    let bit = circ.alloc_bit();
+    circ.hmr(carry, bit);
+    circ.push_condition(bit);
+
+    let mut cy: Vec<Option<QubitId>> = Vec::with_capacity(n);
+    let c0 = circ.alloc_qubit();
+    circ.x(c0);
+    circ.cx(*cin, c0);
+    cy.push(Some(c0));
+    for i in 0..n - 1 {
+        let next = circ.alloc_qubit();
+        let ci = cy[i].as_ref().unwrap();
+        circ.cx(*ci, y[i]);
+        circ.x(*ci);
+        circ.ccx(y[i], *ci, next);
+        circ.x(*ci);
+        circ.cx(*ci, next);
+        cy.push(Some(next));
+    }
+    {
+        let i = n - 1;
+        let ci = cy[i].as_ref().unwrap();
+        circ.cx(*ci, y[i]);
+        circ.neg();
+        circ.x(*ci);
+        circ.cz(y[i], *ci);
+        circ.x(*ci);
+        circ.z(*ci);
+        circ.cx(*ci, y[i]);
+    }
+    for i in (0..n - 1).rev() {
+        let next = cy[i + 1].take().unwrap();
+        let ci = cy[i].as_ref().unwrap();
+        circ.cx(*ci, next);
+        let mbit = circ.alloc_bit();
+        circ.hmr(next, mbit);
+        circ.zero_and_free(next);
+        circ.x(*ci);
+        circ.cz_if_bit(y[i], *ci, mbit);
+        circ.x(*ci);
+        circ.cx(*ci, y[i]);
+    }
+    let c0 = cy[0].take().unwrap();
+    circ.cx(*cin, c0);
+    circ.x(c0);
+    circ.zero_and_free(c0);
+    circ.pop_condition();
+    circ.zero_and_free(carry);
+}
+
 fn add_mf_fold_chunked(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId], s_chunk: usize) {
     let l = y.len();
     let release_controls = std::env::var("TLM_FOLD_RELEASE_CONTROLS")
@@ -832,6 +898,46 @@ fn fused_fold(circ: &mut B, e: &QubitId, d: &QubitId, ylow: &[QubitId], dirty: &
     }
 }
 
+fn fused_fold_e_only(circ: &mut B, e: &QubitId, y: &[QubitId]) {
+    let call_index = next_fold_call_index();
+    let timeline_start = circ.active_timeline.len();
+    let entry_active = circ.active_qubits;
+    let code = super::next_fold();
+    let default_reserve = std::env::var("TLM_TARGET_FOLD_RESERVE")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(4);
+    let reserve = fold_call_reserve(call_index, default_reserve);
+    let g = if code < 0 {
+        0
+    } else {
+        super::target_qubit_headroom(circ)
+            .map_or(code as usize, |headroom| {
+                (code as usize).min(headroom.saturating_sub(reserve))
+            })
+            .min(LSBS - 1)
+    };
+    let f_bytes = F_SECP256K1.to_le_bytes();
+    super::arith::add_f_window_pub(circ, e, y, LSBS, &f_bytes, Some(g));
+    if std::env::var_os("TRACE_TLM_FOLD").is_some() {
+        let local_peak = circ.active_timeline[timeline_start..]
+            .iter()
+            .map(|(_, active)| *active)
+            .max()
+            .unwrap_or(circ.active_qubits);
+        eprintln!(
+            "TLM_FOLD call={} phase={} code={} nv={} entry_active={} local_peak={} ops={}",
+            call_index,
+            circ.phase,
+            code,
+            g as i32,
+            entry_active,
+            local_peak,
+            circ.current_ops_len(),
+        );
+    }
+}
+
 /// Fused double-then-controlled-double: `y := y * 2 * (1 + s2) mod q`. `y.len() == n
 /// == 256`; the doubling uses two transient overflow bits (a 258-bit working view),
 /// not a persistent reg slot.
@@ -865,6 +971,20 @@ pub fn fused_double_cdouble(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
     circ.zero_and_free(hi2);
 }
 
+pub fn fused_double_only(circ: &mut B, y: &[QubitId]) {
+    let n = 256usize;
+    assert_eq!(y.len(), n, "fused double expects 256-bit y");
+    let hi = circ.alloc_qubit();
+    let mut w: Vec<QubitId> = y.to_vec();
+    w.push(hi);
+    for i in (1..w.len()).rev() {
+        circ.swap(w[i], w[i - 1]);
+    }
+    fused_fold_e_only(circ, &w[n], y);
+    circ.cx(y[0], w[n]);
+    circ.zero_and_free(hi);
+}
+
 /// Exact gate-inverse: `y := y / (2*(1+s2)) mod q`. Reverse of [`fused_double_cdouble`]:
 /// compute the overflow bits, subtract m*f, shift right.
 pub fn fused_double_cdouble_reverse(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
@@ -899,6 +1019,26 @@ pub fn fused_double_cdouble_reverse(circ: &mut B, s2: &QubitId, y: &[QubitId]) {
     circ.zero_and_free(hi2);
 }
 
+pub fn fused_double_only_reverse(circ: &mut B, y: &[QubitId]) {
+    let n = 256usize;
+    assert_eq!(y.len(), n, "fused halve expects 256-bit y");
+    let hi = circ.alloc_qubit();
+    let mut w: Vec<QubitId> = y.to_vec();
+    w.push(hi);
+    circ.cx(y[0], w[n]);
+    for q in &y[..LSBS] {
+        circ.x(*q);
+    }
+    fused_fold_e_only(circ, &w[n], y);
+    for q in &y[..LSBS] {
+        circ.x(*q);
+    }
+    for i in 1..w.len() {
+        circ.swap(w[i], w[i - 1]);
+    }
+    circ.zero_and_free(hi);
+}
+
 /// Exhaust every `(e,d,HMR outcome)` basis case for each nonlinear derived
 /// control.  This is available in normal builds because this worktree's wider
 /// `cfg(test)` suite currently has unrelated compile failures.
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index 9973b9a..d02b8d0 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -173,6 +173,41 @@ fn loan_gcd_y0_enabled() -> bool {
     std::env::var("TLM_LOAN_GCD_Y0").ok().as_deref() == Some("1")
 }
 
+fn apply_fwd_cswap_skip(i: usize) -> bool {
+    let legacy_first_skip =
+        std::env::var("TLM_APPLY_FWD_FIRST_CSWAP_SKIP").ok().as_deref() == Some("1")
+            && i + 1 == ITERS;
+    let last_n = std::env::var("TLM_APPLY_FWD_CSWAP_SKIP_LAST")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(0);
+    legacy_first_skip || (last_n != 0 && i + last_n >= ITERS)
+}
+
+fn apply_inv_cswap_skip(i: usize) -> bool {
+    let last_n = std::env::var("TLM_APPLY_INV_CSWAP_SKIP_LAST")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(0);
+    last_n != 0 && i + last_n >= ITERS
+}
+
+fn apply_fwd_s2_zero(i: usize) -> bool {
+    let last_n = std::env::var("TLM_APPLY_FWD_S2_ZERO_LAST")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(0);
+    last_n != 0 && i + last_n >= ITERS
+}
+
+fn apply_inv_s2_zero(i: usize) -> bool {
+    let last_n = std::env::var("TLM_APPLY_INV_S2_ZERO_LAST")
+        .ok()
+        .and_then(|value| value.parse::<usize>().ok())
+        .unwrap_or(0);
+    last_n != 0 && i + last_n >= ITERS
+}
+
 fn park_known_one(circ: &mut B, q: QubitId) -> QubitId {
     circ.x(q);
     if loan_odd_u0_enabled() {
@@ -958,6 +993,7 @@ fn apply_step_forward(
     dirty_vents: &[QubitId],
 ) {
     let n = 256usize;
+    let s2_known_zero = i != 0 && apply_fwd_s2_zero(i);
 
     // 1) if subtracted: y += x mod q. Apply cofactor add -> cout adder at the
     // schedule's k.
@@ -976,9 +1012,7 @@ fn apply_step_forward(
     });
     // 2) if swap: swap(x, y).
     circ.set_phase("tlm_apply_forward_swap");
-    if !(std::env::var("TLM_APPLY_FWD_FIRST_CSWAP_SKIP").ok().as_deref() == Some("1")
-        && i + 1 == ITERS)
-    {
+    if !apply_fwd_cswap_skip(i) {
         for j in 0..n {
             circ.cswap(*swp, x_reg[j], y_reg[j]);
         }
@@ -990,6 +1024,8 @@ fn apply_step_forward(
     if i == 0 {
         controlled_mod_double(circ, t1, y_reg);
         controlled_mod_double(circ, s2, y_reg);
+    } else if s2_known_zero {
+        super::fused::fused_double_only(circ, y_reg);
     } else {
         super::fused::fused_double_cdouble(circ, s2, y_reg);
     }
@@ -1009,6 +1045,7 @@ fn apply_step_reverse(
     dirty_vents: &[QubitId],
 ) {
     let n = 256usize;
+    let s2_known_zero = i != 0 && apply_inv_s2_zero(i);
 
     // inverse of 3): i==0 two separate reverse-doublings (s2 halve then t1 halve);
     // i>0 the fused inverse double+cdouble.
@@ -1016,13 +1053,17 @@ fn apply_step_reverse(
     if i == 0 {
         controlled_mod_double_reverse(circ, s2, y_reg);
         controlled_mod_double_reverse(circ, t1, y_reg);
+    } else if s2_known_zero {
+        super::fused::fused_double_only_reverse(circ, y_reg);
     } else {
         super::fused::fused_double_cdouble_reverse(circ, s2, y_reg);
     }
     // inverse of 2): swap (involutory).
     circ.set_phase("tlm_apply_inverse_swap");
-    for j in 0..n {
-        circ.cswap(*swp, x_reg[j], y_reg[j]);
+    if !apply_inv_cswap_skip(i) {
+        for j in 0..n {
+            circ.cswap(*swp, x_reg[j], y_reg[j]);
+        }
     }
     // inverse of 1): y -= x mod q. The apply-path operands carry pseudo-Mersenne
     // representation drift, so the borrow clean uses the MBU form.
```

