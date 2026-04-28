import json
import re
import time
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB
import pandas as pd


# ---------------------------------------------------------------------------
# Egyedi fájl megoldása – visszaad egy eredmény-dict-et a summary táblához
#
# Időkorlátok:
#   cycle_time_limit  – ennyi másodpercig keres 3-as köröket (default: 60s)
#   gurobi_time_limit – ennyi másodpercig optimalizál a Gurobi (default: 60s)
# ---------------------------------------------------------------------------
def solve_kep(
    alt,
    size,
    run,
    K=3,
    instance_dir="./KEP_Survey_Experimentation_Instances",
    cycle_time_limit=60,
    gurobi_time_limit=60,
):
    alt_str = f"{alt:.2f}"
    file_name = (
        Path(instance_dir)
        / f"uk_2019_splitpra_bandxmatch_pra0_pdd_{alt_str}_{size}_{run}.json"
    )

    try:
        with open(file_name, "r") as f:
            content = json.load(f)
    except FileNotFoundError:
        print(f"Error: {file_name} file not found.")
        return None

    data = content["data"]

    # Csak azokat a donorokat tartjuk meg, akik NEM altruisták (van source-uk)
    nodes = [
        node_id
        for node_id, d in data.items()
        if "sources" in d and len(d["sources"]) > 0
    ]

    # Élek (donor -> recipient) és súlyok kigyűjtése
    edges = {}
    for donor_id in nodes:
        if "matches" in data[donor_id]:
            for match in data[donor_id]["matches"]:
                rec_id = str(match["recipient"])
                if rec_id in nodes:
                    edges[(donor_id, rec_id)] = match["score"]

    # ------------------------------------------------------------------
    # KÖRKERESÉS (K=2 és K=3) – 3-as köröknél időkorlát
    # ------------------------------------------------------------------
    cycles = []
    cycle_search_timed_out = False

    # 2-es körök: A -> B -> A
    for i, u in enumerate(nodes):
        for v in nodes[i + 1:]:
            if (u, v) in edges and (v, u) in edges:
                weight = edges[(u, v)] + edges[(v, u)]
                cycles.append({"nodes": [u, v], "weight": weight, "length": 2})

    # 3-as körök: A -> B -> C -> A (időkorláttal)
    if K >= 3:
        t0 = time.time()
        search_done = False
        for i, u in enumerate(nodes):
            if search_done:
                break
            for j, v in enumerate(nodes):
                if search_done:
                    break
                if i == j:
                    continue
                for k, w in enumerate(nodes):
                    if k <= i or k <= j:
                        continue
                    if time.time() - t0 > cycle_time_limit:
                        cycle_search_timed_out = True
                        search_done = True
                        break
                    perms = [(u, v, w), (u, w, v)]
                    for p1, p2, p3 in perms:
                        if (
                            (p1, p2) in edges
                            and (p2, p3) in edges
                            and (p3, p1) in edges
                        ):
                            weight = (
                                edges[(p1, p2)]
                                + edges[(p2, p3)]
                                + edges[(p3, p1)]
                            )
                            cycles.append(
                                {"nodes": [p1, p2, p3], "weight": weight, "length": 3}
                            )

        if cycle_search_timed_out:
            print(
                f" [!] 3-cycle search timed out after {cycle_time_limit}s "
                f"— partial results used."
            )

    # --- ÖSSZES KÖR MEGJELENÍTÉSE ---
    num_cycles_2 = sum(1 for c in cycles if c["length"] == 2)
    num_cycles_3 = sum(1 for c in cycles if c["length"] == 3)
    print("\n" + "=" * 60)
    print(f" ALL POSSIBLE CYCLES ({len(cycles)})  [2-cycles: {num_cycles_2}, 3-cycles: {num_cycles_3}]")
    print("=" * 60)
    for idx, c in enumerate(cycles):
        nodes_path = " -> ".join(c["nodes"]) + " -> " + c["nodes"][0]
        print(
            f" #{idx+1:2} | Length: {c['length']} | Weight: {c['weight']:4} | Path: {nodes_path}"
        )

    # ------------------------------------------------------------------
    # OPTIMALIZÁLÁS (Gurobi) – időkorláttal
    # ------------------------------------------------------------------
    model = gp.Model("KidneyExchange_CyclesOnly")
    model.Params.OutputFlag = 0
    model.Params.TimeLimit = gurobi_time_limit  # másodpercben

    x = model.addVars(len(cycles), vtype=GRB.BINARY, name="c")
    model.setObjective(
        gp.quicksum(x[i] * cycles[i]["weight"] for i in range(len(cycles))),
        GRB.MAXIMIZE,
    )

    for node in nodes:
        model.addConstr(
            gp.quicksum(
                x[i] for i in range(len(cycles)) if node in cycles[i]["nodes"]
            )
            <= 1
        )

    model.optimize()

    # ------------------------------------------------------------------
    # EREDMÉNYEK
    # ------------------------------------------------------------------
    used_nodes = set()

    if model.status == GRB.OPTIMAL:
        status_str = "optimal"
    elif model.status == GRB.TIME_LIMIT and model.SolCount > 0:
        status_str = "time_limit_feasible"
    elif cycle_search_timed_out:
        status_str = "cycle_search_timeout"
    else:
        status_str = "no_solution"

    result = {
        "alt": alt,
        "size": size,
        "run": run,
        "K": K,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "candidate_cycles_2": num_cycles_2,
        "candidate_cycles_3": num_cycles_3,
        "candidate_cycles_total": len(cycles),
        "selected_cycles_2": 0,
        "selected_cycles_3": 0,
        "selected_cycles_total": 0,
        "covered_nodes": 0,
        "uncovered_nodes": 0,
        "objective_value": None,
        "cycle_search_timed_out": cycle_search_timed_out,
        "status": status_str,
    }

    if model.status in (GRB.OPTIMAL, GRB.TIME_LIMIT) and model.SolCount > 0:
        print("\n" + "=" * 60)
        print(" CHOSEN CYCLES")
        print(f"FILE: {file_name}")
        if status_str == "time_limit_feasible":
            print(" [!] Gurobi time limit reached — solution may not be optimal.")
        print("=" * 60)

        sel2 = sel3 = 0
        for i in range(len(cycles)):
            if x[i].X > 0.5:
                used_nodes.update(cycles[i]["nodes"])
                nodes_path = (
                    " -> ".join(cycles[i]["nodes"]) + " -> " + cycles[i]["nodes"][0]
                )
                print(f" Cycle: {nodes_path} | Weight: {cycles[i]['weight']}")
                if cycles[i]["length"] == 2:
                    sel2 += 1
                else:
                    sel3 += 1

        remaining_nodes = [n for n in nodes if n not in used_nodes]

        print("-" * 60)
        print(f" OBJ VALUE:             {model.ObjVal}")
        print(f" Selected cycles (2):   {sel2}")
        print(f" Selected cycles (3):   {sel3}")
        print(f" Selected cycles total: {sel2 + sel3}")
        print(f" Covered nodes:         {len(used_nodes)} / {len(nodes)}")

        print("\n" + "=" * 60)
        print(
            f" UNUSED NODES AND THEIR INTERNAL CONNECTIONS ({len(remaining_nodes)} nodes)"
        )
        print("=" * 60)
        found_connection = False
        for u in remaining_nodes:
            for v in remaining_nodes:
                if (u, v) in edges:
                    found_connection = True
                    print(f" Connection: {u} -> {v} (Weight: {edges[(u, v)]})")
        if not found_connection:
            print(" No connections found between unused nodes.")
        else:
            print("\n (Note: If no cycles appear here, the model is working perfectly.)")

        result.update(
            {
                "selected_cycles_2": sel2,
                "selected_cycles_3": sel3,
                "selected_cycles_total": sel2 + sel3,
                "covered_nodes": len(used_nodes),
                "uncovered_nodes": len(remaining_nodes),
                "objective_value": model.ObjVal,
            }
        )
    else:
        print(" No feasible solution found within time limit.")

    print("-" * 60)
    print(f"Parameters: alt={alt}, size={size}, run={run}, K={K}")
    print("=" * 60 + "\n")

    return result


