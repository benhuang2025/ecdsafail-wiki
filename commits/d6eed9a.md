# d6eed9a — Send the square's 128-bit-shifted add/sub through the shifted-low adder, which skips the known-zero low half

| | |
| --- | --- |
| Contestant | yudduy |
| Date | 2026-08-01 |
| Submission | `87bbecb` |
| Commit | `d6eed9a8e3bb67e3c4ea452d37e2ef55850ac4c6` |
| Result | 1154 qubits × 1,289,394 Toffoli = **1,487,960,676** |
| Base | `7726431` (gopikannappan `2684231`, risk-2.5 strip): 1154 qubits × 1,289,771 Toffoli = 1,488,395,734 |
| Change vs base | qubits ±0, Toffoli −377, score −435,058 |
| Leaderboard Δ | −65,778, measured against the frontier at the time, `5265674` (risk-3.0 strip, 1154 × 1,289,451), which is **not** this commit's base |
| Family | Constant Propagation and Classical Specialization → host-derived / classical specialization |
| Concepts | [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [adders-and-carries](../concepts/adders-and-carries.md), [modular-fold](../concepts/modular-fold.md), [dead-gate-strip](../concepts/dead-gate-strip.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **B**: the new `memory/` research directory (notes, Python scripts, `.pyc` files) is copied from the commit; the patch covers the rest |

## Summary

The trailmix squarer forms products of 128-bit halves. Some of them are folded
into the output as `value · 2^128 mod p`. Until now the low 128 bits of
`value`, shifted up by 128, were placed in a 256-bit operand whose low 128 bits
are zero pads, and that operand went through the generic full-width modular
add or subtract. The adder then rippled its carry chain through 128 positions
that are always zero.

This commit sends those three adds (square tags `a`, `b`, `c`) to the existing
`mod_add_shifted_low` / `mod_sub_shifted_low`. These add the 128 live bits
directly into the top half of the accumulator and then do the same fold and
final compare as before. The result is the same, with fewer Toffoli. The high
half of `value`, folded as `f · value_hi`, is unchanged. Net: −377 Toffoli
against `7726431`, at the same 1154 qubits. That figure includes losing 251
strip keys, which the changed stream made stale.

## What changed and why it saves Toffoli

1. **`src/point_add/trailmix_ludicrous/square.rs`, `apply_shifted_128_tagged()`.**
   - If the tag is listed in `TLM_SQUARE_SHIFTED128_LOW_TAGS`, the operand is
     just `value[..min(len,128)]` plus high zero pads, 128 bits in all. It then
     calls `mod_add_shifted_low(circ, operand, output_reg, 128)` for an add, or
     `mod_sub_shifted_low(…)` for a subtract.
   - Otherwise it does what it did before: a 256-bit operand
     `[128 zero pads | value_lo | pads]` into `apply_full_width`, which calls
     `mod_add_lowpeak` or `mod_sub`.
   - The new branch still allocates and frees the 128 low pad wires, although
     it no longer uses them. That keeps the qubit-id assignment of later gates
     unchanged; a comment added in [`4579b79`](4579b79.md) says removing the
     pads would make 4,486 strip keys stale.
2. **What the shifted-low adder does** (`trailmix_ludicrous/arith.rs`, unchanged).
   - The carry ripple (`add_cout_vented_skip_dead`, since
     `TLM_SQUARE_VENT_SHIFTED=1`) runs only over `y[128..]`, with the carry out
     in one ancilla. That is exact: adding zeros to `y[..128]` creates no carry
     into bit 128.
   - Then the usual pseudo-Mersenne fold: `add_f_window` adds `carry · f` into
     the low bits, since 2^256 ≡ f = 2^32 + 977 (mod p).
   - Then the carry is erased with the truncated top-bits compare
     `controlled_lt_msbs_conditional` on the top `msbs()` bits. Those are the
     same bits the full-width path compared.
   - Subtraction does the same between two complement layers.
   - Each call therefore skips the 128 low carry positions. See
     [adders-and-carries](../concepts/adders-and-carries.md),
     [modular-fold](../concepts/modular-fold.md) and
     [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).
3. **`src/point_add/mod.rs`:** new default `TLM_SQUARE_SHIFTED128_LOW_TAGS = "a,b,c"`
   in `configure_q1153_second512_submission_defaults()`. Tail nonce
   `SUB4_TAIL_NONCE` 700076886370 → 58000098603199.
4. **Test helper, `square.rs::shifted128_low_miter()`.** It builds the old and
   new forms for add and subtract and runs 32 batches of 64 random cases each.
   It checks that the outputs agree with each other and with direct modular
   arithmetic, that the source is preserved, and that phase and ancillas are
   clean. Nothing calls it in the build.
5. **Strip table.** `deep_strip_keys.rs` is byte-identical to `7726431`'s risk-2.5
   table. The note says the table was "re-mined" for this stream, but the file
   is not changed. Because the square's gates changed, the build reports
   "removed 12039 / 12290 dead; downgraded 3807 / 3807 to CX/CZ; 251 stale keys
   skipped". The occupancy check discards 251 dead keys instead of applying
   them at shifted ordinals. See [dead-gate-strip](../concepts/dead-gate-strip.md).
6. **`src/point_add/memory/`** gains research notes (`06-research-status.md`,
   `CEILING.md`, `RIG.md`, `reframe_log.md`, `niche_portfolio.json`) and a
   `repro/` folder of Python and C++ search scripts with their tests and
   `__pycache__` files. None of it is compiled.

## Why it is still correct, and what it risks

- **The reroute is exact.** It computes the same `y ± value_lo · 2^128 mod p`
  and keeps the same truncated final compare, so it adds no hard inputs. The
  miter checked 4,096 cases.
- **The strip is still empirical**, with 251 fewer dead keys applied than the
  base. Discarding keys only puts gates back, so it cannot add failures.
- **The note's hunt record:**
  - The same reroute on the risk-3.0 table looked cheaper, about 1,289,084, but
    900M nonces gave no clean draw. The only survivor at 8,192 shots failed at
    shot 8,756.
  - The accepted parent circuit fails at that same shot with that seed, so the
    failure is inherited and not caused by the reroute.
  - On the risk-2.5 table, the winner came after 114M nonces in a second court.
- The shipped nonce `58000098603199` draws a clean set: 9,024 of 9,024 shots, 0
  classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The saving comes from specializing an adder to a structurally known-zero half
of its operand, a fact known when the circuit is built. That is filed under
classical specialization. The runner-up is Strength Reduction → fast-adder
reroute, since the same add is sent to a cheaper existing variant.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 7726431 -- src/point_add`.
   - The note says the work started from `5265674`, the git parent. But the
     shipped tree matches `7726431` in every file it does not change: it has
     the risk-2.5 key table and still contains the four `.orig` files that
     `5265674` deleted.
   - Against the parent, the diff is 19,380 lines. It would show the risk-3.0
     table's 369 extra keys being removed and the four `.orig` files coming
     back, neither of which this commit set out to do.
   - Against `7726431`, `git diff --ignore-cr-at-eol 7726431 d6eed9a -- src/point_add`
     is 13,574 lines in 51 files, almost all of it the new `memory/` files.
2. **Copy the research directory from the commit:**
   `git checkout d6eed9a -- src/point_add/memory`.
3. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It covers `mod.rs` and `square.rs`.
4. **Check the tree.** `git diff --ignore-cr-at-eol d6eed9a -- src/point_add`
   should print nothing.
5. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no `TLM_*` or
   `SUB4_*` overrides set. Expect:
   - 1154 qubits
   - 1,289,394 average Toffoli (1,289,393.594 before rounding)
   - score 1,487,960,676
   - 0 classical, 0 phase and 0 ancilla failures
6. **Nonce caveat.** The score only reproduces with the nonce `58000098603199` and
   an identical op stream. Any other change needs a new nonce hunt and a
   check of the stale-key count.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 090a8f6..c3206e9 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1193,6 +1193,7 @@ fn configure_q1153_second512_submission_defaults() {
     set_default_env("TLM_SQUARE_VENT_MARGIN", "0");
     set_default_env("TLM_COORD_ADD3X_TRUNC", "1");
     set_default_env("TLM_SQUARE_VENT_SHIFTED", "1");
+    set_default_env("TLM_SQUARE_SHIFTED128_LOW_TAGS", "a,b,c");
     set_default_env("TLM_SQUARE_PEAK_CAP", "1154");
     set_default_env("TLM_CUCCARO_SKIP_STRUCTURAL_DEAD_CALLS", "1");
 }
@@ -2375,9 +2376,12 @@ pub fn build() -> Vec<Op> {
     } else {
         apply_deep_strip_identity(ops)
     };
-    // The tail nonce ground for this composed stream (verified PASS 0/0/0, score 1,517,633,280).
-    // SUB4_TAIL_NONCE overrides for re-grinding/seam-export.
-    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE").ok().and_then(|s| s.parse().ok()).unwrap_or(700076886370);
+    // Tail nonce for the exact H2 risk-2.5 stream (9024/9024 PASS, score 1,487,960,676).
+    // SUB4_TAIL_NONCE overrides it for controlled re-grinding.
+    let nonce: u64 = std::env::var("SUB4_TAIL_NONCE")
+        .ok()
+        .and_then(|s| s.parse().ok())
+        .unwrap_or(58000098603199);
     let ops = apply_tail_nonce(ops, nonce);
     // `TLM_DIRTY_SCAN_FINAL=1` runs the reset/phase audit on the stream `eval_circuit`
     // will actually see, i.e. after every rewrite pass. Default off.
diff --git a/src/point_add/trailmix_ludicrous/square.rs b/src/point_add/trailmix_ludicrous/square.rs
index e9a12d6..efe9b06 100644
--- a/src/point_add/trailmix_ludicrous/square.rs
+++ b/src/point_add/trailmix_ludicrous/square.rs
@@ -417,15 +417,29 @@ fn apply_f_times_value(circ: &mut B, value: &[QubitId], output_reg: &[QubitId],
 fn apply_shifted_128_tagged(circ: &mut B, value: &[QubitId], output_reg: &[QubitId], op: ShiftOp, tag: &str) {
     assert!(value.len() <= N + 2, "128-shifted half product must be at most 258 bits");
     let low_len = value.len().min(128);
-    let low_pads = alloc_zeroes(circ, 128);
-    let high_pads = alloc_zeroes(circ, 128 - low_len);
-    let mut operand = Vec::with_capacity(N);
-    operand.extend_from_slice(&low_pads);
-    operand.extend_from_slice(&value[..low_len]);
-    operand.extend_from_slice(&high_pads);
-    apply_full_width(circ, &operand, output_reg, op);
-    free_zeroes(circ, high_pads);
-    free_zeroes(circ, low_pads);
+    if env_tag_enabled("TLM_SQUARE_SHIFTED128_LOW_TAGS", tag) {
+        let low_pads = alloc_zeroes(circ, 128);
+        let high_pads = alloc_zeroes(circ, 128 - low_len);
+        let mut operand = Vec::with_capacity(128);
+        operand.extend_from_slice(&value[..low_len]);
+        operand.extend_from_slice(&high_pads);
+        match op {
+            ShiftOp::Add => mod_add_shifted_low(circ, &operand, output_reg, 128),
+            ShiftOp::Sub => mod_sub_shifted_low(circ, &operand, output_reg, 128),
+        }
+        free_zeroes(circ, high_pads);
+        free_zeroes(circ, low_pads);
+    } else {
+        let low_pads = alloc_zeroes(circ, 128);
+        let high_pads = alloc_zeroes(circ, 128 - low_len);
+        let mut operand = Vec::with_capacity(N);
+        operand.extend_from_slice(&low_pads);
+        operand.extend_from_slice(&value[..low_len]);
+        operand.extend_from_slice(&high_pads);
+        apply_full_width(circ, &operand, output_reg, op);
+        free_zeroes(circ, high_pads);
+        free_zeroes(circ, low_pads);
+    }
 
     if value.len() > 128 {
         if matches!(tag, "a" | "b" | "c") {
@@ -509,3 +523,190 @@ pub fn mod_square_sub_pm_secp256k1_symmetric(circ: &mut B, lambda: &[QubitId], o
     circ.set_phase("square_sum_hi_lo_unbuild");
     unbuild_sum_hi_lo(circ, lambda, sum);
 }
+
+pub fn shifted128_low_miter() -> Result<usize, String> {
+    use crate::point_add::SECP256K1_P;
+    use crate::sim::Simulator;
+    use alloy_primitives::U256;
+    use sha3::{
+        digest::{ExtendableOutput, Update, XofReader},
+        Shake256,
+    };
+
+    struct HelperCircuit {
+        ops: Vec<crate::circuit::Op>,
+        source: Vec<QubitId>,
+        accumulator: Vec<QubitId>,
+        qubits: usize,
+        bits: usize,
+    }
+
+    fn build_helper(shifted: bool, op: ShiftOp) -> HelperCircuit {
+        let mut circ = B::new();
+        let source = circ.alloc_qubits(128);
+        let accumulator = circ.alloc_qubits(N);
+        if shifted {
+            match op {
+                ShiftOp::Add => mod_add_shifted_low(&mut circ, &source, &accumulator, 128),
+                ShiftOp::Sub => mod_sub_shifted_low(&mut circ, &source, &accumulator, 128),
+            }
+        } else {
+            let low_pads = alloc_zeroes(&mut circ, 128);
+            let mut operand = Vec::with_capacity(N);
+            operand.extend_from_slice(&low_pads);
+            operand.extend_from_slice(&source);
+            apply_full_width(&mut circ, &operand, &accumulator, op);
+            free_zeroes(&mut circ, low_pads);
+        }
+        HelperCircuit {
+            ops: circ.ops,
+            source,
+            accumulator,
+            qubits: circ.next_qubit as usize,
+            bits: circ.next_bit as usize,
+        }
+    }
+
+    fn subtract_mod(lhs: U256, rhs: U256) -> U256 {
+        if lhs >= rhs {
+            lhs - rhs
+        } else {
+            SECP256K1_P - (rhs - lhs)
+        }
+    }
+
+    fn run_helper(
+        circuit: &HelperCircuit,
+        source_values: &[U256; 64],
+        accumulator_values: &[U256; 64],
+        seed_label: &[u8],
+    ) -> Result<[U256; 64], String> {
+        let mut seed = Shake256::default();
+        seed.update(b"shifted128-low-helper-miter");
+        seed.update(seed_label);
+        let mut xof = seed.finalize_xof();
+        let mut sim = Simulator::new(circuit.qubits, circuit.bits, &mut xof);
+        sim.clear_for_shot();
+        for shot in 0..64 {
+            for bit in 0..128 {
+                if source_values[shot].bit(bit) {
+                    *sim.qubit_mut(circuit.source[bit]) |= 1u64 << shot;
+                }
+            }
+            for bit in 0..N {
+                if accumulator_values[shot].bit(bit) {
+                    *sim.qubit_mut(circuit.accumulator[bit]) |= 1u64 << shot;
+                }
+            }
+        }
+        sim.apply_iter(circuit.ops.iter());
+        if sim.phase != 0 {
+            return Err(format!("phase garbage 0x{:016x}", sim.phase));
+        }
+
+        let mut outputs = [U256::ZERO; 64];
+        for shot in 0..64 {
+            let mut source_after = U256::ZERO;
+            let mut output = U256::ZERO;
+            for bit in 0..128 {
+                if (sim.qubit(circuit.source[bit]) >> shot) & 1 == 1 {
+                    source_after |= U256::from(1u64) << bit;
+                }
+            }
+            for bit in 0..N {
+                if (sim.qubit(circuit.accumulator[bit]) >> shot) & 1 == 1 {
+                    output |= U256::from(1u64) << bit;
+                }
+            }
+            if source_after != source_values[shot] {
+                return Err(format!(
+                    "shot {shot}: source changed from {:#x} to {source_after:#x}",
+                    source_values[shot]
+                ));
+            }
+            outputs[shot] = output;
+        }
+
+        for q in 0..circuit.qubits as u64 {
+            if circuit.source.iter().any(|source| source.0 == q)
+                || circuit.accumulator.iter().any(|accumulator| accumulator.0 == q)
+            {
+                continue;
+            }
+            let value = sim.qubit(QubitId(q));
+            if value != 0 {
+                return Err(format!("ancilla qubit {q} not clean: 0x{value:016x}"));
+            }
+        }
+        Ok(outputs)
+    }
+
+    unsafe {
+        std::env::set_var("TLM_SQUARE_NO_VENT_REDUCE", "1");
+        std::env::remove_var("TLM_SQUARE_VENT_SHIFTED");
+    }
+    let mut checked = 0usize;
+    for (op_index, op) in [ShiftOp::Add, ShiftOp::Sub].into_iter().enumerate() {
+        let full = build_helper(false, op);
+        let shifted = build_helper(true, op);
+        for batch in 0u64..32 {
+            let mut input_seed = Shake256::default();
+            input_seed.update(b"shifted128-low-inputs");
+            input_seed.update(&(op_index as u64).to_le_bytes());
+            input_seed.update(&batch.to_le_bytes());
+            let mut inputs = input_seed.finalize_xof();
+            let mut source_values = [U256::ZERO; 64];
+            let mut accumulator_values = [U256::ZERO; 64];
+            let mut bytes = [0u8; 32];
+            for shot in 0..64 {
+                inputs.read(&mut bytes);
+                bytes[16..].fill(0);
+                source_values[shot] = U256::from_le_bytes(bytes);
+                inputs.read(&mut bytes);
+                accumulator_values[shot] = U256::from_le_bytes(bytes) % SECP256K1_P;
+            }
+
+            let mut label = [0u8; 24];
+            label[..8].copy_from_slice(&(op_index as u64).to_le_bytes());
+            label[8..16].copy_from_slice(&batch.to_le_bytes());
+            let full_outputs = run_helper(&full, &source_values, &accumulator_values, &label)
+                .map_err(|error| {
+                    format!("full helper op={op_index} batch={batch}: {error}")
+                })?;
+            let shifted_outputs =
+                run_helper(&shifted, &source_values, &accumulator_values, &label).map_err(
+                    |error| format!("shifted helper op={op_index} batch={batch}: {error}"),
+                )?;
+
+            for shot in 0..64 {
+                let operand = source_values[shot] << 128;
+                let expected = match op {
+                    ShiftOp::Add => {
+                        accumulator_values[shot].add_mod(operand, SECP256K1_P)
+                    }
+                    ShiftOp::Sub => subtract_mod(accumulator_values[shot], operand),
+                };
+                if full_outputs[shot] != expected {
+                    return Err(format!(
+                        "full helper op={op_index} batch={batch} shot={shot}: got {:#x}, expected {expected:#x}",
+                        full_outputs[shot]
+                    ));
+                }
+                if shifted_outputs[shot] != expected {
+                    return Err(format!(
+                        "shifted helper op={op_index} batch={batch} shot={shot}: got {:#x}, expected {expected:#x}",
+                        shifted_outputs[shot]
+                    ));
+                }
+                if shifted_outputs[shot] != full_outputs[shot] {
+                    return Err(format!(
+                        "miter op={op_index} batch={batch} shot={shot}: full={:#x}, shifted={:#x}",
+                        full_outputs[shot], shifted_outputs[shot]
+                    ));
+                }
+                checked += 1;
+            }
+        }
+    }
+    Ok(checked)
+}
```

