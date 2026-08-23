"""
Aggregation workload: measures count/group-by query latency.

Query: count of ACTED_IN relationships grouped by Title.startYear
(an aggregation over a relationship type, grouped by a node property).

Works against any bolt-protocol platform (CognoDB, Aura, Memgraph,
self-hosted Neo4j).

Usage: python workloads/aggregation.py <PLATFORM_PREFIX>
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

AGGREGATION_QUERY = """
    MATCH (p:Person)-[:ACTED_IN]->(t:Title)
    RETURN t.startYear AS year, count(*) AS acted_in_count
    ORDER BY year
"""


def time_query(driver, query):
    start = time.perf_counter()
    with driver.session() as session:
        session.run(query).consume()
    return (time.perf_counter() - start) * 1000  # ms


def run_benchmark(driver, query):
    for _ in range(WARMUP_RUNS):
        time_query(driver, query)

    latencies = []
    for _ in range(ITERATIONS):
        latencies.append(time_query(driver, query))

    return latencies


def main():
    if len(sys.argv) != 2:
        print("Usage: python workloads/aggregation.py <PLATFORM_PREFIX>")
        sys.exit(1)

    platform = sys.argv[1].upper()
    uri = os.getenv(f"{platform}_URI")
    user = os.getenv(f"{platform}_USER") or None
    password = os.getenv(f"{platform}_PASSWORD") or None

    if not uri:
        print(f"No {platform}_URI found in .env")
        sys.exit(1)

    print(f"=== Aggregation benchmark: {platform} ===")
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(uri, auth=auth)
    driver.verify_connectivity()

    os.makedirs("results", exist_ok=True)

    print(f"\nRunning count/group-by aggregation ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(driver, AGGREGATION_QUERY)

    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    print(f"  aggregation: p50={p50:.2f}ms  p95={p95:.2f}ms")

    raw_path = f"results/aggregation_{platform.lower()}_raw.csv"
    with open(raw_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "latency_ms"])
        for i, lat in enumerate(latencies):
            writer.writerow([i, lat])

    summary_path = f"results/aggregation_{platform.lower()}_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerow({"query": "count_group_by_year", "p50_ms": p50, "p95_ms": p95, "n": len(latencies)})

    print(f"\nSaved summary to {summary_path}")
    driver.close()


if __name__ == "__main__":
    main()