# ---------------------------------------------------------------------------
# Batch futtatás: az összes illeszkedő JSON fájl automatikus feldolgozása
#
# Újítások:
#   - Checkpoint: a már feldolgozott (alt, size, run) hármasokat átugorja,
#     így megszakítás (Ctrl+C) után folytatható a futás.
#   - Menet közbeni mentés: minden fájl után frissíti a CSV-t.
#   - cycle_time_limit / gurobi_time_limit átadható.
# ---------------------------------------------------------------------------
def run_all(
    instance_dir="./KEP_Survey_Experimentation_Instances",
    K=3,
    output_csv="kep_summary.csv",
    cycle_time_limit=60,
    gurobi_time_limit=60,
    total_time_limit=None,  # teljes batch max. ideje másodpercben (None = korlátlan)
):
    instance_path = Path(instance_dir)
    if not instance_path.exists():
        print(f"Instance directory not found: {instance_dir}")
        return

    pattern = re.compile(
        r"uk_2019_splitpra_bandxmatch_pra0_pdd_"
        r"(?P<alt>\d+\.\d+)_"
        r"(?P<size>\d+)_"
        r"(?P<run>\d+)\.json$"
    )

    json_files = sorted(instance_path.glob("*.json"))
    matched = []
    for f in json_files:
        m = pattern.match(f.name)
        if m:
            matched.append(
                (
                    float(m.group("alt")),
                    int(m.group("size")),
                    int(m.group("run")),
                )
            )

    if not matched:
        print(f"No matching JSON files found in {instance_dir}.")
        return

    # ------------------------------------------------------------------
    # Checkpoint: betöltjük a már meglévő CSV-t (ha van)
    # ------------------------------------------------------------------
    csv_path = Path(output_csv)
    if csv_path.exists():
        existing_df = pd.read_csv(csv_path)
        done = set(
            zip(
                existing_df["alt"].astype(float),
                existing_df["size"].astype(int),
                existing_df["run"].astype(int),
            )
        )
        all_results = existing_df.to_dict("records")
        print(f"Checkpoint loaded: {len(done)} instance(s) already done, skipping them.")
    else:
        done = set()
        all_results = []

    todo = [(a, s, r) for a, s, r in matched if (a, s, r) not in done]
    print(f"Found {len(matched)} instance(s) total, {len(todo)} remaining.")
    if total_time_limit:
        print(f"Total time limit: {total_time_limit}s ({total_time_limit/3600:.1f}h)\n")
    else:
        print()

    batch_start = time.time()

    for idx, (alt, size, run) in enumerate(todo, 1):
        elapsed = time.time() - batch_start
        if total_time_limit and elapsed >= total_time_limit:
            print(f"\n[!] Total time limit reached ({elapsed:.0f}s / {total_time_limit}s). Stopping batch.")
            print(f"    Remaining {len(todo) - idx + 1} instance(s) skipped — re-run to continue (checkpoint will resume).")
            break

        remaining_budget = (total_time_limit - elapsed) if total_time_limit else None
        eff_cycle  = min(cycle_time_limit,  remaining_budget / 2) if remaining_budget else cycle_time_limit
        eff_gurobi = min(gurobi_time_limit, remaining_budget / 2) if remaining_budget else gurobi_time_limit

        print(f">>> [{idx}/{len(todo)}] Solving: alt={alt}, size={size}, run={run}  (elapsed: {elapsed:.0f}s)")
        res = solve_kep(
            alt=alt,
            size=size,
            run=run,
            K=K,
            instance_dir=instance_dir,
            cycle_time_limit=eff_cycle,
            gurobi_time_limit=eff_gurobi,
        )
        if res is not None:
            all_results.append(res)

            # Menet közbeni mentés
            df = pd.DataFrame(all_results)
            df = df.sort_values(["alt", "size", "run"]).reset_index(drop=True)
            df.to_csv(csv_path, index=False)
            print(f"    [saved] {csv_path}  ({len(all_results)} record(s) so far)")

    if not all_results:
        print("No results to summarize.")
        return

    df = pd.DataFrame(all_results)
    df = df.sort_values(["alt", "size", "run"]).reset_index(drop=True)

    print("\n" + "=" * 80)
    print(" FINAL SUMMARY TABLE")
    print("=" * 80)
    print(df.to_string(index=False))
    df.to_csv(csv_path, index=False)
    print(f"\nFinal summary saved to: {csv_path}")
    return df


# ---------------------------------------------------------------------------
# Belépési pont
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Egyedi futtatás:
    # solve_kep(alt=0.05, size=100, run=7, K=3)

    # Batch futtatás – minden illeszkedő fájlra, időkorlátokkal:
    run_all(
        instance_dir="./KEP_Survey_Experimentation_Instances",
        K=3,
        output_csv="kep_summary.csv",
        cycle_time_limit=60,   # 3-as körkeresés max. ennyi mp (fájlonként)
        gurobi_time_limit=60,  # Gurobi optimalizálás max. ennyi mp (fájlonként)
        total_time_limit=300, # teljes batch max. ideje mp-ben (pl. 3600 = 1 óra; None = korlátlan)
    )