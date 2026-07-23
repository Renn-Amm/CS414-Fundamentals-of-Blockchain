import argparse
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from simulator import build_topology, run_single


NODES = 100
STRATEGIES = ["push", "pull", "hybrid"]
TOPOLOGIES = ["sparse", "dense", "fully"]
FANOUT = 3
SEEDS = [0, 1, 2, 3, 4]


def render_topology(kind: str, n: int, outdir: Path) -> dict:
    graph = build_topology(kind, n, seed=42)
    outdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    if kind == "fully":
        pos = nx.circular_layout(graph)
    else:
        pos = nx.spring_layout(graph, seed=42, k=1.5 / (n ** 0.5))

    nx.draw_networkx_nodes(graph, pos, node_size=40, node_color="#2b6cb0", ax=ax)
    nx.draw_networkx_edges(graph, pos, alpha=0.25, width=0.5, ax=ax)
    ax.set_title(
        f"{kind.capitalize()} topology  |  n={n}  |  "
        f"edges={graph.number_of_edges()}  |  "
        f"avg degree={2 * graph.number_of_edges() / n:.1f}"
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(outdir / f"topology_{kind}.png", dpi=120)
    plt.close(fig)

    return {
        "kind": kind,
        "num_nodes": n,
        "num_edges": graph.number_of_edges(),
        "avg_degree": 2 * graph.number_of_edges() / n,
        "diameter": nx.diameter(graph),
        "clustering": nx.average_clustering(graph),
    }


def aggregate(runs: list[dict]) -> dict:
    return {
        "seeds": len(runs),
        "avg_packets_per_node": statistics.mean(r["avg_packets_per_node"] for r in runs),
        "avg_duplicates_per_node": statistics.mean(r["avg_duplicates_per_node"] for r in runs),
        "avg_total_packets": statistics.mean(r["total_packets_sent"] for r in runs),
        "avg_total_duplicates": statistics.mean(r["total_duplicates_received"] for r in runs),
        "avg_convergence_rounds": statistics.mean(r["convergence_rounds"] for r in runs),
        "avg_delivery_efficiency": statistics.mean(r["delivery_efficiency"] for r in runs),
        "avg_coverage": statistics.mean(r["coverage_achieved"] for r in runs),
    }


def sweep_all(outdir: Path) -> list[dict]:
    all_results = []
    for topology in TOPOLOGIES:
        for strategy in STRATEGIES:
            per_seed = [run_single(NODES, topology, strategy, FANOUT, s) for s in SEEDS]
            aggregated = aggregate(per_seed)
            aggregated["topology"] = topology
            aggregated["strategy"] = strategy
            all_results.append(aggregated)
    with (outdir / "results.json").open("w") as f:
        json.dump(all_results, f, indent=2)
    return all_results


def render_bar_charts(results: list[dict], outdir: Path) -> None:
    metrics = [
        ("avg_packets_per_node", "Avg packets sent per node"),
        ("avg_duplicates_per_node", "Avg duplicate packets per node"),
        ("avg_convergence_rounds", "Convergence rounds"),
        ("avg_delivery_efficiency", "Delivery efficiency"),
    ]
    for key, title in metrics:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        x = range(len(STRATEGIES))
        width = 0.25
        for offset, topology in zip([-1, 0, 1], TOPOLOGIES):
            values = []
            for strategy in STRATEGIES:
                row = next(r for r in results if r["strategy"] == strategy and r["topology"] == topology)
                values.append(row[key])
            positions = [xi + offset * width for xi in x]
            ax.bar(positions, values, width=width, label=topology)
        ax.set_xticks(list(x))
        ax.set_xticklabels(STRATEGIES)
        ax.set_ylabel(title)
        ax.set_title(f"{title} — n={NODES}, fanout={FANOUT}")
        ax.legend(title="topology")
        fig.tight_layout()
        fig.savefig(outdir / f"metric_{key}.png", dpi=120)
        plt.close(fig)


def print_table(results: list[dict], topology_stats: list[dict]) -> None:
    print("\n=== Topology summary ===")
    print(f"{'topology':<10} {'edges':>8} {'avg_deg':>8} {'diameter':>10} {'clustering':>12}")
    for t in topology_stats:
        print(
            f"{t['kind']:<10} {t['num_edges']:>8} {t['avg_degree']:>8.2f} "
            f"{t['diameter']:>10} {t['clustering']:>12.4f}"
        )

    print("\n=== Results (averaged over 5 seeds, n=100, fanout=3) ===")
    header = (
        f"{'topology':<8} {'strategy':<8} "
        f"{'pkts/node':>10} {'dupes/node':>11} "
        f"{'rounds':>8} {'efficiency':>11} {'coverage':>9}"
    )
    print(header)
    print("-" * len(header))
    for topology in TOPOLOGIES:
        for strategy in STRATEGIES:
            row = next(r for r in results if r["strategy"] == strategy and r["topology"] == topology)
            print(
                f"{topology:<8} {strategy:<8} "
                f"{row['avg_packets_per_node']:>10.2f} {row['avg_duplicates_per_node']:>11.2f} "
                f"{row['avg_convergence_rounds']:>8.1f} {row['avg_delivery_efficiency']:>11.4f} "
                f"{row['avg_coverage']:>9.3f}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=Path("output"))
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    topology_stats = [render_topology(k, NODES, args.outdir) for k in TOPOLOGIES]
    results = sweep_all(args.outdir)
    render_bar_charts(results, args.outdir)
    print_table(results, topology_stats)
    print(f"\nAll outputs written to {args.outdir}/")


if __name__ == "__main__":
    main()
