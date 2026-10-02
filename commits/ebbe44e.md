# ebbe44e — Narrow the dialog-GCD branch comparator from 46 to 45 bits on the 1309-qubit route

| | |
| --- | --- |
| Contestant | zuiris |
| Date | 2026-06-06 |
| Submission | `bcb39d0` |
| Commit | `ebbe44e3808b4e2f0ea762414cd0626d10cea696` |
| Result | 1309 qubits × 1,510,794 Toffoli = **1,977,629,346** |
| Base | `7f656bd` (the author's previous submission): 1309 qubits × 1,511,678 Toffoli = 1,978,786,502 |
| Change vs base | qubits ±0, Toffoli −884, score −1,157,156 |
| Leaderboard Δ | −827,329, measured against the frontier at the time, `571e67c` (runeape-sats, 1285 × 1,539,655 = 1,978,456,675), which is **not** this commit's base |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [trailmix-jump-gcd](../concepts/trailmix-jump-gcd.md) (dialog-GCD background), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md), [dialog-gcd-early](../concepts/dialog-gcd-early.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit narrows the dialog-GCD branch comparator by one more bit, from 46 to 45,
in the top-of-route override block that the author added in
[`7f656bd`](7f656bd.md). On this route the width envelope is at least 46 bits on
221 of the 259 walk steps. The cap binds on all of those, so each walk saves 221
Toffoli and the four walks save exactly the measured 884. Qubits stay at 1309.
The commit also adds a `KAL_FOLD_CARRY_TRUNC_W=21` override, which has no effect,
re-hunts the tail nonce, and deletes 210 stray macOS `._*` files.

## What changed and why it saves Toffoli

All changes are at the start of `configure_ecdsafail_submission_route()` in
`src/point_add/mod.rs`. These pins come first, so they override the later ones,
because `set_default_env` only sets variables that are still unset.

1. **`DIALOG_GCD_COMPARE_BITS`: 46 → 45.**
   - The route has `DIALOG_GCD_PA9024_COMPARE_SCHEDULE=0`, so
     `dialog_gcd_compare_bits_for_step(step, active_width)` returns
     `min(45, active_width)`. That is the width of the truncated "u > v"
     comparator that picks each walk step's branch.
   - `active_width(step) = 256 − 1.008·step + 10`, rounded up to an even
     number (slope `DIALOG_GCD_WIDTH_SLOPE_X1000=1008`, from the same override
     block). This is at least 46 on steps 0–220. The comparator therefore loses
     one bit on 221 steps of each walk.
   - The comparator runs in the forward and reverse walk of both divisions:
     4 × 221 = 884 Toffoli, exactly the measured saving.
2. **`KAL_FOLD_CARRY_TRUNC_W=21` added to the override block.** The later
   in-place pin already sets 21 on this tree, since
   [`974689f`](974689f.md). The new line changes nothing.
3. **`DIALOG_TAIL_NONCE`: 450007074 → 2100000741.**
4. **210 `._*` files deleted** under `src/point_add/` and
   `src/point_add/memory/`. These are macOS AppleDouble metadata files that
   an earlier commit had added. They are not Rust sources, and deleting them
   does not change the build.

## Why it is still correct, and what it risks

The comparator picks the wrong branch when `u` and `v` agree on all 45 compared
top bits. The walk then follows the wrong branch in its transcript, which gives
a classical mismatch. One bit less roughly doubles that per-step risk. The
author's note calls the cut "value-exact on the reachable support". It is not
exact. It is a probabilistic cut, and the re-hunted nonce `2100000741` draws a
clean test set: 9,024 of 9,024 shots, with 0 classical, 0 phase and 0 ancilla
failures. See [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

A single comparator loses one bit, which is comparator/width truncation.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 7f656bd -- src/point_add`.
   - Do not start from the git parent `571e67c`. That is runeape-sats's 1285-qubit
     tree, with 28 self-hosted carry stages and the vented x-tail square.
   - Diffing against the parent would wrongly show this commit undoing that
     work, and also odinfree's and zuiris's re-balance.
   - Against `7f656bd`, the content diff is 7 lines in `mod.rs`, plus the 210
     deleted `._*` files.
2. **Delete the stray files, then apply the patch below**, both from the repo
   root. The `rm` command is printed above the diff. Apply the patch with
   `git apply --ignore-whitespace`, so that it works whether the files use LF
   or CRLF line endings.
3. **Check the tree.** `git diff --ignore-cr-at-eol ebbe44e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh` with no
   `KAL_*` or `DIALOG_*` environment variables set. Expect:
   - 1309 qubits
   - 1,510,794 average Toffoli (rounded)
   - score 1,977,629,346
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with `DIALOG_TAIL_NONCE=2100000741` and an
identical op stream. Any other change needs a new nonce hunt.

### Patch

Delete these files first:

```sh
rm src/point_add/._blockers_and_paths.md \
   src/point_add/._by.rs \
   src/point_add/._by_sota_architecture.md \
   src/point_add/._coset_proto.md \
   src/point_add/._coset_proto.rs \
   src/point_add/._cost_model.md \
   src/point_add/._creative_attempts_log.md \
   src/point_add/._fermat_inv.rs \
   src/point_add/._google_harness_match.md \
   src/point_add/._halfgcd_coeff_decoder.rs \
   src/point_add/._halfgcd_live_pa.rs \
   src/point_add/._kaliski_1200q_feasibility.md \
   src/point_add/._kaliski_classical_replay.rs \
   src/point_add/._kaliski_equiv.rs \
   src/point_add/._kaliski_jump.rs \
   src/point_add/._kaliski_linear_transform.rs \
   src/point_add/._kim_costs.md \
   src/point_add/._kim_inv_circuit.rs \
   src/point_add/._kim_proto.rs \
   src/point_add/._lit_tricks.md \
   src/point_add/._luo_compact_inv_plan.md \
   src/point_add/._luo_proto.rs \
   src/point_add/._lut_proto.rs \
   src/point_add/._microbench.rs \
   src/point_add/._mod.rs \
   src/point_add/._next_session_plan.md \
   src/point_add/._primitive_costs.rs \
   src/point_add/._qubit_target_analysis.md \
   src/point_add/._research_log_2026_04_27.md \
   src/point_add/._research_notes.md \
   src/point_add/._round125_jsf.rs \
   src/point_add/._round158_halfgcd_splice_live.rs \
   src/point_add/._round185_halfgcd_fixed_depth64_pa.rs \
   src/point_add/._round218_b5_program.rs \
   src/point_add/._round218_b5_selector.rs \
   src/point_add/._round218_b5_transport.rs \
   src/point_add/._round326_b5_exact_cover_terms.rs \
   src/point_add/._round331_b5_old_g0_full_eraser.kmx \
   src/point_add/._s_equals_p_insight.md \
   src/point_add/._scratch600_frontier.rs \
   src/point_add/._scratch600_ground_up.md \
   src/point_add/._session_summary.md \
   src/point_add/._single_inv_numeric.rs \
   src/point_add/._single_inv_plan.md \
   src/point_add/._sota_gap_analysis.md \
   src/point_add/._sota_plan.md \
   src/point_add/._sota_rebuild_plan.md \
   src/point_add/._source_live_d1.rs \
   src/point_add/._strategy_c_schedule.md \
   src/point_add/._structural_sota_plan_2026_04_28.md \
   src/point_add/._test_timeout.rs \
   src/point_add/._unconditional_kal.rs \
   src/point_add/._venting.rs \
   src/point_add/memory/._2026-06-02-apply-fcut78-1543.md \
   src/point_add/memory/._2026-06-02-chunked-apply-f.md \
   src/point_add/memory/._2026-06-02-cswap-floor-analysis.md \
   src/point_add/memory/._2026-06-02-fused-branch-bits.md \
   src/point_add/memory/._2026-06-02-lowbit-body-skip.md \
   src/point_add/memory/._2026-06-02-next-agent-prompt.md \
   src/point_add/memory/._2026-06-02-projective-and-jump-analysis.md \
   src/point_add/memory/._2026-06-02-round763-applyclean19-stack.md \
   src/point_add/memory/._2026-06-02-session-handoff.md \
   src/point_add/memory/._2026-06-03-peak-1446-body-cin-uvhigh.md \
   src/point_add/memory/research_graph/._README.md \
   src/point_add/memory/research_graph/._frontier_watch.md \
   src/point_add/memory/research_graph/._knowledge_graph.md \
   src/point_add/memory/research_graph/._timeline.md \
   src/point_add/memory/research_graph/commit_notes/._001-c55911f-2548775.md \
   src/point_add/memory/research_graph/commit_notes/._002-15a06af-612df6c.md \
   src/point_add/memory/research_graph/commit_notes/._003-971d801-3f2319b.md \
   src/point_add/memory/research_graph/commit_notes/._004-ca1bf33-90ea031.md \
   src/point_add/memory/research_graph/commit_notes/._005-6f7c159-30c8ded.md \
   src/point_add/memory/research_graph/commit_notes/._006-ed34c00-99ec644.md \
   src/point_add/memory/research_graph/commit_notes/._007-f43a73e-32204b5.md \
   src/point_add/memory/research_graph/commit_notes/._008-168048c-b24ccfa.md \
   src/point_add/memory/research_graph/commit_notes/._009-a16788e-d8ed1df.md \
   src/point_add/memory/research_graph/commit_notes/._010-bc9728a-2c87a07.md \
   src/point_add/memory/research_graph/commit_notes/._011-8631b04-48497c2.md \
   src/point_add/memory/research_graph/commit_notes/._012-9bd0748-aac62d7.md \
   src/point_add/memory/research_graph/commit_notes/._013-a444668-3087b51.md \
   src/point_add/memory/research_graph/commit_notes/._014-b827c9e-23eac07.md \
   src/point_add/memory/research_graph/commit_notes/._015-666b591-37fe445.md \
   src/point_add/memory/research_graph/commit_notes/._016-e33b400-c42b503.md \
   src/point_add/memory/research_graph/commit_notes/._017-81ff75b-fdb8e16.md \
   src/point_add/memory/research_graph/commit_notes/._018-1c400f2-76aa0af.md \
   src/point_add/memory/research_graph/commit_notes/._019-9bcc27d-d35d6e7.md \
   src/point_add/memory/research_graph/commit_notes/._020-74a1a8b-a046bdb.md \
   src/point_add/memory/research_graph/commit_notes/._021-04b3a76-c8f4367.md \
   src/point_add/memory/research_graph/commit_notes/._022-3bbccd3-0c38fea.md \
   src/point_add/memory/research_graph/commit_notes/._023-d19dbb5-f94f726.md \
   src/point_add/memory/research_graph/commit_notes/._024-a3ee589-a630907.md \
   src/point_add/memory/research_graph/commit_notes/._025-b60eec2-d0c398d.md \
   src/point_add/memory/research_graph/commit_notes/._026-77b87f1-42d936f.md \
   src/point_add/memory/research_graph/commit_notes/._027-c8e508f-326f593.md \
   src/point_add/memory/research_graph/commit_notes/._028-36a2989-112d5a4.md \
   src/point_add/memory/research_graph/commit_notes/._029-a428a8c-edac713.md \
   src/point_add/memory/research_graph/commit_notes/._030-f910ba3-bfeee82.md \
   src/point_add/memory/research_graph/commit_notes/._031-ce60f0e-fde221f.md \
   src/point_add/memory/research_graph/commit_notes/._032-36e8578-437e22a.md \
   src/point_add/memory/research_graph/commit_notes/._033-f9fae31-77a20f9.md \
   src/point_add/memory/research_graph/commit_notes/._034-6da9882-70699b7.md \
   src/point_add/memory/research_graph/commit_notes/._035-0e32587-e480ce3.md \
   src/point_add/memory/research_graph/commit_notes/._036-b86e789-4a11f65.md \
   src/point_add/memory/research_graph/commit_notes/._037-13ac8da-03499c8.md \
   src/point_add/memory/research_graph/commit_notes/._038-1e18b4d-037fd71.md \
   src/point_add/memory/research_graph/commit_notes/._039-fc8b9e6-ceb0ce9.md \
   src/point_add/memory/research_graph/commit_notes/._040-2abe7f4-f751e0b.md \
   src/point_add/memory/research_graph/commit_notes/._041-179ab10-f342d57.md \
   src/point_add/memory/research_graph/commit_notes/._042-e739b53-aeaa7c5.md \
   src/point_add/memory/research_graph/commit_notes/._043-0be8d11-49499eb.md \
   src/point_add/memory/research_graph/commit_notes/._044-a97b4e9-99e6b44.md \
   src/point_add/memory/research_graph/commit_notes/._045-ac52c2e-dd590e3.md \
   src/point_add/memory/research_graph/commit_notes/._046-d4959a1-2070b06.md \
   src/point_add/memory/research_graph/commit_notes/._047-6eba4e3-bfe53b2.md \
   src/point_add/memory/research_graph/commit_notes/._048-bf19c9e-2a05eae.md \
   src/point_add/memory/research_graph/commit_notes/._049-0c25aca-66f1312.md \
   src/point_add/memory/research_graph/commit_notes/._050-404d630-2ca410f.md \
   src/point_add/memory/research_graph/commit_notes/._051-a25248f-d247fbf.md \
   src/point_add/memory/research_graph/commit_notes/._052-c7e1ae5-65d2cd7.md \
   src/point_add/memory/research_graph/commit_notes/._053-9fa5a56-1b4e026.md \
   src/point_add/memory/research_graph/commit_notes/._054-330186c-d6e44a1.md \
   src/point_add/memory/research_graph/commit_notes/._055-141b79a-b407149.md \
   src/point_add/memory/research_graph/commit_notes/._056-d6551e8-22bae60.md \
   src/point_add/memory/research_graph/commit_notes/._057-ba05d3a-375fdff.md \
   src/point_add/memory/research_graph/commit_notes/._058-297f5e5-c642799.md \
   src/point_add/memory/research_graph/commit_notes/._059-53f0bdb-ba6b8fc.md \
   src/point_add/memory/research_graph/commit_notes/._060-49b7969-ae7aa8c.md \
   src/point_add/memory/research_graph/commit_notes/._061-5136c0a-38255e0.md \
   src/point_add/memory/research_graph/commit_notes/._062-1b913c5-634b732.md \
   src/point_add/memory/research_graph/commit_notes/._063-85ee8e7-b14667c.md \
   src/point_add/memory/research_graph/commit_notes/._064-8eb6b5e-5b64367.md \
   src/point_add/memory/research_graph/commit_notes/._065-6e71096-47e7700.md \
   src/point_add/memory/research_graph/commit_notes/._066-3f534f2-22f54af.md \
   src/point_add/memory/research_graph/commit_notes/._067-3ab1c72-b0ed7db.md \
   src/point_add/memory/research_graph/commit_notes/._068-0e726ac-934ce80.md \
   src/point_add/memory/research_graph/commit_notes/._069-233a44c-0620443.md \
   src/point_add/memory/research_graph/commit_notes/._070-17ae622-0ae959c.md \
   src/point_add/memory/research_graph/commit_notes/._071-13a7a53-ea4f6e0.md \
   src/point_add/memory/research_graph/commit_notes/._072-8d83e8e-92d7808.md \
   src/point_add/memory/research_graph/commit_notes/._073-9899c06-ce7f062.md \
   src/point_add/memory/research_graph/commit_notes/._074-61bdeb0-ea8ad85.md \
   src/point_add/memory/research_graph/commit_notes/._075-ccd7530-baecd27.md \
   src/point_add/memory/research_graph/commit_notes/._076-115ab0e-e89e266.md \
   src/point_add/memory/research_graph/commit_notes/._077-a8688f8-0a0a631.md \
   src/point_add/memory/research_graph/commit_notes/._078-0435f04-3d9fa0a.md \
   src/point_add/memory/research_graph/commit_notes/._079-cd34b79-5d7f0be.md \
   src/point_add/memory/research_graph/commit_notes/._080-801b73e-abbfe51.md \
   src/point_add/memory/research_graph/commit_notes/._081-700d5a7-e72b854.md \
   src/point_add/memory/research_graph/commit_notes/._082-908521d-764a3ab.md \
   src/point_add/memory/research_graph/commit_notes/._083-cef001a-d1d29eb.md \
   src/point_add/memory/research_graph/commit_notes/._084-cddd5df-0c1d4d9.md \
   src/point_add/memory/research_graph/commit_notes/._085-541bd85-83e2b99.md \
   src/point_add/memory/research_graph/commit_notes/._086-00e3a20-9af8b71.md \
   src/point_add/memory/research_graph/commit_notes/._087-564c4c3-4ac4a16.md \
   src/point_add/memory/research_graph/commit_notes/._088-8cb350c-08573bd.md \
   src/point_add/memory/research_graph/commit_notes/._089-7e660f9-75927ba.md \
   src/point_add/memory/research_graph/commit_notes/._090-6447611-df59687.md \
   src/point_add/memory/research_graph/commit_notes/._091-c813ee5-1f7aabe.md \
   src/point_add/memory/research_graph/commit_notes/._092-3c30191-f1acd7f.md \
   src/point_add/memory/research_graph/commit_notes/._093-4b9cfbb-690bdb9.md \
   src/point_add/memory/research_graph/commit_notes/._094-1846bf7-692d5a0.md \
   src/point_add/memory/research_graph/commit_notes/._095-9b6b9d6-fd70a60.md \
   src/point_add/memory/research_graph/commit_notes/._096-acf2bdb-8ee9ad8.md \
   src/point_add/memory/research_graph/commit_notes/._097-f8a36ba-66ad478.md \
   src/point_add/memory/research_graph/commit_notes/._098-27530d2-1f6a568.md \
   src/point_add/memory/research_graph/commit_notes/._099-ad02935-cf2dfc4.md \
   src/point_add/memory/research_graph/commit_notes/._100-dd103cd-3b5d02e.md \
   src/point_add/memory/research_graph/commit_notes/._101-0aa33ed-634abd5.md \
   src/point_add/memory/research_graph/commit_notes/._102-0261289-987c92d.md \
   src/point_add/memory/research_graph/commit_notes/._103-985ae0f-f78af41.md \
   src/point_add/memory/research_graph/commit_notes/._104-9805d0c-73f81cc.md \
   src/point_add/memory/research_graph/commit_notes/._105-b694e22-a16cb87.md \
   src/point_add/memory/research_graph/commit_notes/._106-eda50f2-37f1ef4.md \
   src/point_add/memory/research_graph/commit_notes/._107-1fd942d-372e40e.md \
   src/point_add/memory/research_graph/commit_notes/._108-8316db1-fda639c.md \
   src/point_add/memory/research_graph/commit_notes/._109-412312f-b898614.md \
   src/point_add/memory/research_graph/commit_notes/._110-4b68e94-f3d33d5.md \
   src/point_add/memory/research_graph/commit_notes/._111-68e3653-744b274.md \
   src/point_add/memory/research_graph/commit_notes/._112-bb27ddd-e810f4e.md \
   src/point_add/memory/research_graph/commit_notes/._113-b6d6f41-e29e120.md \
   src/point_add/memory/research_graph/commit_notes/._114-075c0c6-b54d856.md \
   src/point_add/memory/research_graph/commit_notes/._115-36dcf6b-005e17a.md \
   src/point_add/memory/research_graph/commit_notes/._116-335ac78-3c08496.md \
   src/point_add/memory/research_graph/commit_notes/._117-14fc786-c54d9aa.md \
   src/point_add/memory/research_graph/commit_notes/._118-6e7ca2c-655038c.md \
   src/point_add/memory/research_graph/commit_notes/._119-7408de1-0399ebe.md \
   src/point_add/memory/research_graph/commit_notes/._120-17aad9a-51d09c7.md \
   src/point_add/memory/research_graph/commit_notes/._121-550895c-3bd3aa5.md \
   src/point_add/memory/research_graph/commit_notes/._122-8117d98-944d770.md \
   src/point_add/memory/research_graph/commit_notes/._123-006e38b-bb924c9.md \
   src/point_add/memory/research_graph/commit_notes/._124-ecbf87b-061e105.md \
   src/point_add/memory/research_graph/commit_notes/._125-1207861-02b2c22.md \
   src/point_add/memory/research_graph/commit_notes/._126-b113c6f-44155bb.md \
   src/point_add/memory/research_graph/commit_notes/._127-7787f81-bef8d8d.md \
   src/point_add/memory/research_graph/commit_notes/._128-40574d3-9b18a96.md \
   src/point_add/memory/research_graph/commit_notes/._129-287595e-cbc35ea.md \
   src/point_add/memory/research_graph/commit_notes/._130-fe29b53-d1a28f2.md \
   src/point_add/memory/research_graph/commit_notes/._131-7021abe-8780d1e.md \
   src/point_add/memory/research_graph/commit_notes/._132-df83d16-9d099e1.md \
   src/point_add/memory/research_graph/commit_notes/._133-46c3e3a-632a73b.md \
   src/point_add/memory/research_graph/commit_notes/._134-47f30d4-0a2d807.md \
   src/point_add/memory/research_graph/commit_notes/._135-7297f4f-2ae2218.md \
   src/point_add/memory/research_graph/commit_notes/._136-975b73f-d54ccf6.md \
   src/point_add/memory/research_graph/commit_notes/._137-250774e-da05eeb.md \
   src/point_add/memory/research_graph/commit_notes/._138-7c29f79-e0b0021.md \
   src/point_add/memory/research_graph/commit_notes/._139-92a247e-f2cd713.md \
   src/point_add/memory/research_graph/commit_notes/._140-fd8e712-8383a43.md \
   src/point_add/memory/research_graph/commit_notes/._141-14b84f1-700582e.md \
   src/point_add/memory/research_graph/commit_notes/._142-8ab5f90-53cab17.md \
   src/point_add/memory/research_graph/commit_notes/._143-d2b4bcf-44bc2a4.md
```

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 2d93843..d7af579 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -32703,13 +32703,14 @@ fn set_default_env(name: &str, value: &str) {
 }
 
 fn configure_ecdsafail_submission_route() {
-    // === Config-A bake: tightened GCD comparators + clean tail-nonce island ===
+    // === c45 bake: COMPARE 46->45 on the 7f656bd route + clean tail-nonce island ===
     // set_default_env is first-wins, so these override the later lever lines.
-    set_default_env("DIALOG_GCD_COMPARE_BITS", "46");
+    set_default_env("DIALOG_GCD_COMPARE_BITS", "45");
     set_default_env("DIALOG_GCD_APPLY_CLEAN_COMPARE_BITS", "18");
     set_default_env("KAL_DOUBLE_CARRY_TRUNC_W", "22");
+    set_default_env("KAL_FOLD_CARRY_TRUNC_W", "21");
     set_default_env("DIALOG_GCD_WIDTH_SLOPE_X1000", "1008");
-    set_default_env("DIALOG_TAIL_NONCE", "450007074");
+    set_default_env("DIALOG_TAIL_NONCE", "2100000741");
     set_default_env("SKIP_ALT_SEED_CHECKS", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_SIDECAR_LOG", "1");
     set_default_env("DIALOG_GCD_COMPRESSED_BLOCK_LIFECYCLE", "1");
```

