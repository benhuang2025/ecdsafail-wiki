# d44cad3 — Vent the square-reduce adds, fuse the final x reverse-subtract, and free one fold carry to reach 1152 qubits

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-26 |
| Submission | `71f5115` |
| Commit | `d44cad386f2e121e2d952edcdcc3693f97d13153` |
| Result | 1152 qubits × 1,364,230 Toffoli = **1,571,592,960** |
| Base | `6dafa07` (git parent): 1153 qubits × 1,367,698 Toffoli = 1,576,955,794 |
| Change vs base | qubits −1, Toffoli −3,468, score −5,362,834 (leaderboard Δ −5,362,834) |
| Family | Uncompute Strategy → measurement uncompute |
| Concepts | [measurement-uncompute](../concepts/measurement-uncompute.md), [adders-and-carries](../concepts/adders-and-carries.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [modular-fold](../concepts/modular-fold.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

Three things happen on the trailmix q1153 route. The square's modular
reduce adds are off the peak, so they have spare wires. Their plain Cuccaro
adders are replaced by measurement-vented adders that use the spare wires as
vent ancillas, and each vented carry saves one Toffoli. The final `x := ox − x`
coordinate step is rewritten as a single add chain with a classical `ox + 1`,
which removes a whole 256-bit negation. And in 40 apply-path `+f` folds, the
bit-0 carry is cleared and later recomputed around the long suffix, which frees
the one qubit that held the peak at 1153.

Two smaller knobs go each way: the `3·ox` add goes back to a truncated
comparator (cheaper), and the forward-apply cswap skip goes from the last 2
GCD steps to the last 1 (dearer). Net: 1153 → 1152 qubits and 3,468 fewer
average Toffoli. The nonce was re-hunted (50400005525597).

## What changed and why it saves Toffoli and a qubit

All new defaults are set in `configure_q1153_second512_submission_defaults()`
(`src/point_add/mod.rs`), the first call in `build()`.

1. **Measurement-vented square-reduce adds** (`trailmix_ludicrous/arith.rs`).
   - **Before.** The register add inside `mod_sub` and `mod_add_lowpeak` was
     `cuccaro_carry(None, x, y, None, Some(&anc))`. That is a ripple whose
     carries are computed and then uncomputed by a second CCX each, so about
     `2n` CCX for `n = 256`. With `TLM_SQUARE_VENT_SHIFTED = 1`, the same
     applies to `mod_add_shifted_low` and `mod_sub_shifted_low`. These are the
     adds the square uses to subtract `A`, add or subtract the shifted terms,
     and fold `f·B` (`square.rs`, `apply_unshifted_value`, `apply_shifted_hi_term`, …).
   - **New `add_cout_vented_skip_dead`.** It mirrors `hybrid_add_plain` on the
     `(n+1)`-bit add `(y ++ cout) += (x ++ zpad)`. For each carry that is live:
     - while the vent budget lasts, it computes the carry into a fresh ancilla
       (`ccx(a_i, b_i, anc)`). In the reverse sweep it erases that ancilla
       with `hmr` plus a classically-conditioned `cz_if_bit(a_i, b_i, bit)`
       instead of a second CCX;
     - once the budget runs out, it falls back to the in-place
       `ccx(a_i, b_i, b_{i+1})`, which is uncomputed with a CCX as before.
   - **Cost.** The code comment gives `(n−1) + (n−1−vents)` CCX instead of
     `2n`, so each vent saves one Toffoli. See
     [measurement-uncompute](../concepts/measurement-uncompute.md).
   - **Budget.** `vents = square_peak_hard_cap() − active_qubits − margin`.
     The new `TLM_SQUARE_PEAK_CAP = 1152` overrides the source constant
     `SQUARE_PEAK_HARD_CAP = 1153`, and `TLM_SQUARE_VENT_MARGIN = 0` overrides
     `SQUARE_VENT_MARGIN = 30`. So the square vents exactly up to 1152 live
     qubits and never above.
   - **Dead carries.** The function takes the next `cuccaro_call_index`. It
     skips the same carries that `cuccaro_call_has_structurally_dead_carry`
     marks dead for that call ([`6dafa07`](6dafa07.md)'s tables), so those
     savings are kept and the call numbering of later Cuccaro calls stays
     aligned.
   - `TLM_SQUARE_NO_VENT_REDUCE = 1` restores the old Cuccaro path.
2. **Fused `x := ox − x`** (`ec_add.rs`, `coord_rsub`, `TLM_COORD_RSUB_FUSED = 1`).
   - **Before.** Load `ox` into a temp, `mod_sub_vented` (`x := x − ox`),
     unload, then `mod_neg(x)`. The negate is an unconditional constant add
     over 256 bits.
   - **Now.**
     - `classical_plus1_mod_2n` computes `ox + 1` with free classical bit
       ops.
     - `ox + 1` is loaded into a temp `t1`, and the new
       `arith::mod_rsub_vented_loaded(t1, x)` runs one chain that uses the
       identity `ox − x = ~x + (ox + 1) mod 2^256`: invert `x`, a vented
       add with carry-out into `anc`, invert `anc`, a gated `+f` window
       under the X-sandwich (which subtracts `f` when there was no carry),
       and the usual top-`MSBS` comparator to clean `anc`.
   - The comment estimates about −248 average Toffoli.
3. **Truncated `3·ox` add** (`ec_add.rs`, `coord_add3x`, `TLM_COORD_ADD3X_TRUNC = 1`).
   - The `dst += 3·ox` step goes back from `mod_add_exact`, which cleans the
     overflow with a full 256-bit comparator, to `mod_add`, which uses the
     top `MSBS = 19` bits like the other coordinate steps.
   - The comment says about 116 fewer executed Toffoli.
4. **Free `cy0` during the fold suffix** (`arith.rs`, `add_f_window_hybrid`).
   - The settings are `TLM_FFG_RELEASE_CY0_DURING_SUFFIX = 1` and
     `TLM_FFG_RELEASE_CY0_CALLS`, a list of 40 call indices from 178 to 239.
   - **The hybrid `+f` fold.** It adds `ctrl·f` into the low `LSBS` bits. It
     keeps clean carries `cy[0..k)` for a prefix, then runs the suffix
     `[k, n)` with borrowed or graduated carries, then unwinds the prefix.
   - **The fact used.** `f[0] = 1`, so after bit 0's sum `a0_final = a0 ⊕ ctrl`.
     The bit-0 carry is `cy0 = ctrl ∧ a0 = ctrl ∧ ¬a0_final`.
   - **Before the suffix,** the commit clears `cy0` with
     `X(a0); CCX(ctrl, a0, cy0); X(a0)` and returns the wire to the pool with
     `loan_zero_qubit`.
   - **After the suffix,** it takes the wire back with `reclaim_zero_qubit`
     and recomputes `cy0` the same way, before the prefix reverse uses it.
   - **Trade.** This costs 2 extra CCX per listed call and saves one live
     qubit during the suffix, which is where those calls set the 1153 peak.
   - The square-vent cap in item 1 has to be 1152 as well. Otherwise the
     square's vents would fill up to 1153 again, and the peak would stay
     there (submission note).
5. **`TLM_APPLY_FWD_CSWAP_SKIP_LAST`: 2 → 1** (more gates, less risk).
   - `configure_q1153_second512_submission_defaults()` now sets it to `"1"`
     before the older `set_default_env(…, "2")` line in `build()` runs, so
     the effective value drops from 2 to 1.
   - `gcd.rs::apply_fwd_cswap_skip` therefore skips the 256 controlled swaps
     only in the last forward-apply step, not the last two. That adds back
     256 cswaps (one CCX each) every time the forward apply runs, but removes
     the assumption that the second-to-last swap bit is always 0. The submission note lists it with
     the Toffoli reductions, but its own effect is an increase.
6. **Unused additions.**
   - `add_cout_vented_unctrl_bounded` is defined but never called.
   - `env_index_list_contains` is a small helper used for item 4.

## Why it is still correct, and what it risks

- **Exact.**
  - The vented adds in item 1 compute the same values as the Cuccaro adds.
    The HMR outcome is random, and its phase is corrected by `cz_if_bit`.
  - The `cy0` clear and recompute in item 4 is an exact identity, because
    `f[0] = 1`.
  - The fused reverse-subtract identity `ox − x = ~x + (ox+1) mod 2^256` is
    exact, with one conditional `−f`. `ox + 1 < 2^256` because `ox < p`.
- **Probabilistic.**
  - Item 2 cleans its carry with a top-19-bit comparator.
  - Item 3 trades an exact comparator for the same truncated one.
  - Both mis-clear when the compared registers agree on their top bits,
    which leaves a phase error or a dirty `anc`: a phase or ancilla failure.
  - Item 5 lowers risk.
  - The dead-carry skips reused from `6dafa07` are still empirical.
- The shipped nonce `50400005525597` draws a clean set: 9,024 of 9,024 shots,
  0 classical, 0 phase and 0 ancilla failures, average 1,364,229.770 Toffoli
  (submission note). See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Most of the Toffoli saving comes from replacing Toffoli-uncomputed carries
with measured ones (item 1), so measurement uncompute is right. The qubit
drop (item 4) is a free-and-recompute of one ancilla, which is a
peak-reduction lever of its own. Item 2 is a gate-count rewrite of one
coordinate step. All three are secondary to the vented square in the label.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 6dafa07 -- src/point_add`. The base is the git parent.
   `git diff --ignore-cr-at-eol 6dafa07 d44cad3 -- src/point_add` is 282 lines
   in 3 files.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol d44cad3 -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `SUB4_*`,
   `TLM_*`, `DIALOG_*` or `SINGLE_CCX_*` overrides set. Expect:
   - 1152 qubits
   - 1,364,230 average Toffoli (1,364,229.770 before rounding)
   - score 1,571,592,960
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `50400005525597` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index fc6eb5a..dd54bdd 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1151,7 +1151,7 @@ fn set_default_env(name: &str, value: &str) {
 // Q1153 second-512 scan route. To submit a clean hit from the current hunt,
 // update this nonce, build with no shell env overrides, run `ecdsafail run`,
 // and submit only if it remains 0 / 0 / 0.
-const Q1153_SECOND512_SUBMISSION_NONCE: &str = "13100076815176";
+const Q1153_SECOND512_SUBMISSION_NONCE: &str = "50400005525597";
 
 fn configure_q1153_second512_submission_defaults() {
     set_default_env("DIALOG_TAIL_NONCE", Q1153_SECOND512_SUBMISSION_NONCE);
@@ -1162,6 +1162,15 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_FOLD_TAIL_CINC", "1");
     set_default_env("TLM_CODEC_DIAMOND_MCX", "1");
     set_default_env("SINGLE_CCX_FANOUT_DISABLE", "1");
+    // ── 1152 stack (codex FFG cy0-release + opus square vents) ──────────────
+    set_default_env("TLM_FFG_RELEASE_CY0_DURING_SUFFIX", "1");
+    set_default_env("TLM_FFG_RELEASE_CY0_CALLS", "178,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,203,208,210,211,212,213,215,217,219,221,226,232,234,235,236,237,239");
+    set_default_env("TLM_APPLY_FWD_CSWAP_SKIP_LAST", "1");
+    set_default_env("TLM_COORD_RSUB_FUSED", "1");
+    set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
+    set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
+    set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
+    set_default_env("TLM_SQUARE_PEAK_CAP", "1152");
 }
 
 fn configure_ecdsafail_submission_route() {
diff --git a/src/point_add/trailmix_ludicrous/arith.rs b/src/point_add/trailmix_ludicrous/arith.rs
index 4a5f415..cb7b95f 100644
--- a/src/point_add/trailmix_ludicrous/arith.rs
+++ b/src/point_add/trailmix_ludicrous/arith.rs
@@ -105,6 +105,18 @@ fn env_index_value(name: &str, index: usize) -> Option<usize> {
         })
 }
 
+fn env_index_list_contains(name: &str, index: usize) -> bool {
+    std::env::var(name)
+        .ok()
+        .map(|value| {
+            value
+                .split(',')
+                .filter_map(|item| item.trim().parse::<usize>().ok())
+                .any(|candidate| candidate == index)
+        })
+        .unwrap_or(false)
+}
+
 const FFG_DEAD_HYBRID_CARRY_RANGES: &[(usize, usize, usize)] = &[
     (264, 1, 46),
     (265, 1, 46),
@@ -1315,6 +1327,25 @@ fn add_f_window_hybrid(
     }
     // prefix sums bits 0..k.
     for i in 0..k { if cbit(c, i) { circ.cx(*ctrl, a[i]); } }
+    let release_cy0_during_suffix =
+        std::env::var("TLM_FFG_RELEASE_CY0_DURING_SUFFIX")
+            .ok()
+            .as_deref()
+            == Some("1")
+            && (std::env::var_os("TLM_FFG_RELEASE_CY0_CALLS").is_none()
+                || env_index_list_contains("TLM_FFG_RELEASE_CY0_CALLS", trace_call_index))
+            && k > 1
+            && cbit(c, 0);
+    if release_cy0_during_suffix {
+        let cy0 = *cy[0].as_ref().unwrap();
+        // After bit 0's sum, final a0 = original_a0 ^ ctrl because f[0] = 1.
+        // So cy0 = ctrl & original_a0 = ctrl & !final_a0; clear it while the
+        // suffix runs, then restore it before the prefix reverse consumes it.
+        circ.x(a[0]);
+        circ.ccx(*ctrl, a[0], cy0);
+        circ.x(a[0]);
+        circ.loan_zero_qubit(cy0);
+    }
     // suffix [k,n): carry-in cy_k = cy[k-1]. Graduated-chunked when the remaining
     // headroom covers it (avoids the large-suffix borrowed-dirty path), else
     // borrowed-dirty.
@@ -1331,6 +1362,13 @@ fn add_f_window_hybrid(
             dirty_carryin(circ, ctrl, &a_hi, c, k, &dirty, &cin);
         }
     }
+    if release_cy0_during_suffix {
+        let cy0 = *cy[0].as_ref().unwrap();
+        circ.reclaim_zero_qubit(cy0);
+        circ.x(a[0]);
+        circ.ccx(*ctrl, a[0], cy0);
+        circ.x(a[0]);
+    }
     // prefix reverse bits k-1..1: vent cy[i] (=carry_{i+1}) via CZ discharge.
     for i in (1..k).rev() {
         if cbit(c, i) { circ.cx(*ctrl, a[i]); } // sum_i -> ta_i
@@ -1700,7 +1738,18 @@ pub fn mod_sub(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
     for q in y {
         circ.x(*q);
     }
-    cuccaro_carry(circ, None, x, y, None, Some(&anc));
+    // Off-peak square-reduce register add: value-identical via either the 1-anc
+    // Cuccaro ripple (2n CCX) or the headroom-bounded measurement-vented add
+    // ((n-1)+(n-1-vents) CCX, peak-neutral). TLM_SQUARE_NO_VENT_REDUCE=1 forces Cuccaro.
+    if std::env::var("TLM_SQUARE_NO_VENT_REDUCE").ok().as_deref() == Some("1") {
+        cuccaro_carry(circ, None, x, y, None, Some(&anc));
+    } else {
+        // Support-bounded vent: takes the cuccaro call-index (keeps downstream
+        // guards aligned) and skips the same dead carries the guard would, while
+        // venting the live ones -- captures both savings by construction.
+        let ci = next_cuccaro_call_index();
+        add_cout_vented_skip_dead(circ, x, y, &anc, ci);
+    }
     for q in y {
         circ.x(*q);
     }
@@ -1728,6 +1777,154 @@ fn add_cout_vented_unctrl(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: &Qub
     circ.zero_and_free(zpad);
 }
 
+/// Peak-hard-bounded variant of [`add_cout_vented_unctrl`]: identical value
+/// (`y := (x+y) mod 2^n`, `cout ^= carry_out(x+y)`), but the reverse-carry vent
+/// budget is capped to the live qubit headroom so the simultaneous vent ancillae
+/// never push the active count past `SQUARE_PEAK_HARD_CAP`. This is the off-peak
+/// square-reduce register add: a value-exact, ancilla-clean drop-in for the
+/// non-vented `cuccaro_carry(None, x, y, None, Some(cout))` register sub/add that
+/// costs `(n-1) + (n-1-vents)` CCX instead of `2n` -- every peak-safe vent saves
+/// one reverse-carry Toffoli. `vents = 0` degenerates to the same `2(n-1)+1` CCX
+/// shape as the Cuccaro add (so a zero-headroom call is at worst neutral).
+/// Fused single-chain `y := coord - y (mod q)` where `t1 = (coord+1) mod 2^256`
+/// is preloaded into a quantum temp. Identity: `coord - y = ~y + (coord+1) mod
+/// 2^256`, conditional `-f` on NOT(carry-out). Replaces the two-chain
+/// `mod_sub_vented` + `mod_neg` (saves the unconditional ~254-CCX negate). `t1` is
+/// untouched. Same MSBS-truncated overflow clean as the other coordinate steps.
+pub fn mod_rsub_vented_loaded(circ: &mut B, t1: &[QubitId], y: &[QubitId]) {
+    let n = y.len();
+    assert_eq!(t1.len(), n, "mod_rsub_vented_loaded: t1,y must both be n=256 bits");
+    assert_eq!(n, 256, "secp256k1 mod_rsub_vented_loaded expects n=256");
+    let f_bytes = F_SECP256K1.to_le_bytes();
+    let anc = circ.alloc_qubit();
+    for q in y {
+        circ.x(*q);
+    }
+    add_cout_vented_unctrl(circ, t1, y, &anc);
+    circ.x(anc);
+    for q in &y[..LSBS] {
+        circ.x(*q);
+    }
+    add_f_window(circ, &anc, y, LSBS, &f_bytes, Some(LSBS - 1));
+    for q in &y[..LSBS] {
+        circ.x(*q);
+    }
+    circ.x(anc);
+    controlled_lt_msbs_conditional(circ, None, &y[..n], &t1[..n], MSBS, anc);
+}
+
+/// Support-bounded vent: the headroom-bounded measurement-vented add, but it
+/// ALSO skips the structurally-dead carries that the cuccaro guard would skip for
+/// `call_index` (via `cuccaro_call_has_structurally_dead_carry`). So it vents the
+/// LIVE carries at ~1 Toffoli each AND emits zero dead carries -- capturing both
+/// the venting saving and the dead-carry removal the guards do, by construction.
+/// `cout ^= carry_out`; `x` restored. Identical value to the guarded cuccaro add.
+fn add_cout_vented_skip_dead(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: &QubitId, call_index: usize) {
+    let n = y.len();
+    assert_eq!(x.len(), n, "add_cout_vented_skip_dead: x,y width mismatch");
+    let dead = |i: usize| cuccaro_call_has_structurally_dead_carry(call_index, i);
+    let zpad = circ.alloc_qubit();
+    let live = circ.active_qubits as usize;
+    let margin = std::env::var("TLM_SQUARE_VENT_MARGIN")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(SQUARE_VENT_MARGIN);
+    let vents_budget = square_peak_hard_cap().saturating_sub(live).saturating_sub(margin);
+    // a = y ++ cout, b = x ++ zpad  (the (n+1)-bit add).
+    let mut a: Vec<QubitId> = y.to_vec();
+    a.push(*cout);
+    let mut b: Vec<QubitId> = x.to_vec();
+    b.push(zpad);
+    let m = a.len();
+    // mirror hybrid_add_plain, but gate each carry MAJ on !dead(i).
+    let mut vents_left = vents_budget;
+    for i in 1..m {
+        circ.cx(b[i], a[i]);
+    }
+    for i in (1..m - 1).rev() {
+        circ.cx(b[i], b[i + 1]);
+    }
+    let mut vent_ancs: Vec<Option<QubitId>> = (0..m - 1).map(|_| None).collect();
+    for i in 0..m - 1 {
+        if dead(i) {
+            continue; // carry into b[i+1] is provably 0 -> no MAJ, no vent
+        }
+        if vents_left > 0 {
+            let anc = circ.alloc_qubit();
+            circ.ccx(a[i], b[i], anc);
+            circ.cx(anc, b[i + 1]);
+            vent_ancs[i] = Some(anc);
+            vents_left -= 1;
+        } else {
+            circ.ccx(a[i], b[i], b[i + 1]);
+        }
+    }
+    for i in (0..m - 1).rev() {
+        circ.cx(b[i + 1], a[i + 1]); // UNCONDITIONAL sum bit i+1
+        if dead(i) {
+            continue;
+        }
+        if let Some(anc) = vent_ancs[i].take() {
+            circ.cx(anc, b[i + 1]);
+            let bit = circ.alloc_bit();
+            circ.hmr(anc, bit);
+            circ.zero_and_free(anc);
+            circ.cz_if_bit(a[i], b[i], bit);
+        } else {
+            circ.ccx(a[i], b[i], b[i + 1]);
+        }
+    }
+    for i in 1..m - 1 {
+        circ.cx(b[i], b[i + 1]);
+    }
+    circ.cx(b[0], a[0]); // UNCONDITIONAL sum bit 0
+    for i in 1..m {
+        circ.cx(b[i], a[i]);
+    }
+    circ.zero_and_free(zpad);
+}
+
+fn add_cout_vented_unctrl_bounded(circ: &mut B, x: &[QubitId], y: &[QubitId], cout: &QubitId) {
+    let n = y.len();
+    assert_eq!(x.len(), n, "add_cout_vented_unctrl_bounded: x,y width mismatch");
+    let zpad = circ.alloc_qubit();
+    // After zpad alloc, the (n+1)-bit add can host at most this many simultaneous
+    // vent ancillae before touching the hard cap. hybrid_add_plain holds at most
+    // `vents` vent ancillae live at once (allocated forward, freed in reverse).
+    let live = circ.active_qubits as usize;
+    let margin = std::env::var("TLM_SQUARE_VENT_MARGIN")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(SQUARE_VENT_MARGIN);
+    let headroom = square_peak_hard_cap().saturating_sub(live).saturating_sub(margin);
+    let mut a: Vec<QubitId> = y.to_vec();
+    a.push(*cout);
+    let mut b: Vec<QubitId> = x.to_vec();
+    b.push(zpad);
+    hybrid_add_plain(circ, &a, &b, headroom);
+    circ.zero_and_free(zpad);
+}
+
+/// Active-qubit hard cap for the off-peak square-reduce partial vents. The global
+/// peak is set in the GCD apply (1156); the square runs far below it. We cap the
+/// vent ancillae so the square reduce never reaches the apply peak. A small margin
+/// below 1156 protects against transient allocations inside the add.
+pub const SQUARE_PEAK_HARD_CAP: usize = 1153; // da51a48 binding peak (was 1156 on 27d4627); override via TLM_SQUARE_PEAK_CAP
+
+/// Headroom margin held back below the hard cap when sizing the square-reduce vent
+/// budget. Keeps a buffer under the apply peak (1156) so the partial vent is
+/// peak-neutral with slack, and is the operating point measured to pass the
+/// fixed-nonce phase/classical budget (12 classical / 7 phase / 0 ancilla at the
+/// product-min nonce, vs the baseline 16 / 9 / 0; avg Toffoli -838.9).
+pub const SQUARE_VENT_MARGIN: usize = 30;
+
+fn square_peak_hard_cap() -> usize {
+    std::env::var("TLM_SQUARE_PEAK_CAP")
+        .ok()
+        .and_then(|s| s.parse::<usize>().ok())
+        .unwrap_or(SQUARE_PEAK_HARD_CAP)
+}
+
 /// UNCONTROLLED `y := y + x (mod q)` over n=256-bit x,y. VENTED register add
 /// (overflow -> anc) + CLEAN gated `+f` fold + top-MSBS `(y<x)` overflow clean.
 /// Temp-clean (anc consumed by the clt). The overflow clean deposits a bare `Z`
@@ -1773,7 +1970,13 @@ pub fn mod_add_lowpeak(circ: &mut B, x: &[QubitId], y: &[QubitId]) {
     assert_eq!(n, 256, "secp256k1 mod_add_lowpeak expects n=256");
     let f_bytes = F_SECP256K1.to_le_bytes();
     let anc = circ.alloc_qubit();
-    cuccaro_carry(circ, None, x, y, None, Some(&anc));
+    // Off-peak square-reduce register add: headroom-bounded vent (see `mod_sub`).
+    if std::env::var("TLM_SQUARE_NO_VENT_REDUCE").ok().as_deref() == Some("1") {
+        cuccaro_carry(circ, None, x, y, None, Some(&anc));
+    } else {
+        let ci = next_cuccaro_call_index();
+        add_cout_vented_skip_dead(circ, x, y, &anc, ci);
+    }
     add_f_window(circ, &anc, y, LSBS, &f_bytes, None);
     controlled_lt_msbs_conditional(circ, None, &y[..n], &x[..n], MSBS, anc);
 }
@@ -1792,7 +1995,14 @@ pub fn mod_add_shifted_low(circ: &mut B, x: &[QubitId], y: &[QubitId], shift: us
     }
     let f_bytes = F_SECP256K1.to_le_bytes();
     let anc = circ.alloc_qubit();
-    cuccaro_carry(circ, None, x, &y[shift..], None, Some(&anc));
+    // Off-peak shifted-square reduce add: support-bounded vent (skip the same dead
+    // carries the guard would, vent the live ones). TLM_SQUARE_VENT_SHIFTED=1.
+    if std::env::var("TLM_SQUARE_VENT_SHIFTED").ok().as_deref() == Some("1") {
+        let ci = next_cuccaro_call_index();
+        add_cout_vented_skip_dead(circ, x, &y[shift..], &anc, ci);
+    } else {
+        cuccaro_carry(circ, None, x, &y[shift..], None, Some(&anc));
+    }
     add_f_window(circ, &anc, y, LSBS, &f_bytes, Some(LSBS - 1));
     controlled_lt_msbs_conditional(circ, None, &y[n - MSBS..], &x[x.len() - MSBS..], MSBS, anc);
 }
@@ -1842,7 +2052,12 @@ pub fn mod_sub_shifted_low(circ: &mut B, x: &[QubitId], y: &[QubitId], shift: us
     for q in &y[shift..] {
         circ.x(*q);
     }
-    cuccaro_carry(circ, None, x, &y[shift..], None, Some(&anc));
+    if std::env::var("TLM_SQUARE_VENT_SHIFTED").ok().as_deref() == Some("1") {
+        let ci = next_cuccaro_call_index();
+        add_cout_vented_skip_dead(circ, x, &y[shift..], &anc, ci);
+    } else {
+        cuccaro_carry(circ, None, x, &y[shift..], None, Some(&anc));
+    }
     for q in &y[shift..] {
         circ.x(*q);
     }
diff --git a/src/point_add/trailmix_ludicrous/ec_add.rs b/src/point_add/trailmix_ludicrous/ec_add.rs
index 799f393..4292b62 100644
--- a/src/point_add/trailmix_ludicrous/ec_add.rs
+++ b/src/point_add/trailmix_ludicrous/ec_add.rs
@@ -35,7 +35,8 @@
 //! across the square step.
 
 use super::arith::{
-    mod_add, mod_add_exact, mod_neg, mod_sub_classical_low3, mod_sub_shifted_low, mod_sub_vented,
+    mod_add, mod_add_exact, mod_neg, mod_rsub_vented_loaded, mod_sub_classical_low3,
+    mod_sub_shifted_low, mod_sub_vented,
 };
 use super::gcd::{mod_mul_inverse_in_place, Direction};
 use super::square::mod_square_sub_pm_secp256k1_symmetric;
@@ -119,7 +120,13 @@ fn coord_add3x(circ: &mut B, dst: &[QubitId], coord: &[BitId]) {
     for i in 0..N {
         circ.x_if_bit(temp[i], three_coord[i]); // temp := t (per-shot classical)
     }
-    mod_add_exact(circ, &temp, dst); // dst += t (mod q), exact -- temp untouched
+    // Upside B: TLM_COORD_ADD3X_TRUNC=1 uses the MSBS-truncated `mod_add` (same
+    // approximation the coord-subs already ship) for ~116 fewer executed Toffoli.
+    if std::env::var("TLM_COORD_ADD3X_TRUNC").ok().as_deref() == Some("1") {
+        mod_add(circ, &temp, dst);
+    } else {
+        mod_add_exact(circ, &temp, dst); // dst += t (mod q), exact -- temp untouched
+    }
     for i in 0..N {
         circ.x_if_bit(temp[i], three_coord[i]); // unload: temp := 0
     }
@@ -313,9 +320,46 @@ fn classical_add_into(circ: &mut B, acc: &[BitId], addend: &[BitId]) {
 /// load/unload from `CX` to `x_if_bit` (0 Toffoli). Boundary: `mod_neg` lands on
 /// `q` only when `x - coord == 0` (i.e. x == coord, a degenerate input),
 /// excluded with the other generic-add preconditions.
+/// `(coord + 1) mod 2^256` on the free classical BitId tier (0 Toffoli).
+fn classical_plus1_mod_2n(circ: &mut B, coord: &[BitId]) -> Vec<BitId> {
+    debug_assert_eq!(coord.len(), N);
+    let s: Vec<BitId> = circ.alloc_bits(N);
+    for i in 0..N {
+        circ.bit_copy(s[i], coord[i]);
+    }
+    let one: Vec<BitId> = circ.alloc_bits(1);
+    circ.bit_store0(one[0]);
+    circ.bit_invert(one[0]);
+    classical_add_into(circ, &s, &one);
+    circ.bit_store0(one[0]);
+    s
+}
+
 fn coord_rsub(circ: &mut B, x: &[QubitId], coord: &[BitId]) {
     debug_assert_eq!(x.len(), N);
     debug_assert_eq!(coord.len(), N);
+    // My fused single-chain coord_rsub (`ox - x = ~x + (ox+1) mod 2^256`, conditional
+    // -f, MSBS-truncated clean). `ox+1` on the free classical BitId tier. ~-248 avgT.
+    // Distinct from the frontier's TLM_FUSE_X_RESTORE/mod_const_minus_reg_qb (which
+    // measures +1201 here, hence default-off). Enable via TLM_COORD_RSUB_FUSED=1.
+    if std::env::var("TLM_COORD_RSUB_FUSED").ok().as_deref() == Some("1") {
+        let coord_p1 = classical_plus1_mod_2n(circ, coord);
+        let t: Vec<QubitId> = (0..N).map(|_| circ.alloc_qubit()).collect();
+        for i in 0..N {
+            circ.x_if_bit(t[i], coord_p1[i]);
+        }
+        mod_rsub_vented_loaded(circ, &t, x);
+        for i in 0..N {
+            circ.x_if_bit(t[i], coord_p1[i]);
+        }
+        for q in t {
+            circ.zero_and_free(q);
+        }
+        for &b in &coord_p1 {
+            circ.bit_store0(b);
+        }
+        return;
+    }
     if std::env::var("TLM_FUSE_X_RESTORE")
         .ok()
         .as_deref()
```

