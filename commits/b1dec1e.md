# b1dec1e — Build the fold control d∧¬e from the live e∧d with two CNOTs, hold 3 more comparator carries, and cancel one CCX pair

| | |
| --- | --- |
| Contestant | nasqret |
| Date | 2026-06-19 |
| Submission | `abbbcc8` |
| Commit | `b1dec1edb932111e5860162c321868abae8e624a` |
| Result | 1166 qubits × 1,421,183 Toffoli = **1,657,099,378** |
| Base | `70bf11a` (git parent, rubenmarcus): 1166 qubits × 1,422,258 Toffoli = 1,658,352,828 |
| Change vs base | qubits ±0, Toffoli −1,075, score −1,253,450 (leaderboard Δ −1,253,450) |
| Family | Fusion → gate/op fusion |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md), [modular-fold](../concepts/modular-fold.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit makes three exact changes to the trailmix circuit:

1. **Fold controls.** The fused `(e + 2d)·f` fold needs the control
   `d ∧ ¬e`. The circuit already holds `e ∧ d` at that moment, so
   `d ∧ ¬e = d ⊕ (e ∧ d)` can be made with two CNOTs instead of an
   X-sandwiched CCX. Clearing it is the same two CNOTs, instead of a measured
   uncompute.
2. **Comparator carries.** The GCD swap comparators' extra held-carry
   allowance goes from +4 to +7 (see [`75851e6`](75851e6.md)).
3. **CCX pair.** A post-pass over the finished op stream finds the first
   pattern `CCX(a,b,t); CX(t,u); CCX(a,b,t)` and rewrites it to
   `CX(t,u); CCX(a,b,u)`, which removes one CCX.

Together they save 1,075 average Toffoli at 1166 qubits.

## What changed and why it saves Toffoli

### 1. `d ∧ ¬e` from the intersection (`trailmix_ludicrous/fused.rs`)

- Background: the fused double `y := 2y(1 + s2)` folds `(e + 2d)·f` into
  `y`'s low 54 bits (see [modular-fold](../concepts/modular-fold.md)). The
  addend bit at each position is one of `e`, `d`, `e⊕d`, `e∨d`, `d∧¬e` or
  `e∧d`. These derived controls are built as ancillas `sxor`, `sor`, `dne` and
  `cc`.
- New helper `toggle_dnot_e_from_intersection(d, cc, dne)`: `cx(d, dne)` and
  `cx(cc, dne)`. With `cc = e∧d`, this toggles `dne` by `d ⊕ (e∧d) = d∧¬e`.
  It is its own inverse, so it both sets and clears.
- It replaces, in `add_mf_fold_clean_tail`, `build_fold_controls` and
  `uncompute_fold_controls`:
  - every compute of the form `x(e); ccx(e, d, dne); x(e)`, which is 1 CCX
    each: at fold start, and on the reverse rebuild at `LAST_AND`;
  - every clear of the form `x(e); clear_and(dne, e, d); x(e)`, which is
    `hmr` plus a conditional CZ: at `LAST_AND`, at the end, and in
    `uncompute_fold_controls`.
- `cc` is live at every one of these points: it is computed just before
  `dne`, and cleared just after it. Each clean fused fold therefore saves 2
  CCX, plus a couple of measurements. These folds run in every GCD step of
  both passes.

### 2. Comparator held-carry allowance +4 → +7 (`trailmix_ludicrous/mod.rs`)

- `next_cmp_k()` now returns the `CMP_K` entry plus 7.
- In `comparator::compare_geq_chunked_middle`, the top `k` bits of the
  swap-decision window use fresh carries. Each costs 1 CCX forward and is
  erased by `hmr` for free. The other bits use in-place MAJ/UMA, which costs
  2 CCX. So 3 more bits per compare save 3 CCX on the forward decision, and
  about 1.5 on average on the conditionally executed vented uncompute. The
  cost is 3 more transient qubits during each compare, and the peak stays at
  1166.
- The window `GAP_J2[i]` is unchanged, so the result is the same. See
  [measurement-uncompute](../concepts/measurement-uncompute.md).

### 3. One CCX target-fanout conjugation (new `src/point_add/single_ccx_fanout.rs`, 375 lines)

- `rewrite_first_target_fanout(ops, 96)` scans the op stream, excluding the
  96-op nonce tail, for:
  - two identical unconditioned `CCX(a, b, t)` gates;
  - with exactly one op between them that uses `t` as a control, a
    `CX(t, u)` with `u ∉ {a, b, t}`, which may be classically conditioned.
- It checks, with per-wire "epoch" counters, that nothing else between them
  writes `a` or `b`, controls on `t`, puts a phase on `t`, measures or resets
  any of the three, or swaps them. Any `PushCondition`/`PopCondition` resets
  the search.
- It applies the identity
  `CCX(a,b,t); CX(t,u); CCX(a,b,t) = CX(t,u); CCX(a,b,u)`: drop both CCX,
  and insert `CCX(a, b, u)` right after the CX, with the CX's condition.
  Check: on the left `u ^= t₀ ⊕ ab` and `t` returns to `t₀`; on the right
  `u ^= t₀`, then `u ^= ab`.
- It does this for the first match only. It checks that exactly one op was
  removed and that the nonce tail is byte-identical. It includes unit tests:
  exhaustive equality on 4 wires, and condition-stack barriers.
- This saves one Toffoli. See [dead-gate-strip](../concepts/dead-gate-strip.md)
  for the later, larger op-stream rewriting passes.
- `src/point_add/mod.rs`: declares `mod single_ccx_fanout;`. `build()` runs
  the rewrite on the trailmix op stream, asserts the op count fell by
  exactly 1, and prints a `SINGLE_CCX_FANOUT: PASS …` witness line to stderr.

### Nonce

`DIALOG_TAIL_NONCE` default in `build()`: `"1006790"` → `"13955"`.

## Why it is still correct, and what it risks

- **Exact.** All three changes leave the computed values unchanged:
  - a Boolean identity on live wires;
  - a different carry layout for the same truncated window;
  - a verified gate identity.

  No truncation moves, so the hard inputs are the base's. A mistake in any of
  them would show up as ancilla or phase garbage.
- **Nonce.** Nonce `13955` was checked on the author's cluster with the
  trusted evaluator: 0 classical, 0 phase and 0 ancilla failures over 9,024
  shots. The explicit and environment-free op streams hash identically. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The main savings come from gate-level algebra:
- reusing a live AND to build a second one with CNOTs only;
- merging a CCX–CX–CCX sandwich into CX–CCX.

That is gate/op fusion. The `CMP_K` bump is an exact headroom retune that
rides along in the same commit.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 70bf11a -- src/point_add`. The base is the git
   parent. It is the bket7 tree [`75851e6`](75851e6.md) with a new nonce and a
   stray `mod.rs.bak`, which this commit keeps unchanged.
   `git diff --ignore-cr-at-eol 70bf11a b1dec1e -- src/point_add` is 442
   lines in 4 files, 375 of them the new `single_ccx_fanout.rs`.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol b1dec1e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `LUD_*`, `TRAILMIX_*`, `DIALOG_*` or `TLM_*` environment variables set.
   `build_circuit` prints the `SINGLE_CCX_FANOUT: PASS` line. Expect:
   - 1166 qubits
   - 1,421,183 average Toffoli (1,421,183.147 before rounding)
   - score 1,657,099,378
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `13955` and an identical op stream.
Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 08411bb..ab8fa10 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -80,6 +80,7 @@ mod rounds;
 pub(crate) use rounds::*;
 
 mod trailmix_ludicrous;
+mod single_ccx_fanout;
 
 thread_local! {
     static D1_PHASE_CORRECTED_PRODUCT_CORE_SCOPE: std::cell::Cell<bool> =
@@ -1972,8 +1973,26 @@ pub fn build() -> Vec<Op> {
     // at the nonce-ground operating point (1166 qubits x 1,422,266 executed
     // Toffoli). The tail nonce reseeds the Fiat-Shamir inputs so all 9024
     // verifier draws land in the schedule-supported set.
-    set_default_env("DIALOG_TAIL_NONCE", "1006790");
-    trailmix_ludicrous::build_trailmix_ludicrous_ops()
+    set_default_env("DIALOG_TAIL_NONCE", "13955");
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
index 70e2141..301ecfa 100644
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
diff --git a/src/point_add/trailmix_ludicrous/mod.rs b/src/point_add/trailmix_ludicrous/mod.rs
index b05bb80..a9669e7 100644
--- a/src/point_add/trailmix_ludicrous/mod.rs
+++ b/src/point_add/trailmix_ludicrous/mod.rs
@@ -126,7 +126,7 @@ fn next_gcd_branch() -> u8 { SCHED.with(|s| step(&mut s.borrow_mut().gcd_branch,
 fn next_cmp_k() -> usize {
     SCHED.with(|s| {
         let k = step(&mut s.borrow_mut().cmp_k, usize::MAX);
-        if k == usize::MAX { k } else { k.saturating_add(4) }
+        if k == usize::MAX { k } else { k.saturating_add(7) }
     })
 }
 fn next_ffg() -> usize { SCHED.with(|s| step(&mut s.borrow_mut().ffg, usize::MAX)) }
```

