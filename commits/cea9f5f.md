# cea9f5f — Lend the known-1 wire u[0] during every GCD subtract and apply step (1166 → 1165 qubits), plus nasqret's fold-control and single-fanout Toffoli cuts

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-19 |
| Submission | `05c0b96` |
| Commit | `cea9f5fc1f5a20bd5bfa47138aacba95990bab5d` |
| Result | 1165 qubits × 1,413,487 Toffoli = **1,646,712,355** |
| Base | `ed2715f` (gnuchev): 1166 qubits × 1,414,439 Toffoli = 1,649,235,874 |
| Change vs base | qubits −1, Toffoli −952, score −2,523,519 |
| Leaderboard Δ | −2,059,451, measured against the frontier at the time, `b02b354` (git parent, gopikannappan, 1166 × 1,414,041), which is **not** this commit's base |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [modular-fold](../concepts/modular-fold.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit has three parts.

1. **The new lever saves one qubit.**
   - In every step of the jump-GCD walk, the register `u` is odd, so its bit `u[0]` is
     always 1. The controlled subtract `v −= u` never reads `u[0]`, because bit 0 is
     handled with a single CX.
   - So right after the step's controlled swap, the commit flips `u[0]` to 0 with an X
     and returns the wire to the free pool. The subtract and the apply step can then use
     it as scratch. Afterwards the commit takes the wire back and flips it to 1 again.
   - The binding peak sits inside that window, so it drops from 1166 to 1165. The cost is
     two X gates per step and no Toffoli.
2. **Two Toffoli cuts are ported from nasqret's [`b1dec1e`](b1dec1e.md).**
   That submission was built on the tree before the layout search, and the later frontier
   line dropped these cuts.
   - In the fused fold, the control `d AND NOT e` is now built from the live `e AND d`
     with two CX gates, instead of a fresh CCX.
   - A post-pass applies one CCX fan-out identity.
3. **The tail nonce was re-hunted.**

Average Toffoli falls by 952 against `ed2715f`. The score drops by 2.52 M.

## What changed and why it saves qubits and Toffoli

### 1. Odd-`u[0]` loan (`trailmix_ludicrous/gcd.rs`, `trailmix_ludicrous/mod.rs`, `mod.rs`)

**New builder hooks** (`BExt` in `trailmix_ludicrous/mod.rs`):

- `loan_zero_qubit(q)` pushes `q` onto `free_qubits` and decrements
  `active_qubits`. It emits no `R`. The caller has already returned `q` to |0⟩.
- `reclaim_zero_qubit(q)` calls `reacquire(q)`, which takes that exact id back
  out of the free list. It panics if the id is not free at that moment.

See [venting-and-wire-loans](../concepts/venting-and-wire-loans.md) for this
loan pattern.

**New helpers in `gcd.rs`:**

- `park_known_one(q)` runs `x(q)`, then loans the wire if `TLM_LOAN_ODD_U0=1`, or
  otherwise does `zero_and_free(q)`.
- `restore_known_one(parked)` reclaims the same wire, or allocates a new one,
  and then runs `x`.
- `park_odd_u0_enabled(i, side)` is true if `TLM_PARK_ODD_U0=1`, or the per-side
  `TLM_PARK_ODD_U0_FWD` / `_REV` is set, and `i < TLM_PARK_ODD_U0_LIMIT` (no limit by default).

**Where the loan opens and closes:**

- **`forward_gcd_jump`.** The loan opens right after step 4, `cswap(swp, u[j], v[j])`.
  It covers step 5, the controlled subtract `controlled_add_active(subtracted, u, v)`
  inside its X-sandwich, and the fused `apply_step_reverse` that builds λ. It closes
  before the symbol is written to the tape.
- **`reverse_gcd_jump`.** The loan opens before the fused forward apply and
  the inverse subtract `v += subtracted·u`, and closes before the inverse cswap.

**Why `u[0]` is known.**

- The walk keeps `u` odd. At step 0 `u = q`, which is odd. A swap only happens when
  `v` is odd too, since `s = b AND (v < u)` with `b = v[0]`.
- So after the cswap, `u[0] = 1` on every input, and `X(u[0])` returns it to |0⟩
  exactly.
- `controlled_add_active` emits bit 0 as `cx(ctrl, y[0])`, because `x[0] = 1`, and
  runs the adder on bits `1..`. So it never reads `u[0]`.
