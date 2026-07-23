import argparse
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx


def build_topology(kind: str, n: int, seed: int = 42) -> nx.Graph:
    if kind == "sparse":
        g = nx.random_regular_graph(3, n, seed=seed)
    elif kind == "dense":
        g = nx.erdos_renyi_graph(n, 0.5, seed=seed)
    elif kind == "fully":
        g = nx.complete_graph(n)
    else:
        raise ValueError(kind)

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


KIND_PUSH = "PUSH"
KIND_HAVE = "HAVE"
KIND_WANT = "WANT"
KIND_DIGEST = "DIGEST"


@dataclass
class Packet:
    src: int
    dst: int
    kind: str
    msg_id: str
    payload: Optional[str] = None


@dataclass
class NodeStats:
    packets_sent: int = 0
    packets_received: int = 0
    duplicates_received: int = 0
    delivered_at_round: Optional[int] = None


@dataclass
class Node:
    node_id: int
    neighbours: list[int]
    known: dict[str, str] = field(default_factory=dict)
    seen_digest_from: dict[int, set[str]] = field(default_factory=lambda: defaultdict(set))
    outstanding_wants: set[str] = field(default_factory=set)
    stats: NodeStats = field(default_factory=NodeStats)


class GossipSimulator:

    def __init__(self, graph: nx.Graph, strategy: str, fanout: int = 3, seed: int = 0) -> None:
        self.graph = graph
        self.strategy = strategy
        self.fanout = fanout
        self.rng = random.Random(seed)
        self.nodes: dict[int, Node] = {
            i: Node(node_id=i, neighbours=list(graph.neighbors(i)))
            for i in graph.nodes()
        }
        self.inbox: dict[int, list[Packet]] = defaultdict(list)
        self.round = 0

    def _send(self, src: int, dst: int, kind: str, msg_id: str, payload: Optional[str] = None) -> None:
        pkt = Packet(src=src, dst=dst, kind=kind, msg_id=msg_id, payload=payload)
        self._pending_next_round[dst].append(pkt)
        self.nodes[src].stats.packets_sent += 1

    def seed_message(self, origin: int, msg_id: str, content: str) -> None:
        node = self.nodes[origin]
        node.known[msg_id] = content
        node.stats.delivered_at_round = 0
        self._pending_seed = (origin, msg_id, content)

    def _deliver(self, node: Node, msg_id: str, content: str) -> None:
        if msg_id in node.known:
            node.stats.duplicates_received += 1
            return
        node.known[msg_id] = content
        if node.stats.delivered_at_round is None:
            node.stats.delivered_at_round = self.round

    def _process_inbox_push(self, node: Node) -> None:
        for pkt in self.inbox[node.node_id]:
            node.stats.packets_received += 1
            if pkt.kind == KIND_PUSH and pkt.payload is not None:
                already = pkt.msg_id in node.known
                self._deliver(node, pkt.msg_id, pkt.payload)
                if not already:
                    for t in self._pick_targets(node, exclude={pkt.src}):
                        self._send(node.node_id, t, KIND_PUSH, pkt.msg_id, pkt.payload)

    def _process_inbox_pull(self, node: Node) -> None:
        for pkt in self.inbox[node.node_id]:
            node.stats.packets_received += 1
            if pkt.kind == KIND_HAVE:
                node.seen_digest_from[pkt.src].add(pkt.msg_id)
                if pkt.msg_id not in node.known and pkt.msg_id not in node.outstanding_wants:
                    self._send(node.node_id, pkt.src, KIND_WANT, pkt.msg_id)
                    node.outstanding_wants.add(pkt.msg_id)
            elif pkt.kind == KIND_WANT:
                if pkt.msg_id in node.known:
                    self._send(node.node_id, pkt.src, KIND_PUSH, pkt.msg_id, node.known[pkt.msg_id])
            elif pkt.kind == KIND_PUSH and pkt.payload is not None:
                self._deliver(node, pkt.msg_id, pkt.payload)
                node.outstanding_wants.discard(pkt.msg_id)

    def _pull_advertise(self, node: Node) -> None:
        for msg_id in list(node.known.keys()):
            candidates = [n for n in node.neighbours if msg_id not in node.seen_digest_from.get(n, set())]
            if not candidates:
                continue
            targets = self.rng.sample(candidates, min(self.fanout, len(candidates)))
            for t in targets:
                self._send(node.node_id, t, KIND_HAVE, msg_id)
                node.seen_digest_from[t].add(msg_id)

    def _process_inbox_hybrid(self, node: Node) -> None:
        for pkt in self.inbox[node.node_id]:
            node.stats.packets_received += 1
            if pkt.kind == KIND_DIGEST:
                ids = pkt.payload.split(",") if pkt.payload else []
                for mid in ids:
                    node.seen_digest_from[pkt.src].add(mid)
                    if mid and mid not in node.known and mid not in node.outstanding_wants:
                        self._send(node.node_id, pkt.src, KIND_WANT, mid)
                        node.outstanding_wants.add(mid)
            elif pkt.kind == KIND_WANT:
                if pkt.msg_id in node.known:
                    self._send(node.node_id, pkt.src, KIND_PUSH, pkt.msg_id, node.known[pkt.msg_id])
            elif pkt.kind == KIND_PUSH and pkt.payload is not None:
                already = pkt.msg_id in node.known
                self._deliver(node, pkt.msg_id, pkt.payload)
                node.outstanding_wants.discard(pkt.msg_id)
                if not already:
                    digest = ",".join(node.known.keys())
                    for t in self._pick_targets(node, exclude={pkt.src}):
                        self._send(node.node_id, t, KIND_DIGEST, "digest", digest)

    def _pick_targets(self, node: Node, exclude: set[int]) -> list[int]:
        pool = [n for n in node.neighbours if n not in exclude]
        if not pool:
            return []
        return self.rng.sample(pool, min(self.fanout, len(pool)))

    def run(self, max_rounds: int = 300, target_coverage: float = 0.99) -> dict:
        assert hasattr(self, "_pending_seed"), "call seed_message() before run()"
        origin, msg_id, content = self._pending_seed
        self._pending_next_round: dict[int, list[Packet]] = defaultdict(list)
        origin_node = self.nodes[origin]
        if self.strategy in ("push", "hybrid"):
            for t in self._pick_targets(origin_node, exclude=set()):
                self._send(origin, t, KIND_PUSH, msg_id, content)

        n = len(self.nodes)
        for r in range(1, max_rounds + 1):
            self.round = r
            self.inbox = self._pending_next_round
            self._pending_next_round = defaultdict(list)

            for node in self.nodes.values():
                if self.strategy == "push":
                    self._process_inbox_push(node)
                elif self.strategy == "pull":
                    self._process_inbox_pull(node)
                elif self.strategy == "hybrid":
                    self._process_inbox_hybrid(node)
                else:
                    raise ValueError(self.strategy)

            if self.strategy == "pull":
                for node in self.nodes.values():
                    self._pull_advertise(node)

            delivered = sum(1 for x in self.nodes.values() if msg_id in x.known)
            no_traffic = not any(len(v) > 0 for v in self._pending_next_round.values())
            if no_traffic:
                break
            if delivered == n:
                break

        return self._collect_metrics(msg_id, target_coverage)

    def _collect_metrics(self, msg_id: str, target_coverage: float) -> dict:
        sent = [n.stats.packets_sent for n in self.nodes.values()]
        dupes = [n.stats.duplicates_received for n in self.nodes.values()]
        delivered_at = [
            n.stats.delivered_at_round for n in self.nodes.values() if msg_id in n.known
        ]
        n = len(self.nodes)
        reached = sum(1 for x in self.nodes.values() if msg_id in x.known)
        return {
            "strategy": self.strategy,
            "num_nodes": n,
            "target_coverage": target_coverage,
            "rounds_used": self.round,
            "total_packets_sent": sum(sent),
            "avg_packets_per_node": sum(sent) / n,
            "total_duplicates_received": sum(dupes),
            "avg_duplicates_per_node": sum(dupes) / n,
            "coverage_achieved": reached / n,
            "delivery_efficiency": reached / max(1, sum(sent)),
            "convergence_rounds": max(delivered_at) if delivered_at else -1,
        }


