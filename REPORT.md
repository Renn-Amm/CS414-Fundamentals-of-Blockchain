# Assignment 3 — Gossip Report

## Setup

- 100 nodes, three topologies, three gossip strategies, fanout = 3.
- One message injected at node 0; measured how it propagates.
- Each result averaged over 5 seeds.

## Topologies

| Topology | Edges | Avg degree | Diameter |
|----------|------:|-----------:|---------:|
| sparse   | 150   | 3.00       | 8        |
| dense    | 2449  | 48.98      | 2        |
| fully    | 4950  | 99.00      | 1        |

**Enforcing topology:** IPv8 by default uses Dispersy bootstrappers plus the RandomWalk strategy to auto-discover peers. Both are disabled (empty walker list, no bootstrappers) and each node is given a fixed neighbour list built by `build_topology()`, so each of the three topology types is enforced exactly instead of emerging from discovery.

### The three topology graphs

- **`topology_sparse.png`** — 3-regular random graph. Every node has exactly 3 neighbours; long paths exist between distant nodes (diameter 8).
- **`topology_dense.png`** — - **`topology_dense.png`** — Random graph where every pair of nodes has a 50% chance of being connected. Each node ends up connected to about half the others; well-mixed (diameter 2).
- **`topology_fully.png`** — Complete graph. Every node knows every other; diameter 1.

## Gossip strategies

- **Push** — on first receipt, forward to 3 random neighbours.
- **Pull** — periodically advertise `HAVE(id)`; neighbours reply `WANT(id)` for missing ones; holder sends the content.
- **Hybrid** — on first receipt, send a `DIGEST` (list of known ids, no payload) to 3 neighbours; content only flows in response to a `WANT`.

## Results

| Topology | Strategy | Pkts/node | Dupes/node | Rounds | Efficiency | Coverage |
|----------|----------|----------:|-----------:|-------:|-----------:|---------:|
| sparse   | push     | 2.01      | 0.90       | 7.4    | 0.4975     | 1.000    |
| sparse   | pull     | 3.71      | 0.00       | 23.2   | 0.2693     | 1.000    |
| sparse   | hybrid   | 3.93      | 0.00       | 20.2   | 0.2545     | 1.000    |
| dense    | push     | 2.86      | 1.91       | 7.2    | 0.3333     | 0.952    |
| dense    | pull     | 15.96     | 0.00       | 12.6   | 0.0632     | 1.000    |
| dense    | hybrid   | 4.68      | 0.00       | 19.6   | 0.2034     | 0.952    |
| fully    | push     | 2.81      | 1.89       | 6.8    | 0.3333     | 0.938    |
| fully    | pull     | 16.37     | 0.00       | 12.8   | 0.0613     | 1.000    |
| fully    | hybrid   | 4.61      | 0.00       | 18.4   | 0.2035     | 0.938    |

Bar charts for each metric are in `output/metric_*.png`.

**Custom metric — delivery efficiency**: nodes reached ÷ packets sent. Direct measure of wasted bandwidth (1.0 = every packet was a fresh delivery).

## Observations

Push is cheapest and fastest but has duplicates and misses some nodes on dense/fully at fanout 3. Pull has zero duplicates and full coverage but sends many `HAVE` advertisements (16 per node on dense/fully). Hybrid keeps pull's zero-duplicate property with far fewer packets than pull, at the cost of slower convergence than push.

## Running

```
pip install -r requirements.txt
python src/experiment.py
```