- `apply_step_reverse` and `apply_step_forward` act on the payload registers and the
  symbol bits, not on `u`. If either read `u[0]`, the wire would hold another value
  during the loan, and the circuit would fail validation.

**Why it lowers Q.** The free list is LIFO, so the next allocation inside the
subtract or apply gets `u[0]`'s index. The peak inside that window is one wire
lower. The measured peak is 1165. Both knobs are baked in `build()`:
`TLM_PARK_ODD_U0=1` and `TLM_LOAN_ODD_U0=1`.

### 2. `d AND NOT e` from the live intersection (`trailmix_ludicrous/fused.rs`)

- **What the fold needs.** The fused pseudo-Mersenne fold of the doubling folds two
  overflow bits `e` and `d` at once. It needs four control combinations:
  `cc = e AND d`, `dne = d AND NOT e`, `sxor = e XOR d` and `sor = e OR d`.
- **Old way.** `dne` was built as `x(e); ccx(e, d, dne); x(e)`, which is one CCX. It was
  cleared with a measured `clear_and`, which costs `hmr` plus `cz_if_bit` and no Toffoli.
- **New way.** `toggle_dnot_e_from_intersection(d, cc, dne)` runs `cx(d, dne); cx(cc, dne)`.
  - This uses the identity `d AND NOT e = d XOR (e AND d)`, with `cc` already live.
  - The same two CX gates also clear `dne`.
- **Where.** The change is made at every build and clear site: in `add_mf_fold_clean_tail`,
  at the initial build, the `LAST_AND` clear, the reverse-pass rebuild and the final clear,
  and in `build_fold_controls` / `uncompute_fold_controls`.
- **Saving.** Each build saves one CCX, and each clear saves one `hmr`.

### 3. One target-fanout rewrite (new `src/point_add/single_ccx_fanout.rs`, 375 lines)

- **Identity.** `rewrite_first_target_fanout(ops, 96)` applies
  `CCX(a,b→t); CX(t→u); CCX(a,b→t) = CX(t→u); CCX(a,b→u)` exactly once, at the first
  place where it is valid.
- **Validity check.** The check uses dependency epochs. Between the two CCX nothing may
  write `a` or `b`, use `t` as a control (except the single CX blocker), put a phase on
  `t`, or measure, reset or swap the three wires, and condition-stack changes are
  barriers.
- **Safety.** The last 96 ops, the nonce tail, are checked byte-for-byte to be unchanged.
- **Call site.** `build()` calls it after `build_trailmix_ludicrous_ops()`, and with it
  after the constant-propagation pass. It asserts that the stream got exactly one op
  shorter, which saves one CCX.
- The file is byte-identical to the one in `b1dec1e`. See
  [dead-gate-strip](../concepts/dead-gate-strip.md) for the closure version of this
  rewrite, which later commits loop until no match is left.

### 4. Nonce

The default `DIALOG_TAIL_NONCE` goes from 123000008384 to 100000033721.

## Why it is still correct, and what it risks

All three parts are exact.

- **The loan** relies on two invariants: `u[0] = 1` after every cswap, and nothing
  inside the window reads `u[0]`.
  - If `u[0]` were not 1, the X would leave a 1 on a "free" wire. The next allocation
    would start dirty, and the error would show up as ancilla garbage or classical errors.
  - If something read `u[0]` during the window, it would see a borrowed scratch value.
  - `reacquire` also checks that the wire is back in the free list when the loan closes.
- **The `dne` identity** is Boolean, so it holds on every input.
- **The fan-out rewrite** is a gate identity checked by the dependency scan.