def run_single(n: int, topology: str, strategy: str, fanout: int, seed: int) -> dict:
    graph = build_topology(topology, n, seed=seed)
    sim = GossipSimulator(graph, strategy=strategy, fanout=fanout, seed=seed)
    sim.seed_message(origin=0, msg_id="tx1", content="hello-gossip")
    metrics = sim.run(max_rounds=300)
    metrics["topology"] = topology
    metrics["fanout"] = fanout
    metrics["seed"] = seed
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=100)
    parser.add_argument("--topology", choices=["sparse", "dense", "fully"], default="sparse")
    parser.add_argument("--strategy", choices=["push", "pull", "hybrid"], default="push")
    parser.add_argument("--fanout", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_single(args.nodes, args.topology, args.strategy, args.fanout, args.seed)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"=== Gossip run: {args.strategy} on {args.topology} ({args.nodes} nodes) ===")
    print(f"  fanout                    = {args.fanout}")
    print(f"  rounds_used               = {result['rounds_used']}")
    print(f"  coverage_achieved         = {result['coverage_achieved']:.3f}")
    print(f"  total_packets_sent        = {result['total_packets_sent']}")
    print(f"  avg_packets_per_node      = {result['avg_packets_per_node']:.2f}")
    print(f"  total_duplicates_received = {result['total_duplicates_received']}")
    print(f"  avg_duplicates_per_node   = {result['avg_duplicates_per_node']:.2f}")
    print(f"  delivery_efficiency       = {result['delivery_efficiency']:.4f}")
    print(f"  convergence_rounds        = {result['convergence_rounds']}")


if __name__ == "__main__":
    main()
