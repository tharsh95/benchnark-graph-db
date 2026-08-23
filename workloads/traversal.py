"""
Traversal workload: measures 1-hop, 2-hop, 3-hop query latency.

Works against any bolt-protocol platform (CognoDB, Aura, Memgraph,
self-hosted Neo4j) since they all speak Cypher via the same driver.

For each hop depth:
  - pick a random start node
  - run the traversal query
  - time it (ms)
Runs WARMUP_RUNS first (discarded), then ITERATIONS timed runs.
Saves raw latencies + p50/p95 summary to results/traversal_<platform>.csv

Usage: python workloads/traversal.py <platform_name>
  platform_name must match a *_URI / *_USER / *_PASSWORD prefix in .env
  e.g. COGNODB, AURA, MEMGRAPH, NEO4J_SELFHOSTED
"""
import csv
import os
import sys
import time

import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

WARMUP_RUNS = 15
ITERATIONS = 100

QUERIES = {
    1: """
        MATCH (p:Person {personId: $startId})-[:ACTED_IN]->(t:Title)
        RETURN t.titleId AS result
        LIMIT 50
    """,
    2: """
        MATCH (p:Person {personId: $startId})-[:ACTED_IN]->(:Title)<-[:ACTED_IN]-(p2:Person)
        RETURN DISTINCT p2.personId AS result
        LIMIT 50
    """,
    3: """
        MATCH (p:Person {personId: $startId})-[:ACTED_IN]->(:Title)<-[:ACTED_IN]-(:Person)-[:ACTED_IN]->(t2:Title)
        RETURN DISTINCT t2.titleId AS result
        LIMIT 50
    """,
}


def get_random_person_ids(driver, n=200):
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person) RETURN p.personId AS id ORDER BY rand() LIMIT $n", n=n
        )
        return [r["id"] for r in result]


def time_query(driver, query, params):
    start = time.perf_counter()
    with driver.session() as session:
        session.run(query, **params).consume()
    return (time.perf_counter() - start) * 1000  # ms


def run_hop_benchmark(driver, hop, start_ids):
    query = QUERIES[hop]

    # warmup
    for i in range(WARMUP_RUNS):
        sid = start_ids[i % len(start_ids)]
        time_query(driver, query, {"startId": sid})

    # timed runs
    latencies = []
    for i in range(ITERATIONS):
        sid = start_ids[i % len(start_ids)]
        latencies.append(time_query(driver, query, {"startId": sid}))

    return latencies


def main():
    if len(sys.argv) != 2:
        print("Usage: python workloads/traversal.py <PLATFORM_PREFIX>")
        print("  e.g. COGNODB, AURA, MEMGRAPH, NEO4J_SELFHOSTED")
        sys.exit(1)

    platform = sys.argv[1].upper()
    uri = os.getenv(f"{platform}_URI")
    user = os.getenv(f"{platform}_USER") or None
    password = os.getenv(f"{platform}_PASSWORD") or None

    if not uri:
        print(f"No {platform}_URI found in .env")
        sys.exit(1)

    print(f"=== Traversal benchmark: {platform} ===")
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(uri, auth=auth)
    driver.verify_connectivity()

    print("Fetching random start node pool...")
    start_ids = get_random_person_ids(driver, n=200)
    if not start_ids:
        print("No Person nodes found - did you run the loader for this platform?")
        sys.exit(1)
    print(f"  got {len(start_ids)} candidate start nodes")

    os.makedirs("results", exist_ok=True)
    summary_rows = []

    for hop in (1, 2, 3):
        print(f"\nRunning {hop}-hop traversal ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
        latencies = run_hop_benchmark(driver, hop, start_ids)

        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        print(f"  {hop}-hop: p50={p50:.2f}ms  p95={p95:.2f}ms")

        raw_path = f"results/traversal_{platform.lower()}_{hop}hop_raw.csv"
        with open(raw_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["iteration", "latency_ms"])
            for i, lat in enumerate(latencies):
                writer.writerow([i, lat])

        summary_rows.append({"hop": hop, "p50_ms": p50, "p95_ms": p95, "n": len(latencies)})

    summary_path = f"results/traversal_{platform.lower()}_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["hop", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved summary to {summary_path}")
    driver.close()


if __name__ == "__main__":
    main()
