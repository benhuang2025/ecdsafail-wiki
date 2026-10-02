# a3bbb0e — Sell back fold-window protection, truncate the split modular-add compare to 24 bits, and make more multiply replays use the joint low fold

| | |
| --- | --- |
| Contestant | dysnasia |
| Date | 2026-09-27 |
| Submission | `3d9b324` |
| Commit | `a3bbb0e19596288e584d9c5ede6e21d2d0e941f2` |
| Result | 1251 qubits × 890,988 Toffoli = **1,114,625,988** |
| Base | `5a08ebd` (git parent and frontier at the time, mochimodev; the pin comments call it "PR 426"): 1251 qubits × 891,823 Toffoli = 1,115,670,573 |
| Change vs base | qubits ±0, Toffoli −835, score −1,044,585 (leaderboard Δ −1,044,585) |
| Family | Dead-Code and Redundancy Elimination → comparator/width truncation |
| Concepts | [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md), [modular-fold](../concepts/modular-fold.md), [pingpong-division](../concepts/pingpong-division.md), [measurement-uncompute](../concepts/measurement-uncompute.md), [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md) |
| Reproduce tier | **A**: the patch below is the whole change |

## Summary

The base had bought a lot of protection: wider fold windows on most replay
rounds. This commit sells most of it back, and spends some of the freed error
budget on two new truncations. To keep a clean nonce findable, it adds one
cheap division round at the end. It also regroups some late multiply replay
batches.

The levers are:
- Remove the +1-bit fold widening on early rounds and cut the late
  retained-fold widening from 3 bits to 1.
- In a modular add that has to split around the qubit cap, erase the split
  carry with a 24-bit compare instead of a full-width exact one.
- For multiply replays whose chunk layout starts with an exact chunk, try an
  all-approximate layout, so that the cheaper joint low fold fits.

Each of these makes some operation narrower and saves Toffoli, at the cost of
more rare failing inputs. Net −835 Toffoli at the same 1251 qubits.

## What changed and why it saves Toffoli

All knobs are fixed entries of `env_raw()` in `src/point_add/mod.rs`. The
commit moves the changed ones into a block at the end of the table, headed
"pkgFdP + stk2 package pins (pr426-sub3)". The comment there gives the
spec and says every knob that differs from PR 426 lives in that block.

### 1. Sell back fold protection, buy one round

- **`PP_FOLD_WIDEN` 242 → 0.** `fold_offset(round)` in `pingpong.rs` adds
  `+1` to the replay fold window when `round < fold_widen()`. At 242, rounds
  0–241 had a 1-bit-wider fold. At 0, no round does. This removes the base's
  widening and also the older 76-round widening it replaced. Every fold on
  those rounds is one bit narrower, about one Toffoli per fold. See
  [modular-fold](../concepts/modular-fold.md).
- **`PP_RETAIN_LATE_WIDEN` 3 → 1.** `retained_window()` adds this many bits
  to the retained-fold window where the walk's policy width is below 32.
- **`PP_WIDTH_SCHEDULE` gains a trailing `,8`.** `rounds_div()` is the
  schedule's length, so the divide walk goes from 698 to 699 rounds. The new
  round is 8 bits wide, so it costs little. One more round lets more slow
  inputs converge, which lowers λ. `PP_ROUNDS_MUL` stays at 698.

### 2. Truncated compare in the split modular add (`modular.rs`)

- `peak_fitted_add(value, acc, carry_out)` is the add inside
  `mod_addsub` (the coordinate shell's modular adds and the square's folds).
  When the full ripple does not fit under `PP_WALK_MAX_QUBITS`, it splits at
  `low = width − room`. The low part's carry lands on a `mid` wire, the high
  part continues from it, and then `mid` is erased with
  `erase_with_compare(mid, acc[..low], value[..low])`.
- That erase measures `mid` with `hmr` and, only when the outcome is 1, runs
  a phase compare `acc_low < value_low` to repair the phase. In the base the
  compare covered all `low` bits, so it was exact.
- New `peak_cmp_bits()` reads `PP_F_PEAKCMP = 24`. When `low > 24`, only the
  top 24 bits of the low part are compared: `acc[low-24..low]` against
  `value[low-24..low]`. That saves `low − 24` compare Toffoli on half the
  shots. It is wrong only when those 24 bits tie and the lower bits decide,
  about 2^-24 per call. See
  [comparator-and-width-truncation](../concepts/comparator-and-width-truncation.md)
  and [measurement-uncompute](../concepts/measurement-uncompute.md).

### 3. Drop an exact leading chunk so the joint low fold fits (`pingpong.rs`, `joint_lowfold.rs`, `retained_prebias.rs`)

- Background. A replay cell's add runs in chunks under the qubit cap. Each
  chunk boundary carry is erased by a truncated compare (a "B" site). The
  *joint low fold* (`joint_lowfold::try_replay`, used by the multiply
  replay) does the cell's mod-p fold inside the last chunk's add and erases
  the overflow from that add's own frame. This skips the separate overflow
  flag compare. It needs the last chunk to be at most `room − 32` wide, and
  its `plan()` accepts it only if the estimated `saving` is positive.
- Some layouts start with an *exact* chunk: its boundary compare covers the
  whole chunk (`boundary_repair_spec(…, 0, first) == (first, false)`). With
  such a layout the last chunk can be too wide, and the joint fold is
  refused.
- New `drop_exact_lead()`: when `PP_DROP_EXACT_LEAD=1`, it builds a new
  layout with the same number of chunks, each as wide as `widest_chunk`
  allows, and the remainder last. The first boundary becomes an ordinary
  seeded compare, widened by `PP_DROP_EXACT_LEAD_WIDEN` (default 1) bits
  through `drop_lead_first_compare()`. It returns the extra boundary-compare
  cost `db`, which is subtracted from the plan's `saving`.
