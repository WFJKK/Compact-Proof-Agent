#!/usr/bin/env python3
"""The results in this repository that were measured under cost-v3, measured again under cost-v4.

    python -B results/cost-v4-2026-11-09/remeasure.py [--skip-max2]

Writes new files next to this script and never touches the originals. cost-v4 (9 November 2026) stops
charging a proof file's plan: the tree, the plan entries of read and the symmetry count. Every other charge
is unchanged, so:

- A proof file whose record has its length by category and no approximation is shorter by exactly its
  read, tree and symmetry charges (without an approximation, all of cost-v3's read was plan). Where a fresh
  check is cheap (the tiny attention networks) the proofs are also built and checked again, and the two
  must agree.
- Lengths that never charged a plan stay as they are: the open lane's (bill + E + certificate), and
  Gross et al.'s proofs, whose lengths were counted by walking their loops.
- The metrics are computed again from those lengths with core.scoring and cost-v4's E and B (the zoo
  manifests), the way the original scripts computed them, with Q_exact added where it was missing.
- The max2 reference proofs (results/max2-2026-10-13) are checked again: their checked baselines, under
  cost-v4 (84 checks, a few minutes). Their estimated strategies keep their formulas, whose base now has no
  plan charges. --skip-max2 leaves this part out. The whole script takes about a quarter of an hour on two
  cores, most of it the metrics of the v64 attention networks (millions of breakpoints of the brute-force
  line).

Runs whose archives live outside the repository (the max2 reruns, the attention runs of
results/frontiers-2026-10-19) are re-measured where they live, with `python -m core.remeasure --run <run>`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = REPO / "results"
sys.path.insert(0, str(REPO))

from core.check.cost import VERSION as COST_VERSION  # noqa: E402
from core.model_folder import load_model_folder  # noqa: E402
from core.scoring import network_metrics  # noqa: E402
from core.zoo import networks  # noqa: E402

PLAN = ("read", "tree", "symmetry")  # what cost-v3 charged for a proof file's plan
METRICS = ("Q", "Q_exact", "Q_grid", "cost_of_finishing", "shortest_full")
_ENTRIES: dict = {}


def entry(model: str, nid: str) -> dict:
    """The network's zoo entry under the current manifests (cost-v4's E and B)."""
    if model not in _ENTRIES:
        _ENTRIES[model] = {e["id"]: e for e in networks(load_model_folder(REPO / model), None)}
    e = _ENTRIES[model][nid]
    assert e["cost_model"] == COST_VERSION, f"{nid}: the manifest is under {e['cost_model']}"
    return e


def model_of(nid: str) -> str:
    return "models/" + nid.rsplit("-", 2)[0] if not nid.split("-")[0].endswith("_tiny") else "tests/" + nid.split("-")[0]


def without_plan(point: dict) -> dict:
    """A cost-v3 record of a proof file under cost-v4: its plan charges taken out (exact without an approximation)."""
    by = dict(point["length_by_rule"])
    if by.get("approximate"):
        raise ValueError("a proof with an approximation: its read was not all plan, so check the proof file again instead")
    plan = sum(by.pop(k, 0) for k in PLAN)
    return {**point, "length": point["length"] - plan, "length_by_rule": by, "length_cost_v3": point["length"]}


def metrics(points: list[dict], e: dict, records=None) -> dict:
    """core.scoring on the points plus brute force at B with the network's true count, as the scripts did."""
    pts = [{"length": p["length"], "certified": p["certified"], "n_inputs": e["n_inputs"]} for p in points]
    pts.append({"length": e["B"], "certified": e["real_correct"], "n_inputs": e["n_inputs"]})
    m = network_metrics(pts, e, records=records)
    return {k: m[k] for k in METRICS}


def write(name: str, data) -> None:
    path = HERE / name
    path.write_text(json.dumps(data, indent=1) + "\n")
    print("written", path.relative_to(REPO), flush=True)


# The hand proofs on the tiny attention networks (results/attn-tiny-reference-2026-10-23) ---------------------


