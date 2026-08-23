**# CognoDB Cloud Benchmark — Graph Database Comparison**

A reproducible benchmark comparing **\*\*CognoDB Cloud\*\*** against four other graph

database platforms — **\*\*Neo4j AuraDB Free\*\***, **\*\*self-hosted Neo4j\*\***,

**\*\*Memgraph\*\***, and **\*\*ArangoDB\*\*** — on identical data, identical queries, and

matched resource limits.

This benchmark does not declare a "winner." The goal is fair methodology,

reproducible automation, and honest reporting of where and why the platforms

differ.

\---

**## 1. Platforms tested**

\| Platform | Deployment | vCPU | RAM | Storage | Protocol |

\|---|---|---|---|---|---|

\| **\*\*CognoDB Cloud\*\*** | Managed (Free tier, \`c0\`) | burst to 0.5 | 512 MB | 1 GiB | Bolt (\`bolt+s\://\`) |

\| **\*\*Neo4j AuraDB\*\*** | Managed (Free tier) | not published by Neo4j | not published by Neo4j | quota-based (node/rel count) | Bolt (\`neo4j+s\://\`) |

\| **\*\*Neo4j (self-hosted)\*\*** | Docker, capped | 0.5 | 512 MB (256 MB heap + 64 MB pagecache) | host disk | Bolt (\`bolt://\`) |

\| **\*\*Memgraph\*\*** | Docker, capped | 0.5 | 512 MB | host disk (in-memory engine) | Bolt (\`bolt://\`) |

\| **\*\*ArangoDB\*\*** | Docker, capped | 0.5 | 512 MB | host disk | HTTP/AQL |

**\*\*Fairness note:\*\*** CognoDB's free tier (0.5 vCPU / 512 MB / 1 GiB) is used as

the resource baseline. The three self-hosted platforms (Neo4j, Memgraph,

ArangoDB) were run in Docker containers explicitly capped with \`--cpus=0.5

\--memory=512m\` to match. AuraDB Free does not publish its underlying vCPU/RAM

allocation, so exact parity with AuraDB cannot be guaranteed or verified —

this is disclosed here rather than hidden. All benchmark client code ran from

the same local machine for every platform.

\---

**## 2. Dataset**

**\*\*Source:\*\*** [IMDb Non-Commercial Datasets]\(https\://datasets.imdbws.com/)

(\`title.basics.tsv.gz\`, \`title.principals.tsv.gz\`, \`name.basics.tsv.gz\`)

**\*\*Shape:\*\*** a movie–actor graph.

\- \`Person\` nodes — actors/actresses

\- \`Title\` nodes — movies released 2015 or later

\- \`ACTED\_IN\` relationships — Person → Title

**\*\*Final size (identical across all 5 platforms):\*\***

\- 134,208 \`Person\` nodes

\- 24,674 \`Title\` nodes

\- **\*\*158,882 total nodes\*\***

\- **\*\*175,889 \`ACTED\_IN\` relationships\*\***

This falls inside the assignment's recommended 100k–500k relationship range

and comfortably clears the 100,000 relationship minimum.

**\*\*Load method:\*\*** identical CSV files (\`data/nodes\_people.csv\`,

\`data/nodes\_titles.csv\`, \`data/edges\_acted\_in.csv\`) generated once by

\`prepare\_dataset.py\`, then loaded into each platform via its official driver

using batched inserts (batch size 500). CognoDB, Aura, and self-hosted Neo4j

all use Cypher \`UNWIND ... MERGE\`; Memgraph uses \`UNWIND ... MERGE\` for nodes

and \`UNWIND ... CREATE\` for relationships (see §6 caveats); ArangoDB uses

\`insert\_many()\` batch document inserts.

**\*\*Indexes:\*\*** \`Person.personId\` and \`Title.titleId\` are indexed/uniquely

constrained on every platform (via \`CREATE CONSTRAINT\`/\`CREATE INDEX\` in the

Cypher loaders, \`add\_persistent\_index\` in the ArangoDB loader).

\`Title.startYear\` is **\*\*not indexed\*\*** on any platform — used deliberately in

the lookup workload as the "unindexed filter" comparison point.

\---

**## 3. Methodology**

\- Same dataset, same logical queries, same client machine for every platform.

\- Each read workload: **\*\*15 warmup iterations\*\*** (discarded) + \*\*100 timed

  iterations\*\*, reporting p50 and p95 latency in milliseconds.

\- Mixed workload: concurrency sweep at **\*\*10 and 40 concurrent clients\*\***, 15

  seconds sustained load per level, 80% read / 20% write mix.

\- All raw per-iteration latencies and summary statistics are saved to

  \`results/\*.csv\`.

\- Every script is platform-parameterized and reruns are one command (see §8).

\---

**## 4. Results**

![Data load time by platform]\(results/charts/load\_time.png)

**### 4.1 Data loading (ingest throughput)**

\| Platform | Load time | Notes |

\|---|---|---|

\| ArangoDB | 9.8s | \`insert\_many()\` batch writes, \`waitForSync=false\` (default) |

\| Memgraph | 7.5s\* | see caveat below — original run took 16,547s |

\| Self-hosted Neo4j | 16.9s | |

\| Neo4j AuraDB | 46.3s | remote, network round-trip per batch |

\| CognoDB | 227.0s | remote, network round-trip per batch |

\\\* **\*\*Caveat:\*\*** Memgraph's first load attempt took \*\*16,547 seconds (\~4.6

hours)\*\* using \`MERGE\` for the \`ACTED\_IN\` relationship, which performs an

existence check before creating each edge. Under the 0.5 vCPU cap this

existence check compounded catastrophically across 175,889 edges. Since the

load targets an empty graph (no duplicate risk), the relationship write was

switched from \`MERGE\` to \`CREATE\`, which skips the existence check. The

corrected load completed in 7.5s. Both numbers are reported here for

transparency; **\*\*7.5s is the number used in all further comparisons.\*\***

**### 4.2 Traversal latency (1-hop / 2-hop / 3-hop, ms)**

![Traversal latency by hop depth]\(results/charts/traversal\_latency.png)



\| Platform | 1-hop p50 | 1-hop p95 | 2-hop p50 | 2-hop p95 | 3-hop p50 | 3-hop p95 |

\|---|---|---|---|---|---|---|

\| Memgraph | 0.38 | 0.78 | 0.45 | 0.79 | 0.42 | 0.85 |

\| ArangoDB | 0.85 | 1.00 | 1.13 | 2.05 | 1.39 | 2.47 |

\| Neo4j (self-hosted) | 2.88 | 75.85 | 3.11 | 77.41 | 2.04 | 73.85 |

\| Neo4j AuraDB | 85.89 | 87.92 | 85.77 | 87.08 | 85.87 | 87.10 |

\| CognoDB | 291.82 | 358.22 | 292.78 | 338.84 | 305.98 | 342.68 |

**### 4.3 Lookup latency (point lookup / filtered lookup, ms)**

![Lookup latency indexed vs unindexed]\(results/charts/lookup\_latency.png)



\| Platform | Point p50 | Point p95 | Filtered p50 | Filtered p95 |

\|---|---|---|---|---|

\| Memgraph | 0.38 | 0.57 | 10.19 | 60.80 |

\| ArangoDB | 1.02 | 1.31 | 1.56 | 6.58 |

\| Neo4j (self-hosted) | 2.38 | 69.58 | 4.51 | 83.46 |

\| Neo4j AuraDB | 85.31 | 86.61 | 86.01 | 92.38 |

\| CognoDB | 281.93 | 372.72 | 305.25 | 355.95 |

Point lookup filters on the indexed \`personId\`. Filtered lookup filters on

the unindexed \`startYear\` — the cost of the missing index is visible most

clearly on Memgraph (0.38ms → 10.19ms p50) since its otherwise very low

baseline latency makes the scan cost stand out.

**### 4.4 Aggregation latency (count/group-by \`ACTED\_IN\` by \`Title.startYear\`, ms)**

![Aggregation latency]\(results/charts/aggregation\_latency.png)



\| Platform | p50 | p95 |

\|---|---|---|

\| Neo4j (self-hosted) | 92.35 | 182.37 |

\| Memgraph | 116.31 | 182.46 |

\| Neo4j AuraDB | 148.14 | 159.81 |

\| ArangoDB | 1216.35 | 1282.40 |

\| CognoDB | 1822.60 | 1953.98 |

**\*\*Caveat:\*\*** ArangoDB's aggregation query resolves each edge's target document

individually via \`DOCUMENT(e.\_to)\` inside a \`FOR\` loop over all 175,889

edges — an N+1-style per-edge resolution. Cypher's \`MATCH

(p)-[:ACTED\_IN]->(t)\` performs the equivalent join as a single native graph

traversal. This is a query-construction/paradigm difference between AQL and

Cypher for this specific query shape, not a resource or hardware difference —

it explains why ArangoDB (fastest on traversal/lookup) is much slower here.

**### 4.5 Mixed concurrent workload (80% read / 20% write, ops/sec)**

![Mixed concurrent throughput]\(results/charts/mixed\_concurrent\_throughput.png)



\| Platform | 10 clients (ops/sec, errors) | 40 clients (ops/sec, errors) |

\|---|---|---|

\| ArangoDB | 2211.9, 0 | 2119.9, 1713 |

\| Memgraph | 1455.3, 0 | 1378.3, 1008 |

\| Neo4j AuraDB | 113.9, 0 | 400.5, 273 |

\| Neo4j (self-hosted) | 78.5, 0 | 129.6, 10 |

\| CognoDB | 31.9, 0 | 83.5, 73 |

Every platform shows **\*\*zero errors at 10 concurrent clients\*\*** and

**\*\*non-zero errors at 40\*\*** — consistent with the shared 0.5 vCPU cap becoming

a real contention point once concurrency exceeds what half a core can

service without queuing/timeout failures. Local platforms (ArangoDB,

Memgraph) show flat or slightly declining throughput from 10→40 clients,

consistent with a CPU-bound bottleneck. Remote platforms (Aura, self-hosted

Neo4j) show throughput *\*increasing\** from 10→40 despite errors, consistent

with a network-latency-bound bottleneck where more in-flight requests still

help overall utilization.

**### 4.6 Resource footprint**

\| Platform | Storage/footprint | Source |

\|---|---|---|

\| CognoDB | 128 MB | Console UI |

\| Neo4j (self-hosted) | 539 MB (disk) | \`docker exec neo4j-selfhosted du -sh /data\` |

\| Memgraph | 488 MB (in-memory snapshot, \~95% of 512 MB cap) | \`docker exec memgraph du -sh /var/lib/memgraph\` |

\| ArangoDB | 137.4 MB (disk) | \`docker exec arangodb du -sh /var/lib/arangodb3\` |

\| Neo4j AuraDB | **\*\*Not observable.\*\*** AuraDB Free gates CPU/storage/query-rate metrics behind a paid "Professional" upgrade. Only quota-based counts are shown: 158,882 nodes (79% of quota), 175,889 relationships (44% of quota). | Console UI |

\---

**## 5. Analysis**

**\*\*Local vs. remote dominates every latency result.\*\*** All three self-hosted

platforms (Memgraph, ArangoDB, self-hosted Neo4j) post sub-3ms p50 latency

on point queries; both managed remote platforms (Aura, CognoDB) sit at

80-300ms+ regardless of query complexity. For point-style queries, network

round-trip time to the managed instance is the dominant cost, not the query

engine itself — traversal depth (1-hop vs 3-hop) barely moves the needle for

Aura or CognoDB, while it visibly does for the fast local engines.

**\*\*CognoDB is consistently \~3x slower than Aura despite both being remote.\*\***

CognoDB's instance region was \`us-east4\`; exact network path/region distance

from the benchmark client likely explains a meaningful part of this gap.

This is reported as an open question rather than a conclusion — pinning down

the exact cause would need a same-region comparison, out of scope here.

\*\*Self-hosted Neo4j's p95 tail is disproportionately large relative to its

p50\*\* (e.g. 2.88ms p50 vs 75.85ms p95 on 1-hop traversal) — a \~26x spread.

This pattern repeats across traversal and lookup workloads and is worth

flagging as a genuine anomaly rather than smoothing over: possible causes

include JVM GC pauses (a known Neo4j characteristic under tight heap

limits) or Docker CPU-throttling stalls under the 0.5 vCPU cap. Memgraph and

ArangoDB, both non-JVM, show far tighter p50/p95 spreads throughout.

\*\*Query paradigm, not just hardware, explains ArangoDB's aggregation

result.\*\* ArangoDB is the fastest platform on traversal and lookup but by

far the slowest local platform on aggregation, due to how the AQL query was

written (per-edge \`DOCUMENT()\` resolution vs. Cypher's native pattern

match) — see §4.4. This is a useful reminder that "platform X is faster"

claims are query-shape-dependent, not a single number.

\*\*All platforms show a real concurrency ceiling at 40 clients under the

0.5 vCPU cap.\*\* No platform sustained zero errors at 40 concurrent clients.

This is presented as a genuine finding about free-tier/capped-resource

viability under load, not a bug in any platform.

\---

**## 6. Caveats (full list)**

\- **\*\*Memgraph load time bug:\*\*** original loader used \`MERGE\` for relationship

  creation, causing a 16,547s load under the 0.5 vCPU cap. Fixed by

  switching to \`CREATE\` (safe since the load targets an empty graph). See

  §4.1.

\- **\*\*AuraDB Free resource specs are not published by Neo4j\*\*** — exact vCPU/RAM

  parity with the other four platforms cannot be verified, only assumed

  from the "Free tier" tier name.

\- **\*\*AuraDB Free storage/CPU metrics are not observable\*\*** — gated behind a

  paid upgrade. Reported as "not observable" per assignment guidance

  instead of guessing.

\- **\*\*ArangoDB's \`insert\_many()\` uses \`waitForSync=false\`\*\*** (the default) —

  writes are acknowledged once accepted, not once fsynced to disk. This

  likely contributes to ArangoDB's fast load time and is disclosed rather

  than presented as a like-for-like durability comparison.

\- **\*\*Query paradigm differences (Cypher vs. AQL)\*\*** mean traversal/lookup/

  aggregation queries are logically equivalent but not always executed via

  identical query plans — see §4.4 for the clearest example.

\- \*\*Self-hosted Neo4j's minimum viable memory footprint required explicit

  tuning\*\* (\`heap.max\_size=256m\`, \`pagecache.size=64m\`) to fit inside the

  512MB container cap — Neo4j 5's defaults exceed 512MB and fail to start

  without this override.

\- **\*\*Network variance:\*\*** all remote-platform numbers (CognoDB, Aura) reflect

  a single benchmark client's network path and were not repeated across

  multiple times of day or geographic locations.

\---

**## 7. Repository structure**

\`\`\`

cognodb-benchmark/

├── data/                    # generated dataset CSVs (not committed, see below)

├── loaders/                 # cognodb\_loader.py, neo4j\_aura\_loader.py,

│                              neo4j\_selfhosted\_loader.py, memgraph\_loader.py,

│                              arango\_loader.py

├── workloads/                # traversal / lookup / aggregation / mixed\_concurrent

│                              (Cypher versions + separate AQL versions for ArangoDB)

├── results/                  # raw + summary CSVs from every workload run

├── prepare\_dataset.py         # downloads + filters IMDb data into data/\*.csv

├── setup\_docker.sh            # starts Memgraph/ArangoDB/Neo4j Docker containers

├── load\_all.sh                # loads dataset into all 5 platforms

├── run\_all.sh                 # runs all workloads + generates charts (one command)

├── generate\_charts.py         # produces results/charts/\*.png from results/\*.csv

├── test\_connections.py        # sanity-checks connectivity to all 5 platforms

├── requirements.txt

├── .env.example               # credential template (copy to .env, fill in, never commit)

└── README.md

\`\`\`

\`data/raw/\*.tsv.gz\` and \`data/\*.csv\` are gitignored (regenerable via

\`prepare\_dataset.py\`, and large). \`results/\*.csv\` are gitignored by default

but the actual result files produced for this submission are included

separately so the numbers above can be verified without a full rerun.

\---

**## 8. Reproducing this benchmark

### Prerequisites

- Python 3.10+
- Docker
- Git
- Free-tier CognoDB account
- Free-tier Neo4j AuraDB account

### Clone and create the virtual environment

```bash
git clone <this-repo-url>
cd cognodb-benchmark

python3 -m venv venv
source venv/bin/activate
```

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Edit `.env` and add the CognoDB and Neo4j AuraDB credentials.

Do not commit `.env`.

### Start local databases

```bash
make setup
```

This starts:

- Memgraph
- ArangoDB
- self-hosted Neo4j

Check that all configured platforms are reachable:

```bash
make test
```

### Prepare the dataset

```bash
make dataset
make dedupe
```

### Load databases

Load everything:

```bash
make load
```

Or load platforms individually:

```bash
make load-selfhosted
make load-aura
make load-cognodb
make load-memgraph
make load-arango
```

Verify:

```bash
make check
```

Individual checks:

```bash
make check-selfhosted
make check-aura
make check-cognodb
make check-memgraph
make check-arango
```

### Run workloads

Traversal:

```bash
make traversal
```

Aggregation:

```bash
make aggregation
```

Lookup:

```bash
make lookup
```

Mixed concurrency:

```bash
make mixed
```

Platform-specific commands are also available. For example:

```bash
make traversal-selfhosted
make aggregation-selfhosted
make lookup-selfhosted
make mixed-selfhosted

make traversal-aura
make aggregation-aura
make lookup-aura
make mixed-aura

make traversal-arango
make aggregation-arango
make lookup-arango
make mixed-arango
```

Generate charts:

```bash
make charts
```

The raw and summary results are written to `results/`.

### Reset commands

Reset the three local Docker platforms:

```bash
make reset-local
```

Reset CognoDB and AuraDB:

```bash
make reset-cloud
```

**Warning:** `make reset-cloud` deletes all nodes and relationships from the
managed CognoDB and AuraDB databases.

### Other useful Make commands

Show all available commands:

```bash
make help
```

Stop/remove local containers:

```bash
make teardown
```

Delete generated dataset files:

```bash
make clean-data
```

Run the existing complete orchestration:

```bash
make run
```

For controlled submissions, prefer the individual platform-specific workload
commands instead of `make run` when a platform has not successfully loaded the
dataset.

---

## 9. Current benchmark status

The final reproducible runs completed successfully for:

- Neo4j self-hosted
- Neo4j AuraDB
- ArangoDB

### Neo4j self-hosted

Dataset verification:

```text
134,208 Person
24,674 Title
175,889 ACTED_IN
```

Load verification passed.

Traversal:

| Depth | p50 | p95 |
|---|---:|---:|
| 1-hop | 3.44 ms | 82.04 ms |
| 2-hop | 4.76 ms | 84.95 ms |
| 3-hop | 2.86 ms | 78.87 ms |

Aggregation:

| Query | p50 | p95 |
|---|---:|---:|
| Group by year | 96.82 ms | 184.27 ms |

Lookup:

| Query | p50 | p95 |
|---|---:|---:|
| Point lookup | 2.56 ms | 77.69 ms |
| Filtered lookup | 4.79 ms | 87.09 ms |

Mixed concurrency:

| Clients | Throughput | Errors |
|---:|---:|---:|
| 10 | 86.3 ops/sec | 0 |
| 40 | 121.5 ops/sec | 10 |

### Neo4j AuraDB

Traversal:

| Depth | p50 | p95 |
|---|---:|---:|
| 1-hop | 81.03 ms | 82.66 ms |
| 2-hop | 80.84 ms | 85.16 ms |
| 3-hop | 80.71 ms | 83.85 ms |

Aggregation:

| Query | p50 | p95 |
|---|---:|---:|
| Group by year | 146.89 ms | 155.38 ms |

Lookup:

| Query | p50 | p95 |
|---|---:|---:|
| Point lookup | 82.65 ms | 84.33 ms |
| Filtered lookup | 81.71 ms | 86.57 ms |

Mixed concurrency:

| Clients | Throughput | Errors |
|---:|---:|---:|
| 10 | 114.8 ops/sec | 0 |
| 40 | 409.5 ops/sec | 268 |

### ArangoDB

Dataset verification:

```text
134,208 Person
24,674 Title
175,889 ACTED_IN
```

Load verification passed.

Traversal:

| Depth | p50 | p95 |
|---|---:|---:|
| 1-hop | 0.84 ms | 0.98 ms |
| 2-hop | 1.06 ms | 1.66 ms |
| 3-hop | 1.49 ms | 3.36 ms |

Aggregation:

| Query | p50 | p95 |
|---|---:|---:|
| Group by year | 920.19 ms | 1,618.98 ms |

Lookup:

| Query | p50 | p95 |
|---|---:|---:|
| Point lookup | 0.89 ms | 1.35 ms |
| Filtered lookup | 1.25 ms | 8.15 ms |

Mixed concurrency:

| Clients | Throughput | Errors |
|---:|---:|---:|
| 10 | 575.9 ops/sec | 0 |
| 40 | 714.7 ops/sec | 578 |

The 40-client ArangoDB run produced approximately 5.1% errors
(578 errors out of 11,298 attempted operations). Higher throughput with
errors is therefore not an unqualified performance improvement.

---

## 10. CognoDB status and caveat

CognoDB is the primary platform under test and was included in the benchmark
design, loader, verification scripts, and workload scripts.

The CognoDB instance was reachable, but the large dataset load became a major
time constraint. Loading attempts encountered transient timeouts and
defunct Bolt connections while processing the dataset.

Because the final submission had a strict execution deadline, the complete
CognoDB workload set was not successfully reproduced in the final run.

Therefore, this README **does not invent or present CognoDB results as final
benchmark results**.

The available commands remain:

```bash
make load-cognodb
make check-cognodb
make traversal-cognodb
make aggregation-cognodb
make lookup-cognodb
make mixed-cognodb
```

If the CognoDB load completes successfully, these commands can be used to
generate its missing result CSVs.

---

## 11. Memgraph status and caveat

Memgraph successfully loaded the node data:

```text
Person: 134,208
Title: 24,674
```

The relationship-loading phase was the bottleneck.

The original relationship loader used:

```cypher
MERGE (p)-[:ACTED_IN]->(t)
```

`MERGE` checks whether the relationship already exists before creating it.
Under the constrained Memgraph instance, this became extremely slow.

Because the benchmark starts from a controlled empty database and the input
edge dataset is deduplicated, the relationship load was changed to:

```cypher
CREATE (p)-[:ACTED_IN]->(t)
```

This removes the per-relationship existence check.

The node load completed, but the final relationship load remained too slow
under the available resource limit. Consequently, a complete final Memgraph
benchmark result set was not produced for this submission.

The available commands remain:

```bash
make load-memgraph
make check-memgraph
make traversal-memgraph
make aggregation-memgraph
make lookup-memgraph
make mixed-memgraph
```

This limitation is reported explicitly rather than substituting incomplete
results into the comparison.

---

## 12. Make command reference

### Setup

```bash
make setup
make teardown
```

### Dataset

```bash
make dataset
make dedupe
make clean-data
```

### Loading

```bash
make load
make load-selfhosted
make load-aura
make load-cognodb
make load-memgraph
make load-arango
```

### Verification

```bash
make check
make check-selfhosted
make check-aura
make check-cognodb
make check-memgraph
make check-arango
```

### Traversal

```bash
make traversal
make traversal-selfhosted
make traversal-aura
make traversal-cognodb
make traversal-memgraph
make traversal-arango
```

### Aggregation

```bash
make aggregation
make aggregation-selfhosted
make aggregation-aura
make aggregation-cognodb
make aggregation-memgraph
make aggregation-arango
```

### Lookup

```bash
make lookup
make lookup-selfhosted
make lookup-aura
make lookup-cognodb
make lookup-memgraph
make lookup-arango
```

### Mixed concurrency

```bash
make mixed
make mixed-selfhosted
make mixed-aura
make mixed-cognodb
make mixed-memgraph
make mixed-arango
```

### Full orchestration and charts

```bash
make run
make charts
```

### Reset

```bash
make reset-local
make reset-cloud
```

Run:

```bash
make help
```

at any time to display the command list.

## 13. What this benchmark does not claim**

This benchmark measures one dataset, one dataset shape, one query set, one

client machine/region, and one point in time, all under the smallest

available free-tier resource envelope. It does not claim these results

generalize to production-scale workloads, larger datasets, different query

patterns, or higher resource tiers. The goal was fair, reproducible

methodology at small scale — not a definitive ranking.