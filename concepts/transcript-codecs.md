# Transcript codecs (packing the dialog-GCD branch log)

> The dialog GCD ([dialog-gcd-early.md](dialog-gcd-early.md)) writes a few branch bits per step. Those bits stay live from the forward walk through the apply pass to the reverse walk, so the transcript sits on the qubit peak for most of the circuit. From [cddd5df](../commits/cddd5df.md) on, it is stored in fixed blocks, each packed by a small reversible circuit. Each codec is a bijection only on the bit patterns the walk can actually produce, and it maps all of those onto words whose dropped wires are 0. Over June the 258–399-step log went from 798 raw bits to 616 qubits through five block formats: round763, round763 plus raw `s2`, the K2 pair, K5, and K5 with the head-11 and tail-3 blocks. Two more tricks lower its cost at the peak. Late blocks are parked on high `u` wires that the shrinking GCD no longer uses (the *u-high runway*), and cells not yet written are lent out as scratch. All of this is exact, except the tail-3 "TOP32" block, which is exact only on a listed support of 32 patterns.

## How it works in this circuit

**What a step writes.** Each step writes `b0 = v[0]` and `b01 = b0 ∧ [u > v]`. Under K=2 ([0780f67](../commits/0780f67.md)) it also writes `s2 = ¬v[0]` after the first halving. These are the only rules the codecs rely on:

1. `b01 ≤ b0`, so `(b0, b01) = (0, 1)` never occurs. That leaves 3 states per step with one halving, or 6 under K=2.
2. Under K=2, `s2 = 0` means `v` is already odd, so the next step's `b0` is 1.
3. In the first block `u = p` until the first swap, so `b01 = b0` on those steps.

Counting with these rules gives 3ⁿ patterns for n single-halving steps, 6·5ⁿ⁻¹ for n K=2 steps, and 1,876 for the first five K=2 steps. I counted these myself. Asymptotically a K=2 step therefore carries log₂5 ≈ 2.32 bits. The block formats below approach that bound.

| block | steps | raw → stored | patterns | CCX per pass | introduced |
| --- | --- | --- | --- | --- | --- |
| round763 | 3 | 6 → 5 | 27 of 32 | 9, then 7, then 4 | [cddd5df](../commits/cddd5df.md), [ad02935](../commits/ad02935.md), [17aad9a](../commits/17aad9a.md) |
| round763 + raw `s2` | 3 | 9 → 8 | at most 27 × 8 | 4 | [0780f67](../commits/0780f67.md) |
| K2 pair | 2 | 6 → 5 | 30 of 32 | 6, then 3 | [9a81017](../commits/9a81017.md), [e321f72](../commits/e321f72.md) |
| K5 | 5 | 15 → 12 | 3,750 of 4,096 | 23 | [6953d1b](../commits/6953d1b.md) |
| head-11 (block 0) | 5 | 15 → 11 | 1,876 within a 2,048 support | 25 | [cf310ec](../commits/cf310ec.md) |
| tail-3 TOP32 (last block) | 3 | 9 → 5 | 32 listed, out of 150 allowed | ANF; decode 393, then 287 | [674d0d8](../commits/674d0d8.md), [7bab51f](../commits/7bab51f.md) |

**The round763 compressor** (`emit_dialog_gcd_round763_compressor`). It acts on the 6-qubit raw block, with slot `k` holding `b0` at bit `2k` and `b01` at `2k+1`. On every reachable input it clears bit 5, and the other 5 bits are swapped into the block's log cells. The decoder is the gate-reversed list.

cddd5df's map used 9 CCX; `ROUND763_DEDUP` cancelled a CCX pair (7); `ROUND763_COMPRESS_LEVER` (17aad9a) is a different 4-CCX map that gives 10 of the 27 patterns new codes. I simulated all three on the 27 states: each is injective with bit 5 = 0. Under K=2 the three `s2` bits were stored raw beside the code (0780f67: "Prototype stores shift2 UNCOMPRESSED"), so a block is 8 bits.

**The K2 pair** (`dialog_gcd_k2_pair_core`). Its core is `(b0_A, b01_A, s2_A, b0_B, b01_B)`. Rules 1 and 2 leave 15 values. A 5-qubit encoder maps them onto words with `core[0] = 0`, and the code is stored as 4 bits plus a raw `s2_B`. [e321f72](../commits/e321f72.md) re-synthesised the encoder from 6 CCX down to 3. I checked the 3-CCX version on all 15 states.