def attn_tiny_reference() -> dict:
    sys.path.insert(0, str(RESULTS / "attn-tiny-reference-2026-10-23"))
    sys.path.insert(0, str(RESULTS / "convex-rule-2026-10-19"))
    import run as tiny  # the original script: its proofs are built and checked again here
    from core.check.plugins import use_candidate

    rule = use_candidate(REPO / "rules" / "token_convex")
    old = json.loads((RESULTS / "attn-tiny-reference-2026-10-23" / "results.json").read_text())
    out = {}
    for nid, row in old.items():
        e = entry(row["model"], nid)
        folder = load_model_folder(REPO / row["model"])
        brute, record = tiny.brute_force(folder, e)  # checked again under cost-v4
        assert brute["legacy_length"] == without_plan({"length": row["brute_force"]["legacy_length"],
                                                      "length_by_rule": row["brute_force"]["legacy_by_rule"]})["length"]
        assert brute["legacy_length"] == brute["open_lane_length"] == e["B"], "brute force costs the same in both lanes"
        fresh = tiny.peeling(folder, e, rule, record)  # built and checked again under cost-v4
        moved = [without_plan(p) for p in row["peeling"]["points"]]
        for a, b in zip(fresh["points"], moved):
            assert (a["length"], a["certified"], a["length_by_rule"]) == (b["length"], b["certified"], b["length_by_rule"]), (nid, a, b)
        peel = {**fresh, "points": [{**p, "length_cost_v3": q["length"]} for p, q in zip(fresh["points"], row["peeling"]["points"])],
                "full_length_cost_v3": row["peeling"]["full_length"], "Q_exact_cost_v3": row["peeling"]["Q_exact"]}
        new = {**row, "E": e["E"], "B": e["B"], "B_cost_v3": row["B"],
               "brute_force": {**brute, "legacy_length_cost_v3": row["brute_force"]["legacy_length"]}, "peeling": peel}
        if "cubic" in row:  # their proof's length never charged a plan; only B moves
            c = row["cubic"]
            new["cubic"] = {"length": c["length"], "certified": c["certified"],
                            **tiny.metrics([{"length": c["length"], "certified": c["certified"], "n_inputs": e["n_inputs"]}], e, record),
                            "Q_exact_cost_v3": c["Q_exact"]}
        out[nid] = new
        print(f"{nid}: B {row['B']:,} -> {e['B']:,}; peeling full {row['peeling']['full_length']:,} -> {peel['full_length']:,}, "
              f"Q_exact {row['peeling']['Q_exact']:.4f} -> {peel['Q_exact']:.4f}", flush=True)
    write("attn-tiny-reference.json", {"cost_model": COST_VERSION, "source": "results/attn-tiny-reference-2026-10-23/results.json",
                                       "networks": out})
    return out


# The measured attention proofs (results/convex-rule-2026-10-19, results/query-gap-2026-10-19) ----------------


def measured(folder_name: str) -> dict:
    out = {}
    for src in sorted((RESULTS / folder_name).glob("measure_*.json")):
        old = json.loads(src.read_text())
        new = {}
        for nid, row in old.items():
            e = entry(model_of(nid), nid)
            points = [without_plan(p) for p in row["points"]]
            full = points[-1]
            r = {**row, "points": points, **metrics(points, e), "B": e["B"], "E": e["E"], "real_correct": e["real_correct"],
                 "B_cost_v3": row["B"], "Q_cost_v3": row["Q"], "Q_grid_cost_v3": row["Q_grid"],
                 "shortest_full_cost_v3": row["shortest_full"]}
            if "full_B_over_length" in row:
                r["full_B_over_length"] = e["B"] / full["length"]
            if "full_share_of_correct" in row:
                r["full_share_of_correct"] = full["certified"] / e["real_correct"]
            new[nid] = r
        name = f"{folder_name.rsplit('-', 3)[0]}_{src.name}"
        write(name, {"cost_model": COST_VERSION, "source": f"results/{folder_name}/{src.name}", "networks": new})
        out[name] = new
    return out


# Gross et al.'s proofs on the attention zoos (results/gross-cubic-2026-10-16): lengths unchanged, B moves ----


