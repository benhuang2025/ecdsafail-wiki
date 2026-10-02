# d11bdbb — Turn on the shifted-low square fold of `3df690f` on the 1159-qubit tree of `fed64cf`

| | |
| --- | --- |
| Contestant | BitWonka |
| Date | 2026-06-20 |
| Submission | `88ed0f5` |
| Commit | `d11bdbb0109b120d9363bb804c1a6d8e94981962` |
| Result | 1159 qubits × 1,380,711 Toffoli = **1,600,244,049** |
| Base | `fed64cf` (nasqret, the 1159-qubit tree): 1159 qubits × 1,388,180 Toffoli = 1,608,900,620 |
| Change vs base | qubits ±0, Toffoli −7,469, score −8,656,571 |
| Leaderboard Δ | −6,765,039, measured against the frontier at the time, `42b56c6` (odinfree, 1164 × 1,380,592 = 1,607,009,088), which is **not** this commit's base |
| Family | Register and Scratch Allocation → ancilla-lifetime / venting |
| Concepts | [squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md), [modular-fold](../concepts/modular-fold.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [venting-and-wire-loans](../concepts/venting-and-wire-loans.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [trailmix-schedules-and-reserves](../concepts/trailmix-schedules-and-reserves.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

On 20 June two lines led the board. nasqret's [`fed64cf`](fed64cf.md) had the
lowest peak, 1159 qubits, from fitting every primitive under a live qubit
target. gopikannappan's [`3df690f`](3df690f.md) had the cheapest square, at
1164 qubits: it applies every NAF term of the square's `f`-folds as a
shifted-low add instead of a modular-doubling ramp. This commit stacks the
two. It starts from `fed64cf` and changes two square defaults in `build()` so
that the 1159-qubit route takes `3df690f`'s fold path.

The square saves about 7,500 average Toffoli, as it did on `3df690f`'s tree.
The peak stays at 1159, because the square is not the peak phase and the
`TLM_TARGET_Q` clamps still apply. The tail nonce was re-hunted.

## What changed and why it saves Toffoli

Only `src/point_add/mod.rs`, `build()`, changes:

- `TLM_SQUARE_F_RAMP10_DIRECT32_TAGS`: `"a"` → `""`. The `A` lane leaves the
  ramp-to-shift-10-plus-direct-32 path of [`e25c7d8`](e25c7d8.md); with an
  empty list no lane matches.
- New `TLM_SQUARE_F_SHIFTED_LOW=1`. In
  `trailmix_ludicrous/square.rs::apply_f_times_value_tagged`, every limb with
  `len + 32 ≤ 256` now applies each term of
  `F_NAF_TERMS = [(0,Sub),(4,Sub),(6,Add),(10,Sub),(32,Sub)]` with
  `apply_shifted_value_low`: a modular add or subtract of the limb at bit
  offset `j` through `arith::mod_add_shifted_low` / `mod_sub_shifted_low`,
  with the low `j` bits implicit zeros. No `mod_double` or
  `mod_double_reverse` is run.
- That covers the `C[128..]` (130-bit), `A[128..]` and `B[128..]` limbs of the
  `×2^128` terms. The `f·B` fold of the `2^256` term has a 256-bit limb and
  keeps its 32-step ramp.
- **Cost on this tree.** `arith::PAD = 19` here, so each `+f` window is 52
  bits and 51 CCX. The `C` and `B×2^128` lanes each lose 64 windows, and the
  `A` lane loses the 20 left by `e25c7d8`'s path: 148 × 51 ≈ 7,550 Toffoli,
  plus a few hundred from the narrower `256 − j`-bit Cuccaro adders. The
  measured drop is 7,469.
- `DIALOG_TAIL_NONCE`: 453700 → 200001456973.

The details of the fold and why it is exact are in the [`3df690f`](3df690f.md)
note. See also [modular-fold](../concepts/modular-fold.md) and
[squaring-and-karatsuba](../concepts/squaring-and-karatsuba.md).

**Why the peak holds.** `fed64cf`'s budgets are clamped live against
`TLM_TARGET_Q = 1159` (see
[peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md)). The
shifted-low adds allocate fewer pad wires than the ramp's 257-bit `ext`
register, and the square runs well below the GCD/apply peak. The per-call
fold reserve map `TLM_TARGET_FFG_CALL_RESERVES` is keyed by `add_f_window`
call index. The square issues far fewer windows now, so any window calls
after the square get lower indices and may read different reserves. The
author kept the maps unchanged, and the result still peaks at 1159.

## Why it is still correct, and what it risks

- **Value-exact fold.** The three limbs are below `2^130`, so `limb·2^j` never
  reaches `2^256` for `j ≤ 32`. The old ramp's doublings never fired their
  `+f` window, and the shifted-low add computes the same value.
- Each shifted-low add keeps the usual approximations of a modular add: one
  `+f` window that can drop a carry with probability about `2^-19`, and a
  19-bit truncated overflow compare. They replace the same number of
  full-width adds, so the failure set is essentially the base's.
- A peak overrun would show up as 1160+ qubits, not as a validation failure;
  a dirty wire would be an ancilla failure.
- The shipped nonce 200001456973 draws a clean set: 9,024 of 9,024 shots
  pass, with 0 classical, 0 phase and 0 ancilla failures (avg
  1,380,710.731 Toffoli, per the author's run).

## Classification rationale

The published label is ancilla-lifetime / venting. That fits the diff against
the git parent `42b56c6`, which would bring in the whole of `fed64cf`. Against
its real base `fed64cf`, the only circuit change is the square fold, a cheaper
way to apply the NAF terms of the Solinas `f`-fold. The diff suggests
Strength Reduction → solinas / NAF fold, as for `3df690f`. The commit is a
stack of two earlier levers, and its own new part is the square switch.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout fed64cf -- src/point_add`.
   - Do not start from the git parent `42b56c6`. That is odinfree's nonce
     reroll of the 1164-qubit `3df690f` tree.
   - Against the parent, the diff is 1,957 lines in 12 files. It would add all
     of `fed64cf` and the 1162-qubit budget trims of `7b7bd12`.
   - Against `fed64cf`, `git diff --ignore-cr-at-eol fed64cf d11bdbb -- src/point_add`
     is 7 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`. The flag lets the patch apply whether the files use LF or CRLF line endings. It is the
   complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol d11bdbb -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `DIALOG_*`, `TLM_*`, `LUD_*`, `CONSTPROP_*` or `TRACE_*` environment
   variables set, because they override the defaults in `build()`. Expect:
   - 1159 qubits
   - 1,380,711 average Toffoli (1,380,710.731 before rounding)
   - score 1,600,244,049
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `200001456973` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index ee6ff1f..e0a4b92 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -1976,8 +1976,11 @@ pub fn build() -> Vec<Op> {
     set_default_env("LUD_EXTRA_FOLD_VENTS", "0");
     set_default_env("LUD_EXTRA_FOLD_MIN_G", "0");
     set_default_env("LUD_EXTRA_FOLD_MAX_G", "999");
-    set_default_env("DIALOG_TAIL_NONCE", "453700");
-    set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "a");
+    set_default_env("DIALOG_TAIL_NONCE", "200001456973");
+    // Stack the latest frontier square fold: use shifted-low folding for all
+    // square lanes instead of the older `a`-only direct32 ramp shortcut.
+    set_default_env("TLM_SQUARE_F_RAMP10_DIRECT32_TAGS", "");
+    set_default_env("TLM_SQUARE_F_SHIFTED_LOW", "1");
     set_default_env("CONSTPROP_MAX_ITERS", "16");
     set_default_env("TLM_TARGET_Q", "1159");
     set_default_env("TLM_FOLD_RELEASE_CONTROLS", "1");
```

