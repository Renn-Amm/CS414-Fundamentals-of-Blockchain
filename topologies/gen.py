import argparse
import random
from pathlib import Path

import networkx as nx
import yaml


def build(kind: str, n: int, seed: int) -> nx.Graph:
    if kind == "sparse":
        g = nx.random_regular_graph(3, n, seed=seed)
    elif kind == "dense":
        g = nx.erdos_renyi_graph(n, 0.5, seed=seed)
    elif kind == "fully":
        g = nx.complete_graph(n)
    else:
        raise SystemExit(f"unknown kind: {kind!r}")

    if not nx.is_connected(g):
        rng = random.Random(seed)
        components = list(nx.connected_components(g))
        main = max(components, key=len)
        for comp in components:
            if comp is main:
                continue
            u = rng.choice(list(comp))
            v = rng.choice(list(main))
            g.add_edge(u, v)
    return g


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("num_nodes", type=int)
    ap.add_argument("kind", choices=["sparse", "dense", "fully"])
    ap.add_argument("output", type=Path)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    g = build(args.kind, args.num_nodes, args.seed)
    adjacency = {int(node): sorted(int(n) for n in g.neighbors(node)) for node in g.nodes()}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as f:
        yaml.safe_dump(adjacency, f)

    print(f"wrote {args.output}: {args.num_nodes} nodes, {g.number_of_edges()} edges, "
          f"avg degree {2 * g.number_of_edges() / args.num_nodes:.2f}")


if __name__ == "__main__":
    main()