**K5** (`DIALOG_GCD_K5_CLEAN_BLOCK`). In the dialog route "K5" means a block of five K=2 steps (`sidecar_group_size() = 5`). Two 3-CCX pair encoders (steps 0–1, 2–3) zero `raw[0]` and `raw[4]`; the 13 remaining data wires go through `DIALOG_GCD_K5_FABLE_GATES` (17 CCX, with one temporary wire), which zeroes data wire 10; twelve survivors move into the block.

**Head-11** (`DIALOG_GCD_K5_HEAD11_CODEC`). It adds a 2-CCX preconditioner that also zeroes data wire 3. Its self-test requires exactly 2,048 supported words.

Porting both encoders to Python and running every pattern the rules allow, K5 accepts all 3,750 with distinct codes and head-11 all 1,876.

**Tail-3 TOP32** (`DIALOG_GCD_K5_TAIL3_TOP32_CODEC`). With 258 = 51·5 + 3 steps, the last block has 3 steps. The block stores a 5-bit code for one of the 32 entries in `DIALOG_GCD_K5_TAIL3_TOP32_SUPPORT`. Most entries end in the converged digits 4 (`s2` only) and 5 (`b0, s2`). The encoder is a constant XOR a degree-≤2 ANF of the raw bits (12 CCX); the decoder is a degree-≤5 ANF of the code on dirty-ancilla CCX ladders (`dialog_gcd_toggle_mcx_with_dirty`). [7bab51f](../commits/7bab51f.md) re-assigned the codes, cutting a full decode from 393 to 287 CCX. [35ceb01](../commits/35ceb01.md)'s `…_S2CONST` maps fix the last step to `b01 = 0`, `s2 = 1` so it skips its swap; they round-trip only 25 of the 32 patterns.

**Block lifecycle.** The forward walk fills a block's raw slots step by step and compresses after the last; the reverse walk decompresses before undoing them; the apply decodes and re-encodes each block (a CX copy at first, a swap from [3166bbd](../commits/3166bbd.md), whose emptied cells then host apply carries).

So, before the streamed decodes, every block passed through its codec 8 times per point addition, 4 encodes and 4 decodes, which is how 17aad9a's saving works out to 3 × 8 × 133 = 3,192 T. Later commits shrank the raw scratch: per-block hosting ([dd188f8](../commits/dd188f8.md)), in-place pair decode ([420e0c2](../commits/420e0c2.md)), freeing the K5 block while `y` shifts ([bb579bb](../commits/bb579bb.md)), and pair- or slot-streamed apply that decodes only what the current step needs ([674d0d8](../commits/674d0d8.md), [35ceb01](../commits/35ceb01.md)).

**u-high runway** (`DIALOG_GCD_COMPRESSED_LOG_U_HIGH_RUNWAY`, `dialog_gcd_runway_layout`). The width envelope says `u[i]` is |0⟩ and untouched once `active_width(step) ≤ i`. The layout takes the longest suffix of blocks and gives their cells descending hosts, starting at `u[249]`. The top 6 lanes are left free for a raw block. A host is accepted only if it lies at or above the largest `active_width` among that block's steps. The earliest parked block gets the highest hosts, because it is written first in the forward walk and read last in the reverse walk, when `u` is widest. The parked cells are never allocated, and `dialog_gcd_release_terminal_u` keeps them while the rest of `u` is freed for the apply. [3166bbd](../commits/3166bbd.md) parked 3 blocks; [13a01b8](../commits/13a01b8.md) raised the cap `…_RUNWAY_BLOCKS` to 999 (49 of 132 blocks, 245 qubits); 0780f67 made it block-width aware (208 of 696 bits); `RUNWAY_PARTIAL_BLOCK` (674d0d8) lets the suffix start mid-block.

**Borrowing unwritten slots.** During a block's steps these cells are |0⟩: every later block (not yet written forward, already emptied in reverse), the current block's own cells, the current step's `s2`, and later raw slots.

