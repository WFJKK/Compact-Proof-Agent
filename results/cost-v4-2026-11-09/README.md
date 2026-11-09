# The repository's results under cost-v4 (9 November 2026)

Cost-v4 stops charging a proof file's plan: its tree, the plan entries of read and the symmetry count
([docs/COST_MODEL.md](../../docs/COST_MODEL.md), [the decision](../../docs/decisions/same-proof-same-cost.md)).
Every other charge is the same as in cost-v3, so the same proof now costs the same in both lanes. This folder
holds the results of this repository that were measured under cost-v3 (or cost-v2, which gives the same
lengths for them), measured again under cost-v4 by [`remeasure.py`](remeasure.py). The originals are not
touched.

How each kind of number was re-measured:

- **Proof files with their length by category and no approximation.** Shorter by exactly their read, tree
  and symmetry charges, since without an approximation all of cost-v3's read was plan. Where a fresh check
  is cheap the proofs were also built and checked again, and the two agree: the tiny attention networks'
  hand proofs and brute force, and the open-lane pilot's brute force.
- **The max2 reference proofs.** Checked again (the checked baselines of
  [max2-2026-10-13](../max2-2026-10-13/README.md)); every count is the same as before.
- **Lengths that never charged a plan.** Unchanged: the open lane's (bill, E and the certificate) and Gross et
  al.'s proofs (counted by walking their loops).
- **Metrics.** Computed again from those lengths with `core.scoring` and cost-v4's E and B (the zoo
  manifests), as the original scripts computed them, with Q_exact added where it was missing.

## B under the two versions

E does not change. B is now E plus one forward pass per input, so it loses the brute-force file's tree.

| Model | Setting | E | B, cost-v3 | B, cost-v4 |
| --- | --- | --- | --- | --- |
| tests/max2_tiny | v8 | 80 | 4,323 | 4,112 |
| tests/attn_max2_tiny, attn_min2_tiny | v8d4 | 136 | 12,571 | 12,360 |
| tests/attn_max4_tiny, attn_min4_tiny | v4d4 | 112 | 74,523 | 73,584 |
| models/max2 | v64 | 1,088 | 2,696,387 | 2,683,968 |
| models/max2 | v128 | 4,352 | 40,407,555 | 40,358,144 |
| models/attn-max2, attn-min2 | v64 | 8,256 | 35,553,475 | 35,541,056 |
| models/attn-max2, attn-min2 | v128 | 12,352 | 176,795,971 | 176,746,560 |
| models/attn-max4, attn-min4 | v16 | 544 | 65,152,067 | 64,946,720 |
| models/attn-max4, attn-min4 | v24 | 1,200 | 684,152,163 | 683,127,984 |
| models/attn-max4 | v64 | 8,320 | 220,822,257,923 | 220,771,393,664 |
| models/xorformer-majority | n12h1d8 | 465 | 9,363,920 | 9,343,441 |

## What moved

**The open-lane pilot** ([open-lane-pilot-tiny-3](../open-lane-pilot-tiny-3/report.md);
[archive and rescore here](open-lane-pilot-tiny-3/)). Only round 0's brute force was a proof file
(4,323 to 4,112); the agent's proofs are open-lane proofs and keep their lengths. After round 4:

| Metric | cost-v3 | cost-v4 |
| --- | --- | --- |
| Q_exact | 0.5101 | 0.5039 |
| Q_above | 0.3634 | 0.3634 |
| Q_grid | 0.5375 | 0.4188 |

Q_above does not move: the brute-force line certifies every input from 4,112 on, so between the two Bs there
is no room above it. Q_grid falls because the agent tuned its proofs to land just under cost-v3's budgets
(536 under 540, 269 under 270), and cost-v4's grid (2,056, 1,028, 514, 257, 128) puts them over. That is the
budget-boundary effect of the pilot-2 note, not a change in the proofs.

**The hand proofs on the tiny attention networks** ([attn-tiny-reference.json](attn-tiny-reference.json)):

| Network | Peeling, full proof | Q_exact | Gross et al.'s cubic | Its Q_exact |
| --- | --- | --- | --- | --- |
| attn_max2_tiny-v8d4-s1 | 7,384 to 7,217 | 0.2496 to 0.2576 | 12,436 | 0.0024 to 0 |
| attn_min2_tiny-v8d4-s1 | 7,156 to 6,989 | 0.2560 to 0.2643 | 12,436 | 0.0024 to 0 |
| attn_max4_tiny-v4d4-s0 | 7,288 to 7,183 | 0.4570 to 0.4609 | 5,486 | 0.4013 to 0.4002 |
| attn_min4_tiny-v4d4-s0 | 7,596 to 7,491 | 0.4580 to 0.4620 | 5,486 | 0.4013 to 0.4002 |

On the two-position networks the cubic proof (12,436) is now longer than brute force (12,360). So an
open-lane proof beats the hand proofs if its full proof is shorter than the best one above (6,989 to 7,217
on two positions, 5,486 on four) and its Q_exact is above about 0.26 or 0.46.

**max2** ([max2-reference-proofs.json](max2-reference-proofs.json); medians over the six development
networks):

| Proof | v64 | v128 |
| --- | --- | --- |
| Symmetry | 1,372,250 to 1,363,488 | 20,372,796 to 20,338,880 |
| The cubic proof (contraction, interval leaves) | 312,264 to 311,682 | 2,446,083 to 2,444,929 |
| Its Q with the budget knob | 0.3229 to 0.3228 | 0.3473 to 0.3472 |

Under cost-v4 the symmetric proof costs the same on every network (1,363,488 on v64): cost-v3 also charged
each accepted leaf, so its length depended on how many leaves passed.

**The attention zoo** (54 networks over the files): the measured hand proofs
([convex-rule](../convex-rule-2026-10-19/README.md) and [query-gap](../query-gap-2026-10-19/README.md),
`*_measure_*.json` here) lose 0.06 to 1.4 percent of their full length (on attn-max4 v16 the median
query-gap proof goes from 141,725 to 140,506), Q rises by at most 0.0021, and Q_grid moves on 3 of the 54
networks, by at most 0.0093. Gross et al.'s proofs (`gross-cubic_*.json`) keep their lengths; their Q and
Q_grid move by at most 0.00015, and their cost of finishing by B's change, at most 0.3 percent.

## Runs kept elsewhere

The archives of the agent's runs are not in the repository: the max2 reruns ([max2-rerun-q](../max2-rerun-q/report.md),
[max2-rerun-cof](../max2-rerun-cof/report.md)), the attention runs of
[frontiers-2026-10-19](../frontiers-2026-10-19/README.md) and RESULTS.md, and the run behind
`max2-2026-10-13/reference_grid.json`. Each is re-measured where it lives:

    python -m core.remeasure --run ~/auto-research-compact-proof-runs/<run_id>

It checks every archived proof again under cost-v4, writes `<run_id>-remeasured-cost-v4` next to the run
(the run is never changed) and prints the per-round medians. Lengths only fall, by each proof's plan; counts do
not change, and the command says so if one does.