def gross() -> dict:
    out = {}
    src_dir = RESULTS / "gross-cubic-2026-10-16"
    for src in sorted(src_dir.glob("all_proofs_*.json")):
        old = json.loads(src.read_text())
        new = {}
        for nid, net in old.items():
            e = entry(model_of(nid), nid)
            pts = [p for p in net["proofs"] if p.get("certified", 0) > 0]
            pts.append({"length": e["B"], "certified": e["real_correct"]})
            frontier, best = [], -1
            for p in sorted(pts, key=lambda p: (p["length"], -p["certified"])):
                if p["certified"] > best:
                    frontier.append({"length": p["length"], "certified": p["certified"], "n_inputs": e["n_inputs"]})
                    best = p["certified"]
            m = network_metrics(frontier, e)
            new[nid] = {"B": e["B"], "B_cost_v3": net["scores"]["frontier"][-1]["length"],
                        "scores": {k: m[k] for k in ("Q", "Q_exact", "Q_grid", "cost_of_finishing")} | {"frontier": frontier},
                        "scores_cost_v3": {k: net["scores"][k] for k in ("Q", "Q_grid", "cost_of_finishing")}}
        write(f"gross-cubic_{src.name}", {"cost_model": COST_VERSION, "source": f"results/gross-cubic-2026-10-16/{src.name}",
                                          "note": "the proofs' lengths are unchanged (counted by walking their loops, with no plan); "
                                                  "only B, the last frontier point and the scores move", "networks": new})
        out[src.name] = new
    for src in sorted(src_dir.glob("cubic_results*.json")):
        old = json.loads(src.read_text())
        new = {}
        for nid, r in old.items():
            e = entry(model_of(nid), nid)
            points = [{"length": r["length"], "certified": r["certified"], "n_inputs": r["n_inputs"]}]
            if e["real_correct"] > r["certified"]:
                points.append({"length": e["B"], "certified": e["real_correct"], "n_inputs": r["n_inputs"]})
            m = network_metrics(points, e)
            new[nid] = {**r, "B": e["B"], "E": e["E"], "B_over_length": e["B"] / r["length"], "Q": m["Q"], "Q_exact": m["Q_exact"],
                        "Q_grid": m["Q_grid"], "cost_of_finishing": m["cost_of_finishing"], "B_cost_v3": r["B"], "Q_cost_v3": r["Q"]}
        write(f"gross-cubic_{src.name}", {"cost_model": COST_VERSION, "source": f"results/gross-cubic-2026-10-16/{src.name}",
                                          "networks": new})
        out[src.name] = new
    return out


# The open-lane pilot on the tiny max-of-2 network (results/open-lane-pilot-tiny-3) ----------------------------