`dialog_gcd_compressed_sidecar_future_carry_slice` lends the walk's adder `n − 1` future cells. With `HOST_GATED` it lends `2n − 1` ([68e3653](../commits/68e3653.md)). [92a247e](../commits/92a247e.md) moved the comparator's carries there too. Later borrows added `BORROW_CURRENT_BLOCK` ([69bd3d7](../commits/69bd3d7.md), −4 q), `BORROW_CURRENT_S2` ([89abe1b](../commits/89abe1b.md)) and `BORROW_ZERO_RAW_FUTURE` ([8983da8](../commits/8983da8.md)). `dialog_gcd_runway_safe_future_prefix` cuts the lent slice before any cell that is parked on still-active `u`. When the future region gets shorter than the request, late in the walk, the borrower falls back to fresh wires.

**Why the step count moves the peak in block-sized jumps.** The live log is

  `Σ_blocks block_bits − runway cells`, with `blocks = ⌈ACTIVE_ITERATIONS / group⌉`.

A step cut that does not cross a block boundary saves only Toffoli. [39134ec](../commits/39134ec.md) went from 395 to 394 steps at 1355 q, and both counts need 132 blocks. A cut that does cross a boundary removes a whole block:

- [dd103cd](../commits/dd103cd.md): 399 → 396, −5 q;
- [fec6d25](../commits/fec6d25.md): 259 → 258, −8 q, because the 87th block held one step.

The gain only appears if the dropped bits were freshly allocated. A parked block's cells are already free, so [8ef64e9](../commits/8ef64e9.md) needed 393 steps together with margin 25 to keep the runway's length. Codec gates add constraints of their own. Tail-3 is enabled only when `ACTIVE_ITERATIONS % 5 == 3`, and head-11 needs at least 5 steps.

## Why it is (or is not) exact

- **round763, K2 pair and K5.** Rules 1 and 2 follow from how the bits are computed, so they hold on every input, even one where a truncated comparator picked the wrong branch (17aad9a). These codecs are bijections on a superset of what can occur.
- **Re-synthesis.** Every reader decodes with the matching inverse, so a re-synthesis that changes the code words is also exact.
- **Head-11.** Rule 3 can only fail through a comparator tie on a step where `u = p` is still in place. That input has already mis-branched (`v − p` wraps), so the codec adds no new failure.
- **Tail-3 TOP32.** It is not structural. The rules allow 150 three-step patterns, and the codec accepts 32. The code calls them the reachable support, but I found no proof, and the name suggests the 32 most common patterns. S2CONST narrows this to 25. An input outside the list leaves a dirty wire or a wrong transcript. The classical filter rejects such inputs (`Tail3Top32Mismatch`; `HeadK5Mismatch` covers block 0), so the risk is priced into λ ([nonce-island-and-lambda.md](nonce-island-and-lambda.md)).
- **The runway and the borrows** are exact on inputs that respect the width envelope. If `u` overflowed onto a host, the walk would already have failed. A borrower that is not restored to |0⟩ would leave ancilla garbage in the log.

## Knobs and names you will see in commits

- **Block formats:** `DIALOG_GCD_COMPRESSED_SIDECAR_LOG`, `…_COMPRESSED_BLOCK_LIFECYCLE`, `DIALOG_GCD_HIGH_TAIL_ALIAS_GROUP_SIZE` (3) and `_BLOCK_BITS` (5), `dialog_gcd_block_bits()`, `dialog_gcd_raw_block_len()`.
- **Codecs:** `ROUND763_DEDUP`, `ROUND763_COMPRESS_LEVER`, `K2_PAIR_COMPRESS`, `K5_CLEAN_BLOCK`, `K5_HEAD11_CODEC`, `K5_TAIL3_TOP32_CODEC`. Default-off experiments: `K5_TAIL3_FIXED_LAST`, `TAIL7`, `TAIL6_GRAPH(9)`, `TAIL_PAIR1`.
- **Lifecycle:** `APPLY_REPLAY_SWAP_HOST`, `K2_APPLY_INPLACE_RAW_BLOCK`, `K5_FREE_CLEAN_BLOCK_DURING_SHIFT`, `K5_STREAM_PAIR_APPLY`, `K5_HEAD11_*_APPLY`, `K5_TAIL3_TOP32_{STREAM,SPLIT_SLOT,FINAL_S2_CONST}_APPLY`, `K5_PARTIAL_RAW_RELEASE`.
- **Runway and borrows:** `COMPRESSED_LOG_U_HIGH_RUNWAY(_BLOCKS)`, `RUNWAY_PARTIAL_BLOCK`, `RAW_TOBITVECTOR_BORROW_FUTURE_LOG_CARRIES`, `HOST_GATED`, `COMPOSITE_SCRATCH`, `BORROW_CURRENT_BLOCK`, `BORROW_CURRENT_S2`, `BORROW_ZERO_RAW_FUTURE`, `APPLY_BORROW_FUTURE_BOUNDARY_CARRIES`.
- **Naming.** In the trailmix route "K5" refers to the base-5 packing ([trailmix-jump-gcd.md](trailmix-jump-gcd.md)). The `DIALOG_GCD_K5_*` knobs come from this route, where K5 names the 5-step block. The two meet only in that a K=2 step carries about log₂5 bits.