- `plan()` in both `joint_lowfold.rs` and `retained_prebias.rs` takes a new
  `drop` flag. `try_replay` first tries the normal plan, then
  `plan(…, drop = true)`. `PP_DROP_EXACT_LEAD_DIR = mul` makes
  `drop_exact_lead` return `None` for the divide traversal, so only multiply
  replays use it. The retained-prebias (divide) edits are inert here.
- Net per affected round: one exact boundary compare becomes approximate,
  and the overflow-flag compare goes away.

### 4. Regroup late multiply replay batches

- `PP_TAIL_MUL` 655 → 657 (`plan.r2`: the trailing batch is rounds `r2 + 1`
  to the end).
- `I12_MUL_PROFILE`, the explicit multiply batch ranges, changes in a few
  places. For example 648–640 becomes one batch (was 648, 647, 646 and
  645–640), 570–567 and 566–548 … 538–536 become 570–566 and 565–536,
  619–618 splits into two single rounds, and the boundary between 608–602
  and 601–595 moves by one round.
- The pin comment says these "only choose which late multiply walk rounds
  batch before their replays; no round, width, fold window, guard or compare
  width changes". The grouping changes how much room each replay's chunk
  ladder has, and so how many boundary compares it needs.

### 5. Nonce

`TAIL_NONCE` 211106234700983 → 26225815260.

## Why it is still correct, and what it risks

- **All three savings are probabilistic.** The narrower folds, the 24-bit
  split compare and the approximate first boundary each add rare failing
  inputs. A wrong fold carry shows up as a classical failure, and a wrong
  compare as a phase failure.
- **The extra 8-bit round lowers λ.** It gives slow-converging inputs one
  more round, and it is cheap because the registers are narrow there.
- **The batch regrouping is exact.** It only moves where replays happen.
- The shipped nonce `26225815260` draws a clean test set: 0 classical, 0
  phase and 0 ancilla failures. See
  [nonce-island-and-lambda](../concepts/nonce-island-and-lambda.md).

## Classification rationale

Every lever that saves Toffoli makes a fold or compare narrower: the fold
widening goes, the split compare drops to 24 bits, and an exact boundary
compare becomes a truncated one. That is comparator/width truncation. The
extra round and the batch regrouping are a protection buy and a schedule
retune that support it.

## Reproduce

1. **Start from the base.** Clone https://github.com/ecdsafail/ecdsafail-challenge
   and run `git checkout 5a08ebd -- src/point_add`. The base is the git
   parent. `git diff --ignore-cr-at-eol 5a08ebd a3bbb0e -- src/point_add` is
   160 changed lines in 5 files. Five more files (`affine_constant.rs`,
   `known_stream.rs`, `round2_fused.rs`, `round2_receiver.rs`,
   `stream_wide.rs`) differ only in line endings, so the patch skips them.
2. **Apply the patch below** from the repo root with `git apply --ignore-whitespace`.
   The flag lets the patch apply whether the files use LF or CRLF line
   endings. It is the complete diff against the base.
3. **Check the tree.** `git diff --ignore-cr-at-eol a3bbb0e -- src/point_add`
   should print nothing.
4. **Run the benchmark.** Run `./setup.sh && ./benchmark.sh`. This tree reads
   no environment variables: every knob is a fixed entry in `env_raw()`, so
   `PP_*`, `SQ_*` or `SUB4_*` overrides are ignored. Leave them unset anyway.
   Expect:
   - 1251 qubits
   - 890,988 average Toffoli (rounded)
   - score 1,114,625,988
   - 0 classical, 0 phase and 0 ancilla failures

The score only reproduces with the nonce `26225815260` and an identical op
stream. Any other change needs a new nonce hunt.

### Patch