The new nonce `100000033721` gives 0 classical, 0 phase and 0 ancilla failures
over all 9,024 shots. The trailmix approximations (`ITERS`, `SCHED_J2`, `GAP_J2`,
truncated folds) are unchanged. See
[nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The qubit drop comes from shortening the lifetime of one wire by lending it out
while its value is known. That is ancilla-lifetime / venting. The Toffoli cuts are
a gate identity (**Fusion**) and a ported peephole. They are secondary, and they
are not this author's lever.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout ed2715f -- src/point_add`.
   - `git diff --ignore-cr-at-eol ed2715f cea9f5f -- src/point_add` is about 520 lines in 5 files.
   - Do not start from the git parent `b02b354`. This commit keeps the original
     607-line `constprop.rs` from `497cc20`, so diffing against the parent would
     delete b02b354's fixpoint, pair and affine passes, about 1,170 lines.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol cea9f5f -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `DIALOG_*`, `TLM_*`, `LUD_*` or `CONSTPROP_*`
   environment variables set. Expect:
   - 1165 qubits
   - 1,413,487 average Toffoli (rounded; 1,413,487.417 before rounding)
   - score 1,646,712,355
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `100000033721` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 141d5f9..bc1f2ba 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -80,6 +80,7 @@ mod rounds;
 pub(crate) use rounds::*;
 
 mod trailmix_ludicrous;
+mod single_ccx_fanout;
 
 thread_local! {
     static D1_PHASE_CORRECTED_PRODUCT_CORE_SCOPE: std::cell::Cell<bool> =
@@ -1986,13 +1987,34 @@ pub fn build() -> Vec<Op> {
     // shots at 1166q x 1,414,439.206 => 1,414,439 x 1166 = 1,649,235,874.
     set_default_env("LUD_EXTRA_FOLD_VENTS", "2");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "18");
-    set_default_env("DIALOG_TAIL_NONCE", "123000008384");
+    set_default_env("DIALOG_TAIL_NONCE", "100000033721");
     set_default_env("TLM_COUT_LAYOUT_SEARCH", "1");
     set_default_env("TLM_COUT_LAYOUT_MARGIN", "0");
     set_default_env("TLM_COUT_LAYOUT_FORCE_M1_KS", "129");
     set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_SEARCH", "1");
     set_default_env("TLM_GCD_ADAPTIVE_LAYOUT_MARGIN", "0");
-    trailmix_ludicrous::build_trailmix_ludicrous_ops()
+    // u0 lifecycle loan (peak 1166->1165) — BAKED so the env-less grader reproduces it.
+    set_default_env("TLM_PARK_ODD_U0", "1");
+    set_default_env("TLM_LOAN_ODD_U0", "1");
+    let ops = trailmix_ludicrous::build_trailmix_ludicrous_ops();
+    let input_ops = ops.len();
+    let (ops, witness) = single_ccx_fanout::rewrite_first_target_fanout(ops, 96)
+        .unwrap_or_else(|error| panic!("single-fanout rewrite failed: {error}"));
+    assert_eq!(ops.len() + 1, input_ops, "single-fanout output-op drift");
+    eprintln!(
+        "SINGLE_CCX_FANOUT: PASS input_ops={} output_ops={} first={} blocker={} second={} controls={},{} old_target={} new_target={} condition={}",
+        input_ops,
+        ops.len(),
+        witness.first_index,
+        witness.blocker_index,
+        witness.second_index,
+        witness.control_a,
+        witness.control_b,
+        witness.old_target,
+        witness.new_target,
+        witness.condition,
+    );
+    ops
 }
 
 pub fn square_window_selftest() -> Result<(), String> {
diff --git a/src/point_add/single_ccx_fanout.rs b/src/point_add/single_ccx_fanout.rs
new file mode 100644
index 0000000..5c41ab5
--- /dev/null
+++ b/src/point_add/single_ccx_fanout.rs
@@ -0,0 +1,375 @@
+use crate::circuit::{Op, OperationType, NO_BIT, NO_QUBIT};
+use std::collections::HashMap;
+
+const NO_INDEX: usize = usize::MAX;
+
+#[derive(Clone, Copy, Debug, PartialEq, Eq)]
+pub(crate) struct FanoutWitness {
+    pub(crate) first_index: usize,
+    pub(crate) blocker_index: usize,
+    pub(crate) second_index: usize,
+    pub(crate) control_a: u64,
+    pub(crate) control_b: u64,
+    pub(crate) old_target: u64,
+    pub(crate) new_target: u64,
+    pub(crate) condition: u64,
+}
+
+#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
+struct GateKey {
+    control_a: u64,
+    control_b: u64,
+    target: u64,
+}
+
+#[derive(Clone, Copy, Debug)]
+struct Candidate {
+    index: usize,
+    snapshot: [u64; 8],
+}
+
+struct Epochs {
+    x_targets: Vec<u64>,
+    x_controls: Vec<u64>,
+    z_touches: Vec<u64>,
+    hard_touches: Vec<u64>,
+    swap_touches: Vec<u64>,
+    swap_pairs: HashMap<(u64, u64), u64>,
+    last_x_control: Vec<usize>,
+}
+
+impl Epochs {
+    fn new(wire_count: usize) -> Self {
+        Self {
+            x_targets: vec![0; wire_count],
+            x_controls: vec![0; wire_count],
+            z_touches: vec![0; wire_count],
+            hard_touches: vec![0; wire_count],
+            swap_touches: vec![0; wire_count],
+            swap_pairs: HashMap::new(),
+            last_x_control: vec![NO_INDEX; wire_count],
+        }
+    }
+
+    fn swap_pair(&self, a: u64, b: u64) -> u64 {
+        *self.swap_pairs.get(&sorted_pair(a, b)).unwrap_or(&0)
+    }
+}
+
+fn sorted_pair(a: u64, b: u64) -> (u64, u64) {
+    if a <= b {
+        (a, b)
+    } else {
+        (b, a)
+    }
+}
+
+fn ccx_key(op: &Op) -> Option<GateKey> {
+    if op.kind != OperationType::CCX || op.c_condition != NO_BIT {
+        return None;
+    }
+    let (control_a, control_b) = sorted_pair(op.q_control1.0, op.q_control2.0);
+    Some(GateKey {
+        control_a,
+        control_b,
+        target: op.q_target.0,
+    })
+}
+
+fn x_controls(op: &Op) -> Option<([u64; 2], usize)> {
+    match op.kind {
+        OperationType::X => Some(([NO_QUBIT.0; 2], 0)),
+        OperationType::CX => Some(([op.q_control1.0, NO_QUBIT.0], 1)),
+        OperationType::CCX => Some(([op.q_control1.0, op.q_control2.0], 2)),
+        _ => None,
+    }
+}
+
+fn quantum_support(op: &Op) -> ([u64; 3], usize) {
+    match op.kind {
+        OperationType::X | OperationType::Z | OperationType::R | OperationType::Hmr => {
+            ([op.q_target.0, NO_QUBIT.0, NO_QUBIT.0], 1)
+        }
+        OperationType::CX | OperationType::CZ | OperationType::Swap => {
+            ([op.q_control1.0, op.q_target.0, NO_QUBIT.0], 2)
+        }
+        OperationType::CCX | OperationType::CCZ => {
+            ([op.q_control2.0, op.q_control1.0, op.q_target.0], 3)
+        }
+        _ => ([NO_QUBIT.0; 3], 0),
+    }
+}
+
+fn max_wire(ops: &[Op]) -> usize {
+    ops.iter()
+        .flat_map(|op| {
+            let (support, count) = quantum_support(op);
+            support.into_iter().take(count)
+        })
+        .max()
+        .unwrap_or(0) as usize
+}
+
+fn snapshot(key: GateKey, epochs: &Epochs) -> [u64; 8] {
+    let swap_touches = epochs.swap_touches[key.control_a as usize]
+        + epochs.swap_touches[key.control_b as usize]
+        + epochs.swap_touches[key.target as usize];
+    let swap_blockers = swap_touches - 2 * epochs.swap_pair(key.control_a, key.control_b);
+    [
+        epochs.x_targets[key.control_a as usize],
+        epochs.x_targets[key.control_b as usize],
+        epochs.x_controls[key.target as usize],
+        epochs.z_touches[key.target as usize],
+        epochs.hard_touches[key.control_a as usize],
+        epochs.hard_touches[key.control_b as usize],
+        epochs.hard_touches[key.target as usize],
+        swap_blockers,
+    ]
+}
+
+fn advance_epochs(op: &Op, index: usize, epochs: &mut Epochs) -> bool {
+    if matches!(
+        op.kind,
+        OperationType::PushCondition | OperationType::PopCondition
+    ) {
+        return true;
+    }
+    if let Some((controls, count)) = x_controls(op) {
+        epochs.x_targets[op.q_target.0 as usize] += 1;
+        for &control in &controls[..count] {
+            epochs.x_controls[control as usize] += 1;
+            epochs.last_x_control[control as usize] = index;
+        }
+        return false;
+    }
+    match op.kind {
+        OperationType::Z | OperationType::CZ | OperationType::CCZ => {
+            let (support, count) = quantum_support(op);
+            for &wire in &support[..count] {
+                epochs.z_touches[wire as usize] += 1;
+            }
+        }
+        OperationType::Swap => {
+            let (a, b) = sorted_pair(op.q_control1.0, op.q_target.0);
+            epochs.swap_touches[a as usize] += 1;
+            epochs.swap_touches[b as usize] += 1;
+            *epochs.swap_pairs.entry((a, b)).or_insert(0) += 1;
+        }
+        OperationType::R | OperationType::Hmr => {
+            epochs.hard_touches[op.q_target.0 as usize] += 1;
+        }
+        _ => {}
+    }
+    false
+}
+
+fn validate_protected_tail(ops: &[Op], protected: usize) -> Result<Vec<Op>, String> {
+    if protected > ops.len() || protected % 2 != 0 {
+        return Err("invalid protected-tail length".to_owned());
+    }
+    let tail = &ops[ops.len() - protected..];
+    for (pair_index, pair) in tail.chunks_exact(2).enumerate() {
+        if pair[0] != pair[1]
+            || pair[0].kind != OperationType::X
+            || pair[0].c_condition != NO_BIT
+        {
+            return Err(format!(
+                "protected nonce pair {pair_index} is not unconditional X/X"
+            ));
+        }
+    }
+    Ok(tail.to_vec())
+}
+
+/// Apply exactly one target-fanout conjugation:
+///
+/// CCX(a,b,t); CX(t,u); CCX(a,b,t) = CX(t,u); CCX(a,b,u).
+///
+/// Dependency epochs permit commuting operations around the sole CX blocker.
+/// Condition-stack transitions are barriers, and the fixed nonce suffix is
+/// checked byte-for-byte after the rewrite.
+pub(crate) fn rewrite_first_target_fanout(
+    ops: Vec<Op>,
+    protected_tail_ops: usize,
+) -> Result<(Vec<Op>, FanoutWitness), String> {
+    let protected_tail = validate_protected_tail(&ops, protected_tail_ops)?;
+    let prefix_len = ops.len() - protected_tail_ops;
+    let mut epochs = Epochs::new(max_wire(&ops) + 1);
+    let mut candidates = HashMap::<GateKey, Candidate>::new();
+
+    for index in 0..prefix_len {
+        let op = ops[index];
+        if let Some(key) = ccx_key(&op) {
+            let current_snapshot = snapshot(key, &epochs);
+            if let Some(prior) = candidates.get(&key).copied() {
+                let mut deltas = [0u64; 8];
+                let monotonic = deltas
+                    .iter_mut()
+                    .zip(current_snapshot.into_iter().zip(prior.snapshot))
+                    .all(|(delta, (current, old))| {
+                        if let Some(value) = current.checked_sub(old) {
+                            *delta = value;
+                            true
+                        } else {
+                            false
+                        }
+                    });
+                let blocker_index = epochs.last_x_control[key.target as usize];
+                let blocker = (blocker_index != NO_INDEX).then(|| ops[blocker_index]);
+                if monotonic
+                    && deltas == [0, 0, 1, 0, 0, 0, 0, 0]
+                    && prior.index < blocker_index
+                    && blocker_index < index
+                    && blocker.is_some_and(|blocker| {
+                        blocker.kind == OperationType::CX
+                            && blocker.q_control1.0 == key.target
+                            && blocker.q_target.0 != key.control_a
+                            && blocker.q_target.0 != key.control_b
+                            && blocker.q_target.0 != key.target
+                    })
+                {
+                    let blocker = blocker.unwrap();
+                    let mut replacement = Op::empty();
+                    replacement.kind = OperationType::CCX;
+                    replacement.q_control2.0 = key.control_a;
+                    replacement.q_control1.0 = key.control_b;
+                    replacement.q_target = blocker.q_target;
+                    replacement.c_condition = blocker.c_condition;
+                    let witness = FanoutWitness {
+                        first_index: prior.index,
+                        blocker_index,
+                        second_index: index,
+                        control_a: key.control_a,
+                        control_b: key.control_b,
+                        old_target: key.target,
+                        new_target: blocker.q_target.0,
+                        condition: blocker.c_condition.0,
+                    };
+                    let mut rewritten = Vec::with_capacity(ops.len() - 1);
+                    for (op_index, stream_op) in ops.into_iter().enumerate() {
+                        if op_index == prior.index || op_index == index {
+                            continue;
+                        }
+                        rewritten.push(stream_op);
+                        if op_index == blocker_index {
+                            rewritten.push(replacement);
+                        }
+                    }
+                    if rewritten.len() + 1 != prefix_len + protected_tail_ops {
+                        return Err("single-fanout rewrite changed the wrong op count".to_owned());
+                    }
+                    if rewritten[rewritten.len() - protected_tail_ops..] != protected_tail {
+                        return Err("single-fanout rewrite changed the nonce suffix".to_owned());
+                    }
+                    return Ok((rewritten, witness));
+                }
+            }
+            candidates.insert(
+                key,
+                Candidate {
+                    index,
+                    snapshot: current_snapshot,
+                },
+            );
+        }
+        if advance_epochs(&op, index, &mut epochs) {
+            candidates.clear();
+        }
+    }
+    Err("no target-fanout conjugation found".to_owned())
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+    use crate::circuit::{BitId, QubitId};
+
+    fn x(target: u64) -> Op {
+        let mut op = Op::empty();
+        op.kind = OperationType::X;
+        op.q_target = QubitId(target);
+        op
+    }
+
+    fn cx(control: u64, target: u64) -> Op {
+        let mut op = Op::empty();
+        op.kind = OperationType::CX;
+        op.q_control1 = QubitId(control);
+        op.q_target = QubitId(target);
+        op
+    }
+
+    fn ccx(a: u64, b: u64, target: u64) -> Op {
+        let mut op = Op::empty();
+        op.kind = OperationType::CCX;
+        op.q_control2 = QubitId(a);
+        op.q_control1 = QubitId(b);
+        op.q_target = QubitId(target);
+        op
+    }
+
+    fn nonce_tail() -> Vec<Op> {
+        (0..48).flat_map(|_| [x(0), x(0)]).collect()
+    }
+
+    fn eval(ops: &[Op], mut state: u8, condition: bool) -> u8 {
+        for op in ops {
+            if op.c_condition != NO_BIT && !condition {
+                continue;
+            }
+            match op.kind {
+                OperationType::CX => {
+                    if ((state >> op.q_control1.0) & 1) != 0 {
+                        state ^= 1 << op.q_target.0;
+                    }
+                }
+                OperationType::CCX => {
+                    if ((state >> op.q_control1.0) & 1) != 0
+                        && ((state >> op.q_control2.0) & 1) != 0
+                    {
+                        state ^= 1 << op.q_target.0;
+                    }
+                }
+                OperationType::X => state ^= 1 << op.q_target.0,
+                _ => {}
+            }
+        }
+        state
+    }
+
+    #[test]
+    fn first_fanout_rewrite_is_exact_and_tail_stable() {
+        let mut blocker = cx(2, 3);
+        blocker.c_condition = BitId(7);
+        let before_prefix = vec![ccx(0, 1, 2), blocker, ccx(1, 0, 2)];
+        let mut before = before_prefix.clone();
+        let tail = nonce_tail();
+        before.extend(tail.clone());
+        let (after, witness) = rewrite_first_target_fanout(before, 96).unwrap();
+        assert_eq!(witness.first_index, 0);
+        assert_eq!(witness.blocker_index, 1);
+        assert_eq!(witness.second_index, 2);
+        assert_eq!(witness.condition, 7);
+        assert_eq!(&after[after.len() - 96..], tail.as_slice());
+        for condition in [false, true] {
+            for state in 0..16 {
+                assert_eq!(
+                    eval(&before_prefix, state, condition),
+                    eval(&after[..2], state, condition)
+                );
+            }
+        }
+    }
+
+    #[test]
+    fn condition_stack_is_a_hard_barrier() {
+        let mut push = Op::empty();
+        push.kind = OperationType::PushCondition;
+        push.c_condition = BitId(9);
+        let mut pop = Op::empty();
+        pop.kind = OperationType::PopCondition;
+        let mut ops = vec![ccx(0, 1, 2), push, cx(2, 3), pop, ccx(0, 1, 2)];
+        ops.extend(nonce_tail());
+        assert!(rewrite_first_target_fanout(ops, 96).is_err());
+    }
+}
diff --git a/src/point_add/trailmix_ludicrous/fused.rs b/src/point_add/trailmix_ludicrous/fused.rs
index 97fa7a9..970514b 100644
--- a/src/point_add/trailmix_ludicrous/fused.rs
+++ b/src/point_add/trailmix_ludicrous/fused.rs
@@ -29,6 +29,19 @@ fn clear_and(circ: &mut B, t: &QubitId, a: &QubitId, b: &QubitId) {
     circ.cz_if_bit(*a, *b, bit);
 }
 
+/// Toggle `d AND NOT e` into `dne`, given the live intersection `cc = e AND d`.
+/// The Boolean identity `d & !e = d ^ (e & d)` replaces one CCX with two CX.
+/// This is an involution, so the same sequence clears `dne` after use.
+fn toggle_dnot_e_from_intersection(
+    circ: &mut B,
+    d: &QubitId,
+    cc: &QubitId,
+    dne: &QubitId,
+) {
+    circ.cx(*d, *dne);
+    circ.cx(*cc, *dne);
+}
+
 /// Carry-propagate `c` into the pure-propagation tail `y[..]` via a cascade of
 /// prefix-controlled increments (`mcx_clean_k`, log* ancillae): the clean-tail
 /// fold's tail [nv, L).
@@ -61,9 +74,12 @@ fn add_mf_fold_clean_tail(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId],
     let mut cc = Some(circ.alloc_qubit());
     circ.ccx(*e, *d, *cc.as_ref().unwrap());
     let mut dne = Some(circ.alloc_qubit());
-    circ.x(*e);
-    circ.ccx(*e, *d, *dne.as_ref().unwrap());
-    circ.x(*e);
+    toggle_dnot_e_from_intersection(
+        circ,
+        d,
+        cc.as_ref().unwrap(),
+        dne.as_ref().unwrap(),
+    );
     let mut sxor = Some(circ.alloc_qubit());
     circ.cx(*e, *sxor.as_ref().unwrap());
     circ.cx(*d, *sxor.as_ref().unwrap());
@@ -122,9 +138,7 @@ fn add_mf_fold_clean_tail(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId],
         }
         if i == LAST_AND {
             let dn = dne.take().unwrap();
-            circ.x(*e);
-            clear_and(circ, &dn, e, d);
-            circ.x(*e);
+            toggle_dnot_e_from_intersection(circ, d, cc.as_ref().unwrap(), &dn);
             circ.zero_and_free(dn);
             let c = cc.take().unwrap();
             clear_and(circ, &c, e, d);
@@ -154,9 +168,7 @@ fn add_mf_fold_clean_tail(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId],
             circ.ccx(*e, *d, c);
             cc = Some(c);
             let dn = circ.alloc_qubit();
-            circ.x(*e);
-            circ.ccx(*e, *d, dn);
-            circ.x(*e);
+            toggle_dnot_e_from_intersection(circ, d, cc.as_ref().unwrap(), &dn);
             dne = Some(dn);
         }
         if i == LAST_DERIVED {
@@ -207,9 +219,7 @@ fn add_mf_fold_clean_tail(circ: &mut B, e: &QubitId, d: &QubitId, y: &[QubitId],
     let so = sor.take().unwrap();
     let cc = cc.take().unwrap();
     let dne = dne.take().unwrap();
-    circ.x(*e);
-    clear_and(circ, &dne, e, d);
-    circ.x(*e);
+    toggle_dnot_e_from_intersection(circ, d, &cc, &dne);
     circ.zero_and_free(dne);
     circ.cx(sx, so);
     circ.cx(cc, so);
@@ -237,16 +247,12 @@ fn build_fold_controls(circ: &mut B, e: &QubitId, d: &QubitId) -> (QubitId, Qubi
     circ.cx(sxor, sor);
     circ.cx(cc, sor);
     let dne = circ.alloc_qubit();
-    circ.x(*e);
-    circ.ccx(*e, *d, dne);
-    circ.x(*e);
+    toggle_dnot_e_from_intersection(circ, d, &cc, &dne);
     (cc, sxor, sor, dne)
 }
 
 fn uncompute_fold_controls(circ: &mut B, e: &QubitId, d: &QubitId, cc: QubitId, sxor: QubitId, sor: QubitId, dne: QubitId) {
-    circ.x(*e);
-    clear_and(circ, &dne, e, d);
-    circ.x(*e);
+    toggle_dnot_e_from_intersection(circ, d, &cc, &dne);
     circ.zero_and_free(dne);
     circ.cx(sxor, sor);
     circ.cx(cc, sor);
diff --git a/src/point_add/trailmix_ludicrous/gcd.rs b/src/point_add/trailmix_ludicrous/gcd.rs
index 310baf1..a198abd 100644
--- a/src/point_add/trailmix_ludicrous/gcd.rs
+++ b/src/point_add/trailmix_ludicrous/gcd.rs
@@ -79,6 +79,47 @@ fn clear_and(circ: &mut B, t: &QubitId, a: &QubitId, b: &QubitId) {
     circ.cz_if_bit(*a, *b, bit);
 }
 
+fn park_odd_u0_enabled(i: usize, side: &str) -> bool {
+    let all = std::env::var("TLM_PARK_ODD_U0").ok().as_deref() == Some("1");
+    let side_on = std::env::var(format!("TLM_PARK_ODD_U0_{side}"))
+        .ok()
+        .as_deref()
+        == Some("1");
+    if !all && !side_on {
+        return false;
+    }
+    let limit = std::env::var("TLM_PARK_ODD_U0_LIMIT")
+        .ok()
+        .and_then(|v| v.parse::<usize>().ok())
+        .unwrap_or(usize::MAX);
+    i < limit
+}
+
+fn loan_odd_u0_enabled() -> bool {
+    std::env::var("TLM_LOAN_ODD_U0").ok().as_deref() == Some("1")
+}
+
+fn park_known_one(circ: &mut B, q: QubitId) -> QubitId {
+    circ.x(q);
+    if loan_odd_u0_enabled() {
+        circ.loan_zero_qubit(q);
+    } else {
+        circ.zero_and_free(q);
+    }
+    q
+}
+
+fn restore_known_one(circ: &mut B, parked: QubitId) -> QubitId {
+    let q = if loan_odd_u0_enabled() {
+        circ.reclaim_zero_qubit(parked);
+        parked
+    } else {
+        circ.alloc_qubit()
+    };
+    circ.x(q);
+    q
+}
+
 // =====================================================================
 // Per-step variable shift (controlled right/left shift by 1).
 // =====================================================================
@@ -267,6 +308,12 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         for j in 0..current_n {
             circ.cswap(swp, u[j], v[j]);
         }
+        let parked_u0 = if park_odd_u0_enabled(i, "FWD") {
+            let q = u[0];
+            Some(park_known_one(circ, q))
+        } else {
+            None
+        };
         // 5) v -= subtracted * u (controlled mod-free subtract on the active width;
         //    post-swap v >= u so no borrow on a fitting input). X-sandwich add.
         for q in &v[..current_n] {
@@ -284,6 +331,9 @@ pub fn forward_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, apply_inv: Option<(&
         if let Some((xr, yr)) = apply_inv {
             apply_step_reverse(circ, i, &subtracted, &swp, &s2, &t1, xr, yr);
         }
+        if let Some(q) = parked_u0 {
+            u[0] = restore_known_one(circ, q);
+        }
 
         // 6) record the symbol into fresh |0> slots (returning the ancilla to |0>).
         let slots: Vec<QubitId> = (0..sym_bits).map(|_| circ.alloc_qubit()).collect();
@@ -417,6 +467,13 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
             circ.zero_and_free(q);
         }
 
+        let parked_u0 = if park_odd_u0_enabled(i, "REV") {
+            let q = u[0];
+            Some(park_known_one(circ, q))
+        } else {
+            None
+        };
+
         // Fused forward apply (Direction::Forward multiply): apply this divstep's
         // symbol to the coordinate pair using the live symbol bits, in reverse iter
         // order matching apply_step_forward's order, so the tape is never materialized
@@ -430,6 +487,9 @@ pub fn reverse_gcd_jump(circ: &mut B, v: &mut Vec<QubitId>, tape: &mut Vec<Qubit
         // s_2^-1, shift1^-1.
         // a) sub^-1: v += subtracted*u (X-sandwich cancels).
         controlled_add_active(circ, &subtracted, &u[..current_n], &v[..current_n]);
+        if let Some(q) = parked_u0 {
+            u[0] = restore_known_one(circ, q);
+        }
         // b) cswap^-1 (involutory).
         for j in 0..current_n {
             circ.cswap(swp, u[j], v[j]);
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index ed2e818..5ca8bdd 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -36,6 +36,8 @@ const N: usize = 256;
 // circuit modules also need a phase Z, a doubly-controlled Z, the free Neg, a
 // Fredkin swap, and bit-conditioned forms; this trait supplies them on `B`.
 pub(super) trait BExt {
+    fn loan_zero_qubit(&mut self, q: QubitId);
+    fn reclaim_zero_qubit(&mut self, q: QubitId);
     fn z(&mut self, q: QubitId);
     fn ccz(&mut self, a: QubitId, b: QubitId, c: QubitId);
     fn neg(&mut self);
@@ -49,6 +51,19 @@ pub(super) trait BExt {
 }
 
 impl BExt for B {
+    fn loan_zero_qubit(&mut self, q: QubitId) {
+        self.free_qubits
+            .push(q.0.try_into().expect("qubit id fits in u32"));
+        if self.active_qubits > 0 {
+            self.active_qubits -= 1;
+        }
+        self.record_active_timeline();
+    }
+
+    fn reclaim_zero_qubit(&mut self, q: QubitId) {
+        self.reacquire(q);
+    }
+
     fn z(&mut self, q: QubitId) {
         let mut op = Op::empty();
         op.kind = OperationType::Z;
```

