# Assignment 3 

100 peer nodes, three topology types (sparse, dense, fully connected), three
gossip strategies (push, pull, hybrid). Full details in [`REPORT.md`](REPORT.md).

## Quick start

```
pip install -r requirements.txt
python src/experiment.py
```

Takes about 30 seconds. Writes everything into `output/`:

- `topology_{sparse,dense,fully}.png` — rendered topology graphs
- `metric_avg_*.png` — bar charts for each reported metric
- `results.json` — raw numbers averaged over 5 seeds

## Layout

```
src/
├── simulator.py           # 100-node in-process gossip simulator
├── experiment.py          # sweep runner: builds all topologies × strategies, produces tables/plots
├── run.py                 # multi-process IPv8 runner (from template, extended)
├── da_types.py            # from template
└── algorithms/
    ├── gossip_ipv8.py     # push/pull/hybrid as an IPv8 community (real UDP)
    ├── echo_algorithm.py  # from template
    └── ring_election.py   # from template

topologies/
└── gen.py                 # generates sparse/dense/fully YAML topology files

output/                    # created by experiment.py

REPORT.md                  # the deliverable report
```

## Reproducing individual runs

Single simulator run (pick topology and strategy):

```
python src/simulator.py --topology sparse --strategy push --nodes 100
python src/simulator.py --topology dense --strategy pull --nodes 100
python src/simulator.py --topology fully --strategy hybrid --nodes 100
```

## Real IPv8 (multi-process, for smaller node counts)

The simulator is used for the reported 100-node results because 100 real
UDP processes on one laptop is unreliable. For sanity checking against
real IPv8 with a small number of nodes:

```
# 1. Generate a topology
python topologies/gen.py 10 sparse topologies/sparse.yaml

# 2. Launch 10 IPv8 processes (each is a node)
export GOSSIP_STRATEGY=push        # push | pull | hybrid
export GOSSIP_FANOUT=3
for i in $(seq 0 9); do
    python src/run.py $i topologies/sparse.yaml gossip &
done
wait
```

Each node prints its per-message packet stats. The strategy is picked up
from the `GOSSIP_STRATEGY` env var, so relaunch after changing it.

## Design notes

- **How the topology is enforced.** IPv8's default is bootstrapper + RandomWalk
  auto-discovery. We disable both (empty walker list, no bootstrappers) and
  give each node an explicit YAML list of neighbours; each node calls
  `walk_to(address)` to connect to exactly those neighbours and no others.
  This is what makes it possible to produce sparse and fully connected
  topologies on demand.
- **Simulator vs real IPv8.** The simulator uses the same gossip logic as
  the IPv8 version — same message kinds (`PUSH`, `HAVE`, `WANT`, `DIGEST`),
  same fanout policy, same duplicate accounting. It just delivers packets
  in-process instead of over UDP. For gossip protocol overhead measurements
  this is a valid abstraction: the metrics (packets sent, duplicates
  received, rounds to convergence) don't depend on wire time.

## Metrics reported

- Average packets sent per node
- Duplicates received per node
- **Delivery efficiency** — nodes reached ÷ packets sent (custom metric)
- Convergence rounds
- Coverage

See `REPORT.md` for the full results table and interpretation.