```diff
diff --git a/src/point_add/joint_lowfold.rs b/src/point_add/joint_lowfold.rs
index 5266510..b6ddea9 100644
--- a/src/point_add/joint_lowfold.rs
+++ b/src/point_add/joint_lowfold.rs
@@ -7,9 +7,9 @@ thread_local! { pub(super) static GUARD:std::cell::Cell<Option<usize>>=const{std
 fn low_bits(guard:usize)->usize { super::super::optional_env::<usize>("PP_JOINT_LOW_BITS").unwrap_or(32+guard) }
 
 #[derive(Debug)]
-struct Plan { bounds:Vec<(usize,usize)>, prefix:usize, guard:usize, bits:usize, saving:f64, exact:bool }
+struct Plan { bounds:Vec<(usize,usize)>, prefix:usize, guard:usize, bits:usize, saving:f64, exact:bool, dropped:bool }
 
-fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize)->Option<Plan> {
+fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize,drop:bool)->Option<Plan> {
     if !multiply && env_raw("PP_PREBIAS_RETAIN_BITS").is_some() {return None;}
     let guard=super::super::optional_env::<usize>("PP_JOINT_GUARD")?;
     let low=if env_flag("PP_SPRINT_MIXED") && multiply && (364..=402).contains(&round) {29}else{low_bits(guard)};assert!((12..=fw).contains(&low) && !split_fold());
@@ -17,18 +17,19 @@ fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize)->Option<Plan> {
     assert!(env_flag("PP_REUSE_DIV_PARITY") && env_flag("PP_REUSE_MUL_SELECTORS"));
     let room=walk_max_qubits().saturating_sub(circ.active_qubits()as usize);
     let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
-    let old_bounds=composition_bounds(circ,round,multiply)?;
-    let bounds=retained_rebalance(circ,&old_bounds,round,multiply);
+    let Some(old_bounds)=composition_bounds(circ,round,multiply) else {if !drop{drop_trace(round,multiply,"nocomp",String::new());}return None;};
+    let (bounds,db)=if drop {drop_exact_lead(circ,&old_bounds,round,multiply,fw)?}
+        else {(retained_rebalance(circ,&old_bounds,round,multiply),0.0)};
     if bounds.len()<2 {return None;}
     let &(lo,hi)=bounds.last()?;
     let (plo,phi)=bounds[bounds.len()-2];
     let (k,seeded)=boundary_repair_spec(round,multiply,plo,phi);
-    if lo<fw || phi-k-usize::from(seeded)<fw {return None;}
+    if lo<fw || phi-k-usize::from(seeded)<fw {drop_trace(round,multiply,"lofw",format!("drop={} fw={} {:?}",drop,fw,bounds));return None;}
     let need=(low-3).max(fw-34);
     let existing=walk_max_qubits()as isize-circ.active_qubits()as isize-(hi-lo)as isize-if multiply&&env_flag("PP_JOINT_MUL_FOLD"){3}else{4};
     let missing=(need as isize-existing).max(0)as usize;
     let prefix=if missing==0 {0} else {missing+1};
-    if prefix+1>=hi-lo {return None;}
+    if prefix+1>=hi-lo {drop_trace(round,multiply,"prefix",format!("drop={} fw={} missing={} {:?}",drop,fw,missing,bounds));return None;}
     let mut fk=if multiply {flag_compare(round)+usize::from(a5_policy()=="mul-f-plus1-early200"&&(2..202).contains(&round))}
         else {flag_compare(round)+usize::from(policy_width(round)>=flag_widen_div())};
     // EXP PP_SEED_SHORT_MUL_F_COST: the plain path's narrow multiply F compare is one bit shorter.
@@ -36,23 +37,25 @@ fn plan(circ:&Builder,round:usize,multiply:bool,fw:usize)->Option<Plan> {
     let seeded=if multiply {(policy_width(round)>=38 && matches!(a5_policy(),"mul-f-seed"|"mul-fb-seed")) || short_cost}else{env_flag("CMP_SEED_ALL")};
     if (!multiply && seeded) || short_cost {fk-=1;}
     if !seeded {fk=refined_unseeded_width(fk,N,"PP_REFINE_UNSEEDED_F");}
-    let saving=(fk-1)as f64/2.0-missing as f64/2.0-(low as f64-33.0);
-    if saving<=0.0 {return None;}
+    let saving=(fk-1)as f64/2.0-missing as f64/2.0-(low as f64-33.0)-db;
+    if saving<=0.0 {drop_trace(round,multiply,"saving",format!("drop={} fw={} fk={} missing={} db={} {:?}",drop,fw,fk,missing,db,bounds));return None;}
     // Release a bounded additional carry prefix to fit the full finite fold.
     // Outer B comparisons are unchanged; the inserted midpoint uses exact cleanup.
     let limit=super::super::optional_env::<usize>("PP_RETAIN_EXACT_EXTRA_MUL").unwrap_or(0);
     let exact_missing=((fw-3) as isize-existing).max(0) as usize;
     let exact_prefix=if exact_missing==0 {0}else{exact_missing+1};
-    let exact=multiply && env_flag("PP_RETAIN_EXACT_MUL") && exact_missing<=limit && exact_prefix+1<hi-lo;
+    let exact=(multiply && env_flag("PP_RETAIN_EXACT_MUL") && exact_missing<=limit || drop_exact_lead_exact(drop,exact_missing)) && exact_prefix+1<hi-lo;
     let prefix=if exact {exact_prefix}else{prefix};
     let saving=if exact {saving-(exact_missing-missing) as f64/2.0-1.0}else{saving};
-    Some(Plan{bounds,prefix,guard,bits:low,saving,exact})
+    if !drop_exact_lead_minsave(drop,saving) {return None;}
+    Some(Plan{bounds,prefix,guard,bits:low,saving,exact,dropped:drop})
 }
 
 pub(super) fn try_replay(circ:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw:usize,
     round:usize,doubled:Option<QubitId>)->bool {
     let multiply=doubled.is_some();
-    let Some(p)=plan(circ,round,multiply,fw)else{return false;};
+    let Some(p)=plan(circ,round,multiply,fw,false).or_else(||plan(circ,round,multiply,fw,true))else{return false;};
+    if p.dropped {eprintln!("DROP_EXACT_LEAD mul={} r={} base={} saving={} bounds={:?}",multiply as u8,round,circ.active_qubits(),p.saving,p.bounds);}
     eprintln!("JOINT_LOWFOLD r={} mul={} base={} last={} prefix={} guard={} saving={}",round,multiply as u8,
         circ.active_qubits(),p.bounds.last().unwrap().1-p.bounds.last().unwrap().0,p.prefix,p.guard,p.saving);
     if env_flag("PP_COMPOSE_TRACE"){eprintln!("COMPOSE_MUL {} {} {} {} {} {:?}",round,circ.active_qubits(),fw,p.bits,REPLAY_SIGN_LOANS.with(|s|s.get()),p.bounds);}
@@ -87,7 +90,7 @@ pub(super) fn try_replay(circ:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId
             }
         }else{let at=if pre&&lo==0{1}else{lo};ripple_add(circ,&a[at..hi],&b[at..hi],incoming,Some(next));}
         if let Some((q,plo,phi))=previous {
-            let(k,seeded)=boundary_repair_spec(round,multiply,plo,phi);
+            let(k,seeded)=if p.dropped&&plo==0 {drop_lead_first_compare(round,multiply,phi)}else{boundary_repair_spec(round,multiply,plo,phi)};
             circ.record_replay_site('B',round,phi,k);
             // A full first-chunk compare must skip bit 0, which the add no longer covers.
             let from=if pre&&plo==0&&phi==k{1}else{phi-k};
diff --git a/src/point_add/mod.rs b/src/point_add/mod.rs
index 0d7e4a3..17e1814 100644
--- a/src/point_add/mod.rs
+++ b/src/point_add/mod.rs
@@ -54,7 +54,6 @@ fn env_raw(name: &str) -> Option<String> {
         "I33_DISABLE" => "0",
         "I35_PROFILE" => "408:1:1,409:1:1,410:1:1,411:1:1,412:1:1,413:1:1,414:1:1,415:1:1,416:1:1,417:1:1,418:1:1,419:1:1,420:1:1,421:1:1,422:1:1,423:1:1,512:1:1,513:1:1,514:1:1,515:1:1,516:1:1,517:1:1,518:1:1,519:1:1,520:1:1,521:1:1,522:1:1,523:1:1,524:1:1,525:1:1,526:1:1,527:1:1,528:1:1,529:1:1,530:1:1,531:1:1,532:1:1,533:1:1,534:1:1,535:1:1,547:1:1,574:1:1,575:1:1,576:1:1,577:1:1,578:1:1,579:1:1,580:1:1,581:1:1,582:1:1,583:1:1,584:1:1,585:1:1,586:1:1,587:1:1,588:1:1,589:1:1,590:1:1,591:1:1,609:0:1,619:0:2,620:0:2,620:1:1,621:1:1,622:1:1,623:1:1,624:1:1,625:1:1,626:1:1,627:1:1,628:1:1,629:1:1,630:1:1,631:1:1,632:1:1,633:1:1,634:1:1,635:1:1,636:1:1,637:1:1,638:1:1,639:1:1,646:1:1",
         "I12_DIV_PROFILE" => "192:192,193:193,194:194,195:195,196:196,197:197,198:198,199:199,200:200,201:201,202:202,203:203,204:204,205:205,206:206,207:207,208:208,209:209,210:210,211:211,212:212,213:213,214:214,215:215,216:216,217:217,218:218,219:219,220:220,221:221,222:222,223:223,224:224,225:225,226:226,227:227,228:228,229:229,230:230,231:231,232:232,233:233,234:234,235:235,236:236,237:237,238:238,239:239,240:240,241:241,242:242,243:243,244:244,245:245,246:246,247:247,248:248,249:249,250:392,393:393,394:394,395:395,396:396,397:397,398:398,399:399,400:400,401:401,402:402,403:403,404:404,405:405,406:406,407:407,408:408,409:409,410:410,411:411,412:412,413:413,414:414,415:415,416:416,417:417,418:418,419:419,420:420,421:421,422:422,423:423,424:424,425:425,426:426,427:427,428:428,429:429,430:430,431:431,432:432,433:496,497:497,498:498,499:499,500:500,501:501,502:502,503:503,504:504,505:505,506:506,507:507,508:508,509:509,510:510,511:511,512:512,513:513,514:514,515:515,516:516,517:517,518:518,519:519,520:520,521:522,523:523,524:524,525:525,526:526,527:527,528:528,529:529,530:530,531:531,532:532,533:533,534:534,535:535,536:536,537:537,538:538,539:539,540:540,541:572,573:573,574:574,575:575,576:576,577:577,578:578,579:579,580:580,581:581,582:582,583:583,584:584,585:585,586:586,587:587,588:588,589:596,597:597,598:598,599:599,600:600,601:601,602:602,603:604,605:606,607:608,609:609,610:611,612:613,614:615,616:616,617:618,619:620,621:621,622:622,623:623,624:624,625:625,626:626,627:627,628:628,629:629,630:630,631:631,632:632,633:633,634:634,635:635,636:636,637:637,638:638,639:639,640:640,641:641,642:642,643:643,644:644,645:645,646:646,647:647,648:648,649:664,665:666,667:668,669:670,671:671,672:672,673:673,674:674,675:675,676:676,677:677,678:678,679:679,680:680,681:681,682:682,683:683,684:684",
-        "I12_MUL_PROFILE" => "654:653,652:651,650:649,648:648,647:647,646:646,645:640,639:639,638:638,637:625,624:620,619:618,617:616,615:609,608:602,601:595,594:592,591:586,585:585,584:584,583:579,578:574,573:571,570:567,566:548,547:547,546:542,541:539,538:536,535:533,532:528,527:525,524:512,511:503,502:502,501:495,494:424,423:423,422:420,419:415,414:410,409:409,408:408,407:403",
         "I12_B_GUARD" => "4",
         "CMP_SEED_ALL" => "1",
         "ERASE_COMPARE" => "24",
@@ -70,7 +69,6 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_FLAG_SHAPE" => "38:0,25:-1,0:-3",
         "PP_FLAG_WIDEN_DIV" => "38",
         "PP_FOLD_PROFILE" => "38:0,32:-1,19:-4,0:-4",
-        "PP_FOLD_WIDEN" => "242",
         "PP_HEAD_DIV" => "192",
         "PP_HEAD_MUL" => "403",
         "PP_JOINT_GUARD" => "0",
@@ -95,7 +93,6 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_RETAIN_EXACT_EXTRA_DIV" => "4",
         "PP_RETAIN_EXACT_EXTRA_MUL" => "4",
         "PP_RETAIN_EXACT_MUL" => "1",
-        "PP_RETAIN_LATE_WIDEN" => "3",
         "PP_RETAIN_REBALANCE" => "1",
         "PP_REUSE_DIV_PARITY" => "1",
         "PP_REUSE_MUL_SELECTORS" => "1",
@@ -108,11 +105,9 @@ fn env_raw(name: &str) -> Option<String> {
         "PP_SPLIT_OVERLAP_BITS" => "1",
         "PP_SPRINT_MIXED" => "0",
         "PP_TAIL_DIV" => "682",
-        "PP_TAIL_MUL" => "655",
         "PP_WALK_GUARD_BITS" => "1",
         "PP_WALK_GUARD_MAX_WIDTH" => "64",
         "PP_WALK_MAX_QUBITS" => "1251",
-        "PP_WIDTH_SCHEDULE" => "259,258x19,257x5,256x3,255x4,254x4,253x2,252x4,251x3,250x5,249x2,248x4,247x3,246x2,245x4,244x3,243x3,242x3,241x3,240x3,239x4,238x3,237x2,236x4,235x2,234x3,233x2,232x4,231x4,230x2,229x3,228x3,227x3,226x2,225x4,224x2,223x2,222x3,221x3,220x4,219x3,218x2,217x3,216x3,215x3,214x4,213x2,212x2,211x3,210x4,209x3,208x2,207x2,206x2,205x3,204x2,203x4,202x3,201x3,200x4,199x2,198x2,197x3,196x2,195x2,194x4,193x4,192x2,191x3,190x3,189x2,188x3,187x2,186x3,185x2,184x3,183x4,182x2,181x3,180x4,179x2,178x2,177x3,176x3,175,174x2,173x2,172x4,171x3,170x2,169x2,168x4,167x3,166x3,165x2,164x3,163x3,162x2,161x3,160x2,159x3,158x2,157x3,156x2,155x4,154x2,153x3,152x2,151x3,150x3,149x2,148x2,147x2,146x4,145x4,144x3,143x2,142x2,141x3,140x2,139x2,138x2,137x3,136x2,135x4,134x3,133x3,132x3,131x2,130x3,129x2,128x4,127x3,126x2,125x2,124x3,123x2,122x3,121x3,120x2,119x5,118x2,117x3,116x2,115x3,114x4,113x2,112x2,111x4,110x2,109x2,108x2,107x2,106x2,105x5,104x2,103x2,102x2,101x2,100x4,99x2,98x2,97x2,96x3,95x3,94x3,93x2,92x3,91x2,90x4,89x3,88x2,87x2,86x4,85x2,84,83x4,82x2,81x2,80x2,79x3,78x2,77x2,76x3,75,74x2,73x3,72x3,71x2,70x3,69x3,68x3,67x3,66x2,65x3,64x4,63x2,62x2,61x3,60x2,59x2,58x2,57x2,56x2,55x3,54x3,53x2,52x3,51x2,50x4,49x2,48x2,47x3,46x3,45x2,44x2,43x3,42x2,41x2,40x3,39x2,38x2,37x3,36x4,35x2,34x3,33x2,32x2,31x2,30x2,29x2,28x4,27x2,26x2,25x3,24x2,23x2,22x2,21x3,20x3,19x2,18x3,17x2,16x2,15x3,14x2,13x2,12x2,11x2,10x2,9x4,8x9,8x2",
         "SQ_ALIAS_PRODUCT_LSB" => "1",
         "SQ_A_POLICY" => "7",
         "SQ_BORROW_ROW_CARRIES" => "0",
@@ -138,11 +133,37 @@ fn env_raw(name: &str) -> Option<String> {
         "SQ_ZERO_TOP_SPREAD" => "1",
         "SQ_ZERO_TOP_SUM" => "1",
         // Accepted public-validation nonce from the production grind.
-        "TAIL_NONCE" => "211106234700983",
+        "TAIL_NONCE" => "26225815260",
         "PP_SEED_SHORT_MUL_F_COST" => "1",
         "SQ_HIGH_CARRY_LOAN" => "1",
         "SQ_HOLD_BOUNDARY" => "1",
         "SQ_OWN_TOP_ZEROS" => "1",
+        // ==================== pkgFdP + stk2 package pins (pr426-sub3) ====================
+        // Every knob that differs from PR 426 lives in this block and nowhere else;
+        // FOLD_WIDEN, RETAIN_LATE_WIDEN and WIDTH_SCHEDULE were removed from the
+        // alphabetical list above so no arm shadows these. Spec (pr426-hunt/R/q5.txt):
+        //   PP_RETAIN_LATE_WIDEN=1 PP_FOLD_WIDEN=0 PP_WIDTH_SCHEDULE=<PR 426>,8
+        //   PP_DROP_EXACT_LEAD=1 PP_DROP_EXACT_LEAD_DIR=mul PP_F_PEAKCMP=24
+        // The trailing ",8" adds one division round (699); PP_ROUNDS_MUL stays 698.
+        // Protection buy: change ONE line here (e.g. "PP_FOLD_WIDEN" => "12"), or for
+        // FOLD_GUARD move its line ("FOLD_GUARD" => "25", above) here with the new value.
+        // The first matching arm wins, so a key must never appear twice. Then mirror
+        // it in the grinder's Config::p426fdp (GRIND_WIDEN / GRIND_FOLD_GUARD defaults).
+        "PP_RETAIN_LATE_WIDEN" => "1",
+        "PP_FOLD_WIDEN" => "0",
+        "PP_WIDTH_SCHEDULE" => "259,258x19,257x5,256x3,255x4,254x4,253x2,252x4,251x3,250x5,249x2,248x4,247x3,246x2,245x4,244x3,243x3,242x3,241x3,240x3,239x4,238x3,237x2,236x4,235x2,234x3,233x2,232x4,231x4,230x2,229x3,228x3,227x3,226x2,225x4,224x2,223x2,222x3,221x3,220x4,219x3,218x2,217x3,216x3,215x3,214x4,213x2,212x2,211x3,210x4,209x3,208x2,207x2,206x2,205x3,204x2,203x4,202x3,201x3,200x4,199x2,198x2,197x3,196x2,195x2,194x4,193x4,192x2,191x3,190x3,189x2,188x3,187x2,186x3,185x2,184x3,183x4,182x2,181x3,180x4,179x2,178x2,177x3,176x3,175,174x2,173x2,172x4,171x3,170x2,169x2,168x4,167x3,166x3,165x2,164x3,163x3,162x2,161x3,160x2,159x3,158x2,157x3,156x2,155x4,154x2,153x3,152x2,151x3,150x3,149x2,148x2,147x2,146x4,145x4,144x3,143x2,142x2,141x3,140x2,139x2,138x2,137x3,136x2,135x4,134x3,133x3,132x3,131x2,130x3,129x2,128x4,127x3,126x2,125x2,124x3,123x2,122x3,121x3,120x2,119x5,118x2,117x3,116x2,115x3,114x4,113x2,112x2,111x4,110x2,109x2,108x2,107x2,106x2,105x5,104x2,103x2,102x2,101x2,100x4,99x2,98x2,97x2,96x3,95x3,94x3,93x2,92x3,91x2,90x4,89x3,88x2,87x2,86x4,85x2,84,83x4,82x2,81x2,80x2,79x3,78x2,77x2,76x3,75,74x2,73x3,72x3,71x2,70x3,69x3,68x3,67x3,66x2,65x3,64x4,63x2,62x2,61x3,60x2,59x2,58x2,57x2,56x2,55x3,54x3,53x2,52x3,51x2,50x4,49x2,48x2,47x3,46x3,45x2,44x2,43x3,42x2,41x2,40x3,39x2,38x2,37x3,36x4,35x2,34x3,33x2,32x2,31x2,30x2,29x2,28x4,27x2,26x2,25x3,24x2,23x2,22x2,21x3,20x3,19x2,18x3,17x2,16x2,15x3,14x2,13x2,12x2,11x2,10x2,9x4,8x9,8x2,8",
+        "PP_DROP_EXACT_LEAD" => "1",
+        "PP_DROP_EXACT_LEAD_DIR" => "mul",
+        "PP_F_PEAKCMP" => "24",
+        // ---- stk2 (pr426-sub3): agent M's schedule-only levers on top of pkgFdP ----
+        // Spec pr426-hunt/M/stk2.spec; reference build pr426-hunt/M/runs/stk2w
+        // (ops md5 fed8ad7a5bd1fc23118c448286c2633d). PP_TAIL_MUL (was 655) and
+        // I12_MUL_PROFILE were removed from the alphabetical list above so no arm
+        // shadows these. Both only choose which late multiply walk rounds batch before
+        // their replays; no round, width, fold window, guard or compare width changes.
+        "PP_TAIL_MUL" => "657",
+        "I12_MUL_PROFILE" => "654:653,652:651,650:649,648:640,639:639,638:638,637:625,624:620,619:619,618:618,617:616,615:609,608:603,602:595,594:592,591:587,586:586,585:585,584:584,583:579,578:574,573:571,570:566,565:536,535:533,532:528,527:525,524:512,511:503,502:502,501:495,494:424,423:423,422:420,419:415,414:410,409:409,408:408,407:403",
+        // ================== end pkgFdP + stk2 package pins ==================
         _ => return None,
     };
     Some(value.to_owned())
diff --git a/src/point_add/modular.rs b/src/point_add/modular.rs
index 623f596..0822684 100644
--- a/src/point_add/modular.rs
+++ b/src/point_add/modular.rs
@@ -6,6 +6,11 @@ use super::pingpong::walk_max_qubits;
 use super::{fold_guard, pinned_env, Builder, SECP256K1_P};
 use crate::circuit::{BitId, QubitId};
 
+fn peak_cmp_bits() -> Option<usize> {
+    static SLOT: std::sync::OnceLock<Option<usize>> = std::sync::OnceLock::new();
+    *SLOT.get_or_init(|| super::optional_env("PP_F_PEAKCMP"))
+}
+
 // Width of the measured-erasure comparisons in this file, and nowhere else in
 // the tree. One bit finer than `fold_guard` by the balance rule derived in
 // `mod.rs`: a compare's Toffoli sit under a `push_condition` and execute half
@@ -605,7 +610,14 @@ fn peak_fitted_add(circ: &mut Builder, value: &[QubitId], acc: &[QubitId], carry
     let mid = circ.alloc_qubit();
     ripple_add(circ, &value[..low], &acc[..low], None, Some(mid));
     ripple_add(circ, &value[low..], &acc[low..], Some(mid), Some(carry_out));
-    erase_with_compare(circ, mid, &acc[..low], &value[..low], None);
+    // PP_F_PEAKCMP=k: compare only the top k bits of the leading chunk
+    // (approximate, fails only when those k bits tie). Unset: exact.
+    match peak_cmp_bits() {
+        Some(k) if k >= 2 && low > k => {
+            erase_with_compare(circ, mid, &acc[low - k..low], &value[low - k..low], None)
+        }
+        _ => erase_with_compare(circ, mid, &acc[..low], &value[..low], None),
+    }
     circ.free(mid);
 }
 
diff --git a/src/point_add/pingpong.rs b/src/point_add/pingpong.rs
index 7cb9f1c..582a8e4 100644
--- a/src/point_add/pingpong.rs
+++ b/src/point_add/pingpong.rs
@@ -3627,6 +3627,63 @@ fn retained_rebalance(c:&Builder, old:&[(usize,usize)], round:usize, multiply:bo
     if same {new} else {old.to_vec()}
 }
 
+// EXP PP_DROP_EXACT_LEAD: for a retained-frame receiver whose layout starts
+// with an EXACT leading chunk, replace the layout by an all-approximate one of
+// the same chunk count, [room, room-1, ..., remainder], so the final chunk is
+// narrow enough (<= room-32) for the joint low fold. The first boundary becomes
+// an ordinary seeded chunk compare (optionally WIDEN bits wider); every other
+// boundary keeps the same compare width/seed rule at a moved endpoint.
+// Returns the new bounds and dB, the added boundary-compare Toffoli (window-1)/2.
+fn drop_trace(round:usize,multiply:bool,tag:&str,info:String) {
+    if env_flag("PP_DROP_TRACE") {eprintln!("DROP_TRACE r={} mul={} {} {}",round,multiply as u8,tag,info);}
+}
+fn drop_exact_lead_exact(drop:bool,exact_missing:usize)->bool {
+    drop && super::optional_env::<usize>("PP_DROP_EXACT_LEAD_EXACT").is_some_and(|l|exact_missing<=l)
+}
+fn drop_exact_lead_minsave(drop:bool,saving:f64)->bool {
+    !drop || saving>=super::optional_env::<f64>("PP_DROP_EXACT_LEAD_MINSAVE").unwrap_or(f64::MIN)
+}
+fn drop_exact_lead_widen()->usize {
+    let w=super::optional_env::<usize>("PP_DROP_EXACT_LEAD_WIDEN").unwrap_or(1);
+    assert!(w<=8,"drop-lead widening limited to eight bits");w
+}
+fn drop_exact_lead(c:&Builder,old:&[(usize,usize)],round:usize,multiply:bool,fw:usize)->Option<(Vec<(usize,usize)>,f64)> {
+    if !env_flag("PP_DROP_EXACT_LEAD") || old.len()<2 || old[0].0!=0 {return None;}
+    match env_raw("PP_DROP_EXACT_LEAD_DIR").as_deref() {
+        None|Some("both")=>{}, Some("mul")=>if !multiply {return None;}, Some("div")=>if multiply {return None;},
+        Some(x)=>panic!("PP_DROP_EXACT_LEAD_DIR={x}"),
+    }
+    let min=super::optional_env::<usize>("PP_DROP_EXACT_LEAD_MIN").unwrap_or(2);
+    let widen=drop_exact_lead_widen();
+    let first=old[0].1;
+    if first<min || boundary_repair_spec(round,multiply,0,first)!=(first,false) {drop_trace(round,multiply,"notexactlead",format!("{:?}",old));return None;}
+    let bridge=if env_flag("PP_DROP_EXACT_LEAD_NOBRIDGE"){0}else{super::bridge::budget()};
+    let room=(walk_max_qubits()+bridge).saturating_sub(c.active_qubits() as usize);
+    let k=old.len();
+    let mut sizes:Vec<usize>=(0..k).map(|j|widest_chunk(j,room)).collect();
+    let head:usize=sizes[..k-1].iter().sum();
+    if head>=N {return None;}
+    let last=N-head;
+    sizes[k-1]=last;
+    if last<2 || last+32>room || N-last<fw || layout_ladder(&sizes)>room {drop_trace(round,multiply,"nofit",format!("room={} last={} fw={} {:?}",room,last,fw,old));return None;}
+    let new=to_bounds(&sizes);
+    let (k0,_)=boundary_repair_spec(round,multiply,new[0].0,new[0].1);
+    if new[0].1<k0+widen+2 {return None;}
+    let cost=|b:&[(usize,usize)],w0:usize|->f64 {b[..b.len()-1].iter().enumerate().map(|(j,&(lo,hi))|{
+        let(kk,_)=boundary_repair_spec(round,multiply,lo,hi);(kk+if j==0{w0}else{0})as f64-1.0}).sum::<f64>()/2.0};
+    let db=cost(&new,widen)-cost(old,0);
+    Some((new,db))
+}
+
+/// Seeded or plain window for the first boundary of a drop-lead layout,
+/// widened by PP_DROP_EXACT_LEAD_WIDEN bits; the seed moves with the window.
+fn drop_lead_first_compare(round:usize,multiply:bool,phi:usize)->(usize,bool) {
+    let(k,seeded)=boundary_repair_spec(round,multiply,0,phi);
+    let k=k+drop_exact_lead_widen();
+    assert!(phi>=k+2,"drop-lead first compare must fit its chunk");
+    (k,seeded)
+}
+
 fn chunked_add(circ: &mut Builder, addend: &[QubitId], acc: &[QubitId], round: usize, multiply: bool) -> QubitId {
     let ladder = walk_max_qubits().saturating_sub(circ.active_qubits() as usize);
     let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
diff --git a/src/point_add/retained_prebias.rs b/src/point_add/retained_prebias.rs
index ae3cb80..7a6f041 100644
--- a/src/point_add/retained_prebias.rs
+++ b/src/point_add/retained_prebias.rs
@@ -3,34 +3,35 @@
 use super::*;
 
 #[derive(Debug)]
-struct Plan {bounds:Vec<(usize,usize)>,prefix:usize,bits:usize,saving:f64,exact:bool}
-fn plan(c:&Builder,r:usize,fw:usize)->Option<Plan>{
+struct Plan {bounds:Vec<(usize,usize)>,prefix:usize,bits:usize,saving:f64,exact:bool,dropped:bool}
+fn plan(c:&Builder,r:usize,fw:usize,drop:bool)->Option<Plan>{
  let base_bits=super::super::optional_env::<usize>("PP_PREBIAS_RETAIN_BITS")?;
  let bits=if env_flag("PP_SPRINT_MIXED") && (370..=402).contains(&r) {29}else{base_bits};
  assert!(bits>=12&&bits<=fw&&fw>=36&&!split_fold());
  let room=walk_max_qubits().saturating_sub(c.active_qubits()as usize);
  let loans=REPLAY_SIGN_LOANS.with(|s|s.get());
- let old_bounds=composition_bounds(c,r,false)?;
- let bounds=retained_rebalance(c,&old_bounds,r,false);
+ let Some(old_bounds)=composition_bounds(c,r,false) else {if !drop{drop_trace(r,false,"nocomp",String::new());}return None;};
+ let (bounds,db)=if drop{drop_exact_lead(c,&old_bounds,r,false,fw)?}else{(retained_rebalance(c,&old_bounds,r,false),0.0)};
  if bounds.len()<2{return None;}
  let &(lo,hi)=bounds.last()?;let(plo,phi)=bounds[bounds.len()-2];let(k,seed)=boundary_repair_spec(r,false,plo,phi);
- if lo<fw||phi-k-usize::from(seed)<fw{return None;}
+ if lo<fw||phi-k-usize::from(seed)<fw{drop_trace(r,false,"lofw",format!("drop={} fw={} {:?}",drop,fw,bounds));return None;}
  let need=(bits-3).max(fw-34);
  let existing=room as isize-(hi-lo)as isize-3;
  let missing=(need as isize-existing).max(0)as usize;
- let prefix=if missing==0{0}else{missing+1};if prefix+1>=hi-lo{return None;}
+ let prefix=if missing==0{0}else{missing+1};if prefix+1>=hi-lo{drop_trace(r,false,"prefix",format!("drop={} fw={} missing={} {:?}",drop,fw,missing,bounds));return None;}
  let mut fk=flag_compare(r)+usize::from(policy_width(r)>=flag_widen_div());
  if env_flag("CMP_SEED_ALL"){fk-=1;}else{fk=refined_unseeded_width(fk,N,"PP_REFINE_UNSEEDED_F");}
- let saving=(fk-1)as f64/2.0-missing as f64/2.0-(bits as f64-33.0);
- if saving<=0.0{return None;}
+ let saving=(fk-1)as f64/2.0-missing as f64/2.0-(bits as f64-33.0)-db;
+ if saving<=0.0{drop_trace(r,false,"saving",format!("drop={} fw={} fk={} missing={} db={} {:?}",drop,fw,fk,missing,db,bounds));return None;}
  // Bound released carry wires, retaining the original outer B comparisons.
  let limit=super::super::optional_env::<usize>("PP_RETAIN_EXACT_EXTRA_DIV").unwrap_or(0);
  let exact_missing=((fw-3) as isize-existing).max(0) as usize;
  let exact_prefix=if exact_missing==0{0}else{exact_missing+1};
- let exact=env_flag("PP_RETAIN_EXACT_DIV") && exact_missing<=limit && exact_prefix+1<hi-lo;
+ let exact=(env_flag("PP_RETAIN_EXACT_DIV") && exact_missing<=limit || drop_exact_lead_exact(drop,exact_missing)) && exact_prefix+1<hi-lo;
  let prefix=if exact{exact_prefix}else{prefix};
  let saving=if exact{saving-(exact_missing-missing) as f64/2.0-1.0}else{saving};
- Some(Plan{bounds,prefix,bits,saving,exact})
+ if !drop_exact_lead_minsave(drop,saving){return None;}
+ Some(Plan{bounds,prefix,bits,saving,exact,dropped:drop})
 }
 
 /// J0=488*plus+977*twice-489*minus; high word adds k.
@@ -51,7 +52,8 @@ fn split_half(c:&mut Builder,b:&[QubitId],p:QubitId,s:QubitId,o:QubitId,bits:usi
 }
 
 pub(super)fn try_replay(c:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw:usize,r:usize)->bool{
- let Some(p)=plan(c,r,fw)else{return false;};
+ let Some(p)=plan(c,r,fw,false).or_else(||plan(c,r,fw,true))else{return false;};
+ if p.dropped{eprintln!("DROP_EXACT_LEAD mul=0 r={} base={} saving={} bounds={:?}",r,c.active_qubits(),p.saving,p.bounds);}
  eprintln!("RETAINED_PREBIAS {} {} {} {} {} {}",r,c.active_qubits(),fw,p.bits,p.prefix,p.saving);
  if env_flag("PP_COMPOSE_TRACE"){eprintln!("COMPOSE_RETAIN {} {} {} {} {} {:?}",r,c.active_qubits(),fw,p.bits,REPLAY_SIGN_LOANS.with(|s|s.get()),p.bounds);}
  if p.exact {eprintln!("EXACT_RETAINED_FOLD div {} {}",r,fw);}
@@ -72,10 +74,11 @@ pub(super)fn try_replay(c:&mut Builder,sign:QubitId,a:&[QubitId],b:&[QubitId],fw
   }else{ripple_add(c,&a[at..hi],&b[at..hi],cin,Some(out));}
   if j==0{joint_prebias::erase_initial(c,initial,a[0],sign,b[0]);}
   if let Some((carry,plo,phi))=previous{
-   let(k,seed)=boundary_repair_spec(r,false,plo,phi);
+   let(k,seed)=if p.dropped&&plo==0{drop_lead_first_compare(r,false,phi)}else{boundary_repair_spec(r,false,plo,phi)};
    let full=plo==0&&phi==k;
    let guard=super::super::optional_env::<usize>("I12_B_GUARD").unwrap_or(0);
-   let protected=(589..=620).contains(&r)||(642..=645).contains(&r)||(647..=648).contains(&r);
+   let protected=((589..=620).contains(&r)||(642..=645).contains(&r)||(647..=648).contains(&r))
+    &&!(p.dropped&&env_flag("PP_DROP_EXACT_LEAD_NOGUARD"));
    let width=if protected&&!full {(k+guard).min(phi-plo)}else{k};
    c.record_replay_site('B',r,phi,width);
    if full{c.cx(b[0],sign);}
```