## How optimizations use it

- **Denser blocks (peak):** [9a81017](../commits/9a81017.md) (−6 q for +3,926 T), [6953d1b](../commits/6953d1b.md) (log 645 → 624; with a square-cap cut the peak fell 8 for +6,307 T), [cf310ec](../commits/cf310ec.md), [674d0d8](../commits/674d0d8.md).
- **Cheaper codecs (Toffoli):** [ad02935](../commits/ad02935.md), [17aad9a](../commits/17aad9a.md), [8117d98](../commits/8117d98.md), [e321f72](../commits/e321f72.md), [7bab51f](../commits/7bab51f.md).
- **Lifetime and hosting:** [dd188f8](../commits/dd188f8.md), [3166bbd](../commits/3166bbd.md), [13a01b8](../commits/13a01b8.md), [e0cfe2b](../commits/e0cfe2b.md), [420e0c2](../commits/420e0c2.md), [bb579bb](../commits/bb579bb.md), [35ceb01](../commits/35ceb01.md).
- **Scratch borrowing:** [68e3653](../commits/68e3653.md), [92a247e](../commits/92a247e.md), [69bd3d7](../commits/69bd3d7.md), [8983da8](../commits/8983da8.md).
- **Step cuts that drop a block:** [dd103cd](../commits/dd103cd.md), [f42ce5c](../commits/f42ce5c.md), [8ef64e9](../commits/8ef64e9.md), [fec6d25](../commits/fec6d25.md).

## Timeline

- [cddd5df](../commits/cddd5df.md) (2 Jun): round763, 133 × 5 = 665 qubits for 399 steps. [17aad9a](../commits/17aad9a.md): 4-CCX map.
- [3166bbd](../commits/3166bbd.md), [13a01b8](../commits/13a01b8.md) (3 Jun): u-high runway, 3 blocks and then 49.
- [0780f67](../commits/0780f67.md) (5 Jun): K=2, 87 × 8 = 696 bits. [9a81017](../commits/9a81017.md): pair code, 650.
- [e321f72](../commits/e321f72.md) (7 Jun): 3-CCX pair encoder, −3,096 T.
- [6953d1b](../commits/6953d1b.md) (12 Jun): K5, 52 × 12 = 624. [cf310ec](../commits/cf310ec.md) (13 Jun): head-11, 623. [674d0d8](../commits/674d0d8.md) (14 Jun): tail-3, 616.
- [35ceb01](../commits/35ceb01.md) (15 Jun): streamed decode and S2CONST tail.
- [bdb1d22](../commits/bdb1d22.md) (19 Jun): trailmix replaces the route, with its own base-5 codec (3 steps in 7 qubits).

## Related concepts

[dialog-gcd-early.md](dialog-gcd-early.md) · [trailmix-jump-gcd.md](trailmix-jump-gcd.md) · [peak-qubits-and-budgets.md](peak-qubits-and-budgets.md) · [venting-and-wire-loans.md](venting-and-wire-loans.md) · [measurement-uncompute.md](measurement-uncompute.md) · [dead-gate-strip.md](dead-gate-strip.md) · [nonce-island-and-lambda.md](nonce-island-and-lambda.md) · [comparator-and-width-truncation.md](comparator-and-width-truncation.md)
