# 8bba91b — Re-place the in-place carry bridges after DPARK: fewer bridges, moved to the multiply tail

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-09-27 |
| Submission | `14123d0` |
| Commit | `8bba91b7d6f80a1a6a205faff82feb391128ed7e` |
| Result | 1250 qubits × 889,085 Toffoli = **1,111,356,250** |
| Base | `a231a39` (git parent, the author's previous submission "r6a_dpark"): 1250 qubits × 889,202 Toffoli = 1,111,502,500 |
| Change vs base | qubits ±0, Toffoli −117, score −146,250 (leaderboard Δ −146,250) |
| Family | Register and Scratch Allocation → in-place mutation |
| Concepts | [adders-and-carries](../concepts/adders-and-carries.md), [pingpong-division](../concepts/pingpong-division.md), [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md), [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

This commit changes one pin, `I35_PROFILE`, plus the nonce. `I35_PROFILE` says
how many in-place "bridge" carry stages each replay cell may use. A bridge
keeps a carry inside an operand wire instead of on its own wire. That saves one
wire and costs one extra CCX.

The previous commit, `a231a39`, freed a wire in every multiply replay cell
(`PP_U_DPARK`), so many cells no longer needed their bridge. This commit
re-derives the profile cell by cell. It goes from 82 bridged cells to 45, and
40 of the remaining 45 bridges sit on the late multiply rounds 658–697. The result is 117 fewer average Toffoli at the same 1250
qubits. The author reports that the classical results are bit-identical to
`a231a39`.

## What changed and why it saves Toffoli

**The mechanism** (`src/point_add/bridge.rs`, unchanged; see
[adders-and-carries](../concepts/adders-and-carries.md)):
- `bridge::enter(round, multiply)` looks up `(round, multiply)` in
  `I35_PROFILE`, whose entries are `round:dir:budget` with `dir` 0 for divide
  and 1 for multiply.
- `bridge::budget()` returns that budget while the cell runs. Unlisted cells
  use `I35_BUDGET`, which is pinned to 0.
- The replay's chunk-layout planners add the budget to their room:
  `chunk_layout(N, old + bridge::budget())`, `retained_rebalance`,
  `drop_exact_lead`, and `loaned_chunk_bounds`. So a budget of 1 lets the
  layout plan as if one more wire were free under `PP_WALK_MAX_QUBITS`.
- The layout then lays one Cuccaro MAJ/UMA stage into a chunk ladder, which
  is `cx(a,b); cx(a,p); ccx(b,p,a)`, plus a second CCX to undo it. That carry
  lives in the operand, not on an owned wire. Wider chunks need fewer
  approximate boundary repairs, but each bridge costs one CCX more.

**The change** (`src/point_add/mod.rs`, the `I35_PROFILE` arm in the
"r6a_dpark" block):

| | old (`a231a39`) | new (`8bba91b`) |
| --- | --- | --- |
| multiply cells with budget 1 | 80: rounds 414–439, 518–537, 574–591, 624–639 | 43: rounds 621–623, 658–697 |
| divide cells with budget 1 | 641, 646 | 641, 646 |
| total | 82 | 45 |

- Rounds 414–439, 518–537, 574–591 and 624–639 lose their bridge. The
  per-cell re-derivation found that, after DPARK freed a wire in these cells,
  the bridge's extra CCX no longer paid for itself.
- Rounds 621–623 and 658–697 gain one. The code comment says this lets the multiply's
  drop-exact-lead layout end in an 8-bit last chunk with no prefix compare.
- `TAIL_NONCE`: 29190082163 → 29234024713.

## Why it is still correct, and what it risks

- **Bridges are exact.** A Cuccaro stage computes the same sum as a
  measured-uncompute ripple stage. Only the wire and CCX use change.
- **The layouts are not exact in general.** The chunk layout decides where the
  approximate boundary compares sit. Moving bridges changes the layouts, so in
  principle it changes λ.
- The comment in `mod.rs` reports a paired λ difference ("dfailb") of
  −0.039 ± 0.069 over 512 nonces, which is no measurable change. It also
  reports that the classical results are bit-identical to `a231a39`.
- A wrong boundary compare would show up as a phase failure.
- The peak stays at 1250, because every ladder still sizes itself to
  `PP_WALK_MAX_QUBITS`. See
  [peak-qubits-and-budgets](../concepts/peak-qubits-and-budgets.md).
- The shipped nonce `29234024713` draws a clean test set: 9,024 of 9,024 shots
  pass, with 0 classical, 0 phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

The only circuit change is where carries are stored in operand wires instead
of in owned scratch, which is in-place mutation. The runner-up was
iteration/threshold tuning, since the change is a pure re-tune of a per-round
profile. In-place mutation is kept because that profile chooses where the
in-place trick is used, and that is the whole effect.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout a231a39 -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol a231a39 8bba91b -- src/point_add` is
   8 lines in 1 file.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line endings.
   It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol 8bba91b -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`.
   - All settings are fixed arms of `env_raw` in `mod.rs`, and the process
     environment is never read. Leave `I35_*`, `PP_*` and `SUB4_*` unset
     anyway.
   - Expect 1250 qubits and 889,085 average Toffoli (rounded).
   - Expect a score of 1,111,356,250.
   - Expect 0 classical, 0 phase and 0 ancilla failures.

The score only reproduces with `TAIL_NONCE` `29234024713` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 94f7369..f32fdb5 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -127,7 +127,7 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "29190082163",
+        "TAIL_NONCE" => "29234024713",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
@@ -193,7 +193,11 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_N_BADJ" => "400-449:d:2,649-699:a:-1,554-615:m:-1,589-615:d:-1,616-648:m:1,350-553:d:1,250-349:d:1,350-399:m:1",
         "I12_MUL_PROFILE" => "657:657,656:656,655:655,654:653,652:651,650:649,648:641,640:640,639:639,638:638,637:633,632:624,623:621,620:620,619:616,615:609,608:603,602:592,591:591,590:586,585:585,584:584,583:583,582:574,573:571,570:566,565:538,537:533,532:528,527:525,524:518,517:516,515:513,512:507,506:502,501:495,494:440,439:438,437:437,436:432,431:427,426:424,423:423,422:420,419:419,418:414,413:409",
         "I12_DIV_PROFILE" => "192:192,193:193,194:194,195:195,196:196,197:197,198:198,199:199,200:200,201:201,202:202,203:203,204:204,205:205,206:206,207:207,208:208,209:209,210:210,211:211,212:212,213:213,214:214,215:215,216:216,217:217,218:218,219:219,220:220,221:221,222:222,223:223,224:224,225:225,226:226,227:227,228:228,229:229,230:230,231:231,232:232,233:233,234:234,235:235,236:236,237:237,238:238,239:239,240:240,241:241,242:242,243:243,244:244,245:245,246:246,247:247,248:248,249:250,251:255,256:392,393:393,394:394,395:395,396:396,397:397,398:398,399:399,400:400,401:401,402:402,403:403,404:404,405:405,406:406,407:407,408:408,409:409,410:410,411:411,412:412,413:413,414:414,415:415,416:416,417:417,418:418,419:419,420:420,421:421,422:422,423:423,424:424,425:425,426:426,427:427,428:428,429:429,430:430,431:433,434:434,435:438,439:439,440:441,442:442,443:444,445:496,497:497,498:498,499:499,500:500,501:501,502:502,503:503,504:504,505:505,506:506,507:507,508:508,509:509,510:510,511:511,512:512,513:513,514:514,515:515,516:516,517:517,518:518,519:519,520:520,521:522,523:523,524:524,525:525,526:526,527:527,528:528,529:529,530:530,531:531,532:532,533:533,534:534,535:535,536:536,537:537,538:538,539:572,573:573,574:574,575:575,576:576,577:577,578:578,579:579,580:580,581:581,582:582,583:583,584:584,585:585,586:588,589:596,597:597,598:598,599:599,600:600,601:601,602:602,603:604,605:606,607:608,609:610,611:611,612:613,614:615,616:617,618:618,619:620,621:622,623:624,625:625,626:626,627:627,628:628,629:629,630:630,631:631,632:632,633:633,634:634,635:635,636:636,637:637,638:638,639:639,640:640,641:641,642:642,643:643,644:644,645:645,646:646,647:647,648:648,649:664,665:666,667:668,669:670,671:671,672:672,673:673,674:674,675:675,676:676,677:677,678:678,679:679,680:680,681:681,682:682,683:683,684:684",
-        "I35_PROFILE" => "414:1:1,415:1:1,416:1:1,417:1:1,418:1:1,419:1:1,420:1:1,421:1:1,422:1:1,423:1:1,424:1:1,425:1:1,426:1:1,427:1:1,428:1:1,429:1:1,430:1:1,431:1:1,432:1:1,433:1:1,434:1:1,435:1:1,436:1:1,437:1:1,438:1:1,439:1:1,518:1:1,519:1:1,520:1:1,521:1:1,522:1:1,523:1:1,524:1:1,525:1:1,526:1:1,527:1:1,528:1:1,529:1:1,530:1:1,531:1:1,532:1:1,533:1:1,534:1:1,535:1:1,536:1:1,537:1:1,574:1:1,575:1:1,576:1:1,577:1:1,578:1:1,579:1:1,580:1:1,581:1:1,582:1:1,583:1:1,584:1:1,585:1:1,586:1:1,587:1:1,588:1:1,589:1:1,590:1:1,591:1:1,624:1:1,625:1:1,626:1:1,627:1:1,628:1:1,629:1:1,630:1:1,631:1:1,632:1:1,633:1:1,634:1:1,635:1:1,636:1:1,637:1:1,638:1:1,639:1:1,641:0:1,646:0:1",
+        // r6i (agent O2): I35_PROFILE re-derived per cell after DPARK (spec pr426-hunt/O2/runs/r6i.spec,
+        // reference ops md5 ab7665628b337f4b25f696ff6874ba22 at TAIL_NONCE 26225815260). Bridges move to the
+        // multiply tail so the drop-exact-lead layout ends in an 8-bit last chunk (no prefix compare).
+        // Classical results bit-identical to r6a_dpark; paired dfailb -0.039 +- 0.069 over 512 nonces.
+        "I35_PROFILE" => "621:1:1,622:1:1,623:1:1,641:0:1,646:0:1,658:1:1,659:1:1,660:1:1,661:1:1,662:1:1,663:1:1,664:1:1,665:1:1,666:1:1,667:1:1,668:1:1,669:1:1,670:1:1,671:1:1,672:1:1,673:1:1,674:1:1,675:1:1,676:1:1,677:1:1,678:1:1,679:1:1,680:1:1,681:1:1,682:1:1,683:1:1,684:1:1,685:1:1,686:1:1,687:1:1,688:1:1,689:1:1,690:1:1,691:1:1,692:1:1,693:1:1,694:1:1,695:1:1,696:1:1,697:1:1",
         "PP_HEAD_MUL" => "413",
         "PP_FOLD_PROFILE" => "38:0,32:-1,19:-3,0:-4",
         // New exact constructions (agent J: square B-branch fusions; agent U: doubling-replay park).
```