def open_lane_pilot() -> dict:
    """The archive with its proof-file records (round 0's brute force) under cost-v4, in core.remeasure's record
    format, and core.rescore on it. Open-lane records are kept as archived: their lengths never charged a plan."""
    from core.check.checker import brute_force_proof, check_proof
    from core.rescore import rescore

    src = RESULTS / "open-lane-pilot-tiny-3"
    dst = HERE / "open-lane-pilot-tiny-3"
    dst.mkdir(exist_ok=True)
    folder = load_model_folder(REPO / "tests" / "max2_tiny")
    lines = []
    for line in (src / "archive.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("lane") != "open" and r.get("status") == "ok":
            moved = without_plan(r)
            fresh = check_proof(brute_force_proof(folder, r["network"]), folder, r["network"])  # round 0 was brute force
            assert (fresh["length"], fresh["certified"], fresh["length_by_rule"]) == (moved["length"], r["certified"], moved["length_by_rule"])
            r.update(length=moved["length"], length_by_rule=moved["length_by_rule"], length_archived=moved["length_cost_v3"],
                     cost_model_archived=(r.get("versions") or {}).get("cost_model"), cost_model=COST_VERSION)
        lines.append(json.dumps(r))
    (dst / "archive.jsonl").write_text("".join(x + "\n" for x in lines))
    for name in ("config.yaml", "versions.json"):
        (dst / name).write_bytes((src / name).read_bytes())
    result = rescore(dst)
    write("open-lane-pilot-tiny-3/rescore.json", result)
    return result


# The max2 reference proofs (results/max2-2026-10-13): the checked baselines, checked again ------------------


def max2_reference() -> dict:
    sys.path.insert(0, str(RESULTS / "max2-2026-10-13"))
    import reference_proofs as ref  # the original script's recipes and estimates; its main() writes next to itself
    from core.scoring import cost_of_finishing, q_exact, q_score
    from core.zoo import load_weights

    old = json.loads((RESULTS / "max2-2026-10-13" / "reference_proofs.json").read_text())
    sym, cub, knob = ref.recipe("02_symmetry"), ref.recipe("03_contract_interval"), ref.recipe("04_contract_interval_budget")
    per_net = {}
    for e in ref.DEV:
        e = entry("models/max2", e["id"])
        nid, E, B, real = e["id"], e["E"], e["B"], e["real_correct"]
        w = load_weights(ref.FOLDER, nid)
        V = w["embedding.weight"].shape[1]
        n = V * V
        r = {"setting": e["setting"], "V": V, "E": E, "B": B, "real_correct": real, "n_inputs": n}
        r["brute_force"] = {"length": B, "certified": real}
        r["symmetry"] = ref.checked(sym, nid, w, V, 1.0)
        r["cubic"] = ref.checked(cub, nid, w, V, 1.0)
        r["cubic_knob"] = [dict(knob=k, **ref.checked(knob, nid, w, V, k)) for k in ref.KNOBS]
        lb = r["cubic"]["length_by_rule"]
        base = lb["extract"] + sum(lb.get(k, 0) for k in PLAN) + lb["contract"] + 200  # the plan terms are 0 now
        r.update(ref.estimates(w, V, base))
        r["hybrid"]["certified"] = real
        P = lambda d: ref.pt(d["length"], d["certified"], n)  # noqa: E731
        sets = {
            "brute_force": [P(r["brute_force"])],
            "symmetry": [P(r["symmetry"])],
            "cubic": [P(r["cubic"])],
            "cubic_knob": [P(d) for d in r["cubic_knob"]],
            "convexity_loss": [P(r["convexity_loss"])],
            "convexity_accuracy": [P(r["convexity_accuracy"])],
            "convexity_accuracy+cubic": [P(r["convexity_accuracy"]), P(r["cubic"])],
            "hybrid": [P(r["hybrid"])],
            "convexity_accuracy+hybrid": [P(r["convexity_accuracy"]), P(r["hybrid"])],
        }
        r["scores"] = {}
        for name, pts in sets.items():
            pts = sorted(pts, key=lambda p: p["length"])
            frontier, best = [], -1
            for p in pts:
                if p["certified"] > best and p["certified"] > 0:
                    frontier.append(p)
                    best = p["certified"]
            r["scores"][name] = {"Q": q_score(frontier, E, B), "Q_exact": q_exact(frontier, E, B),
                                 "cost_of_finishing": cost_of_finishing(frontier, real, B)}
        for d in [r["symmetry"], r["cubic"], *r["cubic_knob"]]:
            d.pop("length_by_rule", None)
        o = old["networks"][nid]
        r["cost_v3"] = {"B": o["B"], "symmetry": o["symmetry"]["length"], "cubic": o["cubic"]["length"],
                        "cubic_knob": [d["length"] for d in o["cubic_knob"]]}
        assert [d["certified"] for d in r["cubic_knob"]] == [d["certified"] for d in o["cubic_knob"]], f"{nid}: a count changed"
        assert r["cubic"]["certified"] == o["cubic"]["certified"] and r["symmetry"]["certified"] == o["symmetry"]["certified"]
        per_net[nid] = r
        print(f"{nid}: B {o['B']:,} -> {B:,}; symmetry {o['symmetry']['length']:,} -> {r['symmetry']['length']:,}; "
              f"cubic {o['cubic']['length']:,} -> {r['cubic']['length']:,}", flush=True)
    medians = {}
    for st in sorted({r["setting"] for r in per_net.values()}):
        rs = [r for r in per_net.values() if r["setting"] == st]
        med = statistics.median
        m = {"networks": len(rs)}
        for name in ("brute_force", "symmetry", "cubic", "convexity_loss", "convexity_accuracy", "hybrid"):
            m[name] = {"length": med(r[name]["length"] for r in rs), "accuracy": med(r[name]["certified"] / r["n_inputs"] for r in rs)}
        m["cubic_knob"] = [{"knob": k, "length": med(r["cubic_knob"][i]["length"] for r in rs),
                            "accuracy": med(r["cubic_knob"][i]["certified"] / r["n_inputs"] for r in rs)} for i, k in enumerate(ref.KNOBS)]
        m["scores"] = {name: {s: med(r["scores"][name][s] for r in rs) for s in ("Q", "Q_exact", "cost_of_finishing")}
                       for name in rs[0]["scores"]}
        medians[st] = m
    out = {"cost_model": COST_VERSION, "source": "results/max2-2026-10-13/reference_proofs.json (cost-v2, the same lengths as cost-v3)",
           "checked": old["checked"], "estimated": old["estimated"], "medians": medians, "networks": per_net}
    write("max2-reference-proofs.json", out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-max2", action="store_true", help="leave out the max2 reference proofs (the slow part)")
    args = ap.parse_args()
    if COST_VERSION != "cost-v4":
        raise SystemExit(f"this re-measures under cost-v4, but the checker is {COST_VERSION}")
    attn_tiny_reference()
    measured("convex-rule-2026-10-19")
    measured("query-gap-2026-10-19")
    gross()
    open_lane_pilot()
    if not args.skip_max2:
        max2_reference()


if __name__ == "__main__":
    main()
